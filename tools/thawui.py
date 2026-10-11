"""THAW's menus on THUG2 Remix.

  thawui.py <THAW install> <Remix data dir> <outdir>
      [--qb-scripts <qb_scripts.pre>] [--mainmenu-scripts <mainmenu_scripts.pre>]
      [--panelsprites <panelsprites.pre>]

Builds on the other tools' outputs where given (the HUD's panelsprites.pre, the story's
qb_scripts.pre, the CAS backdrops' mainmenu_scripts.pre), else on Remix's own files.

Sprites: Remix and THAW draw their menus from same-named images (THUG2's art, which THAW redrew:
the grungy menu boxes MM_*, the warning sign, the American Wasteland logo in WDT_logo_big, the
label strips roundbar_*, ...). Every main menu sprite THAW has replaces Remix's, and the panel
sprites the menus are made of (MENU_PANEL_SPRITES). Each keeps Remix's palette depth.

Scripts (tools/qbc.py source in tools/ui/):
  labelmenu.q  THAW's label menu (make_label_menu / add_label_menu_item / ...), appended to
               scripts\\game\\menu\\gamemenu_helpers.qb so every menu can use it
  mainmenu.q   create_main_menu as THAW's label list, in levels\\mainmenu\\mainmenu_scripts.qb

Writes mainmenusprites.pre, panelsprites.pre, qb_scripts.pre, mainmenu_scripts.pre and loose copies
under <outdir>/loose/ (their datap paths, \\ as _).
"""
import argparse
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import pspimg  # noqa: E402
import qb2  # noqa: E402
import qbc  # noqa: E402
import thawhud  # noqa: E402

MENU_PANEL_SPRITES = ['roundbar', 'roundbar_highlight', 'roundbar_middle', 'roundbar_tip_left',
                      'roundbar_tip_right', 'options_bg'] + \
    [f'snaz_{a}_{b}' for a in 'tmb' for b in 'lmr'] + \
    [f'SkateSprites\\{d}_arrow' for d in ('up', 'down', 'left', 'right')]
THEME_COLOURS = ['DE_HIGHLIGHTED_TEXT_COLOR_NEW', 'DE_UNHIGHLIGHTED_TEXT_COLOR_NEW', 'DE_HIGHLIGHT_BAR_COLOR',
                 'DE_PAUSEBAR_COLOR']
UI = os.path.join(os.path.dirname(__file__), 'ui')
# submenus that show their own view of THAW's alley (tools/casbackdrop.py SUB_PANELS): a call added
# at the end of each, after the menu has set its own camera
SUBMENU_VIEWS = {
    'levels\\mainmenu\\mainmenu_scripts.qb': [('create_gamemode_options_menu', 'hw_menu_view bg = 0x3fb50e2f'),
                                              ('create_createamodes_menu', 'hw_menu_view bg = 0x3fa471cf')],
    'levels\\mainmenu\\mainmenu_options.qb': [('create_setup_options_menu', 'hw_menu_view bg = 0x45ab5a86')],
}


def append_call(d, script_name, line):
    """A compiled .qb with `line` (qbc source) run at the end of script_name."""
    import qbscripts
    s, e = qbscripts.scripts(d)[qbscripts.key(script_name)]
    assert d[e - 1] == 0x24
    body = qbc.compile_source(f'script hw_tmp\n{line}\nendscript\n')[qbscripts.key('hw_tmp')][1]
    stmt = body[6:-2]  # past 0x23 and the name, up to the closing 0x24 and newline
    return d[:e - 1] + stmt + d[e - 1:]



def convert_sprite(thaw_path, stock):
    """THAW .img.wpc -> Remix .img.psp with the stock file's checksum and palette depth."""
    img, used = pspimg.read_wpc(open(thaw_path, 'rb').read())
    npal = 256 if struct.unpack_from('<I', stock, 0x10)[0] == 0x13 else 16
    h, w = img.shape[:2]
    W, H = 1 << (w - 1).bit_length(), 1 << (h - 1).bit_length()
    buf = np.zeros((H, W, 4), np.uint8)
    buf[:h, :w] = img
    cks = struct.unpack_from('<I', stock, 4)[0]
    return pspimg.make_psp(buf, (min(used[0], W), min(used[1], H)), cks, npal)


def find_thaw(thaw_dir, rel):
    """Case-insensitive path of <rel>.img.wpc under thaw_dir, or None."""
    cur = thaw_dir
    parts = rel.replace('\\', '/').split('/')
    for i, p in enumerate(parts):
        want = (p + '.img.wpc' if i == len(parts) - 1 else p).lower()
        if not os.path.isdir(cur):
            return None
        hit = [f for f in os.listdir(cur) if f.lower() == want]
        if not hit:
            return None
        cur = os.path.join(cur, hit[0])
    return cur


def swap_sprites(pre_in, pre_out, thaw_dir, only, loose):
    """Replace the pre's images that THAW has (all of them when only is None)."""
    ver, magic, extra, entries = qb2.read_pre(pre_in)
    cur, n = pre_in, 0
    only_l = {o.lower() for o in only} if only else None
    for name, cks, d in entries:
        if not name.lower().endswith('.img.psp'):
            continue
        rel = name.split('\\', 2)[2][:-8]
        if only_l is not None and rel.lower() not in only_l:
            continue
        src = find_thaw(thaw_dir, rel)
        if not src:
            continue
        try:
            new = convert_sprite(src, d)
        except Exception as e:  # a few THAW records are not plain sprites
            print('  skip', rel, e)
            continue
        qb2.replace_in_pre(cur, pre_out, name, new)
        cur = pre_out
        loose['\\' + name] = new
        n += 1
    print(f'{os.path.basename(pre_out)}: {n} sprites from THAW')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('install')
    ap.add_argument('data')
    ap.add_argument('out')
    ap.add_argument('--qb-scripts')
    ap.add_argument('--mainmenu-scripts')
    ap.add_argument('--panelsprites')
    ap.add_argument('--mainmenu-level')
    a = ap.parse_args()
    import qb
    qb.load_names(os.path.join(os.path.dirname(__file__), '..', 'extracted', 'dbg'))
    os.makedirs(os.path.join(a.out, 'loose'), exist_ok=True)
    pre = lambda n: os.path.join(a.data, 'pre', n)  # noqa: E731
    images = os.path.join(a.install, 'data', 'images')
    loose = {}

    swap_sprites(pre('mainmenusprites.pre'), os.path.join(a.out, 'mainmenusprites.pre'),
                 os.path.join(images, 'mainmenusprites'), None, loose)
    swap_sprites(a.panelsprites or pre('panelsprites.pre'), os.path.join(a.out, 'panelsprites.pre'),
                 os.path.join(images, 'panelsprites'), MENU_PANEL_SPRITES, loose)

    def patch_pre(src_pre, dst_pre, entry, sources):
        files = {n.lower(): (n, d) for n, k, d in qb2.read_pre(src_pre)[3]}
        name, d = files[entry.lower()]
        code = qbc.compile_source(''.join(open(os.path.join(UI, s), encoding='utf-8').read() + '\n' for s in sources))
        new = qbc.patch(d, code) if code else d
        for script_name, line in SUBMENU_VIEWS.get(entry.lower(), []):
            new = append_call(new, script_name, line)
        qb2.replace_in_pre(src_pre, dst_pre, name, new)
        loose['\\' + name] = new
        print(f'{entry}: {len(code)} scripts, {len(d)} -> {len(new)} bytes')

    patch_pre(a.qb_scripts or pre('qb_scripts.pre'), os.path.join(a.out, 'qb_scripts.pre'),
              'scripts\\game\\menu\\gamemenu_helpers.qb', ['labelmenu.q'])

    # THAW's menu text and bar colours (Remix highlights in black, which vanishes on THAW's dark
    # label strips; THAW's is its pink)
    qbs = os.path.join(a.out, 'qb_scripts.pre')
    files = {n.lower(): (n, d) for n, k, d in qb2.read_pre(qbs)[3]}
    name, themes = files['scripts\\game\\menu\\themes.qb']
    thawhud.COLOURS = THEME_COLOURS
    themes = thawhud.patch_themes(themes, thawhud.thaw_colours(a.install))
    qb2.replace_in_pre(qbs, qbs, name, themes)
    loose['\\' + name] = themes

    # the main menu room's sign: THUG2's logo (texture 61) becomes THAW's from its own main menu
    # (z_mainmenu texture 72); both are 256x128 and stored upside down
    if a.mainmenu_level:
        import thawscene
        import psptex
        _, _, ztex, _, _ = thawscene.load_zone(a.install, 'z_mainmenu')
        logo = list(ztex.values())[72][0]
        lvl = psptex.replace(open(a.mainmenu_level, 'rb').read(), 61, np.ascontiguousarray(logo))
        open(os.path.join(a.out, 'mainmenu.psp_level'), 'wb').write(lvl)
        print('mainmenu.psp_level: main menu sign is THAW\'s logo')
    patch_pre(a.mainmenu_scripts or pre('mainmenu_scripts.pre'), os.path.join(a.out, 'mainmenu_scripts.pre'),
              'levels\\mainmenu\\mainmenu_scripts.qb', ['mainmenu.q'])
    patch_pre(os.path.join(a.out, 'mainmenu_scripts.pre'), os.path.join(a.out, 'mainmenu_scripts.pre'),
              'levels\\mainmenu\\mainmenu_options.qb', [])

    with open(os.path.join(a.out, 'loose', 'index.txt'), 'w') as idx:
        for path, data in loose.items():
            fn = path.strip('\\').replace('\\', '_')
            open(os.path.join(a.out, 'loose', fn), 'wb').write(data)
            idx.write(f'{path}\t{fn}\n')


if __name__ == '__main__':
    main()
