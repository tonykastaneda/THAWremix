"""Project 8 PSP skinned model (.skin.psp) reader.

  p8skin.py info <file.skin.psp>

Layout (from P8's own files; magic 0xC0EDBABE):
  0x40 header, 16 words: [0] magic, [2] 0x60 (first record), [3] float (bounding radius?),
     [5] texture block offset, [6] its size, [8] vertex data offset, [11] display list offset,
     [12] its size, [14] ? (count)
  0x40 file name (NUL padded to 0x60)
  16-byte records until a zero record: byte 0 type, u16 at 1 = display list offset (bytes);
     type 1 material   (+4 material checksum, +12 colour 0x808080)
     type 4 hook       (+4 a checksum; the list there is BASE 0 / RET, patched at run time)
     type 2 mesh draw  (+8 offset of its vertices from header[8])
  texture block: CLUT and pixels; material lists address them relative to the block (TBP0, CBP)
  display list: per material a state block (CBP, TBP0..3, TBW, TSIZE, TMODE, blend ...); per mesh:
     VTYPE, BONE NUM 0 (0x2a000000), one CALL 0xc00 + 0x40 * bone per weight slot (the run-time bone
     matrix lists), PRIM 3 (triangles) / PRIM 4 (strips) with FFACE (0x9b) between, 0xff000000, RET
  vertices: GE through-skinning format of the mesh's VTYPE (e.g. 0xc33a: 4 u8 weights summing to
     0xf8, s16 UV, 4444 colour, s8 normal, s16 position; 0x033a: 1 weight)
"""
import struct
import sys

GE_FIELD = {'tc': (0, 3), 'col': (2, 7), 'nrm': (5, 3), 'pos': (7, 3), 'wt': (9, 3), 'idx': (11, 3)}
SIZES = {'tc': [0, 1, 2, 4], 'nrm': [0, 1, 2, 4], 'pos': [0, 1, 2, 4], 'wt': [0, 1, 2, 4]}
COL = [0, 0, 0, 0, 2, 2, 2, 4]


def vtype_layout(vt):
    """{field: (offset, element size, count)} and the vertex size, in the GE's order and alignment."""
    f = {k: (vt >> s) & m for k, (s, m) in GE_FIELD.items()}
    nw = ((vt >> 14) & 7) + 1 if f['wt'] else 0
    out, o, align = {}, 0, 1
    for name, n in (('wt', nw), ('tc', 2), ('col', 1), ('nrm', 3), ('pos', 3)):
        size = COL[f['col']] if name == 'col' else SIZES[name][f[name]]
        if not size or (name == 'wt' and not nw):
            continue
        o = (o + size - 1) // size * size
        out[name] = (o, size, n)
        o += size * n
        align = max(align, size)
    return out, (o + align - 1) // align * align


class Skin:
    def __init__(self, d):
        self.d = d
        h = struct.unpack_from('<16I', d, 0)
        assert h[0] == 0xC0EDBABE, 'not a P8 skin'
        self.h = h
        self.radius = struct.unpack_from('<f', d, 12)[0]
        self.name = d[0x40:0x60].split(b'\0')[0].decode('latin-1')
        self.tex, self.tex_size, self.verts, self.dl, self.dl_size = h[5], h[6], h[8], h[11], h[12]
        self.records = []
        o = h[2]
        while d[o:o + 16] != bytes(16):
            t, off = d[o], struct.unpack_from('<H', d, o + 1)[0]
            self.records.append((t, off, struct.unpack_from('<3I', d, o + 4)))
            o += 16
        self.meshes = [self.mesh(off, w[1]) for t, off, w in self.records if t == 2]

    def mesh(self, off, voff):
        """{vtype, bones, prims [(kind, count)], vertices [(field values)]} of one draw."""
        d, p = self.d, self.dl + off
        vt, bones, prims = None, [], []
        while True:
            w = struct.unpack_from('<I', d, p)[0]
            c, a = w >> 24, w & 0xFFFFFF
            if c == 0x12:
                vt = a
            elif c == 0x0A:
                bones.append(a // 0x40)
            elif c == 0x04:
                prims.append((a >> 16 & 7, a & 0xFFFF))
            elif (c == 0x0B or w == 0xFF000000) and prims:  # 0xff000000 ends a mesh's draws
                break
            p += 4
        lay, size = vtype_layout(vt)
        n = sum(k for _, k in prims)
        base = self.verts + voff
        fmt = {1: 'b', 2: 'h', 4: 'f'}
        verts = []
        for i in range(n):
            v = base + i * size
            rec = {}
            for name, (o, s, k) in lay.items():
                if name == 'col':
                    rec[name] = struct.unpack_from('<H' if s == 2 else '<I', d, v + o)[0]
                elif name == 'wt':
                    rec[name] = struct.unpack_from(f'<{k}B', d, v + o)
                elif name == 'tc':
                    rec[name] = struct.unpack_from(f'<{k}{"H" if s == 2 else fmt[s]}', d, v + o)
                else:
                    rec[name] = struct.unpack_from(f'<{k}{fmt[s]}', d, v + o)
            verts.append(rec)
        return dict(vtype=vt, bones=bones, prims=prims, size=size, verts=verts, voff=voff)


if __name__ == '__main__' and sys.argv[1] == 'info':
    s = Skin(open(sys.argv[2], 'rb').read())
    print(s.name, 'radius', round(s.radius, 2), 'records', len(s.records), 'meshes', len(s.meshes),
          'tex', hex(s.tex), s.tex_size, 'dl', hex(s.dl), s.dl_size, 'verts', hex(s.verts), 'h14', s.h[14])
    for m in s.meshes:
        pos = [v['pos'] for v in m['verts']]
        lo = [min(p[i] for p in pos) for i in range(3)]
        hi = [max(p[i] for p in pos) for i in range(3)]
        print(f"  vtype {m['vtype']:06x} size {m['size']} bones {m['bones']} verts {len(m['verts'])} "
              f"prims {len(m['prims'])} pos {lo}..{hi}")
