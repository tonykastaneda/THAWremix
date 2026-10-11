"""THUG2 / Remix token-stream .qb: tokenizer, node array access, and the .pre container.

  qb2.py nodes <file.qb> [n]          print the first n nodes of the level's node array
  qb2.py pre-list <file.pre>          list a .pre's entries

Tokens used by level data (one byte each, then the payload):
  01 newline, 02 newline + u32 line, 03 { 04 }, 05 [ 06 ], 07 =, 16 name u32, 17 int i32,
  1A float, 1B string u32 len + bytes, 1C local string, 1E vector 3f, 1F pair 2f,
  2B checksum-name table entry u32 + NUL-terminated text.
Script bodies use more tokens; only their payload sizes matter here (see SIZES).
"""
import struct
import sys

# payload sizes for tokens with a fixed payload
SIZES = {0x02: 4, 0x16: 4, 0x17: 4, 0x18: 4, 0x19: 4, 0x1A: 4, 0x1E: 12, 0x1F: 8, 0x2E: 4, 0x47: 2, 0x48: 2,
         0x49: 2}
NEWLINE, LBRACE, RBRACE, LBRACK, RBRACK, EQ, NAME, INT, FLOAT, STRING, LSTRING, VEC = (
    0x01, 0x03, 0x04, 0x05, 0x06, 0x07, 0x16, 0x17, 0x1A, 0x1B, 0x1C, 0x1E)


def tokens(d, p=0, end=None):
    """Yields (offset, token, payload bytes)."""
    end = len(d) if end is None else end
    while p < end:
        t = d[p]
        if t == 0x00:
            yield p, t, b''
            return
        if t in (0x1B, 0x1C):
            n = struct.unpack_from('<I', d, p + 1)[0]
            yield p, t, d[p + 1:p + 5 + n]
            p += 5 + n
        elif t == 0x2B:
            e = d.index(b'\0', p + 5)
            yield p, t, d[p + 1:e + 1]
            p = e + 1
        elif t == 0x2F or t == 0x37 or t == 0x40 or t == 0x41:
            n = struct.unpack_from('<I', d, p + 1)[0]
            k = 4 + n * 2 + n * 4  # count, u16 weights, u32 jump offsets
            yield p, t, d[p + 1:p + 1 + k]
            p += 1 + k
        elif t == 0x4A:
            # THAW: inline binary struct, u16 size, padding, then the struct
            # (aligned in THAW's memory, not in the script: the struct header 00 00 01 00 is found
            # within the padding)
            n = struct.unpack_from('<H', d, p + 1)[0]
            q = p + 3
            q += next((k for k in range(4) if d[q + k:q + k + 4] == b'\0\0\1\0'), 0)
            yield p, t, d[q:q + n]
            p = q + n
        else:
            k = SIZES.get(t, 0)
            yield p, t, d[p + 1:p + 1 + k]
            p += 1 + k


def parse_value(d, p):
    """Parses one value at p (struct, array or scalar). Returns (value, next offset).
    Structs are lists of (name or None, value); flags appear as (None, ('name', key))."""
    while d[p] in (NEWLINE, 0x02, 0x09):
        p += 1 + SIZES.get(d[p], 0)
    t = d[p]
    if t == LBRACE:
        out, p = [], p + 1
        while True:
            while d[p] in (NEWLINE, 0x02, 0x09):
                p += 1 + SIZES.get(d[p], 0)
            if d[p] == RBRACE:
                return ('struct', out), p + 1
            if d[p] == NAME and d[p + 5] == EQ:
                k = struct.unpack_from('<I', d, p + 1)[0]
                v, p = parse_value(d, p + 6)
                out.append((k, v))
            else:
                v, p = parse_value(d, p)
                out.append((None, v))
    if t == LBRACK:
        out, p = [], p + 1
        while True:
            while d[p] in (NEWLINE, 0x02, 0x09):
                p += 1 + SIZES.get(d[p], 0)
            if d[p] == RBRACK:
                return ('array', out), p + 1
            v, p = parse_value(d, p)
            out.append(v)
    if t == NAME:
        return ('name', struct.unpack_from('<I', d, p + 1)[0]), p + 5
    if t == INT:
        return ('int', struct.unpack_from('<i', d, p + 1)[0]), p + 5
    if t == FLOAT:
        return ('float', struct.unpack_from('<f', d, p + 1)[0]), p + 5
    if t == VEC:
        return ('vec', struct.unpack_from('<3f', d, p + 1)), p + 13
    if t == 0x1F:
        return ('pair', struct.unpack_from('<2f', d, p + 1)), p + 9
    if t in (STRING, LSTRING):
        n = struct.unpack_from('<I', d, p + 1)[0]
        return ('str' if t == STRING else 'lstr', d[p + 5:p + 5 + n - 1].decode('latin-1')), p + 5 + n
    if t == 0x0A:  # minus before a number
        v, q = parse_value(d, p + 1)
        return (v[0], -v[1]), q
    raise ValueError(f'token {t:#x} at {p:#x}')


def encode_value(v):
    kind, x = v
    if kind == 'struct':
        out = bytearray([LBRACE, NEWLINE])
        for k, val in x:
            if k is not None:
                out += bytes([NAME]) + struct.pack('<I', k) + bytes([EQ])
            out += encode_value(val) + bytes([NEWLINE])
        out.append(RBRACE)
        return bytes(out)
    if kind == 'array':
        out = bytearray([LBRACK])
        for i, val in enumerate(x):
            out += encode_value(val)
        out.append(RBRACK)
        return bytes(out)
    if kind == 'name':
        return bytes([NAME]) + struct.pack('<I', x)
    if kind == 'int':
        return bytes([INT]) + struct.pack('<i', x)
    if kind == 'float':
        return bytes([FLOAT]) + struct.pack('<f', x)
    if kind == 'vec':
        return bytes([VEC]) + struct.pack('<3f', *x)
    if kind == 'pair':
        return bytes([0x1F]) + struct.pack('<2f', *x)
    if kind in ('str', 'lstr'):
        b = x.encode('latin-1') + b'\0'
        return bytes([STRING if kind == 'str' else LSTRING]) + struct.pack('<I', len(b)) + b
    raise ValueError(kind)


def find_item(d, key):
    """Offset of the value of top-level `key = ...` (first NAME key EQ at line start)."""
    want = bytes([NAME]) + struct.pack('<I', key) + bytes([EQ])
    p = 0
    while True:
        p = d.find(want, p)
        if p < 0:
            return None
        if p == 0 or d[p - 1] in (NEWLINE,) or (p >= 5 and d[p - 5] == 0x02):
            return p + 6
        p += 1


def get(st, key):
    for k, v in st[1]:
        if k == key:
            return v
    return None


# ---------------------------------------------------------------- .pre

def read_pre(path):
    """Returns (version, magic, [(name, checksum, data bytes (decompressed))])."""
    from thawscene import lzss
    d = open(path, 'rb').read()
    size, ver, magic, n = struct.unpack_from('<IHHI', d, 0)
    p = 0x10 if ver == 4 else 0x0C
    out = []
    for _ in range(n):
        dsz, csz, nlen, cks = struct.unpack_from('<IIII', d, p)
        name = d[p + 16:p + 16 + nlen].split(b'\0')[0].decode('latin-1')
        body = p + 16 + nlen
        raw = d[body:body + (csz or dsz)]
        out.append((name, cks, lzss(raw, dsz) if csz else raw))
        p = (body + (csz or dsz) + 3) & ~3
    return ver, magic, d[0x0C:0x10] if ver == 4 else b'', out


def lzss_pack(data):
    """Neversoft / Okumura LZSS, the format thawscene.lzss and Remix's loader read: a 4096-byte ring
    preset to spaces with writing from 0xFEE, a flag byte per 8 items (low bit first, 1 = literal
    byte), a match is 2 bytes (ring offset low 8 bits, then offset high 4 bits << 4 | length - 3),
    lengths 3..18. Greedy, matching within the last 4078 bytes written."""
    n = len(data)
    out = bytearray()
    heads = {}
    i = 0
    flags_at, bit, flags = None, 8, 0
    while i < n:
        if bit == 8:
            if flags_at is not None:
                out[flags_at] = flags
            flags_at, bit, flags = len(out), 0, 0
            out.append(0)
        best_len, best_pos = 0, 0
        if i + 2 < n:
            key = data[i:i + 3]
            cands = heads.get(key)
            if cands:
                limit = min(18, n - i)
                for q in reversed(cands[-48:]):
                    if i - q > 4078:
                        break
                    k = 3
                    while k < limit and data[q + k] == data[i + k]:
                        k += 1
                    if k > best_len:
                        best_len, best_pos = k, q
                        if k == limit:
                            break
        if best_len >= 3:
            off = (0xFEE + best_pos) & 0xFFF
            out += bytes([off & 0xFF, ((off >> 4) & 0xF0) | (best_len - 3)])
            step = best_len
        else:
            flags |= 1 << bit
            out.append(data[i])
            step = 1
        for j in range(i, min(i + step, n - 2)):
            heads.setdefault(data[j:j + 3], []).append(j)
        i += step
        bit += 1
    if flags_at is not None:
        out[flags_at] = flags
    return bytes(out)


def pre_entry(data):
    """(stored bytes, compressed size field): LZSS when it saves space, as Remix's own .pre files
    store almost everything. Remix's loader needs about twice an entry's size of buffer room for a
    stored-plain entry (see tools/precheck.py), so big plain entries make it stop at boot."""
    packed = lzss_pack(data)
    if len(packed) < len(data):
        return packed, len(packed)
    return data, 0


def replace_in_pre(src, dst, name, data):
    """Copies a .pre, swapping one entry (matched by name, case-insensitive) for `data`, LZSS-packed
    where that helps (pre_entry). Every other entry keeps its original bytes. The size field at 0x0C
    (the loader's buffer, see tools/precheck.py) grows with the unpacked size."""
    d = open(src, 'rb').read()
    size, ver, magic, n = struct.unpack_from('<IHHI', d, 0)
    head = 0x10 if ver == 4 else 0x0C
    out = bytearray(d[:head])
    p, found = head, False
    grow = 0
    for _ in range(n):
        dsz, csz, nlen, cks = struct.unpack_from('<IIII', d, p)
        ename = d[p + 16:p + 16 + nlen].split(b'\0')[0].decode('latin-1')
        body = p + 16 + nlen
        nxt = (body + (csz or dsz) + 3) & ~3
        if ename.lower() == name.lower():
            stored, packed = pre_entry(data)
            out += struct.pack('<IIII', len(data), packed, nlen, cks) + d[p + 16:body] + stored
            out += bytes(-len(out) % 4)
            grow = max(0, len(data) - dsz)
            found = True
        else:
            out += d[p:nxt]
        p = nxt
    if not found:
        raise SystemExit(f'{name} not in {src}')
    struct.pack_into('<I', out, 0, len(out))
    if ver == 4:
        # a size hint (not the plain sum of entry sizes); grown by what the entry grew
        struct.pack_into('<I', out, 0x0C, struct.unpack_from('<I', d, 0x0C)[0] + ((grow + 15) & ~15))
    open(dst, 'wb').write(out)


def append_to_pre(src, dst, entries):
    """Copies a .pre with new entries [(name, data)] added at the end (LZSS-packed where that helps),
    each keyed by the checksum of its path (as the shipped entries are)."""
    from pak import qbkey
    d = open(src, 'rb').read()
    size, ver, magic, n = struct.unpack_from('<IHHI', d, 0)
    out = bytearray(d)
    out += bytes(-len(out) % 4)
    grow = 0
    for name, data in entries:
        nb = name.encode('latin-1') + b'\0'
        nb += bytes(-len(nb) % 4)
        stored, packed = pre_entry(data)
        out += struct.pack('<IIII', len(data), packed, len(nb), qbkey(name)) + nb + stored
        out += bytes(-len(out) % 4)
        grow += ((len(data) + 15) & ~15) + ((16 + len(nb) + 15) & ~15)
    struct.pack_into('<I', out, 0, len(out))
    struct.pack_into('<I', out, 8, n + len(entries))
    if ver == 4:
        struct.pack_into('<I', out, 0x0C, struct.unpack_from('<I', d, 0x0C)[0] + grow)
    open(dst, 'wb').write(out)


def write_pre(path, ver, magic, extra, entries):
    """Entries stored uncompressed (compressed size 0), as the shipped .pre files already do for
    some entries."""
    body = bytearray()
    for name, cks, data in entries:
        nb = name.encode('latin-1') + b'\0'
        nb += bytes(-len(nb) % 4)
        body += struct.pack('<IIII', len(data), 0, len(nb), cks) + nb + data
        body += bytes(-len(body) % 4)
    total = sum(len(e[2]) for e in entries)
    head = struct.pack('<IHHI', 0, ver, magic, len(entries))
    if ver == 4:
        head += struct.pack('<I', total)
    out = bytearray(head + body)
    struct.pack_into('<I', out, 0, len(out))
    open(path, 'wb').write(out)


if __name__ == '__main__':
    sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])
    if sys.argv[1] == 'nodes':
        d = open(sys.argv[2], 'rb').read()
        v, end = parse_value(d, find_item(d, struct.unpack_from('<I', d, 1)[0]))
        print(len(v[1]), 'nodes, array ends at', hex(end))
        for n in v[1][:int(sys.argv[3]) if len(sys.argv) > 3 else 5]:
            print(n)
    elif sys.argv[1] == 'pre-list':
        ver, magic, extra, entries = read_pre(sys.argv[2])
        for name, cks, data in entries:
            print(f'{cks:08x} {len(data):8d} {name}')
