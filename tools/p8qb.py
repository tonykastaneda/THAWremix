"""In-place edits to Project 8 PSP's script pack (pak\\qb.pak.psp + qb.pab.psp).

  p8qb.py setkey <qb.pak.psp> <qb.pab.psp> <file> <script> <old> <new>
  p8qb.py setfield <qb.pak.psp> <qb.pab.psp> <file> <struct> <field> <int, key, or name:<new field name>>
  p8qb.py swapscript <qb.pak.psp> <qb.pab.psp> <file> <script> <donor .qb>   (also rewrites the .pak)
  p8qb.py extract <qb.pak.psp> <qb.pab.psp> <file> <out .qb>
  p8qb.py rekey <qb.pak.psp> <qb.pab.psp> <file> <script> <old> <new>   (packed or not; stored unpacked)
  p8qb.py setglobal <qb.pak.psp> <qb.pab.psp> <file> <name> <int or key>
  p8qb.py copyfield <qb.pak.psp> <qb.pab.psp> <file> <dst struct> <dst field> <src struct> <src field>
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


POINTER_TYPES = {3, 4, 5, 6, 7, 10, 12}  # string, local string, vec2, vec3, script, struct, array


def pointer_sites(d):
    """Offsets of every word in a QB file that holds a file offset: item values, struct first-field
    and field value / next links, array bases and pointer elements. Items follow each other from
    0x1C ([?][?][type][?][name][file key][value][next = 0], 0x14 bytes, data after); a script value
    points at [?][unpacked size][packed size][code]."""
    u = lambda o: struct.unpack_from('<I', d, o)[0]  # noqa: E731
    sites, seen = [], set()

    def val(t, at):
        if t in POINTER_TYPES:
            sites.append(at)
            o = u(at)
            if t == 10:
                walk_struct(o)
            elif t == 12:
                walk_array(o)

    def walk_struct(o):
        if o in seen:
            return
        seen.add(o)
        sites.append(o + 4)
        p = u(o + 4)
        while p:
            val(d[p + 1] >> 1, p + 8)
            sites.append(p + 12)
            p = u(p + 12)

    def walk_array(o):
        if o in seen:
            return
        seen.add(o)
        et, n = d[o + 2], u(o + 4)
        if n == 0:
            return
        if n == 1:
            val(et, o + 8)
        else:
            sites.append(o + 8)
            base = u(o + 8)
            for i in range(n):
                val(et, base + 4 * i)

    q = qb.QB(d)
    p, items = 0x1C, []
    while p + 0x14 <= u(4):
        t = d[p + 2]
        q.hi = p + 0x14
        v = u(p + 12)
        if t == 7:
            q.touch(v + 12 + u(v + 8))
        else:
            q.value(t, v)
        items.append((p, t, u(p + 4), v))
        val(t, p + 12)
        p = (q.hi + 3) & ~3
    return sorted(set(sites)), items


def resize(d, at, old_len, new):
    """d with the bytes at..at+old_len replaced by new (padded to 4), every later offset moved."""
    d = bytearray(d)
    sites, _ = pointer_sites(bytes(d))
    new = new + bytes(-len(new) % 4)
    delta, end = len(new) - old_len, at + old_len
    for s in sites:
        x = struct.unpack_from('<I', d, s)[0]
        if x >= end:
            struct.pack_into('<I', d, s, x + delta)
    out = d[:at] + new + d[end:]
    struct.pack_into('<I', out, 4, len(out))
    return bytes(out)


def swap_script(d, script_key, block):
    """d with one script's [?][usz][csz][code] block replaced by block (from another build of the
    file), every later offset moved by the size change."""
    _, items = pointer_sites(bytes(d))
    p, t, k, v = next(i for i in items if i[2] == script_key and i[1] == 7)
    return resize(d, v, (12 + struct.unpack_from('<I', d, v + 8)[0] + 3) & ~3, block)


def script_block(d, script_key):
    _, items = pointer_sites(d)
    p, t, k, v = next(i for i in items if i[2] == script_key and i[1] == 7)
    return d[v:v + 12 + struct.unpack_from('<I', d, v + 8)[0]]


def swapscript(pakp, pabp, fname, script, donor):
    """Replaces one script of a pack file with the same-named script from donor (a loose .qb file),
    checks every other item still reads the same, and moves the file to the end of the .pab (its
    pack entry repointed; nothing else moves)."""
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(bytes(p))
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = bytes(b[start:start + e['size']])
    sk = key(script)
    new = swap_script(d, sk, script_block(open(donor, 'rb').read(), sk))
    a = [x for x in qb.QB(d).items() if pak.qbkey(str(x[0])) != sk and str(x[0]) != '0x%08x' % sk]
    c = [x for x in qb.QB(new).items() if pak.qbkey(str(x[0])) != sk and str(x[0]) != '0x%08x' % sk]
    norm = lambda items: [(k, (v[0], v[2], v[3]) if isinstance(v, tuple) and v and v[0] == 'script' else v) for k, v in items]  # noqa: E731
    if norm(a) != norm(c):
        raise SystemExit('other items changed; not written')
    b += bytes(-len(b) % 16)
    pos = len(p) + len(b)
    b += new
    struct.pack_into('<II', p, e['entry_pos'] + 4, pos - e['entry_pos'], len(new))
    open(pakp, 'wb').write(p)
    open(pabp, 'wb').write(b)
    print(f'{e["name"]} {script}: {len(d)} -> {len(new)} bytes, moved to the end of the pab')


def setfield(pakp, pabp, fname, struct_name, field, value):
    """One field of one top-level struct, rewritten in place: an integer value, a key (0x hex or a
    name) for a checksum-valued field, or str:<text> for a string field. A struct is [?][first
    field]; a field is [type word][name][value][next], linked in file order."""
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
    if value.startswith('str:'):  # a string field's text, rewritten in place (it must fit the old one's room)
        at, text = u(f + 8), value[4:].encode('latin-1') + bytes(1)
        room = (d.index(0, at) - at + 4) & ~3
        if d[f + 1] >> 1 != 3 or len(text) > room:
            raise SystemExit(f'{field}: not a string, or {value[4:]!r} does not fit {room} bytes')
        d[at:at + room] = text + bytes(room - len(text))
        b[start:start + e['size']] = d
        open(pabp, 'wb').write(b)
        return print(f'{e["name"]} {struct_name}.{field} = {value[4:]!r}')
    if value.startswith('name:'):  # rename the field instead (e.g. to hide it from GotParam)
        at, new = f + 4, key(value[5:])
    else:
        at, new = f + 8, int(value) if value.lstrip('-').isdigit() else key(value)
    old = u(at)
    struct.pack_into('<I', d, at, new & 0xFFFFFFFF)
    b[start:start + e['size']] = d
    open(pabp, 'wb').write(b)
    print(f'{e["name"]} {struct_name}.{field}: {old:#x} -> {new & 0xFFFFFFFF:#x}')


def copyfield(pakp, pabp, fname, dst_struct, dst_field, src_struct, src_field):
    """Turns one field of a struct into a copy of another struct's field (same file): its type
    word, name and value; the link to the next field stays. A way to give a struct a field it lacks,
    at the cost of one it can spare. A pair or vector lives out of line, and the game's loader reads
    a file's data in layout order (a pointer into another item, or data parked in an unlinked field
    record, crashes it at boot): the destination must then be a string field, whose text is
    replaced by the data, the rest of the file moved to fit; the file then goes to the end of the
    .pab, its pack entry repointed."""
    sys.path.insert(0, os.path.dirname(__file__))
    from p8zone import top_items
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(bytes(p))
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = bytearray(b[start:start + e['size']])
    u = lambda o: struct.unpack_from('<I', d, o)[0]  # noqa: E731
    items = top_items(bytes(d))

    def field(sname, fname_):
        f, k = u(items[key(sname)][1] + 4), key(fname_)
        while f and u(f + 4) != k:
            f = u(f + 12)
        if not f:
            raise SystemExit(f'{fname_} not in {sname}')
        return f
    df, sf = field(dst_struct, dst_field), field(src_struct, src_field)
    t = d[sf + 1] >> 1
    if t not in (5, 6):
        d[df:df + 12] = d[sf:sf + 12]
        b[start:start + e['size']] = d
        open(pabp, 'wb').write(b)
        return print(f'{e["name"]} {dst_struct}.{dst_field} -> copy of {src_struct}.{src_field}')
    if d[df + 1] >> 1 != 3:
        raise SystemExit(f'{dst_struct}.{dst_field}: a pair or vector needs a string field to replace')
    at, v = u(df + 8), u(sf + 8)
    room = (d.index(0, at) - at + 4) & ~3
    head = bytes(d[sf:sf + 8])
    d = bytearray(resize(d, at, room, bytes(d[v:v + (12 if t == 5 else 16)])))
    d[df:df + 8] = head  # the record lies before its data, so it did not move
    b += bytes(-len(b) % 16)
    pos = len(p) + len(b)
    b += d
    struct.pack_into('<II', p, e['entry_pos'] + 4, pos - e['entry_pos'], len(d))
    open(pakp, 'wb').write(p)
    open(pabp, 'wb').write(b)
    print(f'{e["name"]} {dst_struct}.{dst_field} -> copy of {src_struct}.{src_field} '
          f'(in its string data, {room} -> {12 if t == 5 else 16} bytes; file moved to the end of the pab)')


def addfield(pakp, pabp, fname, struct_name, after, field, value):
    """A new string field (value str:<text>) in a top-level struct, right after another field: a
    struct's fields are laid out record by record, each followed by its data, and the game's loader
    reads them in that order, so the record and its text go in just after <after>'s data (the rest
    of the file moved by resize) and the field links are redone. The file moves to the end of the
    .pab."""
    sys.path.insert(0, os.path.dirname(__file__))
    from p8zone import top_items
    if not value.startswith('str:'):
        raise SystemExit('only str:<text> values')
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(bytes(p))
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = bytes(b[start:start + e['size']])
    u = lambda o: struct.unpack_from('<I', d, o)[0]  # noqa: E731
    f, k = u(top_items(d)[key(struct_name)][1] + 4), key(after)
    while f and u(f + 4) != k:
        f = u(f + 12)
    if not f:
        raise SystemExit(f'{after} not in {struct_name}')
    tmpl = f
    while tmpl and d[tmpl + 1] >> 1 != 3:  # a string field's type word to copy
        tmpl = u(tmpl + 12)
    if not tmpl:
        raise SystemExit(f'{struct_name} has no string field to copy the type word from')
    at = u(f + 12)  # the next record: the new one goes there
    if not at:
        raise SystemExit(f'{after} is the last field')
    text = value[4:].encode('latin-1') + bytes(1)
    text += bytes(-len(text) % 4)
    rec = bytearray(d[tmpl:tmpl + 4]) + struct.pack('<III', key(field), at + 16, 0) + text
    d = bytearray(resize(d, at, 0, bytes(rec)))
    struct.pack_into('<I', d, f + 12, at)  # after -> new (resize moved it past the insert)
    struct.pack_into('<I', d, at + 12, at + len(rec))  # new -> the old next, now moved
    b += bytes(-len(b) % 16)
    pos = len(p) + len(b)
    b += d
    struct.pack_into('<II', p, e['entry_pos'] + 4, pos - e['entry_pos'], len(d))
    open(pakp, 'wb').write(p)
    open(pabp, 'wb').write(b)
    print(f'{e["name"]} {struct_name}: new field {field} = {value[4:]!r} after {after}')


def rekey(pakp, pabp, fname, script, old, new):
    """Every occurrence of one checksum in one script swapped for another, packed or not: the body
    is unpacked, edited, and stored unpacked (swap_script relocates the rest of the file, which then
    moves to the end of the .pab, its pack entry repointed)."""
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(bytes(p))
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = bytes(b[start:start + e['size']])
    sk = key(script)
    _, items = pointer_sites(d)
    _, _, _, v = next(i for i in items if i[2] == sk and i[1] == 7)
    usz, csz = struct.unpack_from('<2I', d, v + 4)
    code = body(d, v + 12, usz, csz)
    o, n = struct.pack('<I', key(old)), struct.pack('<I', key(new))
    count = code.count(o)
    if not count:
        raise SystemExit(f'{old} not in {script}')
    code = code.replace(o, n)
    new_d = swap_script(d, sk, d[v:v + 4] + struct.pack('<2I', len(code), len(code)) + code)
    b += bytes(-len(b) % 16)
    pos = len(p) + len(b)
    b += new_d
    struct.pack_into('<II', p, e['entry_pos'] + 4, pos - e['entry_pos'], len(new_d))
    open(pakp, 'wb').write(p)
    open(pabp, 'wb').write(b)
    print(f'{e["name"]} {script}: {old} -> {new} ({count}), stored unpacked, file moved to the end of the pab')


def setglobal(pakp, pabp, fname, name, value):
    """A top-level integer (or checksum) value, rewritten in its item header."""
    p, b = open(pakp, 'rb').read(), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(p)
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = b[start:start + e['size']]
    k = key(name)
    at, t, _, _ = next(i for i in pointer_sites(bytes(d))[1] if i[2] == k)
    if t not in (1, 13):
        raise SystemExit(f'{name}: item type {t}, not an integer or checksum')
    old = struct.unpack_from('<I', d, at + 12)[0]
    new = int(value) if value.lstrip('-').isdigit() else key(value)
    struct.pack_into('<I', b, start + at + 12, new & 0xFFFFFFFF)
    open(pabp, 'wb').write(b)
    print(f'{e["name"]} {name}: {old:#x} -> {new & 0xFFFFFFFF:#x}')


def compact(pakp, pabp):
    """Rewrites the .pab with only the files its pack entries point at, in their order, 16-aligned:
    rekey and copyfield leave the old copy of each file they move (the whole .pab is loaded into
    memory, and the dead copies push it past what the game can spare)."""
    p, b = bytearray(open(pakp, 'rb').read()), open(pabp, 'rb').read()
    ents, _ = pak.read_entries(bytes(p))
    out = bytearray()
    for e in sorted(ents, key=lambda e: e['offset']):
        out += bytes(-len(out) % 16)
        at = e['offset'] - len(p)
        struct.pack_into('<I', p, e['entry_pos'] + 4, len(p) + len(out) - e['entry_pos'])
        out += b[at:at + e['size']]
    out += bytes(-len(out) % 16)
    open(pakp, 'wb').write(p)
    open(pabp, 'wb').write(out)
    print(f'{os.path.basename(pabp)}: {len(b)} -> {len(out)} bytes')


def main():
    if sys.argv[1] == 'addfield':
        return addfield(*sys.argv[2:9])
    if sys.argv[1] == 'compact':
        return compact(*sys.argv[2:4])
    if sys.argv[1] == 'rekey':
        return rekey(*sys.argv[2:8])
    if sys.argv[1] == 'setglobal':
        return setglobal(*sys.argv[2:7])
    if sys.argv[1] == 'copyfield':
        return copyfield(*sys.argv[2:9])
    if sys.argv[1] == 'extract':
        pakp, pabp, fname, out = sys.argv[2:6]
        p, b = open(pakp, 'rb').read(), open(pabp, 'rb').read()
        e = next(e for e in pak.read_entries(p)[0] if e['name'].lower().endswith(fname.lower()))
        open(out, 'wb').write((p + b)[e['offset']:e['offset'] + e['size']])
    elif sys.argv[1] == 'swapscript':
        swapscript(*sys.argv[2:7])
    elif sys.argv[1] == 'setfield':
        setfield(*sys.argv[2:8])
    elif sys.argv[1] == 'setkey':
        setkey(*sys.argv[2:8])
    elif sys.argv[1] == 'setdata':
        setdata(*sys.argv[2:])


if __name__ == '__main__':
    main()
