"""Trace Project 8's script calls on the hidden PPSSPP test copy.

  p8trace.py <tree or iso> "<steps>" [seconds] [--funcs Printf,LoadPak,...] [--out trace.txt]

Retail P8 compiles script printf to a stub (the Printf CFunc returns 1), but a breakpoint on any
CFunc gets its parameter struct in a0, so the scripts' own messages and calls can be read from
memory: a struct is [?][first component] (a0 + 4), a component [?][type][?][?] name, value, next;
in memory the types are 6 string, 2 int, 26 checksum, 7/10 struct, 5 float pair. CFunc addresses
come from the image's CFunc table ({name pointer, function} pairs, unrelocated: + 0x08804000 at
run time). Steps run meanwhile, as in ppsspp_ws.run_seq: wait:<ms>, <button>[+<button>][:<ms>],
shot:<png>. Checksums are resolved with extracted/dbg names (plus THAW's Hollywood goal ids).
"""
import base64
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import pak  # noqa: E402
import ppsspp_ws as p  # noqa: E402
import qb  # noqa: E402

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE = os.path.join(R, 'work', 'p8v', 'p8.img')
BASE = 0x08804000
FUNCS = ('Printf', 'ScriptAssert', 'LoadPak', 'PlayMovie', 'PlayCutscene', 'GoalManager_AddGoal',
         'GoalManager_ActivateGoal', 'GoalManager_WinGoal', 'CareerFunc')


def cfunc(name, image=None):
    """Run-time address of a script CFunc, from the {name, function} table in the image."""
    d = image or open(IMAGE, 'rb').read()
    s = d.find(b'\0' + name.encode() + b'\0') + 1
    if s <= 0:
        raise SystemExit(f'{name}: not in the image')
    i = d.find(struct.pack('<I', s))
    while i >= 0 and i % 4:
        i = d.find(struct.pack('<I', s), i + 1)
    if i < 0:
        raise SystemExit(f'{name}: not in the CFunc table')
    return struct.unpack_from('<I', d, i + 4)[0] + BASE


def main():
    args = sys.argv[1:]
    out = None
    funcs = FUNCS
    if '--funcs' in args:
        i = args.index('--funcs')
        funcs = args[i + 1].split(',')
        del args[i:i + 2]
    if '--out' in args:
        i = args.index('--out')
        out = open(args[i + 1], 'w')
        del args[i:i + 2]
    tree, steps = args[0], args[1]
    total = float(args[2]) if len(args) > 2 else 120
    qb.load_names(os.path.join(R, 'extracted', 'dbg'))
    for t in ('gaps', 'counter', 'highcombo', 'skatetheline'):
        for n in ['z_ho_goal_' + t] + [f'z_ho_goal_{t}{i}' for i in range(120)]:
            qb.NAMES.setdefault(pak.qbkey(n), n)
    image = open(IMAGE, 'rb').read()
    bps = {cfunc(n, image): n for n in funcs}

    def emit(line):
        print(line, flush=True)
        if out:
            out.write(line + '\n')
            out.flush()

    p.start(tree)
    ws = p.WS()
    time.sleep(0.2)
    for a in bps:
        ws.call({'event': 'cpu.breakpoint.add', 'address': a, 'enabled': True})

    def read(a, n):
        return base64.b64decode(ws.call({'event': 'memory.read', 'address': a, 'size': n})['base64'])

    def cstr(a):
        if not 0x08000000 <= a < 0x0A000000:
            return '?%08x' % a
        return read(a, 96).split(b'\0', 1)[0].decode('latin-1')

    def params(a0):
        out_, comp = [], struct.unpack('<I', read(a0 + 4, 4))[0]
        for _ in range(12):
            if not comp:
                break
            c = read(comp, 16)
            t = c[1]
            name, val, nxt = struct.unpack_from('<3I', c, 4)
            k = qb.nm(name) + '=' if name else ''
            if t == 6:
                out_.append(k + repr(cstr(val)))
            elif t == 2:
                out_.append(k + str(struct.unpack('<i', struct.pack('<I', val))[0]))
            elif t == 26:
                out_.append(k + '#' + qb.nm(val))
            else:
                out_.append(f'{k}t{t}:{val:08x}')
            comp = nxt
        return ' '.join(out_)

    def service():
        if not ws.call({'event': 'cpu.status'})['stepping']:
            return True
        r = ws.call({'event': 'cpu.getAllRegs'})['categories'][0]
        v = dict(zip(r['registerNames'], r['uintValues']))
        if v['pc'] not in bps:
            emit('stopped at %08x' % v['pc'])
            return False
        try:
            emit(f"{bps[v['pc']]} {params(v['a0'])}")
        except Exception as ex:  # keep going
            emit(f"{bps[v['pc']]} ? {ex}")
        ws.call({'event': 'cpu.resume'})
        return True

    end = time.time() + total
    for step in [s for s in steps.split(',') if s] + ['wait:%d' % (total * 1000)]:
        k, _, val = step.partition(':')
        if k == 'wait':
            t = time.time() + int(val) / 1000
            while time.time() < min(t, end):
                if not service():
                    return
                time.sleep(0.02)
        elif k == 'shot':
            emit(p.shot_display(ws, val))
        else:
            service()
            p.press(ws, k.split('+'), int(val) if val else 150)
        if time.time() > end:
            break


if __name__ == '__main__':
    main()
