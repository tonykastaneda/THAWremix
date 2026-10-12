"""THAW's Hollywood poster in Project 8's level select.

  p8lsel.py <THAW install> <levelselect.pak.psp> <out .pak.psp>

Free Skate's level select (pak\\levelselect\\levelselect.pak) shows a 128x128 256-colour picture per
level; the Houses slot's is 0x61406c1d (P8's Suburbs). THAW's own level select has
images\\levelselectsprites\\levelposter_hollywood (128x128 too): converted to P8's .img.psp
(version 4, 'seSV', not swizzled) and put in that entry, same size.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import p8zone  # noqa: E402
import pspimg  # noqa: E402

SLOT = 0x61406c1d


def main():
    install, src, dst = sys.argv[1:4]
    img, used = pspimg.read_wpc(open(os.path.join(install, 'data', 'images', 'levelselectsprites',
                                                  'levelposter_hollywood.img.wpc'), 'rb').read())
    ents, blob = p8zone.load_pak(src)
    i, e = next((i, e) for i, e in enumerate(ents) if e['pakkey'] == SLOT)
    new = pspimg.make_psp(img, used, 0, 256, p8=True)
    if len(new) != e['size']:
        raise SystemExit(f'poster: {len(new)} bytes, slot {e["size"]}')
    out = p8zone.write_pak(src, {i: new})
    open(dst, 'wb').write(out)
    print(f'{os.path.basename(dst)}: Hollywood poster in {SLOT:#010x}')


if __name__ == '__main__':
    main()
