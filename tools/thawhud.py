"""THAW's HUD look on THUG2 Remix: the score banner, special meter and balance meter.

  thawhud.py <THAW install> <Remix data dir (unpacked datap)> <outdir>

Remix and THAW build these elements with the same scripts (panelstuff.qb: the_score_sprite,
the_special_bar_special, the_special_bar_sprite, the_balance_meter and its arrow child, with the
same arrow path along the arc), so the port is the textures plus the theme colours that tint them:

  textures  score_small, special, specialbar, balancemeter (THAW's balancemeter_bg),
            balancearrow and balancearrow_glow (THAW's glowing ball)
  colours   DE_HUD_COLOR, DE_HUD_SPECIAL_COLOR, DE_BALANCE_METER_COLOR, DE_BALANCE_ARROW_COLOR,
            DE_SPECIAL_BAR_COLORS from THAW's themes.qb (Remix tints the score banner yellow and
            the meters blue; THAW leaves the art untinted)

Writes panelsprites.pre and qb_scripts.pre (Remix's, with those entries replaced) plus the loose
copies of each replaced file under <outdir>/loose/.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import pspimg  # noqa: E402
import qb  # noqa: E402
import qb2  # noqa: E402
from pak import qbkey  # noqa: E402

SPRITES = {  # Remix name: THAW name
    'score_small': 'score_small',
    'special': 'special',
    'specialbar': 'specialbar',
    'balancemeter': 'balancemeter_bg',
    'balancearrow': 'balancearrow_glow',
    'balancearrow_glow': 'balancearrow_glow',
}
COLOURS = ['DE_HUD_COLOR', 'DE_HUD_SPECIAL_COLOR', 'DE_BALANCE_METER_COLOR', 'DE_BALANCE_ARROW_COLOR',
           'DE_SPECIAL_BAR_COLORS']


def convert_sprite(thaw_path, stock):
    """THAW .img.wpc -> Remix .img.psp in the stock file's palette depth."""
    img, used = pspimg.read_wpc(open(thaw_path, 'rb').read())
    npal = 256 if struct.unpack_from('<I', stock, 0x10)[0] == 0x13 else 16
    h, w = img.shape[:2]
    W, H = 1 << (w - 1).bit_length(), 1 << (h - 1).bit_length()
    buf = np.zeros((H, W, 4), np.uint8)
    buf[:h, :w] = img
    cks = struct.unpack_from('<I', stock, 4)[0]
    return pspimg.make_psp(buf, (min(used[0], W), min(used[1], H)), cks, npal)


def thaw_colours(install):
    from pak import open_pak
    entries, blob = open_pak(os.path.join(install, 'data', 'pak', 'qb.pak.wpc'))
    e = next(e for e in entries if (e['name'] or '').lower().endswith('menu\\themes.qb.wpc'))
    items = dict(qb.QB(blob[e['offset']:e['offset'] + e['size']]).items())
    return {k: items[k] for k in COLOURS}


def as_value(v):
    if isinstance(v, list):
        return ('array', [as_value(x) for x in v])
    return ('int', int(v))


def patch_themes(d, colours):
    for name, v in colours.items():
        p = qb2.find_item(d, qbkey(name))
        old, end = qb2.parse_value(d, p)
        while d[p] in (qb2.NEWLINE, 0x02):
            p += 1
        new = qb2.encode_value(as_value(v))
        d = d[:p] + new + d[end:]
        print(f'{name}: {old} -> {v}')
    return d


def patch_special_layout(d):
    """THAW draws the SPECIAL letters taller and higher on the banner: scale (1.73, 1.4) at
    (10, 30) where Remix has (1.73, 0.87) at (10, 34). Same-size pair tokens, patched in place."""
    for old, new in (((1.73, 0.87), (1.73, 1.4)), ((10.0, 34.0), (10.0, 30.0))):
        a = bytes([0x1F]) + struct.pack('<2f', *old)
        b = bytes([0x1F]) + struct.pack('<2f', *new)
        print(f'panelstuff {old} -> {new}: {d.count(a)} places')
        d = d.replace(a, b)
    return d


def main():
    install, data, out = sys.argv[1:4]
    os.makedirs(os.path.join(out, 'loose'), exist_ok=True)
    pre = os.path.join(data, 'pre', 'panelsprites.pre')
    entries = {n.lower(): (n, d) for n, k, d in qb2.read_pre(pre)[3]}
    cur = pre
    for remix, thaw in SPRITES.items():
        name = f'images\\panelsprites\\{remix}.img.psp'
        stock = entries[name][1]
        new = convert_sprite(os.path.join(install, 'data', 'images', 'panelsprites', f'{thaw}.img.wpc'), stock)
        dst = os.path.join(out, 'panelsprites.pre')
        qb2.replace_in_pre(cur, dst, entries[name][0], new)
        cur = dst
        open(os.path.join(out, 'loose', f'{remix}.img.psp'), 'wb').write(new)
        Image.fromarray(np.ascontiguousarray(pspimg.read_psp(new)[0]), 'RGBA').save(os.path.join(out, 'loose', f'{remix}.png'))
        print(f'{remix}.img.psp <- {thaw}: {len(stock)} -> {len(new)} bytes')

    # the theme's sponsor logo sits at the left end of the score banner: Remix's star, THAW's
    # brush stroke
    pre = os.path.join(data, 'pre', 'themes.pre')
    name, stock = next((n, d) for n, k, d in qb2.read_pre(pre)[3] if n.lower().endswith('de_sponsor.img.psp'))
    new = convert_sprite(os.path.join(install, 'data', 'images', 'panelsprites', 'de_sponsor.img.wpc'), stock)
    qb2.replace_in_pre(pre, os.path.join(out, 'themes.pre'), name, new)
    open(os.path.join(out, 'loose', 'DE_sponsor.img.psp'), 'wb').write(new)

    qb.load_names(os.path.join(os.path.dirname(__file__), '..', 'extracted', 'dbg'))
    pre = os.path.join(data, 'pre', 'qb_scripts.pre')
    files = {n.lower(): (n, d) for n, k, d in qb2.read_pre(pre)[3]}
    name, themes = files['scripts\\game\\menu\\themes.qb']
    themes = patch_themes(themes, thaw_colours(install))
    qb2.replace_in_pre(pre, os.path.join(out, 'qb_scripts.pre'), name, themes)
    open(os.path.join(out, 'loose', 'themes.qb'), 'wb').write(themes)
    name, panel = files['scripts\\game\\menu\\panelstuff.qb']
    panel = patch_special_layout(panel)
    qb2.replace_in_pre(os.path.join(out, 'qb_scripts.pre'), os.path.join(out, 'qb_scripts.pre'), name, panel)
    open(os.path.join(out, 'loose', 'panelstuff.qb'), 'wb').write(panel)


if __name__ == '__main__':
    main()
