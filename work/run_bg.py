"""Background test boot: patch work/ outputs into the unpacked Remix, start PPSSPP in a window that
never takes focus, walk the menus to Continue Story Mode with debugger button presses.

  python work/run_bg.py [tag]
"""
import os
import subprocess
import sys
import time

ROOT = r'C:\Users\tonyk\Documents\GitHub\THX'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import ppsspp_ws as p  # noqa: E402

U = os.path.join(ROOT, r'extracted\remix_psp\PSP_GAME\USRDIR')
W = os.path.join(ROOT, 'work')
PATCH = [
    (r'\levels\tr\tr.psp_level', r'out\tr.psp_level'),
    (r'\levels\tr\tr.col.ps2', r'out\tr.col.ps2'),
    (r'\levels\tr_sky\tr_sky.psp_level', r'out\tr_sky.psp_level'),
    (r'\pre\panelsprites.pre', r'hudout\panelsprites.pre'),
    (r'\scripts\game\menu\themes.qb', r'hudout\loose\themes.qb'),
    (r'\scripts\game\menu\panelstuff.qb', r'hudout\loose\panelstuff.qb'),
    (r'\pre\themes.pre', r'hudout\themes.pre'),
    (r'\images\themes\de_theme\de_sponsor.img.psp', r'hudout\loose\DE_sponsor.img.psp'),
] + [(rf'\images\panelsprites\{n}.img.psp', rf'hudout\loose\{n}.img.psp')
     for n in ('score_small', 'special', 'specialbar', 'balancemeter', 'balancearrow', 'balancearrow_glow')] + [
    (r'\levels\tr\tr.qb', r'story\tr.qb'),
    (r'\levels\tr\tr_scripts.qb', r'story\tr_scripts.qb'),
    (r'\pre\tr_scripts.pre', r'story\tr_scripts.pre'),
    (r'\pre\qb_scripts.pre', r'story\qb_scripts.pre'),
    (r'\scripts\game\menu\chapter_info.qb', r'story\chapter_info.qb'),
]


PATCH.append((r'\legal.tga', 'screens_legal.tga'))  # boot title
PATCH += [(r'\levels\mainmenu\mainmenu.psp_level', r'backdrops\mainmenu.psp_level'),  # CAS shop backdrops
          (r'\levels\mainmenu\mainmenu_cas.qb', r'backdrops\mainmenu_cas.qb'),
          (r'\levels\mainmenu\mainmenu_scripts.qb', r'backdrops\mainmenu_scripts.qb'),
          (r'\pre\mainmenu_scripts.pre', r'backdrops\mainmenu_scripts.pre')]
# THAW menus (tools/thawui.py, built on the HUD, story and backdrop outputs): applied last
UI = os.path.join(W, 'ui')
if os.path.isdir(UI):
    PATCH += [(rf'\pre\{n}', rf'ui\{n}') for n in ('mainmenusprites.pre', 'panelsprites.pre', 'qb_scripts.pre',
                                                   'mainmenu_scripts.pre')]
    if os.path.exists(os.path.join(UI, 'mainmenu.psp_level')):
        PATCH.append((r'\levels\mainmenu\mainmenu.psp_level', r'ui\mainmenu.psp_level'))
    for line in open(os.path.join(UI, 'loose', 'index.txt')):
        path, fn = line.rstrip('\n').split('\t')
        PATCH.append((path, rf'ui\loose\{fn}'))
SCREENS = os.path.join(W, 'screens')
if os.path.isdir(SCREENS):
    PATCH += [(rf'\images\{f}', rf'screens\{f}') for f in os.listdir(SCREENS)]


def patch():
    for name, src in PATCH:
        path = os.path.join(W, src)
        if os.path.exists(path):
            subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'hed.py'), 'replace',
                            os.path.join(U, 'datap.hed'), os.path.join(U, 'datap.wad'), name, path],
                           check=True, capture_output=True, creationflags=0x08000000)


def boot(tag='bg', then=''):
    patch()
    p.start(os.path.join(ROOT, r'extracted\remix_psp'))
    steps = 'wait:25000,cross,wait:6000,start,wait:6000,start,wait:6000,start,wait:8000,cross,' \
            'wait:18000,cross,wait:16000,cross,wait:5000,cross,wait:5000,cross,wait:3000,' \
            rf'shot:{W}\shots\{tag}_boot.png'
    ws = p.WS()
    p.run_seq(ws, steps + (',' + then if then else ''))


if __name__ == '__main__':
    boot(sys.argv[1] if len(sys.argv) > 1 else 'bg', sys.argv[2] if len(sys.argv) > 2 else '')
