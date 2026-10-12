"""2D sprite images: THUG2 Remix .img.psp and THAW PC .img.wpc.

  pspimg.py png <file.img.psp|file.img.wpc> <out.png>
  pspimg.py make <in.png> <out.img.psp> [--like <stock.img.psp>]

.img.psp (Remix): 0x20-byte header
  u32 2, u32 checksum, u32 log2 width, u32 log2 height, u32 format (0x14 = 16 colours, 4 bits;
  0x13 = 256 colours, 8 bits), u32 0, u16 0, u16 0x10, u16 width, u16 height (the drawn part of
  the power-of-two buffer)
then the 32-bit RGBA palette (alpha 0..FF) and the pixels, 4 or 8 bits each, swizzled in the
GE's 16-byte x 8-row blocks.
.img.wpc (THAW PC): the same ABADD00D texture record as level .tex files.
"""
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])


def read_psp(d):
    """Remix's .img.psp, or Project 8's (version 4, 'seSV', pixels not swizzled)."""
    ver, cks, lw, lh, fmt, z, z2, x10, w, h = struct.unpack_from('<6I4H', d, 0)
    W, H = 1 << lw, 1 << lh
    if fmt == 0:  # 32-bit RGBA, no palette (P8's backgrounds and larger art), linear
        return np.frombuffer(d, np.uint8, w * h * 4, 0x20).reshape(h, w, 4), (w, h), cks  # stored at the used size
    npal = 256 if fmt == 0x13 else 16
    pal = np.frombuffer(d, np.uint8, npal * 4, 0x20).reshape(npal, 4)
    p = 0x20 + npal * 4
    rb = W // 2 if npal == 16 else W
    raw = np.frombuffer(d, np.uint8, rb * H, p)
    raw = raw.reshape(H, rb) if ver == 4 and cks == P8_MAGIC else unswizzle(raw, rb, H)
    if npal == 16:
        idx = np.stack([raw & 15, raw >> 4], -1).reshape(H, W)
    else:
        idx = raw
    return pal[idx], (w, h), cks


def unswizzle(raw, row_bytes, h):
    bw, bh = max(row_bytes, 16) // 16, (h + 7) // 8
    if row_bytes < 16 or h % 8:
        return raw.reshape(h, row_bytes)
    return raw.reshape(bh, bw, 8, 16).transpose(0, 2, 1, 3).reshape(h, row_bytes)


def swizzle(rows):
    h, rb = rows.shape
    if rb < 16 or h % 8:
        return rows.tobytes()
    return rows.reshape(h // 8, 8, rb // 16, 16).transpose(0, 2, 1, 3).tobytes()


def read_wpc(d):
    import thawscene
    tex = thawscene.parse_tex(b'\0' * 8 + d)
    (img, comp), = tex.values()
    w, h = struct.unpack_from('<HH', d, 16)
    # sprites are stored bottom row first
    return img[::-1], (w, h)


P8_MAGIC = struct.unpack('<I', b'seSV')[0]


def make_psp(rgba, used, cks, npal=16, p8=False):
    """rgba (H, W, 4) with power-of-two sides; used = (w, h) drawn part. p8: Project 8's variant,
    version 4 with 'seSV' in the checksum word, flags 0 and the pixels not swizzled."""
    H, W = rgba.shape[:2]
    im = Image.fromarray(rgba, 'RGBA')
    q = im.quantize(colors=npal, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette(rawmode='RGBA')[:npal * 4], np.uint8).reshape(-1, 4)
    pal = np.vstack([pal, np.zeros((npal - len(pal), 4), np.uint8)]) if len(pal) < npal else pal
    idx = np.array(q, np.uint8)
    if npal == 16:
        pix = (idx[:, 0::2] & 15) | (idx[:, 1::2] << 4)
    else:
        pix = idx
    pix = np.ascontiguousarray(pix).tobytes() if p8 else swizzle(np.ascontiguousarray(pix))
    fmt = 0x13 if npal == 256 else 0x14
    head = struct.pack('<6I4H', 4 if p8 else 2, P8_MAGIC if p8 else cks, W.bit_length() - 1, H.bit_length() - 1, fmt,
                       0, 0, 0 if p8 else 0x10, *used)
    return head + pal.tobytes() + pix


if __name__ == '__main__':
    if sys.argv[1] == 'png':
        d = open(sys.argv[2], 'rb').read()
        img = read_psp(d)[0] if sys.argv[2].endswith('.psp') else read_wpc(d)[0]
        Image.fromarray(np.ascontiguousarray(img), 'RGBA').save(sys.argv[3])
