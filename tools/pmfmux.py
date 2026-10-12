"""Make PSP movies (PSMF .pmf) from any video ffmpeg reads, for THUG2 Remix.

  pmfmux.py <input video> <out.pmf> [--template <a stock .pmf>] [--vbitrate 700k] [--crop W:H:X:Y]

Layout copied from Remix's own movies (USRDIR\\Movies\\*.pmf):
  header   0x800 bytes; the template's header with data size (0x0C) and the end timestamp
           (0x5A and 0x74, 6-byte PTS) rewritten. Start time is 90000 (1 s), the EP map is empty.
  body     2048-byte sectors, each a pack header (0xBA, 14 bytes) and exactly one PES packet:
           0xE0 video, H.264 Main profile 480x272 29.97 fps, Annex B with access unit delimiters,
             PTS (and DTS) on packets where an access unit starts;
           0xBD audio, ATRAC3plus 44.1 kHz stereo 560-byte frames (about 96 kbps), each frame
             preceded by 8 bytes 0F D0 28 45 00 00 00 00; the payload starts with 4 bytes
             00 00 <u16 BE offset of the first whole frame header>; PTS on every packet.
           The first sector also has a system header (0xBB). Short final packets are followed
           by a padding PES (0xBE) to fill the sector.
Audio is encoded with atracdenc (bin/atracdenc, LGPL, github.com/dcherednik/atracdenc).
"""
import argparse
import os
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
ATRACDENC = os.path.join(ROOT, 'bin', 'atracdenc', 'x86', 'atracdenc.exe')
SECTOR = 2048
FPS = 30000 / 1001
TICKS_PER_FRAME = 3003
AT3_FRAME = 560
AT3_HEAD = bytes.fromhex('0fd0284500000000')
AT3_SAMPLES = 2048
MUX_RATE = 25000  # units of 50 bytes/s, as in the stock movies
NOWIN = 0x08000000


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, creationflags=NOWIN)


def pts_bytes(marker, t):
    t &= (1 << 33) - 1
    return bytes([(marker << 4) | ((t >> 29) & 0x0E) | 1, (t >> 22) & 0xFF, ((t >> 14) & 0xFE) | 1,
                  (t >> 7) & 0xFF, ((t << 1) & 0xFE) | 1])


def pack_header(scr):
    base, ext = scr // 300, scr % 300
    b = bytearray(14)
    b[0:4] = b'\x00\x00\x01\xba'
    b[4] = 0x44 | ((base >> 27) & 0x38) | ((base >> 28) & 0x03)
    b[5] = (base >> 20) & 0xFF
    b[6] = 0x04 | ((base >> 12) & 0xF8) | ((base >> 13) & 0x03)
    b[7] = (base >> 5) & 0xFF
    b[8] = 0x04 | ((base << 3) & 0xF8) | ((ext >> 7) & 0x03)
    b[9] = ((ext << 1) & 0xFE) | 1
    b[10:13] = bytes([(MUX_RATE >> 14) & 0xFF, (MUX_RATE >> 6) & 0xFF, ((MUX_RATE << 2) & 0xFC) | 3])
    b[13] = 0xF8
    return bytes(b)


SYSTEM_HEADER = bytes.fromhex('000001bb000c80c35140f07fb9e1efbde004')


def pes(sid, payload, pts=None, dts=None, stuff=0):
    """PES packet; `stuff` 0xFF bytes in the header fill a sector exactly."""
    if pts is None:
        flags, ts = 0x00, b''
    elif dts is None or dts == pts:
        flags, ts = 0x80, pts_bytes(2, pts)
    else:
        flags, ts = 0xC0, pts_bytes(3, pts) + pts_bytes(1, dts)
    head = bytes([0x81, flags, len(ts) + stuff]) + ts + bytes([0xFF]) * stuff
    body = head + payload
    return b'\x00\x00\x01' + bytes([sid]) + struct.pack('>H', len(body)) + body


def padding(n):
    """Padding PES of exactly n bytes (n >= 6)."""
    return b'\x00\x00\x01\xbe' + struct.pack('>H', n - 6) + b'\xff' * (n - 6)


def sector(scr, packet, first=False):
    if isinstance(packet, tuple):
        sid, pay, pts, dts = packet
        base = 14 + (len(SYSTEM_HEADER) if first else 0)
        pk = pes(sid, pay, pts, dts)
        left = SECTOR - base - len(pk)
        packet = pes(sid, pay, pts, dts, stuff=left) if 0 < left < 6 else pk
    s = pack_header(scr) + (SYSTEM_HEADER if first else b'') + packet
    left = SECTOR - len(s)
    if left:
        assert left >= 6, left
        s += padding(left)
    assert len(s) == SECTOR
    return s


def encode_video(src, out, bitrate, seconds=None, start=None, crop=None):
    vf = 'scale=480:272:force_original_aspect_ratio=decrease,pad=480:272:(ow-iw)/2:(oh-ih)/2,setsar=1'
    if crop:  # e.g. THAW's 640x480 videos hold a 16:9 picture at 640:360:0:60; that fills the screen
        vf = f'crop={crop},scale=480:272,setsar=1'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src, '-an', '-vf', vf,
           '-r', '30000/1001', '-c:v', 'libx264', '-profile:v', 'main', '-level', '2.1', '-pix_fmt', 'yuv420p',
           '-b:v', bitrate, '-maxrate', bitrate, '-bufsize', '1000k',
           # as Sony's encodes in Remix's own movies: no B-frames (picture order type 2), one
           # reference frame, no weighted prediction, and HRD buffering period / picture timing
           # SEI with pic_struct on every frame; the PSP's hardware decoder rejects the rest
           '-x264-params', 'aud=1:bframes=0:ref=1:weightp=0:weightb=0:8x8dct=0:keyint=30:min-keyint=1:'
                           'nal-hrd=vbr:pic-struct=1:slices=1',
           '-video_track_timescale', '90000', out + '.mp4']
    at = cmd.index('-i')
    cmd[at:at] = (['-ss', str(start)] if start else []) + (['-t', str(seconds)] if seconds else [])
    run(cmd)
    run(['ffmpeg', '-v', 'error', '-y', '-i', out + '.mp4', '-c', 'copy', '-bsf:v', 'h264_mp4toannexb', '-f', 'h264', out])


def access_units(data):
    """Split an Annex B stream on access unit delimiters (NAL type 9, 3- or 4-byte start codes);
    anything before the first delimiter (x264's SEI) stays with the first access unit."""
    starts = []
    i = 0
    while True:
        i = data.find(bytes([0, 0, 1, 9]), i)
        if i < 0:
            break
        starts.append(i - 1 if i > 0 and data[i - 1] == 0 else i)
        i += 4
    if starts and starts[0] != 0:
        starts[0] = 0
    starts.append(len(data))
    return [data[starts[k]:starts[k + 1]] for k in range(len(starts) - 1)]


def frame_types(h264_file):
    """Display order of decode-order frames, from ffprobe packet pts."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'packet=pts,dts',
                          '-of', 'csv=p=0', '-fflags', '+genpts', h264_file],
                         capture_output=True, text=True, creationflags=NOWIN).stdout
    return [tuple(int(x) if x not in ('', 'N/A') else None for x in l.split(',')) for l in out.split() if l]


def encode_audio(src, out_raw, seconds=None, start=None):
    wav = out_raw + '.wav'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src, '-vn', '-ac', '2', '-ar', '44100', wav]
    at = cmd.index('-i')
    cmd[at:at] = (['-ss', str(start)] if start else []) + (['-t', str(seconds)] if seconds else [])
    run(cmd)
    oma = out_raw + '.oma'
    run([ATRACDENC, '-e', 'atrac3plus', '-i', wav, '-o', oma])
    data = open(oma, 'rb').read()
    assert data[:3] == b'EA3' and data[0x20] == 1, 'not ATRAC3plus OMA'
    params = data[0x22:0x24]  # e.g. 28 FF: 44.1 kHz, stereo, (0xFF + 1) * 8 = 2048-byte frames
    size = ((((params[0] << 8) | params[1]) & 0x3FF) + 1) * 8
    body = data[0x60:]
    head = bytes([0x0F, 0xD0]) + params + bytes(4)
    return head, [body[i:i + size] for i in range(0, len(body) // size * size, size)]


def mux(aus, au_times, frames, start=90000):
    """aus: H.264 access units in decode order; au_times: (pts, dts) ticks; frames: ATRAC3plus frames."""
    vpk = []  # (dts, packet bytes)
    max_pay = SECTOR - 14 - 6 - 3 - 10
    buf = b''
    first_pts = None
    queue = list(zip(aus, au_times))
    # fill video packets; a packet carries the timestamps of the first access unit that starts in it
    pending_start = None
    for au, (p, d) in queue:
        if not buf:
            pending_start = (p, d)
        elif pending_start is None:
            pending_start = (p, d)
        buf += au
        while len(buf) >= max_pay:
            vpk.append((pending_start, buf[:max_pay]))
            buf = buf[max_pay:]
            pending_start = None if buf else None
            if buf:
                pending_start = None
    if buf:
        vpk.append((pending_start, buf))
    # audio packets: 4-byte sub-header then framed audio, PTS of the first frame that starts in it
    at3_head, frames = frames
    stream = b''.join(at3_head + f for f in frames)
    unit = len(at3_head) + len(frames[0])
    a_pay = SECTOR - 14 - 6 - 3 - 5 - 4
    apk = []
    pos = 0
    a_start = start - 4180  # audio starts slightly ahead of video, as in the stock movies
    while pos < len(stream):
        chunk = stream[pos:pos + a_pay]
        first_hdr = (-pos) % unit
        frame_idx = (pos + first_hdr) // unit
        t = a_start + frame_idx * AT3_SAMPLES * 90000 // 44100
        apk.append((t, b'\x00\x00' + struct.pack('>H', first_hdr) + chunk))
        pos += a_pay
    # interleave by time: audio goes out about half a second before it is due
    out = []
    vi = ai = 0
    last_v = start
    while vi < len(vpk) or ai < len(apk):
        v_due = None
        if vi < len(vpk):
            ts = vpk[vi][0]
            v_due = (ts[1] if ts and ts[1] is not None else (ts[0] if ts else last_v))
            last_v = v_due
        a_due = apk[ai][0] - 45000 if ai < len(apk) else None
        if a_due is not None and (v_due is None or a_due <= v_due):
            t, pay = apk[ai]
            out.append((0xBD, pay, t, None))
            ai += 1
        else:
            ts, pay = vpk[vi]
            out.append((0xE0, pay) + (tuple(ts) if ts else (None, None)))
            vi += 1
    # sector 0: pack header, system header and padding; then one packet per sector
    sectors = [sector(0, b'', first=True)]
    for k, pk in enumerate(out, 1):
        scr = k * SECTOR * 27000000 // (MUX_RATE * 50)
        sectors.append(sector(scr, pk))
    return b''.join(sectors)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('out')
    ap.add_argument('--template', default=os.path.join(ROOT, r'extracted\remix_psp\PSP_GAME\USRDIR\Movies\atvi.pmf'))
    ap.add_argument('--vbitrate', default='700k')
    ap.add_argument('--seconds', type=float)
    ap.add_argument('--start', type=float)
    ap.add_argument('--crop', help='ffmpeg crop W:H:X:Y applied before scaling to 480x272')
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='pmf_')
    h264 = os.path.join(tmp, 'v.h264')
    encode_video(a.input, h264, a.vbitrate, a.seconds, a.start, a.crop)
    data = open(h264, 'rb').read()
    aus = access_units(data)
    times = frame_types(h264 + '.mp4')
    if len(times) != len(aus):
        raise SystemExit(f'{len(aus)} access units but {len(times)} packets')
    start = 90000
    # mp4 timestamps are in 1/90000 already (track timescale); shift so the first frame shows at start
    p0 = min(p for p, d in times)
    au_times = [(start + p - p0, start + d - p0) for p, d in times]
    frames = encode_audio(a.input, os.path.join(tmp, 'a.at3p'), a.seconds, a.start)
    body = mux(aus, au_times, frames, start)
    head = bytearray(open(a.template, 'rb').read()[:0x800])
    struct.pack_into('>I', head, 0x0C, len(body))
    end = start + len(aus) * TICKS_PER_FRAME
    for off in (0x5A, 0x74):
        head[off:off + 6] = struct.pack('>HI', end >> 32, end & 0xFFFFFFFF)
    open(a.out, 'wb').write(bytes(head) + body)
    print(f'{a.out}: {len(aus)} video frames, {len(frames[1])} audio frames of {len(frames[1][0])} bytes, {len(head) + len(body)} bytes')


if __name__ == '__main__':
    main()
