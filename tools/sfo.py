"""Read or change a PARAM.SFO.

  sfo.py <PARAM.SFO>                        list every key
  sfo.py <PARAM.SFO> set <KEY> <int>        set (or add) an integer key, e.g. MEMSIZE 1
"""
import struct
import sys


def read(path):
    d = open(path, 'rb').read()
    magic, ver, ko, do, n = struct.unpack_from('<4sIIII', d)
    assert magic == b'\0PSF', path
    out = []
    for i in range(n):
        kof, fmt, ln, mx, dof = struct.unpack_from('<HHIII', d, 20 + 16 * i)
        k = d[ko + kof:d.index(b'\0', ko + kof)].decode()
        out.append((k, fmt, d[do + dof:do + dof + mx], ln))
    return ver, out


def write(path, ver, entries):
    entries = sorted(entries, key=lambda e: e[0])  # keys stay sorted, as the system reads them
    keys = b''.join(k.encode() + b'\0' for k, *_ in entries)
    keys += b'\0' * (-len(keys) % 4)
    ko = 20 + 16 * len(entries)
    do = ko + len(keys)
    index, data, kof = b'', b'', 0
    for k, fmt, v, ln in entries:
        index += struct.pack('<HHIII', kof, fmt, ln, len(v), len(data))
        kof += len(k) + 1
        data += v
    open(path, 'wb').write(struct.pack('<4sIIII', b'\0PSF', ver, ko, do, len(entries)) + index + keys + data)


def main():
    path = sys.argv[1]
    ver, entries = read(path)
    if len(sys.argv) > 2 and sys.argv[2] == 'set':
        key, val = sys.argv[3], int(sys.argv[4])
        entries = [e for e in entries if e[0] != key] + [(key, 0x404, struct.pack('<I', val), 4)]
        write(path, ver, entries)
        ver, entries = read(path)
    for k, fmt, v, ln in entries:
        print(k, struct.unpack('<I', v[:4])[0] if fmt == 0x404 else v[:ln].rstrip(b'\0').decode('utf-8', 'replace'))


if __name__ == '__main__':
    main()
