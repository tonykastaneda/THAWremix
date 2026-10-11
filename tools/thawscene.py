"""THAW (PC) level scene reader for conversion work: .geom meshes as raw strips, .tex textures
decoded to RGBA, and the node array (pieces present at level start, restarts).

Same layouts as thaw-bevy/src/formats/scene.rs; see the comments there.

  thawscene.py stats <zone pak dir>     counts for the pieces that exist at level start
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import qb  # noqa: E402
from pak import open_pak, qbkey  # noqa: E402

MATERIAL_SIZE = 0x120
MESH_SIZE = 0xE0


class Mesh:
    __slots__ = ('material', 'sector', 'center', 'radius', 'pos', 'col', 'uv', 'strips')


def parse_geom(d):
    """Returns (materials {checksum: raw 0x120 record}, [Mesh]). Mesh.strips is a list of index
    arrays: one per triangle strip (prim 5), or one 3-index strip per triangle (prim 4)."""
    u16 = lambda o: struct.unpack_from('<H', d, o)[0]
    u32 = lambda o: struct.unpack_from('<I', d, o)[0]
    nmat = u16(0x22)
    scene = 0x20 + u32(0x24)
    assert u32(scene) == 0xBABEFACE
    materials = {}
    for i in range(nmat):
        o = 0x30 + i * MATERIAL_SIZE
        materials[u32(o)] = d[o:o + MATERIAL_SIZE]
    base = scene + u32(scene + 4)
    mesh_base = base + u32(base + 0x9C)
    nsec = u32(base + 0x88)
    sec_base = base + u32(base + 0x8C)
    rec_base = base + u32(base + 0x90)
    mesh_sector = []
    for i in range(nsec):
        mesh_sector += [u32(sec_base + i * 0x30 + 0x0C)] * min(u32(rec_base + i * 0x68 + 0x4C), 4096)
    count = (base + u32(mesh_base + 0x84) - mesh_base) // MESH_SIZE
    meshes = []
    for k in range(count):
        o = mesh_base + k * MESH_SIZE
        stride, coff, uoff = d[o + 0x20], d[o + 0x24], d[o + 0x27]
        if d[o + 0x26]:
            continue  # skinned
        vc, ic, prim = u16(o + 0x2E), u32(o + 0x30), u32(o + 0x60)
        ib = base + u32(o + 0x64) + 12
        vb = base + u32(o + 0x84) + 8
        if stride < 12 or vc == 0 or ic < 3 or vb + vc * stride > len(d) or ib + ic * 2 > len(d):
            continue
        raw = np.frombuffer(d, np.uint8, vc * stride, vb).reshape(vc, stride)
        m = Mesh()
        m.material = u32(o + 0x1C)
        m.sector = mesh_sector[k] if k < len(mesh_sector) else 0
        m.center = struct.unpack_from('<3f', d, o + 0x0C)
        m.radius = struct.unpack_from('<f', d, o + 0x18)[0]
        m.pos = raw[:, 0:12].copy().view('<f4').reshape(vc, 3).astype(np.float64)
        if 12 <= coff and coff + 4 <= stride:
            bgra = raw[:, coff:coff + 4]
            m.col = bgra[:, [2, 1, 0, 3]].copy()  # RGBA, 0x80 = full
        else:
            m.col = np.full((vc, 4), 0x80, np.uint8)
        if 12 <= uoff and uoff + 8 <= stride:
            m.uv = raw[:, uoff:uoff + 8].copy().view('<f4').reshape(vc, 2).astype(np.float64)
        else:
            m.uv = np.zeros((vc, 2))
        idx = np.frombuffer(d, '<u2', ic, ib).astype(np.int64)
        if idx.max() >= vc:
            continue
        if prim == 5:
            m.strips = [idx]
        elif prim == 4:
            m.strips = [idx[i:i + 3] for i in range(0, ic // 3 * 3, 3)]
        else:
            continue
        meshes.append(m)
    return materials, meshes


def _dxt_colors(c0, c1, four):
    """Palette of 4 RGB colours per block (n, 4, 3)."""
    def rgb(c):
        return np.stack([(c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31], -1)
    a, b = rgb(c0.astype(np.int32)), rgb(c1.astype(np.int32))
    p2 = np.where(four[:, None], (2 * a + b) // 3, (a + b) // 2)
    p3 = np.where(four[:, None], (a + 2 * b) // 3, 0)
    return np.stack([a, b, p2, p3], 1)


def decode_dxt(data, w, h, fmt):
    """fmt 1/2 DXT1, 5 DXT5. Returns (h, w, 4) uint8."""
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    n = bw * bh
    if fmt == 5:
        blk = np.frombuffer(data, np.uint8, n * 16).reshape(n, 16)
        ab, cb = blk[:, :8], blk[:, 8:]
    else:
        cb = np.frombuffer(data, np.uint8, n * 8).reshape(n, 8)
    c0 = cb[:, 0].astype(np.uint16) | cb[:, 1].astype(np.uint16) << 8
    c1 = cb[:, 2].astype(np.uint16) | cb[:, 3].astype(np.uint16) << 8
    four = (c0 > c1) | (fmt == 5)
    pal = _dxt_colors(c0, c1, four)
    bits = cb[:, 4:8].copy().view('<u4')[:, 0]
    sel = (bits[:, None] >> (2 * np.arange(16, dtype=np.uint32))) & 3
    rgb = np.take_along_axis(pal, sel[:, :, None].astype(np.int64).repeat(3, 2), 1)
    if fmt == 5:
        a0, a1 = ab[:, 0].astype(np.int32), ab[:, 1].astype(np.int32)
        abits = np.zeros(n, np.uint64)
        for i in range(6):
            abits |= ab[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
        asel = ((abits[:, None] >> (np.uint64(3) * np.arange(16, dtype=np.uint64))) & np.uint64(7)).astype(np.int64)
        k = np.arange(8)
        eight = np.where(k[None] == 0, a0[:, None], np.where(k[None] == 1, a1[:, None],
                         ((8 - k[None]) * a0[:, None] + (k[None] - 1) * a1[:, None]) // 7))
        six = np.where(k[None] == 0, a0[:, None], np.where(k[None] == 1, a1[:, None],
                       np.where(k[None] < 6, ((6 - k[None]) * a0[:, None] + (k[None] - 1) * a1[:, None]) // 5,
                                np.where(k[None] == 6, 0, 255))))
        apal = np.where((a0 > a1)[:, None], eight, six)
        alpha = np.take_along_axis(apal, asel, 1)
    elif fmt == 2:
        alpha = np.where((~four[:, None]) & (sel == 3), 0, 255)
    else:
        alpha = np.full(sel.shape, 255)  # compression 1: DXT1 without alpha
    px = np.concatenate([rgb, alpha[:, :, None]], 2).astype(np.uint8).reshape(bh, bw, 4, 4, 4)
    return px.transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)[:h, :w]


def parse_tex(d):
    """{checksum: (rgba (h, w, 4) uint8 of the top mip, compression)}"""
    out = {}
    magic = b'\x0D\xD0\xAD\xAB'
    o = 8
    while o + 28 <= len(d):
        if d[o:o + 4] != magic:
            j = d.find(magic, o)
            if j < 0:
                break
            o = j
            continue
        cks = struct.unpack_from('<I', d, o + 8)[0]
        w, h = struct.unpack_from('<HH', d, o + 12)
        mips, bpp, comp = d[o + 20], d[o + 21], d[o + 22]
        p = o + 24
        size = struct.unpack_from('<I', d, p)[0]
        if comp in (1, 2, 5):
            img = decode_dxt(d[p + 4:p + 4 + size], w, h, comp)
        elif comp == 0 and bpp == 32:
            img = np.frombuffer(d, np.uint8, w * h * 4, p + 4).reshape(h, w, 4)[:, :, [2, 1, 0, 3]]
        else:
            o += 4
            continue
        out[cks] = (img, comp)
        # skip the mip chain
        p += 4 + size
        for _ in range(1, max(1, mips)):
            if p + 4 > len(d):
                break
            s = struct.unpack_from('<I', d, p)[0]
            if s > len(d) - p - 4 or (d[p + 4:p + 8] == magic and s == 0):
                break
            p += 4 + s
            if d[p:p + 4] == magic:
                break
        o = max(p, o + 4)
    return out


def node_flags(install):
    """Free-skate node flag values (see load_node_flags in thaw-bevy/src/world.rs)."""
    entries, blob = open_pak(os.path.join(install, 'data', 'pak', 'qb.pak.wpc'))
    e = next(e for e in entries if (e['name'] or '').lower().endswith('game\\menu\\chapter_info.qb.wpc'))
    q = qb.QB(blob[e['offset']:e['offset'] + e['size']])
    want = qbkey('game_progress_set_non_story_mode_nodeflags')
    p = 0x1C
    size = q.u32(4)
    code = None
    while p + 0x14 <= size:
        t = q.d[p + 2]
        idk, fk, v, nxt = struct.unpack_from('<4I', q.d, p + 4)
        q.hi = p + 0x14
        if t == 7:
            usz, csz = struct.unpack_from('<2I', q.d, v + 4)
            q.touch(v + 12 + csz)
            if idk == want:
                raw = q.d[v + 12:v + 12 + csz]
                code = lzss(raw, usz) if csz < usz else raw
        else:
            try:
                q.value(t, v)
            except Exception:
                pass
        p = (q.hi + 3) & ~3
    out = {}
    i = 0
    while code and i + 12 <= len(code):
        if code[i] == 3 and code[i + 1] == 0x16 and code[i + 6] == 0x17 and code[i + 11] == 4:
            k, v = struct.unpack_from('<Ii', code, i + 2)
            out[k] = v
            i += 12
        else:
            i += 1
    return out


def lzss(src, out_len):
    ring = bytearray(b' ' * 4096)
    r = 4096 - 18
    out = bytearray()
    i = 0
    flags = 0
    while i < len(src) and len(out) < out_len:
        flags >>= 1
        if not flags & 0x100:
            flags = src[i] | 0xFF00
            i += 1
            if i >= len(src):
                break
        if flags & 1:
            c = src[i]
            i += 1
            out.append(c)
            ring[r] = c
            r = (r + 1) & 4095
        else:
            if i + 1 >= len(src):
                break
            a, b = src[i], src[i + 1]
            i += 2
            off = a | ((b & 0xF0) << 4)
            for k in range((b & 15) + 3):
                c = ring[(off + k) & 4095]
                out.append(c)
                ring[r] = c
                r = (r + 1) & 4095
    return bytes(out[:out_len])


def expanded_nodes(qb_path, zone):
    """The zone's node array as dicts, with compressed nodes' shared fields merged in."""
    q = qb.QB(open(qb_path, 'rb').read())
    items = dict(q.items())
    arr = next(v for k, v in items.items() if k.lower() == f'{zone}_nodearray')
    out = []
    for n in arr:
        d = qb.todict(n)
        for f in list(d.get('_flags', [])):
            base = items.get(f[1:]) if isinstance(f, str) and f.startswith('$') else None
            if isinstance(base, list):
                for k, v in qb.todict(base).items():
                    if k == '_flags':
                        d['_flags'].extend(v)
                    else:
                        d.setdefault(k, v)
        out.append(d)
    return out


def node_exists(d, flags):
    fl = [x for x in d.get('_flags', []) if isinstance(x, str)]
    var = d.get('CreatedFromVariable')
    return '$CreatedAtStart' in fl or (isinstance(var, str) and flags.get(_key(var), 0) != 0)


def rail_nodes(nodes, flags):
    """[(index, pos, angles, name key, type key, terrain key, [link indices])] for rail nodes that
    exist at level start; links to absent nodes are dropped."""
    keep = {i for i, d in enumerate(nodes) if d.get('Class') == '$RailNode' and node_exists(d, flags) and 'Pos' in d}
    out = []
    for i in sorted(keep):
        d = nodes[i]
        links = [int(x) for x in (d.get('Links') or []) if isinstance(x, (int, float)) and int(x) in keep]
        key = lambda f: _key(d[f]) if isinstance(d.get(f), str) and d[f].startswith('$') else None
        out.append((i, d['Pos'], d.get('Angles', [0, 0, 0]), key('Name'), key('Type'), key('TerrainType'), links))
    return out


def read_nodes(qb_path, zone, flags):
    """Returns (pieces {checksum: (created, placement or None)}, restarts [(name, pos, angles)]).
    placement is (pos, angles) for LevelObjects, which are modelled at the origin."""
    pieces, restarts = {}, []
    read_nodes.variables = {}
    for d in expanded_nodes(qb_path, zone):
        cls = d.get('Class')
        fl = [x for x in d.get('_flags', []) if isinstance(x, str)]
        var = d.get('CreatedFromVariable')
        created = '$CreatedAtStart' in fl or (isinstance(var, str) and flags.get(_key(var), 0) != 0)
        if cls in ('$LevelGeometry', '$LevelObject') and isinstance(d.get('Name'), str):
            place = (d['Pos'], d.get('Angles', [0, 0, 0])) if cls == '$LevelObject' and 'Pos' in d else None
            pieces[_key(d['Name'])] = (created, place)
            if isinstance(var, str):
                read_nodes.variables[_key(d['Name'])] = var[1:]
        elif cls == '$Restart' and 'Pos' in d:
            restarts.append((d.get('RestartName', ''), d['Pos'], d.get('Angles', [0, 0, 0])))
    return pieces, restarts


def _key(name):
    """'$Name' or '$0x1234abcd' back to its checksum."""
    s = name[1:]
    return int(s, 16) if s.startswith('0x') else qbkey(s)


def load_zone(install, zone, flag_overrides=None, hidden_flags=()):
    """Pieces present at level start, with LevelObjects moved into place.
    flag_overrides {node flag name: value} replace the free-skate values; pieces created from a flag
    in hidden_flags are kept (for scripts to create later) and listed in load_zone.hidden.
    Returns (materials, meshes, textures, pieces, restarts)."""
    if not qb.NAMES:
        qb.load_names(os.path.join(os.path.dirname(__file__), '..', 'extracted', 'dbg'))
    pak_path = os.path.join(install, 'data', 'worlds', 'worldzones', zone, f'{zone}.pak.wpc')
    entries, blob = open_pak(pak_path)
    get = lambda e: blob[e['offset']:e['offset'] + e['size']]
    largest = lambda ext: max((e for e in entries if e['type'] == qbkey(ext)), key=lambda e: e['size'])
    materials, meshes = parse_geom(get(largest('.geom')))
    textures = parse_tex(get(largest('.tex')))
    qbe = next(e for e in entries if (e['name'] or '').lower().endswith(f'\\{zone}.qb.wpc'))
    tmp = os.path.join(os.environ.get('TEMP', '.'), f'{zone}_nodes.qb')
    open(tmp, 'wb').write(get(qbe))
    flags = node_flags(install)
    for name, v in (flag_overrides or {}).items():
        flags[qbkey(name)] = v
    pieces, restarts = read_nodes(tmp, zone, flags)
    load_zone.hidden = {k for k, var in read_nodes.variables.items() if var.lower() in {h.lower() for h in hidden_flags}}
    for k in load_zone.hidden:
        pieces[k] = (True, pieces[k][1])
    kept = []
    for m in meshes:
        p = pieces.get(m.sector)
        if p and not p[0]:
            continue
        if p and p[1]:
            pos, ang = p[1]
            r = euler_yxz(ang)
            m.pos = m.pos @ r.T + np.array(pos)
        kept.append(m)
    return materials, kept, textures, pieces, restarts


def load_rails(install, zone):
    """Rail nodes present at level start (see rail_nodes)."""
    if not qb.NAMES:
        qb.load_names(os.path.join(os.path.dirname(__file__), '..', 'extracted', 'dbg'))
    entries, blob = open_pak(os.path.join(install, 'data', 'worlds', 'worldzones', zone, f'{zone}.pak.wpc'))
    qbe = next(e for e in entries if (e['name'] or '').lower().endswith(f'\\{zone}.qb.wpc'))
    tmp = os.path.join(os.environ.get('TEMP', '.'), f'{zone}_nodes.qb')
    open(tmp, 'wb').write(blob[qbe['offset']:qbe['offset'] + qbe['size']])
    return rail_nodes(expanded_nodes(tmp, zone), node_flags(install))


def euler_yxz(a):
    """Rotation matrix for glam's Quat::from_euler(YXZ, a.y, a.x, a.z)."""
    x, y, z = a
    cy, sy, cx, sx, cz, sz = np.cos(y), np.sin(y), np.cos(x), np.sin(x), np.cos(z), np.sin(z)
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return ry @ rx @ rz


if __name__ == '__main__':
    if sys.argv[1] == 'stats':
        install, zone = sys.argv[2], sys.argv[3]
        qb.load_names('extracted/dbg')
        materials, meshes, textures, pieces, restarts = load_zone(install, zone)
        tris = sum(len(s) - 2 for m in meshes for s in m.strips)
        verts = sum(len(m.pos) for m in meshes)
        used = {struct.unpack_from('<I', materials[m.material], 0x40)[0] for m in meshes if m.material in materials}
        allp = np.concatenate([m.pos for m in meshes])
        print(f'meshes {len(meshes)} strip-tris {tris} verts {verts} materials {len(materials)} textures {len(textures)} used {len(used & set(textures))}')
        print('bbox', allp.min(0).round(), allp.max(0).round())
        print('pieces', len(pieces), 'created', sum(p[0] for p in pieces.values()))
        for r in restarts[:3]:
            print('restart', r)
        sizes = {}
        for c in used & set(textures):
            h, w = textures[c][0].shape[:2]
            sizes[(w, h)] = sizes.get((w, h), 0) + 1
        print('texture sizes', sorted(sizes.items(), key=lambda kv: -kv[1])[:12])


def read_col_objects(d, header=0x50):
    """Collision objects of a v10 file as dicts: checksum, verts (n, 3) world, faces
    [(flags, terrain, a, b, c)], tail (the last float of the record, copied as is)."""
    ver, nobj, tverts, tlf, tsf, tlv, tsv, _ = struct.unpack_from('<8i', d, 0)
    bv = (header + 0x40 * nobj + 15) & ~15
    bi = bv + tlv * 12 + tsv * 6
    bf = (bi + tverts + 3) & ~3
    out = []
    for i in range(nobj):
        o = header + i * 0x40
        cks, flags, nv, nf, small, fixed, ffo = struct.unpack_from('<IHHHBBI', d, o)
        bmin = struct.unpack_from('<3f', d, o + 0x10)
        fvo, bsp, into, tail = struct.unpack_from('<IIIf', d, o + 0x30)
        if fixed:
            v = np.array(struct.unpack_from(f'<{nv * 3}H', d, bv + fvo), np.float64).reshape(nv, 3) / 16 + bmin
        else:
            v = np.array(struct.unpack_from(f'<{nv * 3}f', d, bv + fvo), np.float64).reshape(nv, 3)
        faces = []
        for j in range(nf):
            p = bf + ffo + j * (8 if small else 10)
            if small:
                ff, tt, a, b, c = struct.unpack_from('<HH3B', d, p)
            else:
                ff, tt, a, b, c = struct.unpack_from('<HH3H', d, p)
            faces.append((ff, tt, a, b, c))
        out.append(dict(checksum=cks, flags=flags, verts=v, faces=faces, tail=tail))
    return out


def load_props(install, zone):
    """GameObjects present at level start whose type has a model under data/models/Props, placed at
    their node. Returns (meshes, materials, textures, collision objects); each prop's meshes and
    collision object carry the checksum of its node name."""
    import glob
    if not qb.NAMES:
        qb.load_names(os.path.join(os.path.dirname(__file__), '..', 'extracted', 'dbg'))
    entries, blob = open_pak(os.path.join(install, 'data', 'worlds', 'worldzones', zone, f'{zone}.pak.wpc'))
    qbe = next(e for e in entries if (e['name'] or '').lower().endswith(f'\\{zone}.qb.wpc'))
    tmp = os.path.join(os.environ.get('TEMP', '.'), f'{zone}_nodes.qb')
    open(tmp, 'wb').write(blob[qbe['offset']:qbe['offset'] + qbe['size']])
    nodes = expanded_nodes(tmp, zone)
    flags = node_flags(install)
    cache = {}
    meshes, materials, textures, cols = [], {}, {}, []
    for i, d in enumerate(nodes):
        if d.get('Class') != '$GameObject' or not node_exists(d, flags) or 'Pos' not in d:
            continue
        t = str(d.get('Type', ''))[1:]
        if t not in cache:
            folder = os.path.join(install, 'data', 'models', 'Props', t)
            files = {os.path.basename(p).lower(): p for p in glob.glob(os.path.join(folder, '*.wpc'))}
            mdl, tex, col = (files.get(f'{t.lower()}.{x}.wpc') for x in ('mdl', 'tex', 'col'))
            if not mdl:
                cache[t] = None
                continue
            mats, ms = parse_geom(open(mdl, 'rb').read())
            cache[t] = (mats, ms, parse_tex(open(tex, 'rb').read()) if tex else {},
                        read_col_objects(open(col, 'rb').read()) if col else [])
        if not cache[t]:
            continue
        mats, ms, texs, cobjs = cache[t]
        materials.update(mats)
        textures.update(texs)
        name = _key(d['Name']) if isinstance(d.get('Name'), str) else qbkey(f'{zone}_prop_{i}')
        r = euler_yxz(d.get('Angles', [0, 0, 0]))
        pos = np.array(d['Pos'], np.float64)
        for m in ms:
            c = Mesh()
            c.material, c.sector, c.radius, c.col, c.uv, c.strips = m.material, name, m.radius, m.col, m.uv, m.strips
            c.pos = m.pos @ r.T + pos
            c.center = tuple(np.array(m.center) @ r.T + pos)
            meshes.append(c)
        for k, o in enumerate(cobjs):
            cols.append(dict(o, checksum=name if k == 0 else qbkey(f'{zone}_prop_{i}_{k}'), verts=o['verts'] @ r.T + pos))
    return meshes, materials, textures, cols
