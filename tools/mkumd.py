"""Build a PSP UMD-style ISO from an unpacked game tree.

  mkumd.py <game dir> <out.iso> [--like <original.iso>] [--compact-wad <PSP_GAME/USRDIR/datap>]

The layout follows the shipped UMD images: ISO9660 level 1 with plain names (no ;1 version), system
and application id "PSP GAME", a blank volume id, every file starting on a 16-sector (32 KB)
boundary. With --like, the original image's file order and creation date are kept (files missing
from the tree are dropped, new ones go at the end).

--compact-wad repacks a Neversoft .hed/.wad pair first (into a temp copy, the tree is not
touched): tools/hed.py's replace appends files that outgrow their slot, so a patched .wad carries
every older copy. Each distinct file is written once, 2048-aligned, in index order, and only the
offsets in the index change.
"""
import os
import struct
import sys
import tempfile

SECTOR = 2048
ALIGN = 16  # sectors


def both16(v):
    return struct.pack('<H', v) + struct.pack('>H', v)


def both32(v):
    return struct.pack('<I', v) + struct.pack('>I', v)


def compact_wad(hed_path, wad_path, out_dir):
    hed = bytearray(open(hed_path, 'rb').read())
    entries, p = [], 0
    while p + 8 <= len(hed):
        off, size = struct.unpack_from('<II', hed, p)
        if off == 0xFFFFFFFF:
            break
        end = hed.index(b'\0', p + 8)
        if end == p + 8:
            break
        entries.append((p, off, size))
        p = (end + 4) & ~3
    new_off = {}
    out_wad = os.path.join(out_dir, os.path.basename(wad_path))
    with open(wad_path, 'rb') as src, open(out_wad, 'wb') as dst:
        pos = 0
        for at, off, size in entries:
            if (off, size) not in new_off:
                src.seek(off)
                data = src.read(size)
                assert len(data) == size, (off, size)
                new_off[(off, size)] = pos
                dst.write(data + bytes(-size % SECTOR))
                pos += size + (-size % SECTOR)
            struct.pack_into('<I', hed, at, new_off[(off, size)])
        total = pos
    out_hed = os.path.join(out_dir, os.path.basename(hed_path))
    open(out_hed, 'wb').write(hed)
    print(f'{os.path.basename(wad_path)}: {os.path.getsize(wad_path):,} -> {total:,} bytes '
          f'({len(new_off)} files, {len(entries)} index entries)')
    return out_hed, out_wad


def read_iso_order(path):
    """[(path, lba)] of the files in an ISO, and its PVD creation date."""
    f = open(path, 'rb')
    f.seek(16 * SECTOR)
    pvd = f.read(SECTOR)
    root_lba, root_size = struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0]
    out = []

    def walk(lba, size, prefix):
        f.seek(lba * SECTOR)
        d = f.read(size)
        p = 0
        while p < len(d):
            n = d[p]
            if n == 0:
                p = (p // SECTOR + 1) * SECTOR
                continue
            elba, esz = struct.unpack_from('<I', d, p + 2)[0], struct.unpack_from('<I', d, p + 10)[0]
            flags, nl = d[p + 25], d[p + 32]
            name = d[p + 33:p + 33 + nl]
            if name not in (b'\0', b'\1'):
                full = prefix + '/' + name.decode('latin-1')
                if flags & 2:
                    walk(elba, esz, full)
                else:
                    out.append((full, elba))
            p += n
    walk(root_lba, root_size, '')
    return out, pvd[813:830]


class Node:
    def __init__(self, name, parent=None):
        self.name, self.parent, self.children, self.lba, self.size = name, parent, {}, 0, 0


def dir_record(name_bytes, lba, size, is_dir, date):
    n = len(name_bytes)
    length = 33 + n + (1 - n % 2)
    rec = bytes([length, 0]) + both32(lba) + both32(size) + date + bytes([2 if is_dir else 0, 0, 0]) + \
        both16(1) + bytes([n]) + name_bytes
    return rec + bytes(length - len(rec))


def build(root_dir, out_iso, like=None, overrides=None):
    overrides = overrides or {}
    files = []
    for dp, dn, fn in os.walk(root_dir):
        for f in fn:
            rel = '/' + os.path.relpath(os.path.join(dp, f), root_dir).replace('\\', '/')
            files.append(rel)
    date7 = bytes([105, 2, 15, 13, 18, 16, 0])  # 2005-02-15 13:18:16, as the original's PVD
    pvd_date = b'2005021513181600\x24'
    order = files
    if like:
        orig, pvd_date = read_iso_order(like)
        rank = {p: i for i, (p, lba) in enumerate(sorted(orig, key=lambda x: x[1]))}
        order = sorted(files, key=lambda p: (rank.get(p, 10 ** 9), p))
    # tree
    root = Node('')
    for path in files:
        node = root
        for part in path.strip('/').split('/')[:-1]:
            node = node.children.setdefault(part, Node(part, node))
        node.children[path.rsplit('/', 1)[1]] = path
    dirs = []  # breadth first, children sorted

    def collect():
        queue = [root]
        while queue:
            n = queue.pop(0)
            dirs.append(n)
            for k in sorted(n.children):
                if isinstance(n.children[k], Node):
                    queue.append(n.children[k])
    collect()
    dir_num = {id(d): i + 1 for i, d in enumerate(dirs)}

    # path table
    def path_table(big):
        out = bytearray()
        for d in dirs:
            name = d.name.encode() if d.name else b'\0'
            parent = dir_num[id(d.parent)] if d.parent else 1
            out += bytes([len(name), 0]) + (struct.pack('>I', d.lba) if big else struct.pack('<I', d.lba)) + \
                (struct.pack('>H', parent) if big else struct.pack('<H', parent)) + name + bytes(len(name) % 2)
        return bytes(out)

    # directory sizes (records for '.', '..' and children)
    def dir_bytes(d):
        recs = [dir_record(b'\0', 0, 0, True, date7), dir_record(b'\1', 0, 0, True, date7)]
        recs += [dir_record(k.encode(), 0, 0, isinstance(v, Node), date7) for k, v in sorted(d.children.items())]
        size, cur = 0, 0
        for r in recs:
            if cur + len(r) > SECTOR:
                size += SECTOR
                cur = 0
            cur += len(r)
        return size + SECTOR
    pt_size = len(path_table(False))
    pt_sectors = (pt_size + SECTOR - 1) // SECTOR
    lba = 18
    l_table, lba = lba, lba + pt_sectors
    m_table, lba = lba, lba + pt_sectors
    for d in dirs:
        d.size = dir_bytes(d)
        d.lba = lba
        lba += d.size // SECTOR
    file_lba, file_size, src = {}, {}, {}
    for path in order:
        lba = (lba + ALIGN - 1) // ALIGN * ALIGN
        s = overrides.get(path, os.path.join(root_dir, path.strip('/')))
        src[path] = s
        file_lba[path], file_size[path] = lba, os.path.getsize(s)
        lba += (file_size[path] + SECTOR - 1) // SECTOR
    total = (lba + ALIGN - 1) // ALIGN * ALIGN

    def dir_data(d):
        recs = [dir_record(b'\0', d.lba, d.size, True, date7),
                dir_record(b'\1', d.parent.lba if d.parent else d.lba, d.parent.size if d.parent else d.size, True, date7)]
        for k, v in sorted(d.children.items()):
            if isinstance(v, Node):
                recs.append(dir_record(k.encode(), v.lba, v.size, True, date7))
            else:
                recs.append(dir_record(k.encode(), file_lba[v], file_size[v], False, date7))
        out, cur = bytearray(), bytearray()
        for r in recs:
            if len(cur) + len(r) > SECTOR:
                out += cur + bytes(SECTOR - len(cur))
                cur = bytearray()
            cur += r
        out += cur + bytes(SECTOR - len(cur))
        return bytes(out)

    pvd = bytearray(SECTOR)
    pvd[0:6] = b'\x01CD001'
    pvd[6] = 1
    pvd[8:40] = b'PSP GAME'.ljust(32)
    pvd[40:72] = b' ' * 32
    pvd[80:88] = both32(total)
    pvd[120:124] = both16(1)
    pvd[124:128] = both16(1)
    pvd[128:132] = both16(SECTOR)
    pvd[132:140] = both32(pt_size)
    pvd[140:144] = struct.pack('<I', l_table)
    pvd[148:152] = struct.pack('>I', m_table)
    pvd[156:190] = dir_record(b'\0', root.lba, root.size, True, date7)
    for a, b in ((190, 318), (318, 446), (446, 574), (702, 739), (739, 776), (776, 813)):
        pvd[a:b] = b' ' * (b - a)
    pvd[574:702] = b'PSP GAME'.ljust(128)
    pvd[813:830] = pvd_date
    for a in (830, 847, 864):
        pvd[a:a + 17] = b'0' * 16 + b'\0'
    pvd[881] = 1
    term = bytearray(SECTOR)
    term[0:7] = b'\xffCD001\x01'
    with open(out_iso, 'wb') as out:
        out.write(bytes(16 * SECTOR) + pvd + term)
        out.write(bytes(SECTOR * (l_table - 18)))
        for big, at in ((False, l_table), (True, m_table)):
            out.seek(at * SECTOR)
            out.write(path_table(big))
        for d in dirs:
            out.seek(d.lba * SECTOR)
            out.write(dir_data(d))
        for path in order:
            out.seek(file_lba[path] * SECTOR)
            with open(src[path], 'rb') as f:
                while True:
                    chunk = f.read(1 << 22)
                    if not chunk:
                        break
                    out.write(chunk)
        out.truncate(total * SECTOR)
    print(f'{out_iso}: {total * SECTOR:,} bytes, {len(files)} files, {len(dirs)} directories')


def main():
    args = sys.argv[1:]
    like = None
    compact = None
    if '--like' in args:
        i = args.index('--like')
        like = args[i + 1]
        del args[i:i + 2]
    if '--compact-wad' in args:
        i = args.index('--compact-wad')
        compact = args[i + 1]
        del args[i:i + 2]
    game, out = args
    overrides = {}
    tmp = None
    if compact:
        tmp = tempfile.mkdtemp(prefix='mkumd_', dir=os.path.dirname(os.path.abspath(out)))
        h, w = compact_wad(os.path.join(game, compact + '.hed'), os.path.join(game, compact + '.wad'), tmp)
        overrides['/' + compact.replace('\\', '/') + '.hed'] = h
        overrides['/' + compact.replace('\\', '/') + '.wad'] = w
    try:
        build(game, out, like, overrides)
    finally:
        if tmp:
            for f in os.listdir(tmp):
                os.remove(os.path.join(tmp, f))
            os.rmdir(tmp)


if __name__ == '__main__':
    main()
