"""THAW .col (version 10) reader. Header is 0x50 bytes (THUG2 header + grid dims + world bbox)."""
import struct, sys

def read_col(data):
    ver, nobj, tverts, tlf, tsf, tlv, tsv, pad = struct.unpack_from('<8i', data, 0)
    extra = struct.unpack_from('<4i', data, 0x20)
    bbmin = struct.unpack_from('<4f', data, 0x30); bbmax = struct.unpack_from('<4f', data, 0x40)
    HDR, OBJ = 0x50, 0x40
    base_vert = (HDR + OBJ * nobj + 15) & ~15
    base_int = base_vert + tlv * 12 + tsv * 6
    base_face = (base_int + tverts + 3) & ~3
    objs = []
    for i in range(nobj):
        o = HDR + i * OBJ
        cks, flags, nv, nf, small, fixed, ffo = struct.unpack_from('<IHHHBBI', data, o)
        bmin = struct.unpack_from('<4f', data, o + 0x10); bmax = struct.unpack_from('<4f', data, o + 0x20)
        fvo, bsp, into, tail = struct.unpack_from('<IIIf', data, o + 0x30)
        verts = []
        p = base_vert + fvo
        for j in range(nv):
            if fixed:
                x, y, z = struct.unpack_from('<3H', data, p + j * 6)
                verts.append((bmin[0] + x * 0.0625, bmin[1] + y * 0.0625, bmin[2] + z * 0.0625))
            else:
                verts.append(struct.unpack_from('<3f', data, p + j * 12))
        faces = []
        p = base_face + ffo
        for j in range(nf):
            if small:
                ff, tt, a, b, c, _ = struct.unpack_from('<HH4B', data, p + j * 8)
            else:
                ff, tt, a, b, c = struct.unpack_from('<HH3H', data, p + j * 10)
            faces.append((ff, tt, a, b, c))
        objs.append(dict(checksum=cks, flags=flags, verts=verts, faces=faces, bmin=bmin, bmax=bmax, small=small, fixed=fixed))
    return dict(version=ver, objs=objs, bbmin=bbmin, bbmax=bbmax, extra=extra, counts=(tverts, tlf, tsf, tlv, tsv))

if __name__ == '__main__':
    c = read_col(open(sys.argv[1], 'rb').read())
    print('ver', c['version'], 'objs', len(c['objs']), 'counts', c['counts'], 'extra', c['extra'])
    print('bbox', c['bbmin'], c['bbmax'])
    bad = 0; nf = 0; flags = {}; terr = {}; oob = 0
    for o in c['objs']:
        for (ff, tt, a, b, cc) in o['faces']:
            nf += 1
            if max(a, b, cc) >= len(o['verts']): bad += 1
            for bit in range(16):
                if ff & (1 << bit): flags[bit] = flags.get(bit, 0) + 1
            terr[tt] = terr.get(tt, 0) + 1
        for v in o['verts']:
            if any(v[k] < o['bmin'][k] - 1 or v[k] > o['bmax'][k] + 1 for k in range(3)): oob += 1
    print('faces', nf, 'bad idx', bad, 'verts out of bbox', oob)
    print('flag bits', sorted(flags.items())); print('terrains', sorted(terr.items())[:40])
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w') as f:
            base = 1
            for o in c['objs']:
                for v in o['verts']: f.write('v %f %f %f\n' % v)
                for (ff, tt, a, b, cc) in o['faces']: f.write('f %d %d %d\n' % (base + a, base + b, base + cc))
                base += len(o['verts'])
