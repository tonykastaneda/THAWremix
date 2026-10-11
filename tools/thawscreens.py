"""THAW's loading screens on THUG2 Remix.

  thawscreens.py <THAW install> <outdir>

Remix load screens (images\\loadscrn_*.img.psp) are a 0x20-byte header (format 0, buffer 256x256
declared, used 480x272) followed by 480x272 linear RGBA8888, opaque. THAW's are 640x448 sprites in
the ABADD00D texture format. Each mapped THAW screen is scaled to 480x272 and written over the
Remix one; patch with hed.py replace '\\images\\<name>' <outdir>\\<name>.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import pspimg  # noqa: E402

MAP = {  # Remix screen: THAW screen
    'loadscrn': 'x',  # boot title
    'loadscrn_x': 'x',
    'loadscrn_training': 'hollywood',
    'loadscrn_training_story': 'hollywood',
    'loadscrn_training_classic': 'hollywood_2',
    'loadscrn_generic': 'generic',
    'loadscrn_generic_1': 'generic_1',
    'loadscrn_generic_2': 'generic',
    'loadscrn_generic_3': 'generic_3',
    'loadscrn_generic_4': 'generic_4',
    'loadscrn_generic_5': 'generic_5',
    'loadscrn_generic_6': 'generic_1',
    'loadscrn_generic_7': 'generic_7',
    'loadscrn_2player': '2player',
    'loadscrn_online': 'online',
    'loadscrn_online2': 'online2',
    'loadscrn_created': 'created',
    'loadscrn_editor': 'editor',
    'loadscrn_editor_play': 'editor_play',
}


def make(rgb):
    img = Image.fromarray(rgb[:, :, :3]).resize((480, 272), Image.Resampling.LANCZOS).convert('RGBA')
    head = struct.pack('<6I4H', 2, 0x12fc7c, 8, 8, 0, 0, 0, 0, 480, 272)
    return head + np.array(img, np.uint8).tobytes()


def main():
    install, out = sys.argv[1:3]
    os.makedirs(out, exist_ok=True)
    for remix, thaw in MAP.items():
        src = os.path.join(install, 'data', 'images', f'loadscrn_{thaw}.img.wpc')
        img, _ = pspimg.read_wpc(open(src, 'rb').read())
        data = make(np.ascontiguousarray(img))
        open(os.path.join(out, f'{remix}.img.psp'), 'wb').write(data)
        print(f'{remix} <- {thaw}')


if __name__ == '__main__':
    main()
