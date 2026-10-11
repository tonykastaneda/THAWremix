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


def fmt(t, pl):
    if t == 0x16:
        return qb.nm(struct.unpack_from('<I', pl)[0])
    if t == 0x17:
        return str(struct.unpack_from('<i', pl)[0])
    if t == 0x1A:
        return '%g' % struct.unpack_from('<f', pl)[0]
    if t == 0x1F:
        return '(%g, %g)' % struct.unpack_from('<2f', pl)
    if t == 0x1E:
        return '(%g, %g, %g)' % struct.unpack_from('<3f', pl)
    if t in (0x1B, 0x1C):
        return repr(pl[4:-1].decode('latin-1'))
    return OPS.get(t, '#%02x' % t)


def text(code):
    out = []
    for p, t, pl in qb2.tokens(code):
        out.append(fmt(t, pl))
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
