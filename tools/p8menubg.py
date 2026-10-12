"""THAW's alley behind Project 8's main menu.

  p8menubg.py <vanilla z_mainmenu.psp_level> <backdrop 480x272 png> <out.psp_level> [scale 2]
  p8menubg.py --pak <vanilla z_mainmenu.pak.psp> <out pak> <logo png>   (the menu bar's title art)

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
    open(pak_out, 'wb').write(p8zone.write_pak(pak_in, {i: new}))
    print(f'{pak_out}: menu bar title <- {os.path.basename(logo_png)}')


def psptex_read(d):
    import pspimg
    return pspimg.read_psp(d)


def main():
    if '--pak' in sys.argv:  # --pak <z_mainmenu.pak.psp in> <out> <logo png>
        i = sys.argv.index('--pak')
        banner_pak(*sys.argv[i + 1:i + 4])
        del sys.argv[i:i + 4]
        if len(sys.argv) < 4:
            return
    src, png, dst = sys.argv[1:4]
    scale = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    w, h = 128 * scale, 64 * scale
    data = regrow(open(src, 'rb').read(), w, h)
    data = psptex.replace(data, 0, backdrop(Image.open(png), w, h))
    open(dst, 'wb').write(data)
    print(f'{dst}: {w}x{h} backdrop, {len(data)} bytes')


if __name__ == '__main__':
    main()
