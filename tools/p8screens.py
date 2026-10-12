"""THAW's boot and loading screens, and the save/XMB icons, on Project 8 PSP.

  p8screens.py <THAW install> <outdir> [--vanilla] [--logo <png>] [<P8 screen>=<THAW screen> ...]

Writes the files at their archive paths under <outdir> (patch each with hed.py replace ... --sectors);
with --logo, also the XMB/save icons built from that logo (the boot title stays THAW's own), and <outdir>\\PSP_GAME\\ICON0.PNG,
PIC1.PNG for the disc.

Vanilla P8 v1.00 (--vanilla): load screens are images\\loadscrn_<name>.img.psp and, again,
images\\raw\\us\\loadscrn_us\\loadscrn_<name>.img.psp: a 0x20-byte header (format 4, 'seSV', 480x272)
then 480x272 linear RGBA8888. Houses' slot holds Hollywood (p8zone.py --slot z_houses).
Project Mod: images\\raw\\us\\loadscrn_us\\loadscrn_<zone>.img.psp, a 0x20-byte header (format 2,
512x274) then 512x274 RGBA8888 with the picture at the top left (alpha 0x80) and columns 480-511 alpha 0.
Both: the boot screen is images\\raw\\us\\legal\\loadscrn_us.tga (and _uk), 480x272 24-bit bottom-up;
save data shows images\\raw\\icon\\icon0.png (144x80) and pic1.png (480x272). THAW's screens are
640x448, scaled to 480x272.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import pspimg  # noqa: E402

LEGAL_DIR = r'images\raw\us\legal'
ICON_DIR = r'images\raw\icon'
BOOT = ('loadscrn_us', 'loadscrn_uk')
MOD_SCREENS = {r'images\raw\us\loadscrn_us\loadscrn_z_sc': 'hollywood',  # the slot Hollywood takes
               r'images\raw\us\loadscrn_us\loadscrn_generic': 'generic'}
VANILLA_SCREENS = {}
for name, thaw in (('loadscrn_houses', 'hollywood'), ('loadscrn_generic', 'generic')):
    VANILLA_SCREENS[rf'images\{name}'] = thaw
    VANILLA_SCREENS[rf'images\raw\us\loadscrn_us\{name}'] = thaw


def thaw_screen(install, name):
    src = os.path.join(install, 'data', 'images', f'loadscrn_{name}.img.wpc')
    img, _ = pspimg.read_wpc(open(src, 'rb').read())
    rgb = np.ascontiguousarray(img)[:, :, :3]
    return Image.fromarray(rgb).resize((480, 272), Image.Resampling.LANCZOS)


def mod_img(pic):
    buf = np.zeros((274, 512, 4), np.uint8)
    buf[:272, :480, :3] = np.array(pic)
    buf[:272, :480, 3] = 0x80
    head = struct.pack('<6I4H', 2, 0x02840284, 9, 8, 0, 0, 0, 0, 512, 274)
    return head + buf.tobytes()


def vanilla_img(pic):
    buf = np.full((272, 480, 4), 0xFF, np.uint8)
    buf[:, :, :3] = np.array(pic)
    head = struct.pack('<I4s5I2H', 4, b'seSV', 8, 8, 0, 0, 0, 480, 272)
    return head + buf.tobytes()


def logo_on_black(logo, size, width, top=None):
    out = Image.new('RGBA', size, (0, 0, 0, 255))
    lg = logo.resize((width, round(width * logo.height / logo.width)), Image.Resampling.LANCZOS)
    y = (size[1] - lg.height) // 2 if top is None else top
    out.alpha_composite(lg, ((size[0] - width) // 2, y))
    return out


def write(out, rel, data):
    path = os.path.join(out, *rel.split('\\'))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'wb').write(data)
    return path


def main():
    args = sys.argv[1:]
    vanilla = '--vanilla' in args
    logo = None
    if '--logo' in args:
        i = args.index('--logo')
        logo = Image.open(args[i + 1]).convert('RGBA')
        del args[i:i + 2]
    args = [a for a in args if a != '--vanilla']
    install, out = args[:2]
    screens = dict(VANILLA_SCREENS if vanilla else MOD_SCREENS)
    screens.update(a.split('=', 1) for a in args[2:])
    make = vanilla_img if vanilla else mod_img
    for rel, thaw in screens.items():
        write(out, rel + '.img.psp', make(thaw_screen(install, thaw)))
        print(f'{rel} <- {thaw}')
    boot = thaw_screen(install, 'x')  # THAW's own title and legal text, as in the Remix build
    for name in BOOT:
        boot.save(write(out, rf'{LEGAL_DIR}\{name}.tga', b''), compression=None, orientation=-1)
    if vanilla:  # the title card shown with the boot screen
        write(out, r'images\raw\us\loadscrn_us\loadscrn_x.img.psp', make(boot))
    print('boot title <- THAW title')
    if logo:  # the Remix logo is for the XMB only: game icon and background, save data icons
        icon = logo_on_black(logo, (144, 80), 136).convert('RGB')
        pic = logo_on_black(logo, (480, 272), 400).convert('RGB')
        for rel, im in ((rf'{ICON_DIR}\icon0.png', icon), (rf'{ICON_DIR}\icon1.png', icon), (rf'{ICON_DIR}\pic1.png', pic),
                        (r'PSP_GAME\ICON0.PNG', icon), (r'PSP_GAME\PIC1.PNG', pic)):
            im.save(write(out, rel, b''))
        print('icons <- logo')


if __name__ == '__main__':
    main()
