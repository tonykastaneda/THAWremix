"""Textures inside a Remix .psp_level: list, export, and replace in place.

  psptex.py sheet <file.psp_level> <out.png>       contact sheet of every texture (index, size)
  psptex.py export <file.psp_level> <index> <out.png>

A texture is what one material display list points at: CLUT (0xB0, entry count 0xC4 x 8),
pixels (0xA0, level 0), size (0xB8: log2 w | log2 h << 8), buffer width (0xA8 low 16 bits), format
(0xC3: 4 = 4-bit, 5 = 8-bit indices), 32-bit RGBA palette (alpha 0..FF), swizzled pixels. Lists
that set no texture inherit the previous list's (Remix's lists do), so state is tracked in order.
replace(data, index, rgba) writes an image of the same size into a texture's own slot.
"""
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

import os
sys.path.insert(0, os.path.dirname(__file__))
import psplevel  # noqa: E402


def textures(L):
    """[(clut offset, pixel offset, w, h, bufw, bits, palette entries, mips)] distinct, in list
    order; mips is ((pixel offset, bufw, w, h), ...) for levels 1-3 where the list sets them."""
    d = L.data
    words = struct.unpack_from(f'<{L.n_texcmds}I', d, L.texcmds)
    st = {}
    addr, bufw, size = {}, {}, {}
    seen, out = set(), []
    for w in words:
        op, arg = w >> 24, w & 0xFFFFFF
        if op == 0xB0:
            st['clut'] = arg
        elif op == 0xC4:
            st['n'] = (arg & 0x3F) * 8
        elif 0xA0 <= op <= 0xA3:
            addr[op - 0xA0] = arg
        elif 0xA8 <= op <= 0xAB:
            bufw[op - 0xA8] = arg & 0xFFFF
        elif 0xB8 <= op <= 0xBB:
            size[op - 0xB8] = (1 << (arg & 0xF), 1 << ((arg >> 8) & 0xF))
        elif op == 0xC3:
            st['bits'] = 4 if arg == 4 else 8
        elif op == 0x0B and all(k in st for k in ('clut', 'bits', 'n')) and 0 in addr and 0 in bufw and 0 in size:
            key = (st['clut'], addr[0])
            if key not in seen:
                seen.add(key)
                mips = tuple((addr[i], bufw[i], *size[i]) for i in (1, 2, 3)
                             if i in addr and i in bufw and i in size and addr[i] != addr[0])
                out.append((st['clut'], addr[0], *size[0], bufw[0], st['bits'], st['n'], mips))
    return out


def decode(L, t):
    clut, pix, w, h, bufw, bits, n = t[:7]
    d, base = L.data, L.tex
    pal = np.frombuffer(d, np.uint8, n * 4, base + clut).reshape(-1, 4).copy()
    hh = max(h, 8)
    row = bufw * bits // 8
    raw = np.frombuffer(d, np.uint8, row * hh, base + pix)
    blocks = raw.reshape(hh // 8, row // 16, 8, 16).transpose(0, 2, 1, 3).reshape(hh, row)
    if bits == 4:
        idx = np.empty((hh, row * 2), np.uint8)
        idx[:, 0::2], idx[:, 1::2] = blocks & 15, blocks >> 4
    else:
        idx = blocks
    idx = np.minimum(idx[:h, :w], len(pal) - 1)
    return pal[idx]


def replace(data, index, rgba):
    """The level bytes with texture `index` redrawn from rgba (same w x h), quantised to its own
    palette size, written in place."""
    from thaw2psp import swizzle
    L = psplevel.Level.__new__(psplevel.Level)
    open_level(L, data)
    clut, pix, w, h, bufw, bits, n, mips = textures(L)[index]
    assert rgba.shape[:2] == (h, w), (rgba.shape, w, h)
    img = Image.fromarray(rgba, 'RGBA')
    q = img.quantize(colors=n, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette(rawmode='RGBA')[:n * 4], np.uint8).reshape(-1, 4)
    pal = np.vstack([pal, np.zeros((n - len(pal), 4), np.uint8)])
    out = bytearray(data)
    out[L.tex + clut:L.tex + clut + n * 4] = pal.tobytes()

    def put(at, bw, lw, lh, indices):
        idx = np.zeros((max(lh, 8), bw), np.uint8)
        idx[:lh, :lw] = indices
        if bits == 4:
            idx = (idx[:, 0::2] & 15) | (idx[:, 1::2] << 4)
        sw = swizzle(np.ascontiguousarray(idx), idx.shape[1], idx.shape[0])
        out[L.tex + at:L.tex + at + len(sw)] = sw
    put(pix, bufw, w, h, np.array(q, np.uint8))
    # the mip levels, against the same palette (their old indices would read the new palette)
    for at, bw, lw, lh in mips:
        small = np.array(img.resize((lw, lh), Image.Resampling.BOX), np.int32).reshape(-1, 1, 4)
        nearest = ((small - pal[None].astype(np.int32)) ** 2).sum(-1).argmin(1)
        put(at, bw, lw, lh, nearest.astype(np.uint8).reshape(lh, lw))
    return bytes(out)


def open_level(L, data):
    """psplevel.Level over bytes in memory."""
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.psp_level') as f:
        f.write(data)
    try:
        L.__init__(f.name)
    finally:
        os.unlink(f.name)


def main():
    L = psplevel.Level(sys.argv[2])
    ts = textures(L)
    if sys.argv[1] == 'sheet':
        cell = 128
        W = Image.new('RGB', (cell * 8, (cell + 12) * ((len(ts) + 7) // 8)), (60, 60, 60))
        dr = ImageDraw.Draw(W)
        for i, t in enumerate(ts):
            try:
                im = Image.fromarray(decode(L, t), 'RGBA')
            except Exception as e:
                print(i, 'fail', e)
                continue
            im.thumbnail((cell - 4, cell - 4))
            x, y = (i % 8) * cell, (i // 8) * (cell + 12)
            bg = Image.new('RGB', im.size, (90, 0, 90))
            bg.paste(im, (0, 0), im)
            W.paste(bg, (x + 2, y + 2))
            dr.text((x + 2, y + cell), f'{i} {t[2]}x{t[3]} {t[5]}b', fill=(255, 255, 0))
        W.save(sys.argv[3])
        print(len(ts), 'textures')
    elif sys.argv[1] == 'export':
        Image.fromarray(decode(L, ts[int(sys.argv[3])]), 'RGBA').save(sys.argv[4])


if __name__ == '__main__':
    main()
