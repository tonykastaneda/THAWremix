"""THUG2 Remix (PSP) .psp_level reader.

  psplevel.py check <file.psp_level> [...]     validate the layout, print one line per file
  psplevel.py info <file.psp_level>            header, blocks, first material display list
  psplevel.py obj <file.psp_level> <out.obj>   export geometry in world inches (+Y up)

Layout (from the loader at 0005fcb0 and the strip interpreter at 00061690 in BOOT.BIN):

  0x40 header: 15 ints then '7777'
     0 version (0xB)          1 nObjs                2 texture bytes     3 nBoxes
     4 vertex bytes           5 nTexCmds (words)     6 nObjCmds (words)  7 nUVAnims
     8 nObjVerts              9 nPrims (shorts)      10-12 offset x,y,z
     13 first translucent prim short                 14 first translucent vertex byte
  nObjs * 0x40      level objects (matrix, display list index, vertex index, box index)
  texture bytes     32-bit palettes and swizzled 8-bit pixels, addressed by the display lists
  nBoxes * 16       half floats: min xyz, 0, max xyz, 0 in vertex space / 32768 (visibility boxes,
                    view-tested by the VFPU routine at 0006154c; every strip names the box holding it)
  vertex bytes      12 bytes each: u16 u, v; u16 colour 4444; s16 x, y, z
  1 word            GE RET, so "list -1" is a no-op
  nTexCmds words    GE display lists, one per material, each ending in RET
  nObjCmds words    GE display lists for level objects
  nUVAnims * 44     texture scroll animations patching TOFFSET in a material list
  nObjVerts * 12    level object vertices
  nObjs words, nBoxes words (box name checksums), nBoxes bytes padded to 4 (box flags)
  nPrims shorts     count << 11 | (box + 2): one triangle strip taking the next `count` vertices.
                    0 then N: N > 0 calls the material list at word N, otherwise the pass ends.

Vertex to world: world = (v + offset) / 4 with GE axes (x, -z, y). UVs are (raw / 32768) * TSCALE
+ TOFFSET from the material list (8 and -8 in shipped levels).
"""
import struct
import sys


class Level:
    def __init__(self, path):
        d = self.data = open(path, 'rb').read()
        h = self.h = struct.unpack_from('<15i', d, 0)
        assert h[0] == 0xB and d[0x3C:0x40] == b'7777', 'not a v11 psp_level'
        (_, self.n_objs, self.tex_bytes, self.n_boxes, self.vert_bytes, self.n_texcmds, self.n_objcmds,
         self.n_uvanims, self.n_objverts, self.n_prims, ox, oy, oz, self.trans_prim, self.trans_vert) = h
        self.offset = (ox, oy, oz)
        p = 0x40
        self.objs = p; p += self.n_objs * 0x40
        self.tex = p; p += self.tex_bytes
        self.boxes = p; p += self.n_boxes * 16
        self.verts = p; p += self.vert_bytes + 4
        self.texcmds = p; p += self.n_texcmds * 4
        self.objcmds = p; p += self.n_objcmds * 4
        self.uvanims = p; p += self.n_uvanims * 44
        self.objverts = p; p += self.n_objverts * 12
        self.objwords = p; p += self.n_objs * 4
        self.boxnames = p; p += self.n_boxes * 4
        self.boxflags = p; p += (self.n_boxes + 3) & ~3
        self.prims = p; p += self.n_prims * 2
        self.end = p

    def passes(self):
        """Yields (first prim short, first vertex index) for the opaque and translucent passes."""
        yield 0, 0
        if self.trans_prim or self.trans_vert:
            yield self.trans_prim, self.trans_vert

    def strips(self, prim, vert):
        """Yields (material list word, box, vertex byte offset, count, stride) for one pass.

        `vert` is a byte offset into the vertex block. Stride 12 is the compact format; 0 then -1
        toggles to 20-byte vertices (u16 u, v; u32 colour 8888; float x, y, z in units of 32768).
        """
        d, mat, stride = self.data, 0, 12
        while prim < self.n_prims:
            s = struct.unpack_from('<H', d, self.prims + prim * 2)[0]
            prim += 1
            idx, count = s & 0x7FF, s >> 11
            if idx >= 2:
                yield mat, idx - 2, vert, count, stride
                vert += count * stride
            elif idx == 0 and count == 0:
                n = struct.unpack_from('<h', d, self.prims + prim * 2)[0]
                prim += 1
                if n == 0:
                    return
                if n == -1:
                    stride ^= 0x18
                elif n < 0:
                    raise ValueError(f'control {n} at short {prim - 1}')
                else:
                    mat = n
            else:
                raise ValueError(f'special prim {s:#x} at short {prim - 1}')

    def vertex(self, off, stride=12):
        if stride == 12:
            u, v, c, x, y, z = struct.unpack_from('<HHHhhh', self.data, self.verts + off)
        else:
            u, v, c, x, y, z = struct.unpack_from('<HHIfff', self.data, self.verts + off)
            x, y, z = x * 32768, y * 32768, z * 32768
        ox, oy, oz = self.offset
        return ((x + ox) / 4, (z + oz) / 4, -(y + oy) / 4), (u / 4096 - 8, v / 4096 - 8), c


def check(path):
    lv = Level(path)
    ok = lv.end == len(lv.data)
    nv = lv.vert_bytes
    used, strips, mats, maxbox, wide, ends = 0, 0, set(), -1, 0, []
    try:
        for p, v in lv.passes():
            end = v
            for mat, box, first, count, stride in lv.strips(p, v):
                end = first + count * stride
                strips += 1
                wide += stride == 20
                mats.add(mat)
                maxbox = max(maxbox, box)
            ends.append(end)
        used = ends[-1]
        if len(ends) == 2 and ends[0] != lv.trans_vert:
            raise ValueError(f'opaque pass ends at {ends[0]:#x}, translucent starts {lv.trans_vert:#x}')
        note = f'wide strips {wide}' if wide else ''
    except ValueError as e:
        note = str(e)
    ok = ok and used == nv and maxbox < lv.n_boxes and not note.startswith(('special', 'control', 'opaque'))
    print(f'{"ok " if ok else "BAD"} {path.split(chr(92))[-1]:28s} vbytes {nv:7d} used {used:7d} strips {strips:5d} '
          f'mats {len(mats):4d} boxes {lv.n_boxes:5d} objs {lv.n_objs:3d} tex {lv.tex_bytes:8d} {note}')
    return ok


def info(path):
    lv = Level(path)
    print('header', ' '.join(f'{x:#x}' for x in lv.h))
    for k in ('objs', 'tex', 'boxes', 'verts', 'texcmds', 'objcmds', 'uvanims', 'objverts', 'boxnames',
              'boxflags', 'prims', 'end'):
        print(f'  {k:9s} {getattr(lv, k):#9x}')
    print('file size', hex(len(lv.data)))
    d, p = lv.data, lv.texcmds
    print('first material list:')
    for i in range(min(lv.n_texcmds, 40)):
        w = struct.unpack_from('<I', d, p + i * 4)[0]
        print(f'  {i:3d} {w >> 24:02x} {w & 0xFFFFFF:06x}')
        if w >> 24 == 0x0B:
            break
    flags = d[lv.boxflags:lv.boxflags + lv.n_boxes]
    print('box flag values', sorted(set(flags)))


def obj(path, out):
    lv = Level(path)
    with open(out, 'w') as f:
        cur, tris, n = None, 0, 0
        for p, v0 in lv.passes():
            for mat, box, first, count, stride in lv.strips(p, v0):
                if mat != cur:
                    f.write(f'g mat{mat}\n')
                    cur = mat
                for k in range(count):
                    (x, y, z), (u, v), _ = lv.vertex(first + k * stride, stride)
                    f.write(f'v {x:.2f} {y:.2f} {z:.2f}\nvt {u:.4f} {1 - v:.4f}\n')
                base, n = n, n + count
                for k in range(count - 2):
                    a, b, c = base + k + 1, base + k + 2, base + k + 3
                    if k & 1:
                        a, b = b, a
                    f.write(f'f {a}/{a} {b}/{b} {c}/{c}\n')
                    tris += 1
    print(tris, 'triangles')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'check':
        bad = sum(not check(f) for f in sys.argv[2:])
        print(f'{len(sys.argv) - 2 - bad} ok, {bad} bad')
    elif cmd == 'info':
        info(sys.argv[2])
    elif cmd == 'obj':
        obj(sys.argv[2], sys.argv[3])
