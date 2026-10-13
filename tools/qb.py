"""THAW PC .qb reader (data items; scripts returned as byte ranges).

Top-level item:  00 flags type 00 | id | filekey | value/ptr | next(0)   -- items are laid out sequentially
Struct:          00 00 01 00 | ptr first item
Struct item:     00 (type<<1|1) 00 00 | id | value/ptr | next
Array:           00 01 elemtype 00 | count | ptr (or inline value when count==1)
Float blocks (pair/vector): 00 01 00 00 | floats
Script body:     u32 crc | u32 uncompressed size | u32 stored size | bytes (LZSS if stored < uncompressed)
Types: 1 int, 2 float, 3 string, 4 wstring, 5 pair, 6 vector, 7 script, 10 struct, 12 array, 13 qbkey
"""
import glob
import os
import struct
import sys

NAMES = {}


def load_names(dbg_root):
    for p in glob.glob(os.path.join(dbg_root, '**', '*.dbg'), recursive=True):
        with open(p, 'r', errors='replace') as f:
            on = False
            for line in f:
                line = line.strip()
                if line.startswith('['):
                    on = line == '[Checksums]'
                    continue
                if on and line.startswith('0x'):
                    k, _, v = line.partition(' ')
                    NAMES[int(k, 16)] = v


def script_end(d, o):
    """End of a script stored as plain tokens (a struct field's script in P8 PSP files, placed right
    after the field): through its endscript and the newline after it."""
    import qb2
    seen = False
    for p, t, pl in qb2.tokens(d, o):
        if seen:
            return p + 1 + len(pl) if t in (0x01, 0x02) else p
        seen = t == 0x24
    return len(d)


def nm(k):
    return NAMES.get(k, '0x%08x' % k)


class QB:
    def __init__(self, data):
        self.d = data
        self.hi = 0

    def touch(self, o):
        if o > self.hi:
            self.hi = o

    def u32(self, o):
        return struct.unpack_from('<I', self.d, o)[0]

    def cstr(self, o):
        e = self.d.index(b'\0', o)
        self.touch(e + 1)
        return self.d[o:e].decode('latin-1')

    def wstr(self, o):
        e = o
        while self.d[e:e + 2] != b'\0\0':
            e += 2
        self.touch(e + 2)
        return self.d[o:e].decode('utf-16-le', 'replace')

    def floats(self, o, n):
        self.touch(o + 4 + 4 * n)
        return list(struct.unpack_from('<%df' % n, self.d, o + 4))

    def value(self, t, v):
        if t == 0:
            return None
        if t == 1:
            return struct.unpack('<i', struct.pack('<I', v))[0]
        if t == 2:
            return struct.unpack('<f', struct.pack('<I', v))[0]
        if t == 3:
            return self.cstr(v)
        if t == 4:  # "local string": plain single-byte text in this build
            return self.cstr(v)
        if t == 5:
            return self.floats(v, 2)
        if t == 6:
            return self.floats(v, 3)
        if t == 10:
            return self.struct(v)
        if t == 12:
            return self.array(v)
        if t == 13:
            return '$' + nm(v)
        if t == 7 and v + 5 <= len(self.d) and self.d[v] in (0x01, 0x02):
            self.touch(script_end(self.d, v))
        return ('?%d' % t, v)

    def struct(self, o):
        out = []
        self.touch(o + 8)
        p = self.u32(o + 4)
        while p:
            self.touch(p + 16)
            t = self.d[p + 1] >> 1
            idk, v, nxt = struct.unpack_from('<3I', self.d, p + 4)
            out.append((nm(idk) if idk else None, self.value(t, v)))
            p = nxt
        return out

    def array(self, o):
        et = self.d[o + 2]
        n = self.u32(o + 4)
        self.touch(o + 12)  # an empty array still has its (null) pointer word
        if n == 0:
            return []
        base = o + 8 if n == 1 else self.u32(o + 8)
        self.touch(base + 4 * n)
        return [self.value(et, self.u32(base + 4 * i)) for i in range(n)]

    def items(self):
        p = 0x1C
        out = []
        size = self.u32(4)
        while p + 0x14 <= size:
            t = self.d[p + 2]
            idk, fk, v, nxt = struct.unpack_from('<4I', self.d, p + 4)
            self.hi = p + 0x14
            if t == 7:
                usz, csz = struct.unpack_from('<2I', self.d, v + 4)
                self.touch(v + 12 + csz)
                out.append((nm(idk), ('script', v + 12, usz, csz)))
            else:
                try:
                    out.append((nm(idk), self.value(t, v)))
                except Exception as ex:  # keep going, report where
                    out.append((nm(idk), ('ERR at 0x%x type %d: %s' % (p, t, ex),)))
            p = (self.hi + 3) & ~3
        return out


def todict(st):
    """struct (list of pairs) -> dict; unnamed entries collect under '_flags'."""
    d = {}
    for k, v in st:
        if k is None:
            d.setdefault('_flags', []).append(v)
        else:
            d[k] = v
    return d


if __name__ == '__main__':
    load_names('extracted/dbg')
    q = QB(open(sys.argv[1], 'rb').read())
    for k, v in q.items():
        s = repr(v)
        print(k, '=', s if len(s) < 400 or len(sys.argv) > 2 else s[:400] + '...')
