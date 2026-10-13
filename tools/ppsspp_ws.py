"""Drive a test copy of PPSSPP in the background through its remote debugger (WebSocket).

The test copy (work/ppsspp_test, portable: its own memstick and ppsspp.ini) runs minimized, never
takes focus, is muted, uses D3D11 at 1x, and has RemoteDebuggerOnStartup = True with
RemoteISOPort = 45678. Buttons and screenshots go through the debugger, so nothing touches the
keyboard or the screen. A watchdog kills the test copy if its window is ever restored. Only the
test copy's own process is ever killed.

  ppsspp_ws.py start <game path>
  ppsspp_ws.py stop
  ppsspp_ws.py register                     once: the scheduled task used to launch from an SSH login
  ppsspp_ws.py press <button>[+<button>...] [ms]
  ppsspp_ws.py seq "<step>,<step>,..."     steps: wait:<ms> | <buttons>[:<ms>] | shot:<png> | stick:<x>:<y>:<ms>
  ppsspp_ws.py shot <png>                   the emulated PSP framebuffer

Buttons: cross circle triangle square up down left right start select ltrigger rtrigger.
"""
import base64
import io
import json
import os
import socket
import struct
import subprocess
import sys
import time

PORT = 45678
EXE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'ppsspp_test',
                                    'PPSSPPWindows64.exe'))
PIDFILE = EXE + '.pid'


class WS:
    def __init__(self, port=PORT):
        self.s = socket.create_connection(('127.0.0.1', port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f'GET /debugger HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n'
                        f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n'
                        f'Sec-WebSocket-Protocol: debugger.ppsspp.org\r\n\r\n').encode())
        resp = b''
        while b'\r\n\r\n' not in resp:
            resp += self.s.recv(4096)
        if b' 101 ' not in resp.split(b'\r\n')[0]:
            raise RuntimeError(resp.decode(errors='replace'))
        self.buf = resp.split(b'\r\n\r\n', 1)[1]

    def send(self, obj):
        data = json.dumps(obj).encode()
        head = bytearray([0x81])
        n = len(data)
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack('>H', n)
        else:
            head += bytes([0x80 | 127]) + struct.pack('>Q', n)
        mask = os.urandom(4)
        head += mask
        self.s.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(65536)
            if not chunk:
                raise EOFError
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self):
        msg = b''
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack('>H', self._read(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._read(8))[0]
            payload = self._read(n)
            if b0 & 0x0F == 8:
                raise EOFError
            msg += payload
            if b0 & 0x80:
                return json.loads(msg)

    def call(self, obj, timeout=10):
        """Send and wait for the reply (matched by ticket, or by event name when replies have none).
        Right after launch the game may not be running yet ('CPU not started'): retried for 60 s."""
        for _ in range(60):
            try:
                return self._call(obj, timeout)
            except RuntimeError as e:
                if 'CPU not started' not in str(e):
                    raise
                time.sleep(1)
        return self._call(obj, timeout)

    def _call(self, obj, timeout):
        obj = dict(obj, ticket=str(time.time()))
        self.send(obj)
        self.s.settimeout(timeout)
        end = time.time() + timeout
        while time.time() < end:
            m = self.recv()
            if m.get('event') == 'error':
                raise RuntimeError(m)
            if m.get('ticket') == obj['ticket'] or (m.get('event') == obj['event'] and 'ticket' not in m):
                return m
        raise TimeoutError(obj['event'])


def buttons(ws, names, down):
    ws.call({'event': 'input.buttons.send', 'buttons': {n: down for n in names}})


def press(ws, names, ms=120):
    buttons(ws, names, True)
    time.sleep(ms / 1000)
    buttons(ws, names, False)


def shot_display(ws, path):
    """What the window shows (movie frames included), read through the debugger."""
    from PIL import Image
    ws.call({'event': 'cpu.stepping'})
    try:
        m = ws.call({'event': 'gpu.buffer.screenshot', 'type': 'uri'}, timeout=30)
    finally:
        ws.call({'event': 'cpu.resume'})
    im = Image.open(io.BytesIO(base64.b64decode(m['uri'].split(',', 1)[1]))).convert('RGB')
    w, h = im.size
    sc = min(w / 480, h / 272)
    pw, ph = int(480 * sc), int(272 * sc)
    x0, y0 = (w - pw) // 2, (h - ph) // 2
    im.crop((x0, y0, x0 + pw, y0 + ph)).resize((480, 272), Image.Resampling.BOX).save(path)
    return path


def shot(ws, path):
    """The emulated PSP framebuffer, read through the debugger (the window stays minimized)."""
    from PIL import Image
    ws.call({'event': 'cpu.stepping'})
    try:
        m = ws.call({'event': 'gpu.buffer.renderColor', 'type': 'uri'}, timeout=30)
    finally:
        ws.call({'event': 'cpu.resume'})
    im = Image.open(io.BytesIO(base64.b64decode(m['uri'].split(',', 1)[1]))).convert('RGB')
    im.crop((0, 0, min(im.width, 480), min(im.height, 272))).save(path)
    return path


def kill():
    """Kills only the test copy (tracked by PID), never another PPSSPP that is running."""
    try:
        pid = int(open(PIDFILE).read())
    except (OSError, ValueError):
        return
    subprocess.run(['taskkill', '/PID', str(pid), '/F'], capture_output=True, creationflags=NO_WINDOW)
    try:
        os.remove(PIDFILE)
    except OSError:
        pass
    trim_log()


LOG_CAP = 20 << 20  # a crash loop logs ~1 GB a minute; keep only the end


def trim_log():
    log = os.path.join(os.path.dirname(EXE), 'ppsspp.log')
    for _ in range(20):
        try:
            if os.path.getsize(log) > LOG_CAP:
                with open(log, 'rb') as f:
                    f.seek(-LOG_CAP, 2)
                    tail = f.read()
                with open(log, 'wb') as f:
                    f.write(tail)
            return
        except FileNotFoundError:
            return
        except PermissionError:  # the killed emulator can hold it for a moment
            time.sleep(0.5)


WATCHDOG = r'''
import ctypes, sys, time
from ctypes import wintypes
k, u = ctypes.windll.kernel32, ctypes.windll.user32
pid = int(sys.argv[1])
h = k.OpenProcess(0x0001 | 0x1000 | 0x00100000, False, pid)  # TERMINATE | QUERY_LIMITED | SYNCHRONIZE
proto = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
def restored():
    bad = []
    def cb(w, _):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(w, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(w) and not u.IsIconic(w):
            bad.append(w)
        return True
    u.EnumWindows(proto(cb), 0)
    return bad
# no child processes and no console: everything is a direct Windows call
while h and k.WaitForSingleObject(h, 50) == 0x102:  # WAIT_TIMEOUT: still running
    if restored():
        k.TerminateProcess(h, 1)
'''

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW, for every process the tools start


DESKTOP = 'thx_ppsspp_test'


TASK = 'THX PPSSPP test'  # scheduled task (run only when logged on): launches in the desktop session
REQFILE = EXE + '.req'


def session_id():
    import ctypes
    sid = ctypes.c_ulong()
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
    return sid.value


def start(game):
    """Launches the test copy on its own hidden desktop: its windows (and any error dialog) are never
    drawn on the user's screen and can never take focus. It also starts minimized there.
    From session 0 (an SSH login: no display, no audio, D3D11 fails) the launch goes through the
    scheduled task TASK, which runs `ppsspp_ws.py launch` in the user's desktop session."""
    kill()
    log = os.path.join(os.path.dirname(EXE), 'ppsspp.log')
    for _ in range(20):  # PPSSPP appends; one log per boot (it reached 43 GB once)
        try:
            if os.path.exists(log):
                os.replace(log, log[:-4] + '.prev.log')
            break
        except PermissionError:  # a just-killed emulator can hold it for a moment
            time.sleep(0.5)
    if session_id() == 0:
        with open(REQFILE, 'w', encoding='utf-8') as f:
            f.write(os.path.abspath(game))
        r = subprocess.run(['schtasks', '/run', '/tn', TASK], capture_output=True, text=True,
                           creationflags=NO_WINDOW)
        if r.returncode:
            raise OSError(f'schtasks /run {TASK}: {r.stdout}{r.stderr} (register it: ppsspp_ws.py register)')
        for _ in range(40):
            if os.path.exists(PIDFILE):
                break
            time.sleep(0.25)
    else:
        launch(game)
    for _ in range(60):
        try:
            WS().s.close()
            break
        except OSError:
            time.sleep(0.5)
    else:
        raise RuntimeError('debugger did not come up')
    for _ in range(60):  # the debugger answers before the game runs; inputs then fail ("CPU not started")
        try:
            ws = WS()
            st = ws.call({'event': 'cpu.status'})
            ws.s.close()
            if st.get('ticks'):
                return 'started'
        except (OSError, RuntimeError):
            pass
        time.sleep(0.5)
    raise RuntimeError('the game did not start')


def register():
    """Creates TASK (once): pythonw runs `ppsspp_ws.py launch` as this user in the desktop session."""
    pyw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    ps = (f"$a = New-ScheduledTaskAction -Execute '{pyw}' -Argument '\"{os.path.abspath(__file__)}\" launch';"
          f"$p = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited;"
          f"$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
          f"-ExecutionTimeLimit (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew;"
          f"Register-ScheduledTask -TaskName '{TASK}' -Action $a -Principal $p -Settings $s -Force | Out-Null")
    subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True, creationflags=NO_WINDOW)


def launch(game):
    """The launch itself, in the current session: hidden desktop, PPSSPP on it, PIDFILE."""
    import ctypes
    from ctypes import wintypes
    k, u = ctypes.windll.kernel32, ctypes.windll.user32
    u.CreateDesktopW.restype = wintypes.HANDLE
    if not u.CreateDesktopW(DESKTOP, None, None, 0, 0x10000000, None):  # GENERIC_ALL
        raise OSError('CreateDesktop failed')

    class SI(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR), ('lpDesktop', wintypes.LPWSTR),
                    ('lpTitle', wintypes.LPWSTR), ('dwX', wintypes.DWORD), ('dwY', wintypes.DWORD),
                    ('dwXSize', wintypes.DWORD), ('dwYSize', wintypes.DWORD), ('dwXCountChars', wintypes.DWORD),
                    ('dwYCountChars', wintypes.DWORD), ('dwFillAttribute', wintypes.DWORD),
                    ('dwFlags', wintypes.DWORD), ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD),
                    ('lpReserved2', ctypes.c_void_p), ('hStdInput', wintypes.HANDLE),
                    ('hStdOutput', wintypes.HANDLE), ('hStdError', wintypes.HANDLE)]

    class PI(ctypes.Structure):
        _fields_ = [('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE),
                    ('dwProcessId', wintypes.DWORD), ('dwThreadId', wintypes.DWORD)]
    si = SI()
    si.cb = ctypes.sizeof(SI)
    si.lpDesktop = DESKTOP
    si.dwFlags = 0x1  # STARTF_USESHOWWINDOW
    si.wShowWindow = 4  # SW_SHOWNOACTIVATE; on the hidden desktop it is never drawn on the user's screen
    pi = PI()
    log = os.path.join(os.path.dirname(EXE), 'ppsspp.log')
    cmd = ctypes.create_unicode_buffer(f'"{EXE}" "{game}" --log="{log}"')
    if not k.CreateProcessW(None, cmd, None, None, False, NO_WINDOW, None, os.path.dirname(EXE),
                            ctypes.byref(si), ctypes.byref(pi)):
        raise OSError(f'CreateProcess failed: {k.GetLastError()}')
    with open(PIDFILE, 'w') as f:
        f.write(str(pi.dwProcessId))


def run_seq(ws, steps):
    for step in steps.split(','):
        step = step.strip()
        if not step:
            continue
        kind, _, rest = step.partition(':')
        if kind == 'wait':
            time.sleep(int(rest) / 1000)
        elif kind == 'shot':
            print(shot(ws, rest))
        elif kind == 'dshot':
            print(shot_display(ws, rest))
        elif kind == 'stick':
            x, y, ms = rest.split(':')
            ws.call({'event': 'input.analog.send', 'stick': 'left', 'x': float(x), 'y': float(y)})
            time.sleep(int(ms) / 1000)
            ws.call({'event': 'input.analog.send', 'stick': 'left', 'x': 0, 'y': 0})
        else:
            press(ws, kind.split('+'), int(rest) if rest else 120)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'start':
        print(start(sys.argv[2]))
    elif cmd == 'launch':  # run by TASK in the desktop session
        with open(REQFILE, encoding='utf-8') as f:
            game = f.read().strip()
        os.remove(REQFILE)
        launch(game)
    elif cmd == 'register':
        register()
        print('registered', TASK)
    elif cmd == 'stop':
        kill()
        print('stopped')
    else:
        ws = WS()
        if cmd == 'press':
            press(ws, sys.argv[2].split('+'), int(sys.argv[3]) if len(sys.argv) > 3 else 120)
        elif cmd == 'shot':
            print(shot(ws, sys.argv[2]))
        elif cmd == 'seq':
            run_seq(ws, sys.argv[2])
