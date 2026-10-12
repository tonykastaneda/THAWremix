"""THAW's boot and loading screens on Project 8 PSP (Tony Hawk's Project Mod).

  p8screens.py <THAW install> <outdir> [<P8 screen>=<THAW screen> ...]

P8 load screens (images\\raw\\us\\loadscrn_us\\loadscrn_<zone>.img.psp, one per zone) are a 0x20-byte
header (format 2, 512x274 declared) followed by 512x274 linear RGBA8888: the picture is 480x272 at
the top left, alpha 0x80, and columns 480-511 (and the two spare rows) are alpha 0. The boot screen
is images\\raw\\us\\legal\\loadscrn_us.tga (and _uk), 480x272 24-bit bottom-up, as in Remix.
THAW's screens are 640x448 and are scaled to 480x272. Writes the files at their archive paths
under <outdir>; patch each with hed.py replace ... --sectors.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import pspimg  # noqa: E402

LOAD_DIR = r'images\raw\us\loadscrn_us'
LEGAL_DIR = r'images\raw\us\legal'
MAP = {  # P8 screen: THAW screen
    'loadscrn_z_sc': 'hollywood',  # the zone slot Hollywood takes (p8zone.py --slot)
    'loadscrn_generic': 'generic',
}
BOOT = ('loadscrn_us', 'loadscrn_uk')


def thaw_screen(install, name):
    src = os.path.join(install, 'data', 'images', f'loadscrn_{name}.img.wpc')
    img, _ = pspimg.read_wpc(open(src, 'rb').read())
    rgb = np.ascontiguousarray(img)[:, :, :3]
    return Image.fromarray(rgb).resize((480, 272), Image.Resampling.LANCZOS)


def make_img(pic):
    buf = np.zeros((274, 512, 4), np.uint8)
    buf[:272, :480, :3] = np.array(pic)
    buf[:272, :480, 3] = 0x80
    head = struct.pack('<6I4H', 2, 0x02840284, 9, 8, 0, 0, 0, 0, 512, 274)
    return head + buf.tobytes()


def write(out, rel, data):
    path = os.path.join(out, *rel.split('\\'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'wb').write(data)


def main():
    install, out = sys.argv[1:3]
    screens = dict(MAP)
    screens.update(a.split('=', 1) for a in sys.argv[3:])
    for p8, thaw in screens.items():
        write(out, rf'{LOAD_DIR}\{p8}.img.psp', make_img(thaw_screen(install, thaw)))
        print(f'{p8} <- {thaw}')
    title = thaw_screen(install, 'x')
    for name in BOOT:
        path = os.path.join(out, *LEGAL_DIR.split('\\'), f'{name}.tga')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        title.save(path, compression=None, orientation=-1)
        print(f'{name}.tga <- x')


if __name__ == '__main__':
    main()
