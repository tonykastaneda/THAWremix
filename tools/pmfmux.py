"""Make PSP movies (PSMF .pmf) from any video ffmpeg reads, for THUG2 Remix.

  pmfmux.py <input video> <out.pmf> [--template <a stock .pmf>] [--vbitrate 700k] [--crop W:H:X:Y]
            [--video-from <.pmf>] [--audio-from <.pmf>]  (reuse a movie's stream: hardware tests)

The packet layout follows Sony's encoder (see mux): 0xBF GOP packets, decoder-buffer pacing.

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


def sector(scr, packet, pre=b''):
    """pre: what goes between the pack header and the packet (system header, 0xBF packet)."""
    if isinstance(packet, tuple):
        sid, pay, pts, dts = packet
        base = 14 + len(pre)
        pk = pes(sid, pay, pts, dts)
        left = SECTOR - base - len(pk)
        packet = pes(sid, pay, pts, dts, stuff=left) if 0 < left < 6 else pk
    s = pack_header(scr) + pre + packet
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
    """Split an Annex B stream on access unit delimiters (NAL type 9, 3- or 4-byte start codes).
    Anything before the first delimiter (x264's version SEI) is dropped: an access unit starts with
    its delimiter, as in Sony's streams (AUD, SPS, PPS, SEI..., slice)."""
    starts = []
    i = 0
    while True:
        i = data.find(bytes([0, 0, 1, 9]), i)
        if i < 0:
            break
        starts.append(i - 1 if i > 0 and data[i - 1] == 0 else i)
        i += 4
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


def has_sps(au):
    """Sony's GOPs start at an access unit with the sequence parameter set (a scene-cut IDR inside
    a GOP does not start one)."""
    return any(au[m + 3] & 0x1F == 7 for m in range(len(au) - 3) if au[m:m + 3] == b'\x00\x00\x01')


def is_ref(au):
    """nal_ref_idc of the first slice."""
    for m in range(len(au) - 3):
        if au[m:m + 3] == b'\x00\x00\x01' and au[m + 3] & 0x1F in (1, 5):
            return bool(au[m + 3] & 0x60)
    return True


def gop_info(aus, ends):
    """The 0xBF packet Sony's encoder puts at the start of each GOP (every stock P8 / Remix movie has
    them; the PSP's decoder relies on them): 01 E0, the sectors (counted from this one) where the GOP's
    first four pictures end, 4 zero bytes, u16 2 + 4n, u16 n, then per picture u32 size | 0x800000
    for a reference picture. `ends`: those four sector offsets (zeros for sizing)."""
    ends = (list(ends) + [ends[-1]] * 4)[:4]
    body = bytes([1, 0xE0]) + struct.pack('>4HIHH', *ends, 0, 2 + 4 * len(aus), len(aus))
    body += b''.join(struct.pack('>I', len(a) | (0x800000 if is_ref(a) else 0)) for a in aus)
    return b'\x00\x00\x01\xbf' + struct.pack('>H', len(body)) + body


def buffer_sizes(system_header):
    """The P-STD buffer sizes (bytes) the system header declares: {stream id: size}."""
    out, p = {}, 12
    while p + 3 <= len(system_header):
        sid, v = system_header[p], (system_header[p + 1] << 8) | system_header[p + 2]
        out[sid] = (v & 0x1FFF) * (1024 if v & 0x2000 else 128)
        p += 3
    return out


def mux(aus, au_times, frames, start=90000, system_header=SYSTEM_HEADER):
    """aus: H.264 access units in decode order (I/P only); au_times: (pts, dts) ticks; frames:
    (ATRAC3plus frame head, frames). Laid out as Sony's encoder does (checked against P8's and
    Remix's stock movies):
      - each GOP (from an access unit with an SPS) starts a sector, its 0xBF packet first
        (gop_info), and the first sector (pack and system header) already carries video;
      - video PTS and DTS (Sony's streams decode one frame early: DTS = PTS - 3003; x264's
        without B-frames have DTS = PTS, PTS only) only on a GOP's first packet and then on the first
        packet an access unit starts in at least VIDEO_TS_FRAMES frames later; other video
        packets are full and carry none;
      - packets go out earliest deadline first while they fit the decoder buffers the system
        header declares (P8: video 251 KB, audio 8 KB); when nothing fits, the pack clock (SCR)
        jumps to the next removal. Audio thus arrives just in time, video well ahead."""
    VIDEO_TS_FRAMES = 16
    pts = [p for p, _ in au_times]
    dts = [d for _, d in au_times]
    gops = [i for i, au in enumerate(aus) if i == 0 or has_sps(au)] + [len(aus)]
    # video packets: [payload, (pts, dts) or None, GOP (g0, g1) or None, first au, last au]
    vpk = []
    last_stamp = -VIDEO_TS_FRAMES
    for g0, g1 in zip(gops, gops[1:]):
        data = b''.join(aus[g0:g1])
        starts = []
        pos = 0
        for i in range(g0, g1):
            starts.append(pos)
            pos += len(aus[i])
        lo = 0
        while lo < len(data):
            first_sector = lo == 0
            room = SECTOR - 14 - 6 - 3
            if first_sector:
                room -= len(gop_info(aus[g0:g1], (0,))) + (len(system_header) if g0 == 0 else 0)
            # (not where an access unit's start code is split across the packet start: a reader
            # then takes that access unit as the first one starting here)
            split = any(s < lo < s + 5 for s in starts)
            stamped = next((g0 + k for k, s in enumerate(starts) if lo <= s and s + 5 <= lo + room - 10
                            and not split and g0 + k - last_stamp >= VIDEO_TS_FRAMES), None)
            if first_sector:
                stamped = g0
            if stamped is not None:
                room -= 10
                last_stamp = stamped
            hi = min(lo + room, len(data))
            k0 = max(k for k, s in enumerate(starts) if s <= lo)
            k1 = max(k for k, s in enumerate(starts) if s < hi)
            vpk.append([data[lo:hi], (pts[stamped], dts[stamped]) if stamped is not None else None,
                        (g0, g1) if first_sector else None, g0 + k0, g0 + k1])
            lo = hi
    # audio packets: 4-byte sub-header then framed audio, PTS of the first frame that starts in it
    at3_head, frames = frames
    stream = b''.join(at3_head + f for f in frames)
    unit = len(at3_head) + len(frames[0])
    a_pay = SECTOR - 14 - 6 - 3 - 5 - 4
    a_start = start - 4180  # audio starts slightly ahead of video, as in the stock movies
    a_time = [a_start + i * AT3_SAMPLES * 90000 // 44100 for i in range(len(frames))]
    apk = []  # [payload, pts, first frame, last frame]
    for pos in range(0, len(stream), a_pay):
        chunk = stream[pos:pos + a_pay]
        first_hdr = (-pos) % unit
        apk.append([b'\x00\x00' + struct.pack('>H', first_hdr) + chunk, a_time[min((pos + first_hdr) // unit, len(frames) - 1)],
                    pos // unit, (pos + len(chunk) - 1) // unit])
    # schedule against the decoder buffers
    bufs = buffer_sizes(system_header)
    cap = {'v': bufs.get(0xE0, 256 << 10) * 9 // 10, 'a': bufs.get(0xBD, 8 << 10) * 9 // 10}
    # and no further ahead of its deadline than the stock movies send it (video 0.9-1.0 s, audio
    # about 0.2 s; only the first audio packet goes out early, in sector 1)
    lead = {'v': 0.9 * 90000, 'a': 0.2 * 90000}
    v_cum = [0]
    for au in aus:
        v_cum.append(v_cum[-1] + len(au))
    tick = SECTOR * 90000 / (MUX_RATE * 50)  # one sector at the mux rate, in 90 kHz ticks
    t = 3044236 / 300  # the stock movies' first SCR
    sent = {'v': 0, 'a': 0}
    v_sent = a_sent = 0  # bytes of the elementary streams sent
    out = []
    vi = ai = 0

    def occupancy(kind, t):
        if kind == 'v':
            gone = sum(1 for d in dts if d <= t)
            return v_sent - v_cum[gone]
        gone = sum(1 for x in a_time if x <= t)
        return a_sent - min(gone * unit, len(stream))

    late = 0
    while vi < len(vpk) or ai < len(apk):
        cands = []
        if vi < len(vpk) and occupancy('v', t) + len(vpk[vi][0]) <= cap['v'] and dts[vpk[vi][3]] - t <= lead['v']:
            cands.append((dts[vpk[vi][3]], 'v'))
        if ai < len(apk) and out and occupancy('a', t) + len(apk[ai][0]) - 4 <= cap['a'] and (
                ai == 0 or a_time[apk[ai][2]] - t <= lead['a']):
            cands.append((a_time[apk[ai][2]], 'a'))
        if not cands:  # nothing fits: the clock moves on to the next removal
            nxt = [d for d in dts if d > t] + [x for x in a_time if x > t]
            if vi < len(vpk) and dts[vpk[vi][3]] - lead['v'] > t:
                nxt.append(dts[vpk[vi][3]] - lead['v'])
            if ai < len(apk) and a_time[apk[ai][2]] - lead['a'] > t:
                nxt.append(a_time[apk[ai][2]] - lead['a'])
            t = min(nxt) if nxt else t + tick
            continue
        deadline, kind = min(cands)
        late += t > deadline
        if kind == 'v':
            out.append(('v', vpk[vi], t))
            v_sent += len(vpk[vi][0])
            vi += 1
        else:
            out.append(('a', apk[ai], t))
            a_sent += len(apk[ai][0]) - 4
            ai += 1
        t += tick
    if late:
        print(f'pmfmux: {late} packets arrive after their deadline', file=sys.stderr)
    # the sector each access unit ends in, for the GOPs' 0xBF packets
    end_sector = {}
    for k, (kind, pk, _) in enumerate(out):
        if kind == 'v':
            for i in range(pk[3], pk[4] + 1):
                end_sector[i] = k
    sectors = []
    for k, (kind, pk, t) in enumerate(out):
        pre = system_header if k == 0 else b''
        if kind == 'a':
            packet = (0xBD, pk[0], pk[1], None)
        else:
            pay, ts, gop = pk[0], pk[1], pk[2]
            if gop:
                g0, g1 = gop
                pre += gop_info(aus[g0:g1], [end_sector[i] - k for i in range(g0, min(g1, g0 + 4))])
            packet = (0xE0, pay) + (ts if ts else (None, None))
        sectors.append(sector(int(t * 300), packet, pre))
    return b''.join(sectors)


def demux(path):
    """A .pmf's streams: (H.264 access units, PTS - DTS of its video, (ATRAC3plus frame head, frames)); for
    remuxing tests."""
    def ts(b):
        return ((b[0] >> 1) & 7) << 30 | b[1] << 22 | (b[2] >> 1) << 15 | b[3] << 7 | b[4] >> 1

    d = open(path, 'rb').read()
    video, audio, delay = bytearray(), bytearray(), None
    for s in range(0x800, len(d), SECTOR):
        p = s + 14
        while p < s + SECTOR and d[p:p + 3] == b'\x00\x00\x01':
            sid, ln = d[p + 3], struct.unpack('>H', d[p + 4:p + 6])[0]
            body = d[p + 6:p + 6 + ln]
            if sid == 0xE0:
                if delay is None and body[1] & 0x80:  # the decode delay its timestamps use
                    delay = ts(body[3:8]) - ts(body[8:13]) if body[1] & 0x40 else 0
                video += body[3 + body[2]:]
            elif sid == 0xBD:
                audio += body[3 + body[2] + 4:]
            p += 6 + ln
    head = bytes(audio[:8])
    size = ((((head[2] << 8) | head[3]) & 0x3FF) + 1) * 8
    unit = 8 + size
    return access_units(bytes(video)), delay or 0, (head, [bytes(audio[i + 8:i + unit]) for i in range(0, len(audio) // unit * unit, unit)])


def template_system_header(path):
    d = open(path, 'rb').read(0x800 + SECTOR)
    p = 0x800 + 14
    assert d[p:p + 4] == b'\x00\x00\x01\xbb'
    return d[p:p + 6 + struct.unpack('>H', d[p + 4:p + 6])[0]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input', nargs='?')
    ap.add_argument('out')
    ap.add_argument('--template', default=os.path.join(ROOT, r'extracted\remix_psp\PSP_GAME\USRDIR\Movies\atvi.pmf'))
    ap.add_argument('--vbitrate', default='700k')
    ap.add_argument('--seconds', type=float)
    ap.add_argument('--start', type=float)
    ap.add_argument('--crop', help='ffmpeg crop W:H:X:Y applied before scaling to 480x272')
    ap.add_argument('--video-from', help='take the video from this .pmf (no encode; tests)')
    ap.add_argument('--audio-from', help='take the audio from this .pmf (no encode; tests)')
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='pmf_')
    start = 90000
    if a.video_from:  # stock movies are I/P only: decode order is display order
        aus, delay, _ = demux(a.video_from)
        au_times = [(start + i * TICKS_PER_FRAME, start + i * TICKS_PER_FRAME - delay) for i in range(len(aus))]
    else:
        h264 = os.path.join(tmp, 'v.h264')
        encode_video(a.input, h264, a.vbitrate, a.seconds, a.start, a.crop)
        data = open(h264, 'rb').read()
        aus = access_units(data)
        times = frame_types(h264 + '.mp4')
        if len(times) != len(aus):
            raise SystemExit(f'{len(aus)} access units but {len(times)} packets')
        # mp4 timestamps are in 1/90000 already (track timescale); shift so the first frame shows at start
        p0 = min(p for p, d in times)
        au_times = [(start + p - p0, start + d - p0) for p, d in times]
    if a.audio_from:
        frames = demux(a.audio_from)[2]
    else:
        frames = encode_audio(a.input, os.path.join(tmp, 'a.at3p'), a.seconds, a.start)
    # no more audio than video
    keep = len(aus) * TICKS_PER_FRAME * 44100 // 90000 // AT3_SAMPLES + 1
    frames = (frames[0], frames[1][:keep])
    body = mux(aus, au_times, frames, start, template_system_header(a.template))
    head = bytearray(open(a.template, 'rb').read()[:0x800])
    struct.pack_into('>I', head, 0x0C, len(body))
    end = start + len(aus) * TICKS_PER_FRAME
    for off in (0x5A, 0x74):
        head[off:off + 6] = struct.pack('>HI', end >> 32, end & 0xFFFFFFFF)
    open(a.out, 'wb').write(bytes(head) + body)
    print(f'{a.out}: {len(aus)} video frames, {len(frames[1])} audio frames of {len(frames[1][0])} bytes, {len(head) + len(body)} bytes')


if __name__ == '__main__':
    main()
