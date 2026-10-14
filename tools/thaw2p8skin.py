"""THAW (PC) skinned model -> Project 8 PSP skin (.skin.psp).

  thaw2p8skin.py <THAW .skin.wpc> <out .skin.psp> [--name <file name>] [--tex 64] [--palette 8]
                 [--also <THAW .skin.wpc> ...]   (more parts merged in, e.g. a separate head)

THAW and P8 share the skeleton (thps7_human), so only the format changes:
  THAW skinned vertex (40 bytes, mesh +0x26 = weight count): position 3 floats (inches, Y up) at 0,
    weights at 12 (11/11/10-bit signed-normalized), bone indices 4 x u16 at 16 (bone * 3), normal at 24
    (11/11/10 signed-normalized), BGRA colour (0x80 = full) at 28, UV 2 floats at 32; strips (prim 5).
  P8 vertex (see p8skin.py): GE skinning format, u8 weights summing to 0xf8 for every bone of the
    draw's palette (one CALL 0x40 * bone per slot, at most 8), s16 UV (raw / 256 - 128), 4444 colour,
    s8 normal, s16 position in 1/16 inch with P8 axes (x, -z, y) of THAW's.
Each THAW mesh becomes draws of triangles whose bones fit one palette. Textures are THAW's own
(.tex.wpc beside the skin), CLUT4 with mips (thaw2psp.TexBlock), addressed from the texture block.
"""
import argparse
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import thaw2psp  # noqa: E402
import thawscene as ts  # noqa: E402
from pak import qbkey  # noqa: E402


def snorm(w, fields):
    out, a = [], 0
    for b in fields:
        x = (w >> a) & ((1 << b) - 1)
        a += b
        out.append((x - (1 << b) if x >= 1 << (b - 1) else x) / ((1 << (b - 1)) - 1))
    return out


def read_thaw_skin(path):
    """(materials, textures, [mesh dict]) of a THAW .skin.wpc and its .tex.wpc."""
    tex_path = path[:-len('.skin.wpc')] + '.tex.wpc'
    textures = ts.parse_tex(open(tex_path, 'rb').read()) if os.path.exists(tex_path) else {}
    return read_thaw_scene(open(path, 'rb').read(), textures)


def read_thaw_scene(d, textures, rigid=False):
    """(materials, textures, [mesh dict]) of a THAW .skin.wpc or .mdl.wpc (same scene container);
    rigid .mdl's meshes (no weights) are bound wholly to bone 0; skins skip unweighted meshes."""
    u16 = lambda o: struct.unpack_from('<H', d, o)[0]  # noqa: E731
    u32 = lambda o: struct.unpack_from('<I', d, o)[0]  # noqa: E731
    materials, _ = ts.parse_geom(d)
    scene = 0x20 + u32(0x24)
    base = scene + u32(scene + 4)
    mb = base + u32(base + 0x9C)
    count = (base + u32(mb + 0x84) - mb) // ts.MESH_SIZE
    meshes = []
    for k in range(count):
        o = mb + k * ts.MESH_SIZE
        st, coff, noff, nw, uoff = d[o + 0x20], d[o + 0x24], d[o + 0x25], d[o + 0x26], d[o + 0x27]
        vc, ic, prim = u16(o + 0x2E), u32(o + 0x30), u32(o + 0x60)
        ib, vb = base + u32(o + 0x64) + 12, base + u32(o + 0x84) + 8
        if (not nw and not rigid) or prim not in (4, 5) or vc == 0:
            continue
        pos, nrm, col, uv, bones, wts = [], [], [], [], [], []
        for v in range(vc):
            r = vb + v * st
            pos.append(struct.unpack_from('<3f', d, r))
            pairs = {}
            if nw:
                w = snorm(u32(r + 12), (11, 11, 10))
                ix = [b // 3 for b in struct.unpack_from('<4H', d, r + 16)]
                for i in range(min(nw, 3)):
                    if w[i] > 0.004:
                        pairs[ix[i]] = pairs.get(ix[i], 0) + w[i]
                if not pairs:
                    pairs = {ix[0]: 1.0}
            else:
                pairs = {0: 1.0}
            bones.append(list(pairs))
            wts.append(list(pairs.values()))
            nrm.append(snorm(u32(r + noff), (11, 11, 10)))
            col.append(d[r + coff:r + coff + 4])
            uv.append(struct.unpack_from('<2f', d, r + uoff))
        idx = np.frombuffer(d, '<u2', ic, ib).astype(np.int64)
        if prim == 5:
            tris = [(idx[i], idx[i + 1], idx[i + 2]) if i % 2 == 0 else (idx[i + 1], idx[i], idx[i + 2])
                    for i in range(len(idx) - 2)]
        else:
            tris = [tuple(idx[i:i + 3]) for i in range(0, len(idx) // 3 * 3, 3)]
        tris = [t for t in tris if len({*t}) == 3]
        meshes.append(dict(material=u32(o + 0x1C), pos=pos, nrm=nrm, col=col, uv=uv, bones=bones, wts=wts,
                           tris=tris, strip=list(idx) if prim == 5 else None))
    return materials, textures, meshes


def draws(mesh, palette_max):
    """[(palette, [triangles])]: triangles in order, a new draw when the palette would overflow."""
    out, pal, tris = [], [], []
    for t in mesh['tris']:
        need = sorted({b for v in t for b in mesh['bones'][v]})
        merged = sorted(set(pal) | set(need))
        if len(merged) > palette_max and tris:
            out.append((pal, tris))
            pal, tris = need, []
            merged = need
        pal = merged
        tris.append(t)
    if tris:
        out.append((pal, tris))
    return out


def strip_runs(mesh, palette_max):
    """THAW's strip cut into runs [(parity, [vertex])] without degenerate triangles, none needing more
    than palette_max bones (a longer run is cut, its pieces overlapping by two vertices)."""
    st = mesh['strip']
    runs, cur, start = [], [], 0
    for i in range(len(st) - 2):
        a, b, c = st[i], st[i + 1], st[i + 2]
        if len({a, b, c}) < 3:
            if len(cur) >= 3:
                runs.append((start % 2, cur))
            cur = []
            continue
        if not cur:
            cur, start = [a, b, c], i
        else:
            cur.append(c)
    if len(cur) >= 3:
        runs.append((start % 2, cur))
    out = []
    for par, seq in runs:
        piece, pbones, pstart = [], set(), 0
        for j, v in enumerate(seq):
            vb = set(mesh['bones'][v])
            if len(piece) >= 3 and len(pbones | vb) > palette_max:
                out.append(((par + pstart) % 2, piece))
                pstart = j - 2
                piece = seq[j - 2:j]
                pbones = {b for u in piece for b in mesh['bones'][u]}
            piece.append(v)
            pbones |= vb
        if len(piece) >= 3:
            out.append(((par + pstart) % 2, piece))
    return out


def strip_draws(mesh, palette_max):
    """[(palette, [(parity, run)])]: runs in order, a new draw when the palette would overflow."""
    out, pal, runs = [], set(), []
    for par, run in strip_runs(mesh, palette_max):
        need = {b for v in run for b in mesh['bones'][v]}
        if len(pal | need) > palette_max and runs:
            out.append((sorted(pal), runs))
            pal, runs = set(), []
        pal |= need
        runs.append((par, run))
    if runs:
        out.append((sorted(pal), runs))
    return out


def vtype(n):
    """GE vertex type: s16 UV, 4444 colour, s8 normal, s16 position, n u8 weights."""
    return 2 | 6 << 2 | 1 << 5 | 2 << 7 | 1 << 9 | (n - 1) << 14


# a rigid .mdl's vertices: as vtype's without weights (the engine sets the object's matrix)
RIGID_VTYPE = 2 | 6 << 2 | 1 << 5 | 2 << 7


def pack_vertex(mesh, v, pal):
    """pal None: a rigid vertex (no weights)."""
    q = []
    if pal is not None:
        w = [0.0] * len(pal)
        for b, x in zip(mesh['bones'][v], mesh['wts'][v]):
            w[pal.index(b)] += x
        tot = sum(w) or 1.0
        q = [int(round(x / tot * 0xF8)) for x in w]
        q[q.index(max(q))] += 0xF8 - sum(q)
    out = bytearray(bytes(q))
    out += bytes(-len(out) % 2)
    u, vv = mesh['uv'][v]
    out += struct.pack('<2H', *(min(65535, max(0, int(round((c + 128) * 256)))) for c in (u, vv)))
    b, g, r, a = mesh['col'][v]
    c4 = lambda c: min(15, c * 15 // 128)  # noqa: E731
    out += struct.pack('<H', c4(r) | c4(g) << 4 | c4(b) << 8 | c4(a) << 12)
    nx, ny, nz = mesh['nrm'][v]
    out += struct.pack('<3b', *(max(-127, min(127, int(round(c * 127)))) for c in (nx, -nz, ny)))
    out += bytes(-len(out) % 2)
    x, y, z = mesh['pos'][v]
    out += struct.pack('<3h', *(max(-32767, min(32767, int(round(c * 16)))) for c in (x, -z, y)))
    out += bytes(-len(out) % 2)
    return bytes(out)


def ge(cmd, arg=0):
    return struct.pack('<I', cmd << 24 | (arg & 0xFFFFFF))


def material_words(tex, vt_next, cutout=False):
    """P8's per-material state block (as its own skins: CLUT4, mips, alpha test), ending in the
    next draw's VTYPE and RET. cutout: alpha test on (texels under alpha 2 dropped), for textures
    that cut shapes out with alpha (THAW's sleeveless shirts' armholes)."""
    lv = tex['levels']
    w = ge(0x10) + ge(0xCB) + ge(0xB0, tex['clut']) + ge(0xB1) + ge(0xC4, 2)
    for i in range(4):
        w += ge(0xA0 + i, lv[min(i, len(lv) - 1)][0])
    for i in range(4):
        w += ge(0xA8 + i, lv[min(i, len(lv) - 1)][1])
    w += ge(0xC3, 4)
    for i in range(4):
        _, _, lw, lh = lv[min(i, len(lv) - 1)]
        w += ge(0xB8 + i, (lw.bit_length() - 1) | (lh.bit_length() - 1) << 8)
    w += ge(0xC2, (len(lv) - 1) << 16 | 1)
    w += (ge(0x1E, 1) + ge(0x17, 1) + ge(0xC9, 0x010100) + ge(0x21) + ge(0x1D) + ge(0xC0) + ge(0x5B) + ge(0x57)
          + ge(0xC6, 0x107 if len(lv) > 1 else 0x101) + ge(0x22, int(cutout)) + ge(0xDB, 0xFF0207) + ge(0xCF, 0x0080A0)
          + ge(0xC7) + ge(0x48, 0x430000) + ge(0x49, 0x430000) + ge(0x4A, 0xC30000) + ge(0x4B, 0xC30000)
          + ge(0x47, 0x46FFDC) + ge(0x12, vt_next) + ge(0x0B))
    return w


def convert(src, out, name=None, max_side=64, palette_max=8, also=(), retex=None):
    """retex: {texture checksum (qbkey of THAW's png name): THAW .img.wpc} baked in place of that
    texture (THAW's CAS 'replace' / 'with' variants of one mesh become skins of their own)."""
    materials, textures, meshes = read_thaw_skin(src)
    for extra in also:  # same skeleton: the parts' meshes just add up
        m2, t2, ms2 = read_thaw_skin(extra)
        materials.update(m2)
        textures.update(t2)
        meshes += ms2
    for cks, img in (retex or {}).items():
        (rgba, comp), = ts.parse_tex(bytes(8) + open(img, 'rb').read()).values()
        textures[cks] = (rgba, comp)
    body, info = build(materials, textures, meshes, name or os.path.basename(out), max_side, palette_max)
    open(out, 'wb').write(body)
    print(f'{out}: {info}')
    return len(body)


def build(materials, textures, meshes, name, max_side=64, palette_max=8, rigid=False):
    """(P8 model body, summary). rigid: a .mdl's geometry (P8's cutscene props): one display list run
    from the vertex data in order, vertices without weights, one material record at list offset 0."""
    tb = thaw2psp.TexBlock(max_side)
    recs, dl, verts = [], bytearray() if rigid else bytearray(ge(0x10) + ge(0x0B)), bytearray()
    if rigid:
        recs.append((1, 0, 0, 0, 0x808080))
    radius, max_bone = 0.0, 0
    for m in meshes:
        rec = materials.get(m['material'])
        tcks = struct.unpack_from('<I', rec, 0x40)[0] if rec else 0
        alpha = textures[tcks][0][:, :, 3] if tcks in textures else None
        cutout = alpha is not None and bool((alpha < 128).any() and (alpha >= 128).any())
        tex = (tb.add(tcks, textures[tcks][0], cutout=cutout) if tcks in textures else
               tb.add('white', thaw2psp.white_texture()))
        groups = ([(p, [('tris', t)]) for p, t in draws(m, palette_max)] if m['strip'] is None else
                  [(p, [('strip', r) for r in rs]) for p, rs in strip_draws(m, palette_max)])
        if rigid:  # one bone: a single group holding every item
            groups = [(None, [i for _, items in groups for i in items])]
        for pal, items in groups:
            if rigid:
                vt = RIGID_VTYPE
                dl += material_words(tex, vt, cutout)[:-4] + ge(0x2A)  # the state block less its RET
            else:
                vt = vtype(len(pal))
                recs.append((1, len(dl), m['material'], 0, 0x808080))
                dl += material_words(tex, vt, cutout)
                recs.append((4, len(dl), tcks, 0, 0))
                dl += ge(0x10) + ge(0x0B)
                recs.append((2, len(dl), 0, len(verts), 0))
                dl += ge(0x10) + ge(0x12, vt) + ge(0x2A)
                for b in pal:
                    dl += ge(0x0A, 0x40 * b)
                    max_bone = max(max_bone, b)
            for kind, item in items:
                if kind == 'tris':
                    for i in range(0, len(item), 21000):  # PRIM counts are 16-bit
                        chunk = item[i:i + 21000]
                        dl += ge(0x04, 3 << 16 | len(chunk) * 3)
                        seq = [v for t in chunk for v in t]
                        for v in seq:
                            verts += pack_vertex(m, v, pal)
                else:
                    par, seq = item
                    dl += ge(0x9B, par) + ge(0x04, 4 << 16 | len(seq))  # FFACE by the run's parity
                    for v in seq:
                        verts += pack_vertex(m, v, pal)
                for v in seq:
                    radius = max(radius, float(np.linalg.norm(m['pos'][v])) * 16)
            if not rigid:
                verts += bytes(-len(verts) % 4)
            dl += ge(0xFF) + (b'' if rigid else ge(0x0B))
    if rigid:
        dl += ge(0x0B)
        verts += bytes(-len(verts) % 4)
    nrec = len(recs) + 1
    tex_off = 0x60 + nrec * 16
    tex_off += -tex_off % 64
    tdata = bytes(tb.data) + bytes(-len(tb.data) % 64)
    dl_off = tex_off + len(tdata)
    v_off = dl_off + len(dl)
    hdr = struct.pack('<16I', 0xC0EDBABE, 0, 0x60, 0, 0, tex_off, len(tdata), 0, v_off, len(verts), 0,
                      dl_off, len(dl), 0, 0 if rigid else max_bone + 1, 0)
    hdr = bytearray(hdr)
    struct.pack_into('<f', hdr, 12, radius)
    body = bytearray(hdr) + (('A' if rigid else '`') + name).encode('latin-1')[:31].ljust(32, b'\0')
    for t, off, a, b, c in recs:
        body += struct.pack('<B', t) + struct.pack('<H', off) + b'\0' + struct.pack('<3I', a, b, c)
    body += bytes(16)
    body += bytes(tex_off - len(body))
    body += tdata + dl + verts
    ndraw = sum(1 for r in recs if r[0] == 2)
    info = (f'{len(meshes)} THAW meshes -> {ndraw} draws, {len(verts)} vertex bytes, {len(tdata)} texture '
            f'bytes, {len(body):,} bytes, bones up to {max_bone}')
    return bytes(body), info


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--name')
    ap.add_argument('--tex', type=int, default=64)
    ap.add_argument('--palette', type=int, default=8)
    ap.add_argument('--also', nargs='*', default=[])
    a = ap.parse_args()
    convert(a.src, a.out, a.name, a.tex, a.palette, a.also)
