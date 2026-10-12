"""In-place edits to Project 8 PSP's script pack (pak\\qb.pak.psp + qb.pab.psp).

  p8qb.py setkey <qb.pak.psp> <qb.pab.psp> <file> <script> <old> <new>
  p8qb.py setfield <qb.pak.psp> <qb.pab.psp> <file> <struct> <field> <int or key>
  p8qb.py setdata <qb.pak.psp> <qb.pab.psp> <file> <old>=<new> [int:<old>=<new>] [str:<Old>=<New> ...]

setkey changes one checksum inside one script of a script file (<file> matches the end of its
name in the pack, e.g. game\\levels.qb.psp; keys are names or 0x hex). Script bodies are often
LZSS-packed; the old key must sit there as literal bytes, and the result is unpacked again to
check that exactly old -> new changed. The .pab is rewritten in place (same size), so patching it
into the archive is a plain hed.py replace.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pak  # noqa: E402
import qb  # noqa: E402
from thawscene import lzss  # noqa: E402


def key(s):
    return int(s, 16) if s.lower().startswith('0x') else pak.qbkey(s)


def body(d, off, usz, csz):
    return lzss(d[off:off + csz], usz) if csz < usz else d[off:off + csz]


def setkey(pakp, pabp, fname, script, old, new):
    p, b = open(pakp, 'rb').read(), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(p)
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = bytearray(b[start:start + e['size']])
    sk = key(script)
    v = next(v for k, v in qb.QB(bytes(d)).items() if pak.qbkey(str(k)) == sk or str(k) == '0x%08x' % sk)
    _, off, usz, csz = v
    before = body(bytes(d), off, usz, csz)
    o, n = struct.pack('<I', key(old)), struct.pack('<I', key(new))
    hits = [i for i in range(off, off + csz - 3) if d[i:i + 4] == o]
    if not hits:
        raise SystemExit('old key not found as literal bytes in the script')
    for i in hits:
        d[i:i + 4] = n
    after = body(bytes(d), off, usz, csz)
    if after != before.replace(o, n):
        raise SystemExit('unpacked result differs from a plain key swap; not written')
    b[start:start + e['size']] = d
    open(pabp, 'wb').write(b)
    print(f'{e["name"]} {script}: {old} -> {new} ({len(hits)} place(s))')


def setdata(pakp, pabp, fname, *pairs):
    """Data (not script) edits in one script file: each pair is old=new, a key swap (0x hex or name,
    every occurrence), "int:Old=New" an integer value (every occurrence, so pick a distinctive one)
    or "str:Old=New" an inline string swapped in place (the new one shorter, NUL padded)."""
    p, b = open(pakp, 'rb').read(), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(p)
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = bytearray(b[start:start + e['size']])
    for pair in pairs:
        old, new = pair.split('=', 1)
        if old.startswith('int:'):
            o, n = struct.pack('<i', int(old[4:])), struct.pack('<i', int(new))
        elif old.startswith('str:'):
            o, n = (old[4:] + '\0').encode(), new.encode()
            if len(n) >= len(o):
                raise SystemExit(f'{new!r} is not shorter than {old[4:]!r}')
            n = n.ljust(len(o), b'\0')
        else:
            o, n = struct.pack('<I', key(old)), struct.pack('<I', key(new))
        count = d.count(o)
        if not count:
            raise SystemExit(f'{old} not in {e["name"]}')
        d = d.replace(o, n)
        print(f'{e["name"]}: {old} -> {new} ({count})')
    b[start:start + e['size']] = d
    open(pabp, 'wb').write(b)


def setfield(pakp, pabp, fname, struct_name, field, value):
    """One field of one top-level struct, rewritten in place: an integer value, or a key (0x hex or a
    name) for a checksum-valued field. A struct is [?][first field]; a field is [type word][name]
    [value][next], linked in file order."""
    sys.path.insert(0, os.path.dirname(__file__))
    from p8zone import top_items
    p, b = open(pakp, 'rb').read(), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(p)
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = bytearray(b[start:start + e['size']])
    u = lambda o: struct.unpack_from('<I', d, o)[0]  # noqa: E731
    t, s = top_items(bytes(d))[key(struct_name)]
    f, fk = u(s + 4), key(field)
    while f and u(f + 4) != fk:
        f = u(f + 12)
    if not f:
        raise SystemExit(f'{field} not in {struct_name}')
    old = u(f + 8)
    new = int(value) if value.lstrip('-').isdigit() else key(value)
    struct.pack_into('<I', d, f + 8, new & 0xFFFFFFFF)
    b[start:start + e['size']] = d
    open(pabp, 'wb').write(b)
    print(f'{e["name"]} {struct_name}.{field}: {old:#x} -> {new & 0xFFFFFFFF:#x}')


def main():
    if sys.argv[1] == 'setfield':
        setfield(*sys.argv[2:8])
    elif sys.argv[1] == 'setkey':
        setkey(*sys.argv[2:8])
    elif sys.argv[1] == 'setdata':
        setdata(*sys.argv[2:])


if __name__ == '__main__':
    main()
