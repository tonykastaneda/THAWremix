"""Neversoft .hed/.wad archives (console builds).

  hed.py list <hed> [--sectors]
  hed.py extract <hed> <wad> <outdir> [--sectors] [--match <substring>]
  hed.py replace <hed> <wad> <archive path> <new file> [--sectors]

Each index entry is offset, size, then a NUL-terminated path padded to four bytes. THUG2 Remix
(PSP) stores byte offsets; THAW PS2 stores 2048-byte sector numbers (--sectors).
"""
import os
import struct
import sys


def read_hed(path, sectors=False):
    data = open(path, 'rb').read()
    out, p = [], 0
    while p + 8 <= len(data):
        off, size = struct.unpack_from('<II', data, p)
        if off == 0xFFFFFFFF:
            break
        end = data.index(b'\0', p + 8)
        name = data[p + 8:end].decode('latin-1')
        if not name:
            break
        p = (end + 4) & ~3
        out.append((name, off * 2048 if sectors else off, size))
    return out


def replace(hed, wad, name, src, sectors=False):
    """Writes in place when the file fits its 2048-padded slot, otherwise
    appends to the wad; either way the index entry gets the new offset and size. Some files are
    listed twice; every entry with the name is pointed at the one new copy."""
    data = bytearray(open(hed, 'rb').read())
    new = open(src, 'rb').read()
    p, written = 0, None
    while p + 8 <= len(data):
        off, size = struct.unpack_from('<II', data, p)
        if off == 0xFFFFFFFF:
            break
        end = data.index(b'\0', p + 8)
        if sectors:
            off *= 2048
        if data[p + 8:end].decode('latin-1').lower() == name.lower():
            if written is None:
                with open(wad, 'r+b') as f:
                    if len(new) > (size + 2047 & ~2047):
                        f.seek(0, 2)
                        off = f.tell() + 2047 & ~2047
                    f.seek(off)
                    f.write(new + bytes(-len(new) % 2048))
                written = off
            struct.pack_into('<II', data, p, written // 2048 if sectors else written, len(new))
            print(f'{name}: {size} -> {len(new)} bytes at {written:#x}')
        p = (end + 4) & ~3
    if written is None:
        raise SystemExit(f'{name} not in {hed}')
    open(hed, 'wb').write(data)


def main():
    args = sys.argv[1:]
    if args[0] == 'replace':
        return replace(*args[1:5], sectors='--sectors' in args)
    sectors = '--sectors' in args
    match = None
    if '--match' in args:
        match = args[args.index('--match') + 1].lower()
        del args[args.index('--match'):args.index('--match') + 2]
    args = [a for a in args if a != '--sectors']
    cmd, hed = args[0], args[1]
    entries = read_hed(hed, sectors)
    if cmd == 'list':
        for name, off, size in entries:
            print(f'{off:10x} {size:10d} {name}')
        return
    wad, outdir = args[2], args[3]
    n = 0
    with open(wad, 'rb') as f:
        for name, off, size in entries:
            if match and match not in name.lower():
                continue
            dest = os.path.join(outdir, name.lstrip('\\').replace('\\', os.sep))
            if not os.path.abspath(dest).startswith(os.path.abspath(outdir)):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            f.seek(off)
            open(dest, 'wb').write(f.read(size))
            n += 1
    print(f'{n} files')


if __name__ == '__main__':
    main()
