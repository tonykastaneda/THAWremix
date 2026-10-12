"""THAW's alley behind Project 8's main menu.

  p8menubg.py <vanilla z_mainmenu.psp_level> <backdrop 480x272 png> <out.psp_level> [scale 2] [label|tabs]
  p8menubg.py --pak <vanilla z_mainmenu.pak.psp> <out pak> <logo png>   (the menu bar's title art)
  p8menubg.py --scripts <pak in> <pak out> <THAW z_mainmenu.pak.ps2> <script,script,...>   (THAW's own scripts)

P8's main menu draws its zone's one quad (a 408 x 223 sky card at z -1220) behind the menu, with
a 128x64 8-bit texture over the whole quad, upside down (texture row 0 at the bottom). The menu
camera sees only part of it: a calibration grid showed texels x 18.9..97.3, y 5.55..49.96 on screen
(78.4 x 44.4, the screen's 16:9). As in the THUG2 Remix build (casbackdrop.py renders THAW's
z_mainmenu from its main menu camera, work/backdrops/mainmenu.png), the alley render goes into
that window, flipped; the rest of the texture repeats the render's edges. The texture is rebuilt
at `scale` times the size (256-entry palette, 3 mip levels; the material list's addresses, buffer
widths and sizes rewritten, the later blocks moved up), then drawn with psptex.replace.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import psplevel  # noqa: E402
import psptex  # noqa: E402

WINDOW = (18.9, 5.55, 97.3, 49.96)  # visible texels of the 128x64 original: x0, y0, x1, y1


def regrow(data, w, h, npal=256, mips=3):
    """The level with its one texture rebuilt at w x h (8-bit, npal colours, `mips` mip levels), blank."""
    L = psplevel.Level.__new__(psplevel.Level)
    psptex.open_level(L, data)
    sizes = [(w >> i, h >> i) for i in range(mips + 1)]
    addrs, at = [], npal * 4
    for lw, lh in sizes:
        addrs.append(at)
        at += lw * max(lh, 8)
    tex = bytes(at)
    words = list(struct.unpack_from(f'<{L.n_texcmds}I', data, L.texcmds))
    for i, wd in enumerate(words):
        op, arg = wd >> 24, wd & 0xFFFFFF
        if op == 0xB0:
            arg = 0
        elif op == 0xC4:
            arg = npal // 8
        elif 0xA0 <= op <= 0xA3:
            arg = addrs[op - 0xA0]
        elif 0xA8 <= op <= 0xAB:
            arg = (arg & 0xFF0000) | sizes[op - 0xA8][0]
        elif 0xB8 <= op <= 0xBB:
            lw, lh = sizes[op - 0xB8]
            arg = (lw.bit_length() - 1) | (lh.bit_length() - 1) << 8
        words[i] = op << 24 | arg
    h15 = list(struct.unpack_from('<15i', data, 0))
    h15[2] = len(tex)
    out = bytearray(struct.pack('<15i', *h15) + data[0x3C:L.tex])
    out += tex
    rest = bytearray(data[L.tex + L.tex_bytes:])
    off = L.texcmds - (L.tex + L.tex_bytes)
    struct.pack_into(f'<{len(words)}I', rest, off, *words)
    return bytes(out + rest)


# With THAW's label-menu front end (p8qb setglobal 0x44689337 0) every screen uses THAW's cam_main (the
# camera views are pinned to it; only the first frames at boot use a default camera). From cam_main the
# stock card covers only part of the screen, so the card is resized (CARD: x and z scale and shift in
# vertex units, scale_card) to the part of a 3x card that cam_main sees, and the screen corners (TL, TR,
# BL, BR) show these texels of its 512x256 texture, fitted by work/p8v/calib.py (perspective fit to 529
# stripe-boundary points, mean error 0.20 texels).
CARD = (0.9785, 1.1367, (263.3, -288.1))
CORNERS = ((33.8, 229.4), (477.7, 225.8), (30.2, 26.6), (479.8, 30.0))


def perspective_coeffs(src, dst):
    """PIL PERSPECTIVE coefficients mapping each output point in dst to the input point in src."""
    rows, rhs = [], []
    for (x, y), (u, v) in zip(dst, src):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        rhs += [u, v]
    return np.linalg.solve(np.array(rows, float), np.array(rhs, float)).tolist()


def backdrop_warped(img, w, h, corners=CORNERS):
    """The 480x272 render pre-warped into a w x h texture so the menu camera shows it undistorted."""
    s = w / 512
    tex = [(u * s, v * s) for u, v in corners]
    screen = [(0, 0), (480, 0), (0, 272), (480, 272)]
    pic = img.convert('RGBA').resize((480, 272), Image.Resampling.LANCZOS)
    out = pic.transform((w, h), Image.Transform.PERSPECTIVE, perspective_coeffs(screen, tex), Image.Resampling.BICUBIC)
    a = np.array(out)
    a[:, :, 3] = 255
    return a


def scale_card(data, fx, fz=None, shift=(0, 0)):
    """The card's six vertices scaled about its centre in its own plane (vertex-space x across, z up; the
    depth y follows the card's slope) and moved by `shift` (vertex units), with its visibility box regrown.
    Vertex space is world * 4 - offset."""
    fz = fx if fz is None else fz
    L = psplevel.Level.__new__(psplevel.Level)
    psptex.open_level(L, data)
    out = bytearray(data)
    vs = [list(struct.unpack_from('<HHHhhh', data, L.verts + 12 * j)) for j in range(L.vert_bytes // 12)]
    xs, ys, zs = [v[3] for v in vs], [v[4] for v in vs], [v[5] for v in vs]
    cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
    zlo, zhi = min(zs), max(zs)
    ylo, yhi = ys[zs.index(zlo)], ys[zs.index(zhi)]
    slope = (yhi - ylo) / (zhi - zlo)
    for j, v in enumerate(vs):
        x = round(cx + (v[3] - cx) * fx + shift[0])
        z = round(cz + (v[5] - cz) * fz + shift[1])
        y = round(ylo + (z - zlo) * slope)
        struct.pack_into('<HHHhhh', out, L.verts + 12 * j, v[0], v[1], v[2], x, y, z)
    vs = [struct.unpack_from('<HHHhhh', out, L.verts + 12 * j) for j in range(len(vs))]
    lo = [min(v[k] for v in vs) - 4 for k in (3, 4, 5)]
    hi = [max(v[k] for v in vs) + 4 for k in (3, 4, 5)]
    out[L.boxes:L.boxes + 16] = np.array(lo + [0] + hi + [0], np.float64).__truediv__(32768).astype('<f2').tobytes()
    return bytes(out)


def backdrop(img, w, h):
    """The render placed (flipped) in the visible window of a w x h texture, edges repeated around it."""
    sx, sy = w / 128, h / 64
    x0, y0, x1, y1 = (round(WINDOW[0] * sx), round(WINDOW[1] * sy), round(WINDOW[2] * sx), round(WINDOW[3] * sy))
    pic = np.array(img.convert('RGBA').resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS))[::-1]
    out = np.zeros((h, w, 4), np.uint8)
    out[y0:y1, x0:x1] = pic
    out[:y0, x0:x1] = pic[:1]
    out[y1:, x0:x1] = pic[-1:]
    out[:, :x0] = out[:, x0:x0 + 1]
    out[:, x1:] = out[:, x1 - 1:x1]
    out[:, :, 3] = 255
    return out


BANNER = 0xC1F52B7E  # the menu bar's title art: opaque 480x272 RGBA (format 0), drawn scaled into the bar


def banner_pak(pak_in, pak_out, logo_png):
    """The zone pak with the bar's title art (P8's "TONY HAWK'S PROJECT 8" on red) redrawn: THAW's default
    logo on the same red."""
    import p8zone
    import pak
    ents, blob = p8zone.load_pak(pak_in)
    i, e = next((i, e) for i, e in enumerate(ents) if e['pakkey'] == BANNER)
    d = blob[e['offset']:e['offset'] + e['size']]
    img, used, _ = psptex_read(d)
    out = Image.new('RGBA', used, tuple(int(x) for x in img[2, 2]))
    logo = Image.open(logo_png).convert('RGBA')
    w = used[0] - 20
    lg = logo.resize((w, round(w * logo.height / logo.width)), Image.Resampling.LANCZOS)
    out.alpha_composite(lg, ((used[0] - w) // 2, (used[1] - lg.height) // 2))
    new = d[:0x20] + np.array(out, np.uint8).tobytes()
    assert len(new) == len(d)
    out = p8zone.write_pak(pak_in, {i: new})
    open(pak_out, 'wb').write(out)
    print(f'{pak_out}: menu bar title <- {os.path.basename(logo_png)}')


def thaw_scripts(pak_in, pak_out, thaw_zone_pak, names):
    """The zone pak with named scripts of its z_mainmenu_scripts replaced by THAW's own (THAW PS2's
    z_mainmenu_scripts; same QB format), e.g. create_base_main_menu for THAW's main menu items."""
    import p8qb
    import p8zone
    import pak
    ents, blob = p8zone.load_pak(pak_in)
    i, e = next((i, e) for i, e in enumerate(ents) if (e['name'] or '').lower().endswith('z_mainmenu_scripts.qb.psp'))
    d = blob[e['offset']:e['offset'] + e['size']]
    tents, tblob = p8zone.load_pak(thaw_zone_pak)
    te = next(e for e in tents if (e['name'] or '').lower().endswith('z_mainmenu_scripts.qb.ps2'))
    t = tblob[te['offset']:te['offset'] + te['size']]
    for n in names:
        d = p8qb.swap_script(d, pak.qbkey(n), p8qb.script_block(t, pak.qbkey(n)))
        print(f'{n} <- THAW')
    if not os.environ.get('P8MENU_NOPIN'):
        d = pin_cameras(d)
        d = no_spin_start(d)
    out = p8zone.write_pak(pak_in, {i: d})  # before opening pak_out, which may be pak_in
    open(pak_out, 'wb').write(out)


# main_menu_camera_control (P8 kept THAW's) flies along the 3D alley: one camera per screen. The alley
# here is one card seen from cam_main, so every view is pinned to cam_main's Pos and Quat, except the
# ones that frame the skater (skater select, CAS and its taunt view, Create-A-Graphic).
CAM_KEEP = ('cam_main', 'cam_skater', 'cam_cas', 'cam_taunt', 'cam_cag')


def pin_cameras(d):
    """The zone script file with main_menu_camera_control's views moved to cam_main. In the bytecode a
    camera is 16 <name> 07 03 { ... }, its fields 16 <Pos|Quat> 07 1E <3 floats>."""
    import re
    import p8qb
    import pak
    k = pak.qbkey('main_menu_camera_control')
    _, items = p8qb.pointer_sites(d)
    _, _, _, v = next(i for i in items if i[2] == k and i[1] == 7)
    usz, csz = struct.unpack_from('<2I', d, v + 4)
    code = bytearray(p8qb.body(d, v + 12, usz, csz))
    field = lambda n: b'\x16' + struct.pack('<I', pak.qbkey(n)) + b'\x07\x1e'  # noqa: E731
    cams = [(m.start(), struct.unpack_from('<I', code, m.start() + 1)[0])
            for m in re.finditer(re.escape(b'\x16') + b'(....)' + re.escape(b'\x07\x03'), bytes(code), re.S)]
    keep = {pak.qbkey(n) for n in CAM_KEEP}
    main_at = next(p for p, c in cams if c == pak.qbkey('cam_main'))
    vals = {}
    for n in ('Pos', 'Quat'):
        at = bytes(code).find(field(n), main_at) + 7  # 16 <key> 07 1E, then the floats
        vals[n] = bytes(code[at:at + 12])
    pinned = 0
    for i, (start, ck) in enumerate(cams):
        end = cams[i + 1][0] if i + 1 < len(cams) else len(code)
        if ck in keep:
            continue
        for n in ('Pos', 'Quat'):
            at = bytes(code).find(field(n), start, end)
            if at >= 0:
                code[at + 7:at + 19] = vals[n]
                pinned += 1
    print(f'main_menu_camera_control: {pinned} Pos/Quat values pinned to cam_main ({len(cams)} camera structs)')
    code = bytes(code)
    return p8qb.swap_script(d, k, d[v:v + 4] + struct.pack('<2I', len(code), len(code)) + code)


def no_spin_start(d):
    """z_mainmenu_setup sets main_menu_very_first = 1, so the first main menu runs spin_menu_camera_init
    (a default view that sees the card off-centre) instead of main_menu_camera_control's cam_main;
    it sets 0 instead. In the bytecode: 16 <main_menu_very_first> 07 17 <int>."""
    import p8qb
    import pak
    k = pak.qbkey('z_mainmenu_setup')
    _, items = p8qb.pointer_sites(d)
    _, _, _, v = next(i for i in items if i[2] == k and i[1] == 7)
    usz, csz = struct.unpack_from('<2I', d, v + 4)
    code = p8qb.body(d, v + 12, usz, csz)
    pat = b'\x16' + struct.pack('<I', pak.qbkey('main_menu_very_first')) + b'\x07\x17' + struct.pack('<i', 1)
    assert code.count(pat) == 1, code.count(pat)
    code = code.replace(pat, pat[:-4] + struct.pack('<i', 0))
    print('z_mainmenu_setup: main_menu_very_first = 0 (first main menu at cam_main)')
    return p8qb.swap_script(d, k, d[v:v + 4] + struct.pack('<2I', len(code), len(code)) + code)


def psptex_read(d):
    import pspimg
    return pspimg.read_psp(d)


def main():
    if '--scripts' in sys.argv:  # --scripts <pak in> <pak out> <THAW z_mainmenu.pak.ps2> <name,name,...>
        i = sys.argv.index('--scripts')
        a = sys.argv[i + 1:i + 5]
        return thaw_scripts(a[0], a[1], a[2], a[3].split(','))
    if '--pak' in sys.argv:  # --pak <z_mainmenu.pak.psp in> <out> <logo png>
        i = sys.argv.index('--pak')
        banner_pak(*sys.argv[i + 1:i + 4])
        del sys.argv[i:i + 4]
        if len(sys.argv) < 4:
            return
    src, png, dst = sys.argv[1:4]
    scale = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    mode = sys.argv[5] if len(sys.argv) > 5 else 'label'  # label: THAW's front end camera; tabs: P8's
    w, h = 128 * scale, 64 * scale
    data = open(src, 'rb').read()
    if mode == 'label':
        data = scale_card(data, CARD[0], CARD[1], CARD[2])
    data = regrow(data, w, h)
    fill = backdrop_warped if mode == 'label' else backdrop
    data = psptex.replace(data, 0, fill(Image.open(png), w, h))
    open(dst, 'wb').write(data)
    print(f'{dst}: {w}x{h} backdrop, {len(data)} bytes')


if __name__ == '__main__':
    main()
