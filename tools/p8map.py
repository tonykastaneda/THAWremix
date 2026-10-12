"""THAW's pause-menu map sprites on vanilla Project 8 PSP.

  p8map.py <THAW install> <global.pak.psp> <global.pab.psp> <outdir>

P8 kept THAW's pause_menu_map script: in a career it draws the level struct's level_map texture and
the skater's arrow (Bike_arrow) on the pause screen. P8 has neither sprite. ho_level_map is a new
entry of worlds\\global\\global.pak in the format of sprite 0x77b96927 (128x128, 16 colours; the level
select uses that one: taking over its slot crashed Free Skate): one 0x20-byte entry goes before the
end marker, every other entry's data offset moves by 0x20, and the data goes at the end of the .pab.
As in the THUG2 Remix build, mouse_cursor (32x16, 16 colours; debugger only) gives up its slot to
Bike_arrow (THAW's 16x32 arrow turned on its side to fit): key renamed, data replaced in place. Writes <outdir>/global.pak.psp
and <outdir>/global.pab.psp (the .pab can be the HUD's output, p8hud.py).
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import pak  # noqa: E402
import pspimg  # noqa: E402

# (slot key, new name, THAW sprite, quarter turns counter-clockwise, new entry)
SLOTS = ((0x77b96927, 'ho_level_map', 'ho_level_map', 0, True),
         (pak.qbkey('mouse_cursor'), 'Bike_arrow', 'bike_arrow', 1, False))


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
    ents, end = pak.read_entries(bytes(p))
    added = []
    for slot, name, thaw, turns, new_entry in SLOTS:
        e = next(e for e in ents if e['pakkey'] == slot)
        at = e['offset'] - len(p)
        stock = bytes(b[at:at + e['size']])
        new = convert(os.path.join(install, 'data', 'images', 'panelsprites', f'{thaw}.img.wpc'), stock, turns)
        if len(new) != len(stock):
            raise SystemExit(f'{name}: {len(new)} bytes, slot {len(stock)}')
        if new_entry:
            added.append((p[e['entry_pos']:e['entry_pos'] + 0x20], name, new))
        else:
            b[at:at + len(new)] = new
            struct.pack_into('<I', p, e['entry_pos'] + 12, pak.qbkey(name))
        print(f'{name} <- THAW {thaw} ({len(new)} bytes, {"new entry" if new_entry else f"slot {slot:#010x}"})')
    grow = 0x20 * len(added)
    for e in ents:  # their data moves down with the longer header
        struct.pack_into('<I', p, e['entry_pos'] + 4, e['offset'] - e['entry_pos'] + grow)
    hdr = bytearray()
    for i, (tmpl, name, data) in enumerate(added):
        b += bytes(-len(b) % 16)
        pos = end + 0x20 * i
        ent = bytearray(tmpl)
        struct.pack_into('<III', ent, 4, len(p) + grow + len(b) - pos, len(data), pak.qbkey(name))
        hdr += ent
        b += data
    p[end:end] = hdr
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'global.pak.psp'), 'wb').write(p)
    open(os.path.join(out, 'global.pab.psp'), 'wb').write(b)


if __name__ == '__main__':
    main()
