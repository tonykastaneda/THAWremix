"""Convert a THAW (PC) zone into THUG2 Remix (PSP) level files.

  thaw2psp.py build <THAW install> <zone> <outdir> <name> --at x y z [--tex 64] [--texel 0] [--tess 400]
  thaw2psp.py sky <THAW install> <sky> <out.psp_level> [max texture side]

Writes <name>.psp_level (render geometry and textures) and <name>.col.ps2 (collision). The zone
is translated so its "P1: Restart" lands on --at (the target level's own P1 restart), so the target
level's scripts can stay as they are. The shift is rounded to 1/16 inch, the collision grid, so
fixed-point collision vertices and BSP split points stay exact.

Pieces that do not exist at level start are dropped from rendering and made non-collidable;
LevelObjects are placed for rendering only.

Layout written follows tools/psplevel.py. Choices made here:
  - one material list per THAW material, setting all texture and blend state itself, since the
    engine runs lists back to back and a list only changes what it names
  - textures CLUT4 (16 colours, 32-bit palette), longest side at most --tex, swizzled, up to 4 mips
  - strips of at most 31 vertices cut from THAW's own strips; culling is off, so winding is free
  - one visibility box per named piece (sector); box names are the piece checksums
  - opaque pass: blend mode 0 and alpha-tested cutouts; translucent pass: blend/add modes
"""
import argparse
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import thawscene  # noqa: E402
from pak import open_pak, qbkey  # noqa: E402

GE_RET = 0x0B000000
MAX_STRIP = 31
MAX_BOXES = 2045


def ge(op, arg=0):
    return (op << 24) | (arg & 0xFFFFFF)


# ---------------------------------------------------------------- textures

def swizzle(rows, row_bytes, height):
    """PSP swizzle: 16-byte x 8-row blocks, row-major. rows is (height, row_bytes) uint8."""
    blocks = rows.reshape(height // 8, 8, row_bytes // 16, 16).transpose(0, 2, 1, 3)
    return blocks.tobytes()


def pack_clut4(idx, w, h):
    """idx (h, w) palette indices -> (bytes, bufw pixels, stored height)."""
    bufw = max(32, w)
    hh = (h + 7) & ~7
    full = np.zeros((hh, bufw), np.uint8)
    full[:h, :w] = idx
    packed = (full[:, 0::2] & 15) | ((full[:, 1::2] & 15) << 4)
    return swizzle(packed, bufw // 2, hh), bufw


def quantize16(rgba):
    """Returns (palette (16, 4) uint8, function(image) -> index array)."""
    im = Image.fromarray(rgba, 'RGBA')
    q = im.quantize(colors=16, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette(rawmode='RGBA')[:64], np.uint8).reshape(-1, 4)
    if len(pal) < 16:
        pal = np.vstack([pal, np.zeros((16 - len(pal), 4), np.uint8)])
    palf = pal.astype(np.int32)

    def index(img):
        px = img.reshape(-1, 4).astype(np.int32)
        d = ((px[:, None, :] - palf[None, :, :]) ** 2 * np.array([2, 3, 1, 3])).sum(-1)
        return d.argmin(1).astype(np.uint8).reshape(img.shape[:2])
    return pal, index


def pow2_floor(n):
    p = 1
    while p * 2 <= n:
        p *= 2
    return p


class TexBlock:
    """Texture block: per texture a 64-byte palette, then mip levels, all 16-byte aligned."""

    def __init__(self, max_side):
        self.data = bytearray()
        self.max_side = max_side
        self.entries = {}

    def _put(self, b):
        off = len(self.data)
        self.data += b
        self.data += bytes(-len(self.data) % 16)
        return off

    def add(self, key, rgba, max_side=None):
        if key in self.entries:
            return self.entries[key]
        h, w = rgba.shape[:2]
        tw, th = pow2_floor(w), pow2_floor(h)
        scale = min(1.0, (max_side or self.max_side) / max(tw, th))
        tw, th = max(8, int(tw * scale)), max(8, int(th * scale))
        img = np.array(Image.fromarray(rgba, 'RGBA').resize((tw, th), Image.Resampling.BOX))
        pal, index = quantize16(img)
        clut = self._put(pal.tobytes())
        levels = []
        lw, lh, cur = tw, th, img
        while len(levels) < 4 and lw >= 8 and lh >= 8:
            data, bufw = pack_clut4(index(cur), lw, lh)
            levels.append((self._put(data), bufw, lw, lh))
            lw, lh = lw // 2, lh // 2
            if lw >= 8 and lh >= 8:
                cur = np.array(Image.fromarray(cur, 'RGBA').resize((lw, lh), Image.Resampling.BOX))
        alpha = img[:, :, 3]
        e = dict(clut=clut, levels=levels, has_alpha=bool((alpha < 250).any()),
                 soft_alpha=bool(((alpha > 24) & (alpha < 232)).mean() > 0.02))
        self.entries[key] = e
        return e


def white_texture():
    return np.full((8, 8, 4), 255, np.uint8)


# ---------------------------------------------------------------- materials

def material_list(tex, blend, fixed_alpha, wrap_flags):
    """GE words for one material; every list sets the full state."""
    lv = tex['levels']
    w = [ge(0xB0, tex['clut']), ge(0xC4, 2), ge(0xD0, 0x4141C9)]
    for i in range(4):
        w.append(ge(0xA0 + i, lv[min(i, len(lv) - 1)][0]))
    for i in range(4):
        w.append(ge(0xA8 + i, lv[min(i, len(lv) - 1)][1]))
    for i in range(4):
        _, _, lw, lh = lv[min(i, len(lv) - 1)]
        w.append(ge(0xB8 + i, (lw.bit_length() - 1) | (lh.bit_length() - 1) << 8))
    w.append(ge(0xC2, (len(lv) - 1) << 16 | 1))
    w.append(ge(0x1D, 0))
    clamp_u, clamp_v = wrap_flags
    w.append(ge(0xC7, (1 if clamp_u else 0) | (0x100 if clamp_v else 0)))
    w += [ge(0x48, 0x410000), ge(0x49, 0x410000), ge(0x4A, 0xC10000), ge(0x4B, 0xC10000)]
    w.append(ge(0xC3, 4))
    w.append(ge(0xC6, 0x107 if len(lv) > 1 else 0x101))
    if blend == 'opaque':
        w += [ge(0xDB, 0xFF0007), ge(0x21, 0)]
    elif blend == 'cutout':
        w += [ge(0xDB, 0xFF8007), ge(0x21, 0)]
    elif blend == 'add':
        w += [ge(0xDB, 0xFF0207), ge(0x21, 1), ge(0xDF, 0xA2), ge(0xE0, 0xFFFFFF), ge(0xE1, 0xFFFFFF)]
    else:
        w += [ge(0xDB, 0xFF0207), ge(0x21, 1), ge(0xDF, 0x32)]
    w += [ge(0x47, 0x46FFDC), ge(0xCB, 0), GE_RET]
    return w


def classify(rec, tex):
    """THAW material record -> (pass, blend kind, alpha scale, (clamp u, clamp v))."""
    mode = rec[0x90]
    fixed = rec[0x93]
    wrap = (rec[0xA0] != 0, rec[0xA2] != 0)
    if mode == 0:
        kind = 'cutout' if tex['has_alpha'] else 'opaque'
        return 0, kind, 1.0, wrap
    if mode in (1, 2):
        return 1, 'add', (fixed / 128.0) if mode == 2 and fixed else 1.0, wrap
    if mode in (5, 6):
        if not tex['soft_alpha'] and mode == 5:
            return 0, 'cutout', 1.0, wrap
        return 1, 'blend', (fixed / 128.0) if mode == 6 and fixed else 1.0, wrap
    return 1, 'blend', 1.0, wrap


# ---------------------------------------------------------------- level

def to_vertex_space(world):
    """World inches (+Y up) -> GE vertex space before the level offset: (4x, -4z, 4y)."""
    return np.stack([world[:, 0] * 4, -world[:, 2] * 4, world[:, 1] * 4], 1)


def encode_strip(seq):
    """Attribute rows -> (vertex bytes, wide). Compact: u16 u, v; u16 colour 4444; s16 xyz.
    Wide (any coordinate outside 16 bits): u16 u, v; u32 colour 8888; float xyz / 32768."""
    p, uv, rgb, alpha = seq[:, 0:3], seq[:, 3:5], seq[:, 5:8], seq[:, 8]
    wide = bool((np.abs(p) > 32000).any())
    # UVs are stored as (uv + 8) * 4096; shift the strip by whole repeats to fit
    shift = np.floor(uv.min(0))
    uvr = np.clip(np.round((uv - shift + 8) * 4096), 0, 65535).astype(np.uint16)
    if wide:
        # vertex colour is doubled by the texture function, so 0x80 stays 0x80
        c = np.clip(np.concatenate([rgb, alpha[:, None] * 2], 1), 0, 255).astype(np.uint32)
        rec = np.zeros(len(seq), dtype=[('u', '<u2'), ('v', '<u2'), ('c', '<u4'), ('p', '<f4', 3)])
        rec['c'] = c[:, 0] | c[:, 1] << 8 | c[:, 2] << 16 | c[:, 3] << 24
        rec['p'] = p / 32768.0
    else:
        n = np.clip(np.round(rgb * 15 / 255), 0, 15).astype(np.uint16)
        na = np.clip(np.round(alpha * 15 / 128), 0, 15).astype(np.uint16)
        rec = np.zeros(len(seq), dtype=[('u', '<u2'), ('v', '<u2'), ('c', '<u2'), ('p', '<i2', 3)])
        rec['c'] = n[:, 0] | n[:, 1] << 4 | n[:, 2] << 8 | na << 12
        rec['p'] = np.round(p).astype(np.int16)
    rec['u'], rec['v'] = uvr[:, 0], uvr[:, 1]
    return rec.tobytes(), wide


def chunks(seq):
    """Cut a vertex sequence into strips of at most MAX_STRIP, overlapping by two."""
    for start in range(0, max(1, len(seq) - 2), MAX_STRIP - 2):
        part = seq[start:start + MAX_STRIP]
        if len(part) >= 3:
            yield part


def tessellate(a, b, c, n):
    """Triangle split into an n x n barycentric grid, as one strip per row."""
    def at(i, j):
        return a + (b - a) * (i / n) + (c - a) * (j / n)
    for j in range(n):
        row = []
        for i in range(n - j):
            row += [at(i, j), at(i, j + 1)]
        row.append(at(n - j, j))
        yield np.array(row)


def split_strip(attr, s, max_edge):
    """Yields attribute sequences (strips of <= MAX_STRIP vertices) for one THAW strip. Triangles
    with an edge over max_edge (vertex-space units) are tessellated: the PSP rasteriser drops
    triangles that cross the near plane instead of clipping them, so big ground polygons vanish."""
    a, b, c = s[:-2], s[1:-1], s[2:]
    real = (a != b) & (b != c) & (a != c)
    if not real.any():
        return
    P = attr[:, :3]
    if max_edge:
        e = np.maximum.reduce([np.linalg.norm(P[a] - P[b], axis=1), np.linalg.norm(P[b] - P[c], axis=1),
                               np.linalg.norm(P[a] - P[c], axis=1)])
        big = real & (e > max_edge)
    else:
        big = np.zeros(len(a), bool)
    if not big.any():
        for part in chunks(attr[s]):
            pa, pb, pc = part[:-2, :3], part[1:-1, :3], part[2:, :3]
            if (np.abs(np.cross(pb - pa, pc - pa)).sum(1) > 0).any() or len(part) == 3:
                yield part
        return
    # keep runs of small triangles as strips, tessellate the big ones
    k = 0
    while k < len(a):
        if not real[k]:
            k += 1
            continue
        if big[k]:
            n = int(np.ceil(e[k] / max_edge))
            for row in tessellate(attr[a[k]], attr[b[k]], attr[c[k]], n):
                yield from chunks(row)
            k += 1
            continue
        j = k
        while j < len(a) and real[j] and not big[j]:
            j += 1
        # triangles k..j-1 use strip vertices k..j+1
        yield from chunks(attr[s[k:j + 2]])
        k = j


def texture_sides(meshes, materials, max_side, texel):
    """Per texture checksum, the longest side that keeps texels at most `texel` world inches across:
    the world size of one repeat (sqrt of world area over UV area, summed over every triangle using
    it) / texel, rounded up to a power of two, between 32 and max_side."""
    aw, au = {}, {}
    for m in meshes:
        rec = materials.get(m.material)
        if not rec:
            continue
        t = struct.unpack_from('<I', rec, 0x40)[0]
        for s in m.strips:
            a, b, c = s[:-2], s[1:-1], s[2:]
            P, U = m.pos, m.uv
            aw[t] = aw.get(t, 0) + 0.5 * np.linalg.norm(np.cross(P[b] - P[a], P[c] - P[a]), axis=1).sum()
            d1, d2 = U[b] - U[a], U[c] - U[a]
            au[t] = au.get(t, 0) + 0.5 * np.abs(d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum()
    sides = {}
    for t in aw:
        if au[t] > 0:
            want = np.sqrt(aw[t] / au[t]) / texel
            sides[t] = int(min(max_side, max(32, 2 ** int(np.ceil(np.log2(max(want, 1)))))))
    return sides


def lift_decals(meshes, materials, textures, lift, log=print):
    """THAW layers decals (window and shadow decals, road reflections, stains) on surfaces at the same
    depth and draws them with a depth bias; the PSP has none, so they fight with the surface under
    them. Each triangle of a decal mesh (blended material, or an alpha-tested cutout) that lies in the
    plane of an overlapping triangle of an opaque mesh moves `lift` inches along its own normal."""
    def decal(m):
        rec = materials.get(m.material)
        if not rec:
            return False
        if rec[0x90] != 0:
            return True
        t = textures.get(struct.unpack_from('<I', rec, 0x40)[0])
        return t is not None and int(t[0][..., 3].min()) < 128
    kind = [decal(m) for m in meshes]
    cell = 128.0
    grid = {}  # opaque triangles by xz cell: (normal, plane d, bbox lo, bbox hi)
    for mi, m in enumerate(meshes):
        if kind[mi]:
            continue
        P = m.pos
        for st in m.strips:
            for a, b, c in zip(st[:-2], st[1:-1], st[2:]):
                if a == b or b == c or a == c:
                    continue
                t = P[[a, b, c]]
                nrm = np.cross(t[1] - t[0], t[2] - t[0])
                ln = np.linalg.norm(nrm)
                if ln < 1e-3:
                    continue
                nrm = nrm / ln
                lo, hi = t.min(0), t.max(0)
                rec = (nrm, float(nrm @ t[0]), lo, hi)
                for gx in range(int(lo[0] // cell), int(hi[0] // cell) + 1):
                    for gz in range(int(lo[2] // cell), int(hi[2] // cell) + 1):
                        grid.setdefault((gx, gz), []).append(rec)
    moved_meshes = moved = 0
    for mi, m in enumerate(meshes):
        if not kind[mi]:
            continue
        P = m.pos
        shift = np.zeros_like(P)
        for st in m.strips:
            for a, b, c in zip(st[:-2], st[1:-1], st[2:]):
                if a == b or b == c or a == c:
                    continue
                t = P[[a, b, c]]
                nrm = np.cross(t[1] - t[0], t[2] - t[0])
                ln = np.linalg.norm(nrm)
                if ln < 1e-3:
                    continue
                nrm = nrm / ln
                ctr, lo, hi = t.mean(0), t.min(0), t.max(0)
                for on, od, olo, ohi in grid.get((int(ctr[0] // cell), int(ctr[2] // cell)), ()):
                    if abs(on @ nrm) > 0.995 and abs(on @ ctr - od) < 1.0 and (lo <= ohi + 0.5).all() and (hi >= olo - 0.5).all():
                        shift[[a, b, c]] = nrm * lift
                        break
        hit = np.abs(shift).sum(1) > 0
        if hit.any():
            P[hit] += shift[hit]
            moved_meshes += 1
            moved += int(hit.sum())
    log(f'decals lifted {lift} in: {moved} vertices in {moved_meshes} meshes')


def build_level(meshes, materials, textures, delta, max_side, tess_len=400, log=print, offset=None, hidden=(),
                texel=0):
    tb = TexBlock(max_side)
    sides = texture_sides(meshes, materials, max_side, texel) if texel else {}
    lists = [[GE_RET]]  # word 0: never selected explicitly
    mat_word = {}
    mat_info = {}
    list_word = {}
    for m in meshes:
        if m.material in mat_info:
            continue
        rec = materials.get(m.material)
        tcks = struct.unpack_from('<I', rec, 0x40)[0] if rec else 0
        if tcks in textures:
            tex = tb.add(tcks, textures[tcks][0], sides.get(tcks))
        else:
            tex = tb.add('white', white_texture())
        mat_info[m.material] = classify(rec, tex) if rec else (0, 'opaque', 1.0, (False, False))
        words = tuple(material_list(tex, mat_info[m.material][1], mat_info[m.material][2], mat_info[m.material][3]))
        if words not in list_word:
            list_word[words] = sum(len(x) for x in lists)
            lists.append(words)
        mat_word[m.material] = list_word[words]
    texcmds = [w for x in lists for w in x]
    # material switches are signed 16-bit word indices
    assert len(texcmds) < 32768, f'{len(texcmds)} material list words'
    log(f'textures {len(tb.entries)} -> {len(tb.data)} bytes; material lists {len(lists) - 1}, {len(texcmds)} words')

    # vertices in vertex space, already shifted
    all_v = np.concatenate([to_vertex_space(m.pos + delta) for m in meshes])
    lo, hi = all_v.min(0), all_v.max(0)
    # offset: centre of the bulk of the level, not of the far backdrop
    core = np.concatenate([to_vertex_space(m.pos + delta) for m in meshes if m.radius < 6000] or [all_v])
    offset = np.round(np.median(core, 0)).astype(np.int64) if offset is None else np.asarray(offset, np.int64)
    log(f'vertex-space bbox {lo.round()} .. {hi.round()}, offset {offset}')

    # strips first, boxes after: a box is a piece (sector) within one grid cell, so no box spans
    # much more than a cell (stock boxes stay under ~40,000 vertex units across)
    pending = []  # (pass, mat word, sector, seq)
    for m in meshes:
        pas, kind, ascale, _ = mat_info[m.material]
        vs = to_vertex_space(m.pos + delta) - offset
        col = m.col.astype(np.float64)
        # per-vertex rows: vertex-space xyz, uv, rgb, alpha (THAW scale, 0x80 = 1)
        attr = np.concatenate([vs, m.uv, col[:, :3], np.clip(col[:, 3:4] * ascale, 0, 255)], 1)
        far = m.radius > 6000
        for s in m.strips:
            for seq in split_strip(attr, s, None if far else tess_len * 4):
                pending.append((pas, mat_word[m.material], m.sector, seq))
    cell = 16384.0
    while True:
        keys = {}
        assign = []
        for pas, mw, sector, seq in pending:
            c = seq[:, :3].mean(0)
            k = (sector, int(np.floor(c[0] / cell)), int(np.floor(c[1] / cell)))
            assign.append(keys.setdefault(k, len(keys)))
        if len(keys) <= MAX_BOXES:
            break
        cell *= 1.5
    box_name = [k[0] for k in sorted(keys, key=keys.get)]
    box_lo = np.full((len(keys), 3), 1e9)
    box_hi = np.full((len(keys), 3), -1e9)
    strips = {0: [], 1: []}  # pass -> [(mat word, box, wide, vbytes, count)]
    for (pas, mw, sector, seq), b in zip(pending, assign):
        box_lo[b] = np.minimum(box_lo[b], seq[:, :3].min(0))
        box_hi[b] = np.maximum(box_hi[b], seq[:, :3].max(0))
        rec, wide = encode_strip(seq)
        strips[pas].append((mw, b, wide, rec, len(seq)))
    log(f'boxes {len(box_name)} with {cell:.0f}-unit cells')

    # prim stream and vertex block, pass by pass, grouped by format then material
    prims, verts = [], bytearray()
    trans_prim = trans_vert = 0
    for pas in (0, 1):
        if pas == 1:
            if not strips[1]:
                break
            trans_prim, trans_vert = len(prims), len(verts)
        wide_mode, cur = False, None
        for mw, b, wide, data, count in sorted(strips[pas], key=lambda s: (s[2], s[0], s[1])):
            if wide != wide_mode:
                prims += [0, -1 & 0xFFFF]
                wide_mode = wide
            if mw != cur:
                prims += [0, mw]
                cur = mw
            prims.append(count << 11 | (b + 2))
            verts += data
        if wide_mode:
            prims += [0, -1 & 0xFFFF]
        prims += [0, 0]
    log(f'strips opaque {len(strips[0])} translucent {len(strips[1])}; vertex bytes {len(verts)}; prims {len(prims)}; boxes {len(box_name)}')

    # boxes: half floats (min x, y, z, 0, max x, y, z, 0) in vertex space / 32768, tested against
    # the view by the VFPU routine at 0006154c; rounded outwards so they still contain their strips
    lo16 = (box_lo / 32768).astype(np.float16)
    hi16 = (box_hi / 32768).astype(np.float16)
    lo16 = np.where(lo16.astype(np.float64) > box_lo / 32768, np.nextafter(lo16, np.float16(-np.inf)), lo16)
    hi16 = np.where(hi16.astype(np.float64) < box_hi / 32768, np.nextafter(hi16, np.float16(np.inf)), hi16)
    zero = np.zeros((len(lo16), 1), np.float16)
    boxes = np.concatenate([lo16, zero, hi16, zero], 1).astype('<f2').tobytes()

    tex = bytes(tb.data)
    header = struct.pack('<15i', 0xB, 0, len(tex), len(box_name), len(verts), len(texcmds), 0, 0, 0, len(prims),
                         int(offset[0]), int(offset[1]), int(offset[2]), trans_prim, trans_vert) + b'7777'
    out = bytearray(header)
    out += tex
    out += boxes
    out += verts
    out += struct.pack('<I', GE_RET)
    out += struct.pack(f'<{len(texcmds)}I', *texcmds)
    out += struct.pack(f'<{len(box_name)}I', *box_name)
    # box flag bit 0: not drawn (the loader at 0005f79c skips such boxes); pieces that story scripts
    # create later start this way
    flags = bytes(1 if k in hidden else 0 for k in box_name)
    out += flags + bytes(box_flags_len(len(box_name)) - len(box_name))
    out += struct.pack(f'<{len(prims)}H', *prims)
    return bytes(out)


def box_flags_len(n):
    return (n + 3) & ~3


# ---------------------------------------------------------------- collision

def convert_col(d, delta16, disabled, moves=None, start_killed=()):
    """THAW v10 collision (0x50-byte header) -> Remix v10 (0x20-byte header), shifted by delta16
    (sixteenths of an inch per axis); faces of objects in `disabled` become non-collidable.
    `moves` {object checksum: sixteenths} shifts single objects further (LevelObjects, which are
    modelled at the origin): their box, float vertices and their own BSP subtree."""
    moves = moves or {}
    # objects scripts create later start killed and non-collidable (mSD_NON_COLLIDABLE | mSD_KILLED)
    for i in range(struct.unpack_from('<i', d, 4)[0]):
        o = 0x50 + i * 0x40
        if struct.unpack_from('<I', d, o)[0] in start_killed:
            d = d[:o + 4] + struct.pack('<H', struct.unpack_from('<H', d, o + 4)[0] | 0x0006) + d[o + 6:]
    ver, nobj, tverts, tlf, tsf, tlv, tsv, _ = struct.unpack_from('<8i', d, 0)
    assert ver == 10
    out = bytearray(d[:0x20] + d[0x50:])
    H, OBJ = 0x20, 0x40
    base_vert = (H + OBJ * nobj + 15) & ~15
    base_int = base_vert + tlv * 12 + tsv * 6
    base_face = (base_int + tverts + 3) & ~3
    # faces are followed by one byte per large face, padded to 4, then the BSP node array size
    node_size_at = (base_face + tlf * 10 + tsf * 8 + tlf + 3) & ~3
    node_bytes = struct.unpack_from('<i', out, node_size_at)[0]
    base_node = node_size_at + 4
    delta = [v / 16.0 for v in delta16]
    off = 0
    for i in range(nobj):
        o = H + i * OBJ
        cks, flags, nv, nf, small, fixed, ffo = struct.unpack_from('<IHHHBBI', out, o)
        for k in range(3):
            for b in (0x10, 0x20):
                v = struct.unpack_from('<f', out, o + b + 4 * k)[0]
                struct.pack_into('<f', out, o + b + 4 * k, v + delta[k])
        fvo = struct.unpack_from('<I', out, o + 0x30)[0]
        if not fixed:
            p = base_vert + fvo
            for j in range(nv):
                x, y, z = struct.unpack_from('<3f', out, p + 12 * j)
                struct.pack_into('<3f', out, p + 12 * j, x + delta[0], y + delta[1], z + delta[2])
        fsize = 8 if small else 10
        for j in range(nf):
            p = base_face + ffo + j * fsize
            ff = struct.unpack_from('<H', out, p)[0]
            ff &= ~0x40  # trigger: would call scripts the target level does not have
            if cks in disabled:
                ff |= 0x10
            struct.pack_into('<H', out, p, ff)
            off += 1
    # per-object moves: box and float vertices here, BSP subtree below
    extra = {}
    for i in range(nobj):
        o = H + i * OBJ
        cks, flags, nv, nf, small, fixed, ffo = struct.unpack_from('<IHHHBBI', out, o)
        if cks not in moves:
            continue
        mv = moves[cks]
        for k in range(3):
            for b in (0x10, 0x20):
                v = struct.unpack_from('<f', out, o + b + 4 * k)[0]
                struct.pack_into('<f', out, o + b + 4 * k, v + mv[k] / 16.0)
        fvo, bsp = struct.unpack_from('<II', out, o + 0x30)
        if not fixed:
            p = base_vert + fvo
            for j in range(nv):
                x, y, z = struct.unpack_from('<3f', out, p + 12 * j)
                struct.pack_into('<3f', out, p + 12 * j, x + mv[0] / 16, y + mv[1] / 16, z + mv[2] / 16)
        stack = [bsp]
        while stack:
            off = stack.pop()
            w0, w1 = struct.unpack_from('<iI', out, base_node + off)
            if w0 & 3 == 3:
                continue
            if off in extra and extra[off] != mv:
                raise ValueError(f'BSP node {off:#x} shared by objects with different moves')
            extra[off] = mv
            b = w1 & ~3
            stack += [b, b + 8]
    # BSP split points are absolute, in sixteenths, with the axis in the low two bits
    for p in range(base_node, base_node + node_bytes, 8):
        w = struct.unpack_from('<i', out, p)[0]
        axis = w & 3
        if axis != 3:
            sp = (w >> 2) + delta16[axis] + extra.get(p - base_node, (0, 0, 0))[axis]
            struct.pack_into('<i', out, p, (sp << 2) | axis)
    return bytes(out)


def append_col_objects(d, objs, H=0x20):
    """v10 collision with extra objects appended: float vertices, small faces (so the
    one-byte-per-large-face block after the faces is untouched) and a one-leaf BSP each. Every
    block grows at its end, so existing objects' offsets stay valid. objs: dicts with checksum,
    verts (n, 3) world, faces [(flags, terrain, a, b, c)], tail; at most 256 vertices each.
    H is the header size: 0x20 for Remix, 0x50 for THAW's own files (P8), whose extra 0x30 bytes
    (grid dims, world bounds) are kept."""
    OBJ = 0x40
    ver, nobj, tverts, tlf, tsf, tlv, tsv, pad = struct.unpack_from('<8i', d, 0)
    bv = (H + OBJ * nobj + 15) & ~15
    bi = bv + tlv * 12 + tsv * 6
    bf = (bi + tverts + 3) & ~3
    gap = bf + tlf * 10 + tsf * 8
    ns = (gap + tlf + 3) & ~3
    nb = struct.unpack_from('<i', d, ns)[0]
    objects = bytearray(d[H:H + OBJ * nobj])
    verts = bytearray(d[bv:bi])
    inten = bytearray(d[bi:bi + tverts])
    faces = bytearray(d[bf:gap])
    large = bytes(d[gap:gap + tlf])
    nodes = bytearray(d[ns + 4:ns + 4 + nb])
    fidx = bytearray(d[ns + 4 + nb:])
    for o in objs:
        v = np.asarray(o['verts'], np.float64)
        fs = [f for f in o['faces'] if max(f[2:]) < len(v)]
        if len(v) > 256 or not fs:
            continue
        lo, hi = v.min(0), v.max(0)
        objects += struct.pack('<IHHHBBI', o['checksum'], 0, len(v), len(fs), 1, 0, len(faces))
        objects += struct.pack('<4f4f', *lo, 1.0, *hi, 1.0)
        objects += struct.pack('<IIIf', len(verts), len(nodes), len(inten), o.get('tail', 0.0))
        verts += v.astype('<f4').tobytes()
        inten += bytes([0x80]) * len(v)
        for ff, tt, a, b, c in fs:
            faces += struct.pack('<HH4B', ff & ~0x40, tt, a, b, c, 0)
        nodes += struct.pack('<BBHI', 3, 0, len(fs), len(fidx) // 2)
        fidx += struct.pack(f'<{len(fs)}H', *range(len(fs)))
        nobj += 1
        tverts += len(v)
        tlv += len(v)
        tsf += len(fs)
    out = bytearray(struct.pack('<8i', ver, nobj, tverts, tlf, tsf, tlv, tsv, pad)) + d[0x20:H] + objects
    out += bytes(-len(out) % 16) + verts + inten
    out += bytes(-len(out) % 4) + faces + large
    out += bytes(-len(out) % 4) + struct.pack('<i', len(nodes)) + nodes + fidx
    return bytes(out)


# ---------------------------------------------------------------- nodes

def build_qb(target_qb, rails, delta, sink=-100000.0, geometry=()):
    """The target level's .qb with its node array rewritten: its own rail and climbing nodes are
    sunk far below the map (indices, names and links stay, so its scripts still resolve), and the
    zone's rail nodes are appended, shifted, with links renumbered."""
    import qb2
    d = target_qb
    start = qb2.find_item(d, struct.unpack_from('<I', d, 1)[0])
    arr, end = qb2.parse_value(d, start)
    nodes = arr[1]
    bases = {}

    def cls_of(n):
        c = qb2.get(n, qbkey('Class'))
        if c:
            return c[1]
        for k, v in n[1]:
            if k is None and v[0] == 'name':
                if v[1] not in bases:
                    p = qb2.find_item(d, v[1])
                    bases[v[1]] = qb2.parse_value(d, p)[0] if p else None
                c = bases[v[1]] and qb2.get(bases[v[1]], qbkey('Class'))
                if c:
                    return c[1]
        return None
    sunk = 0
    for n in nodes:
        if cls_of(n) in (qbkey('RailNode'), qbkey('ClimbingNode')):
            for i, (k, v) in enumerate(n[1]):
                if k == qbkey('Pos'):
                    n[1][i] = (k, ('vec', (v[1][0], v[1][1] + sink, v[1][2])))
                    sunk += 1
    base = len(nodes)
    index = {r[0]: base + j for j, r in enumerate(rails)}
    for i, pos, ang, name, typ, terrain, links in rails:
        fields = [(qbkey('Pos'), ('vec', tuple(float(pos[k] + delta[k]) for k in range(3)))),
                  (qbkey('Angles'), ('vec', tuple(float(a) for a in ang))),
                  (qbkey('Name'), ('name', name or qbkey(f'thaw_rail_{i}'))),
                  (qbkey('Class'), ('name', qbkey('RailNode'))),
                  (qbkey('Type'), ('name', typ or qbkey('Metal'))),
                  (None, ('name', qbkey('CreatedAtStart'))),
                  (qbkey('TerrainType'), ('name', terrain or qbkey('TERRAIN_GRINDMETAL')))]
        if links:
            fields.append((qbkey('Links'), ('array', [('int', index[l]) for l in links])))
        nodes.append(('struct', fields))
    # LevelGeometry nodes for pieces story scripts kill or create by name: (name key, pos, created)
    for name, pos, created in geometry:
        fields = [(qbkey('Pos'), ('vec', tuple(float(pos[k] + delta[k]) for k in range(3)))),
                  (qbkey('Angles'), ('vec', (0.0, 0.0, 0.0))),
                  (qbkey('Name'), ('name', name)),
                  (qbkey('Class'), ('name', qbkey('LevelGeometry'))),
                  (qbkey('CollisionMode'), ('name', qbkey('Geometry')))]
        if created:
            fields.append((None, ('name', qbkey('CreatedAtStart'))))
        nodes.append(('struct', fields))
    out = d[:start] + qb2.encode_value(arr) + d[end:]
    return out, sunk, len(rails)


# story-start state per zone: THAW's free-skate node flags show the world after the story; these
# put pieces back the way the story starts. 'hidden' pieces are built in but start hidden, for the
# story scripts to create.
STORY_START = {
    'z_ho': {
        'flags': {'NODEFLAG_Z_HO_DINO_BEFORE': 1, 'NODEFLAG_Z_HO_DINO_POOL_BEFORE': 1,
                  'NODEFLAG_Z_HO_DINO_AFTER': 0, 'NODEFLAG_Z_HO_DINO_BLDG_AFTER': 0, 'NODEFLAG_Z_HO_DINO_HEAD': 0},
        'hidden': ('NODEFLAG_Z_HO_DINO_AFTER', 'NODEFLAG_Z_HO_DINO_BLDG_AFTER', 'NODEFLAG_Z_HO_DINO_HEAD'),
        # the dinosaur head: standing pieces, then the fallen ones (story scripts swap them)
        'swap': ('Z_HO_HO_Before_dino_sign', 'Z_HO_HO_Before_Dino01', 'Z_HO_NightOn_03_HO_Before_Dino01_eyes',
                 'Z_HO_HO_Before_dino_bldg', 'Z_HO_HO_Before_dino_roof_pool',
                 'Z_HO_HO_After_dino_bldg', 'Z_HO_HO_After_dino_sign', 'Z_HO_HO_After_Dino01',
                 'Z_HO_HO_After_DinoHead'),
    },
}


# ---------------------------------------------------------------- main

def build_sky(install, sky, out, max_side):
    """A THAW sky dome as a Remix sky level (no shift, no collision)."""
    entries, blob = open_pak(os.path.join(install, 'data', 'skies', sky, f'{sky}.pak.wpc'))
    get = lambda e: blob[e['offset']:e['offset'] + e['size']]
    largest = lambda ext: max((e for e in entries if e['type'] == qbkey(ext)), key=lambda e: e['size'])
    materials, meshes = thawscene.parse_geom(get(largest('.geom')))
    textures = thawscene.parse_tex(get(largest('.tex')))
    # Remix skies are compact-format domes about 8,190 inches across, centred on the origin
    scale = 7800.0 / max(np.abs(m.pos).max() for m in meshes)
    for m in meshes:
        m.pos = m.pos * scale
        m.radius = max(m.radius, 1e9)  # never tessellate
    lvl = build_level(meshes, materials, textures, np.zeros(3), max_side, 0, offset=(0, 0, 0))
    open(out, 'wb').write(lvl)
    print(f'{out} {len(lvl)} bytes')


def main():
    if sys.argv[1] == 'sky':
        return build_sky(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 128)
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('install')
    ap.add_argument('zone')
    ap.add_argument('outdir')
    ap.add_argument('name')
    ap.add_argument('--at', type=float, nargs=3, required=True)
    ap.add_argument('--tex', type=int, default=64)
    ap.add_argument('--texel', type=float, default=0,
                    help='shrink each texture (down to 32) while its texels stay at most this many inches across')
    ap.add_argument('--tess', type=float, default=400, help='longest triangle edge in inches near the playable area')
    ap.add_argument('--decal-lift', type=float, default=0, help='inches decals move off the surface under them')
    ap.add_argument('--max-radius', type=float, default=0, help='drop meshes with a larger bounding radius')
    ap.add_argument('--no-props', action='store_true', help='leave out GameObject props')
    ap.add_argument('--col-base', help='also write <name>.props.col: this collision file (THAW PS2, for Project 8) '
                                       'with the props appended')
    ap.add_argument('--qb', help="target level's .qb (its node array gets the zone's rails)")
    ap.add_argument('--pre', help="target level's scripts .pre (rebuilt holding the new .qb)")
    ap.add_argument('--pre-entry', help=r'path of the .qb inside the .pre, e.g. levels\TR\TR.qb')
    a = ap.parse_args()
    story = STORY_START.get(a.zone, {})
    materials, meshes, textures, pieces, restarts = thawscene.load_zone(
        a.install, a.zone, story.get('flags'), story.get('hidden', ()))
    hidden = thawscene.load_zone.hidden
    print(f'story start: {len(hidden)} pieces built in hidden')
    p1 = next(r for r in restarts if r[0] == 'P1: Restart')
    delta16 = [int(round((t - s) * 16)) for t, s in zip(a.at, p1[1])]
    delta = np.array(delta16) / 16.0
    print(f'{a.zone}: P1 restart {p1[1]} -> {a.at}, shift {delta}')
    if a.max_radius:
        meshes = [m for m in meshes if m.radius <= a.max_radius]
    prop_cols = []
    if not a.no_props:
        pm, pmats, ptex, prop_cols = thawscene.load_props(a.install, a.zone)
        meshes += pm
        materials = {**pmats, **materials}
        textures = {**ptex, **textures}
        print(f'props: {len(pm)} meshes, {len(prop_cols)} collision objects')
    os.makedirs(a.outdir, exist_ok=True)
    if a.decal_lift:
        lift_decals(meshes, materials, textures, a.decal_lift)
    lvl = build_level(meshes, materials, textures, delta, a.tex, a.tess, hidden=hidden, texel=a.texel)
    open(os.path.join(a.outdir, f'{a.name}.psp_level'), 'wb').write(lvl)
    print(f'{a.name}.psp_level {len(lvl)} bytes')

    entries, blob = open_pak(os.path.join(a.install, 'data', 'worlds', 'worldzones', a.zone, f'{a.zone}.pak.wpc'))
    ce = max((e for e in entries if e['type'] == qbkey('.col')), key=lambda e: e['size'])
    # LevelObjects sit at the origin in the file; unrotated ones are moved to their node, the rest
    # (and pieces absent at level start) lose their collision
    moves = {k: [int(round(c * 16)) for c in place[0]] for k, (created, place) in pieces.items()
             if created and place and max(abs(x) for x in place[1]) < 0.05}
    disabled = {k for k, (created, place) in pieces.items() if not created or (place and k not in moves)}
    col = convert_col(blob[ce['offset']:ce['offset'] + ce['size']], delta16, disabled, moves, start_killed=hidden)
    if prop_cols:
        col = append_col_objects(col, [dict(o, verts=o['verts'] + delta) for o in prop_cols])
    open(os.path.join(a.outdir, f'{a.name}.col.ps2'), 'wb').write(col)
    print(f'{a.name}.col.ps2 {len(col)} bytes, {len(disabled)} pieces disabled, {len(moves)} level objects placed')
    if a.col_base:  # Project 8: THAW's own (PS2) collision, which P8 loads as is, plus the props
        pcol = append_col_objects(open(a.col_base, 'rb').read(), [dict(o, verts=o['verts'] + delta) for o in prop_cols], H=0x50)
        open(os.path.join(a.outdir, f'{a.name}.props.col'), 'wb').write(pcol)
        print(f'{a.name}.props.col {len(pcol)} bytes: {os.path.basename(a.col_base)} + {len(prop_cols)} prop objects')

    if a.qb:
        import qb2
        rails = thawscene.load_rails(a.install, a.zone)
        swap = story.get('swap', ())
        tn = {thawscene._key(n['Name']): n for n in thawscene.expanded_nodes(
            os.path.join(os.environ.get('TEMP', '.'), f'{a.zone}_nodes.qb'), a.zone) if isinstance(n.get('Name'), str)}
        geometry = [(qbkey(nm), tn[qbkey(nm)].get('Pos', [0, 0, 0]), qbkey(nm) not in hidden)
                    for nm in swap if qbkey(nm) in tn]
        qbdata, sunk, added = build_qb(open(a.qb, 'rb').read(), rails, delta, geometry=geometry)
        print(f'{len(geometry)} story geometry nodes added')
        open(os.path.join(a.outdir, f'{a.name}.qb'), 'wb').write(qbdata)
        print(f'{a.name}.qb {len(qbdata)} bytes: {sunk} own rail/climb nodes sunk, {added} rail nodes added')
        if a.pre:
            out = os.path.join(a.outdir, os.path.basename(a.pre))
            qb2.replace_in_pre(a.pre, out, a.pre_entry, qbdata)
            print(f'{os.path.basename(a.pre)} {os.path.getsize(out)} bytes')


if __name__ == '__main__':
    main()
