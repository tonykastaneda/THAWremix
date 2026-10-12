"""THAW's pause-menu map sprites on vanilla Project 8 PSP.

  p8map.py <THAW install> <global.pak.psp> <global.pab.psp> <outdir>

P8 kept THAW's pause_menu_map script: in a career it draws the level struct's level_map texture and
the skater's arrow (Bike_arrow) on the pause screen. P8 has neither sprite. As in the THUG2 Remix
build, two sprites in worlds\\global\\global.pak that nothing uses give up their slots: 0x77b96927
(128x128, 16 colours) becomes ho_level_map and mouse_cursor (32x16, 16 colours; debugger only)
becomes Bike_arrow. Each entry's key is renamed in the pak header and the THAW art (16x32, turned on
its side to fit) written over the data in the .pab; the sizes stay. Writes <outdir>/global.pak.psp
and <outdir>/global.pab.psp (the .pab can be the HUD's output, p8hud.py).
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import pak  # noqa: E402
import pspimg  # noqa: E402

# (slot key, new name, THAW sprite, quarter turns counter-clockwise)
SLOTS = ((0x77b96927, 'ho_level_map', 'ho_level_map', 0),
         (pak.qbkey('mouse_cursor'), 'Bike_arrow', 'bike_arrow', 1))


def convert(thaw_path, stock, turns):
    img, used = pspimg.read_wpc(open(thaw_path, 'rb').read())
    img = img[:used[1], :used[0]]
    if turns:
        img = np.ascontiguousarray(np.rot90(img, turns))
    lw, lh = struct.unpack_from('<2I', stock, 8)
    W, H = 1 << lw, 1 << lh
    h, w = img.shape[:2]
    if (w, h) != (W, H):
        raise SystemExit(f'{thaw_path}: {w}x{h}, slot {W}x{H}')
    return pspimg.make_psp(img, (w, h), 0, 16, p8=True)


def main():
    install, pakp, pabp, out = sys.argv[1:5]
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(bytes(p))
    for slot, name, thaw, turns in SLOTS:
        e = next(e for e in ents if e['pakkey'] == slot)
        at = e['offset'] - len(p)
        stock = bytes(b[at:at + e['size']])
        new = convert(os.path.join(install, 'data', 'images', 'panelsprites', f'{thaw}.img.wpc'), stock, turns)
        if len(new) != len(stock):
            raise SystemExit(f'{name}: {len(new)} bytes, slot {len(stock)}')
        b[at:at + len(new)] = new
        struct.pack_into('<I', p, e['entry_pos'] + 12, pak.qbkey(name))
        print(f'{slot:#010x} -> {name} <- THAW {thaw} ({len(new)} bytes)')
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'global.pak.psp'), 'wb').write(p)
    open(os.path.join(out, 'global.pab.psp'), 'wb').write(b)


if __name__ == '__main__':
    main()
