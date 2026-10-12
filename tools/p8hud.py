"""THAW's HUD on vanilla Project 8 PSP: the balance meter and its arrow.

  p8hud.py <THAW install> <global.pak.psp> <global.pab.psp> <outdir>

P8 already draws THAW's HUD: the same panelstuff.qb elements, the same theme colours (DE_HUD_COLOR
and the rest are THAW's values) and THAW's score banner, special bar, SPECIAL letters and sponsor
stroke. Only the balance meter differs: P8 has thin arcs and an arrowhead where THAW has the black
arc with arrow ends and the glowing ball. Those sprites live in worlds\\global\\global.pak (+ .pab),
keyed by their bare names. The THUG2 Remix port (thawhud.py) swapped the same art; here the THAW
sprites are converted at the stock sprite's size and palette depth (P8's .img.psp: version 4,
'seSV', pixels not swizzled), so each fits its slot and the .pab is rewritten in place.
Writes <outdir>/global.pab.psp.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import pak  # noqa: E402
import pspimg  # noqa: E402

SPRITES = ('balancemeter', 'balancemeter_2', 'balancemeter_bg', 'balancearrow_glow')


def convert(thaw_path, stock):
    img, used = pspimg.read_wpc(open(thaw_path, 'rb').read())
    lw, lh, fmt = struct.unpack_from('<3I', stock, 8)
    W, H = 1 << lw, 1 << lh
    h, w = img.shape[:2]
    buf = np.zeros((H, W, 4), np.uint8)
    buf[:min(h, H), :min(w, W)] = img[:H, :W]
    return pspimg.make_psp(buf, (min(used[0], W), min(used[1], H)), 0, 256 if fmt == 0x13 else 16, p8=True)


def main():
    install, pakp, pabp, out = sys.argv[1:5]
    p, b = open(pakp, 'rb').read(), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(p)
    for name in SPRITES:
        e = next(e for e in ents if e['pakkey'] == pak.qbkey(name))
        at = e['offset'] - len(p)
        stock = bytes(b[at:at + e['size']])
        new = convert(os.path.join(install, 'data', 'images', 'panelsprites', f'{name}.img.wpc'), stock)
        if len(new) != len(stock):
            raise SystemExit(f'{name}: {len(new)} bytes, slot {len(stock)}')
        b[at:at + len(new)] = new
        print(f'{name} <- THAW ({len(new)} bytes)')
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'global.pab.psp'), 'wb').write(b)


if __name__ == '__main__':
    main()
