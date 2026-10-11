"""Print THAW (PC) qb scripts as text: thawqbdump.py <file.qb.wpc> [script name substring ...]"""
import struct
import sys

sys.path.insert(0, __import__('os').path.dirname(__file__))
import qb  # noqa: E402
import qb2  # noqa: E402
import thawscene  # noqa: E402

OPS = {0x01: '\n', 0x03: '{', 0x04: '}', 0x05: '[', 0x06: ']', 0x07: '=', 0x08: '.', 0x09: ',', 0x0A: '-',
       0x0B: '+', 0x0C: '/', 0x0D: '*', 0x0E: '(', 0x0F: ')', 0x12: '<', 0x13: '<=', 0x14: '>', 0x15: '>=',
       0x23: 'script', 0x24: 'endscript', 0x2C: '<...>', 0x2D: '<>', 0x32: 'or', 0x33: 'and', 0x39: 'not',
       0x42: ':', 0x47: 'if', 0x48: 'else', 0x49: 'break', 0x28: 'endif', 0x25: 'if', 0x26: 'else', 0x20: 'while',
       0x21: 'repeat', 0x22: 'break', 0x3C: 'switch', 0x3D: 'endswitch', 0x3E: 'case', 0x3F: 'default',
       0x29: 'return'}


def qstr(s, q):
    s = s.replace('\\', '\\\\').replace(q, '\\' + q)
    return q + ''.join(c if 32 <= ord(c) < 127 else '\\x%02x' % ord(c) for c in s) + q


def inline_struct(pl):
    """THAW's 0x4A token: a binary struct (the .qb.wpc item layout, offsets from its own start)
    printed as { ... } source. Item types: 1 int, 2 float, 3 string, 4 local string, 5 pair,
    6 vector, 10 struct, 12 array, 13 name."""
    u32 = lambda o: struct.unpack_from('<I', pl, o)[0]  # noqa: E731

    def cstr(o):
        return pl[o:pl.index(b'\0', o)].decode('latin-1')

    def value(t, v):
        if t == 1:
            return str(struct.unpack('<i', struct.pack('<I', v))[0])
        if t == 2:
            s = '%g' % struct.unpack('<f', struct.pack('<I', v))[0]
            return s if any(c in s for c in '.en') else s + '.0'
        if t in (3, 4):
            return qstr(cstr(v), '"' if t == 3 else "'")
        if t in (5, 6):
            f = struct.unpack_from('<%df' % (t - 3), pl, v + 4)
            return '(' + ', '.join('%g' % x for x in f) + ')'
        if t == 10:
            return struct_at(v)
        if t == 12:
            et, n = pl[v + 2], u32(v + 4)
            if n == 0:
                return '[ ]'
            base = v + 8 if n == 1 else u32(v + 8)
            return '[ ' + ' '.join(value(et, u32(base + 4 * i)) for i in range(n)) + ' ]'
        if t == 13:
            return qb.nm(v)
        return '#?%d' % t

    def struct_at(o):
        out, p = [], u32(o + 4)
        while p:
            t = pl[p + 1] >> 1
            idk, v, nxt = struct.unpack_from('<3I', pl, p + 4)
            out.append(value(t, v) if not idk else f'{qb.nm(idk)} = {value(t, v)}')
            p = nxt
        return '{ ' + ' '.join(out) + ' }'
    return struct_at(0)


def fmt(t, pl):
    if t == 0x4A:
        return inline_struct(pl)
    if t == 0x16:
        return qb.nm(struct.unpack_from('<I', pl)[0])
    if t == 0x17:
        return str(struct.unpack_from('<i', pl)[0])
    if t == 0x1A:
        s = '%g' % struct.unpack_from('<f', pl)[0]
        return s if any(c in s for c in '.en') else s + '.0'  # a float stays a float
    if t == 0x1F:
        return '(%g, %g)' % struct.unpack_from('<2f', pl)
    if t == 0x1E:
        return '(%g, %g, %g)' % struct.unpack_from('<3f', pl)
    if t in (0x1B, 0x1C):
        # "string" (0x1B) and 'local string' (0x1C), escaped the way tools/qbc.py reads them
        return qstr(pl[4:-1].decode('latin-1'), '"' if t == 0x1B else "'")
    return OPS.get(t, '#%02x' % t)


def text(code):
    out = []
    prev = None
    for p, t, pl in qb2.tokens(code):
        if not (t == 0x49 and prev in (0x3E, 0x3F)):  # case/default's own jump is implied
            out.append(fmt(t, pl))
        prev = t
    return ' '.join(out).replace(' \n ', '\n')


def main():
    qb.load_names('extracted/dbg')
    d = open(sys.argv[1], 'rb').read()
    want = sys.argv[2:]
    for name, v in qb.QB(d).items():
        if isinstance(v, tuple) and v[0] == 'script' and (not want or any(w.lower() in name.lower() for w in want)):
            off, usz, csz = v[1], v[2], v[3]
            code = thawscene.lzss(d[off:off + csz], usz) if csz < usz else d[off:off + csz]
            print(f'=== {name}\n{text(code)}\n')


if __name__ == '__main__':
    main()
