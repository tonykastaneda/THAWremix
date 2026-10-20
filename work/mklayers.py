"""Layered test ISOs for real hardware: stock Remix plus groups of our changes, cumulatively.

  python work/mklayers.py [L1 L2 L3 L4]

Each layer starts from the stock archive (work/stock_tree, unpacked from the original ISO), applies
run_bg.PATCH entries whose source is in that layer's groups (in run_bg's order), and builds an ISO
with tools/mkumd.py --like the original (so its layout matches the shipped disc).
"""
import os
import shutil
import subprocess
import sys

ROOT = r'C:\Users\tonyk\Documents\GitHub\THX'
sys.path.insert(0, os.path.join(ROOT, 'work'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import run_bg  # noqa: E402

ORIG = os.path.join(ROOT, 'THAWremix', "Tony Hawk's Underground 2 Remix (USA).iso")
STOCK = os.path.join(ROOT, 'work', 'stock_tree')
TREE = os.path.join(ROOT, 'extracted', 'remix_psp')
OUT = os.path.join(ROOT, 'work', 'iso')


def group(src):
    s = src.lower()
    if s.startswith('screens') or 'legal' in s:
        return 'boot'
    if s.startswith('hudout'):
        return 'hud'
    if s.startswith('out\\') or s.startswith('story'):
        return 'story'
    if s.startswith('backdrops') or s.startswith('ui'):
        return 'ui'
    raise ValueError(src)


LAYERS = {
    'L1': ({'boot'}, 'boot+videos+icons'),
    'L2': ({'boot', 'hud'}, 'plus HUD'),
    'L3': ({'boot', 'hud', 'story'}, 'plus Hollywood and story'),
    'L4': ({'boot', 'hud', 'story', 'ui'}, 'full'),
    'L4-SV': ({'boot', 'hud', 'story', 'ui'}, 'full, stock videos'),
    'L4-NOMAP': ({'boot', 'hud', 'story', 'ui'}, 'full, no pause map', 'ui_nomap'),
    'L4-NOSPR': ({'boot', 'hud', 'story', 'ui'}, 'full, no THAW menu sprites', 'ui_nospr'),
}


def build(name):
    groups, label = LAYERS[name][:2]
    ui_dir = LAYERS[name][2] if len(LAYERS[name]) > 2 else 'ui'
    tmp = os.path.join(OUT, f'_{name}')
    os.makedirs(tmp, exist_ok=True)
    hed, wad = os.path.join(tmp, 'datap.hed'), os.path.join(tmp, 'datap.wad')
    shutil.copyfile(os.path.join(STOCK, 'PSP_GAME', 'USRDIR', 'datap.hed'), hed)
    shutil.copyfile(os.path.join(STOCK, 'PSP_GAME', 'USRDIR', 'datap.wad'), wad)
    n = 0
    for arch, src in run_bg.PATCH:
        if group(src) not in groups:
            continue
        if src.lower().startswith('ui' + os.sep):
            src = ui_dir + src[2:]
        path = os.path.join(run_bg.W, src)
        if os.path.exists(path):
            subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'hed.py'), 'replace', hed, wad, arch, path],
                           check=True, capture_output=True, creationflags=0x08000000)
            n += 1
    files = [('/PSP_GAME/USRDIR/datap.hed', hed), ('/PSP_GAME/USRDIR/datap.wad', wad)]
    # videos and the XMB/save icons ride with the boot group: the modded tree's copies
    for sub in () if name.endswith('-SV') else ('PSP_GAME/USRDIR/Movies',):
        for f in os.listdir(os.path.join(TREE, sub)):
            files.append((f'/{sub}/{f}', os.path.join(TREE, sub, f)))
    for f in ('ICON0.PNG', 'PIC1.PNG'):
        files.append((f'/PSP_GAME/{f}', os.path.join(TREE, 'PSP_GAME', f)))
    iso = os.path.join(OUT, f'THX {name} ({label}).iso')
    args = [sys.executable, os.path.join(ROOT, 'tools', 'mkumd.py'), STOCK, iso, '--like', ORIG,
            '--compact-wad', 'PSP_GAME/USRDIR/datap']
    for k, v in files:
        args += ['--file', f'{k}={v}']
    # the compacted pair must come from the layer's copy: point the tree's at it
    env = dict(os.environ, MKUMD_HED_DIR=tmp)
    r = subprocess.run(args, capture_output=True, text=True, env=env)
    print(name, n, 'patched;', r.stdout.strip().replace('\n', ' | '), r.stderr.strip()[-300:])
    shutil.rmtree(tmp)


if __name__ == '__main__':
    for name in sys.argv[1:] or list(LAYERS):
        build(name)
