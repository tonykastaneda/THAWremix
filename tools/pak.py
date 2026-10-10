"""THAW (PC, .pak.wpc / .pab.wpc) archive reader.

Header entry layout (little-endian, 0x20 bytes, optionally followed by a 160-byte name):
  u32 type        QBKey of the extension (".qb", ".scn", ...); ".last" ends the list
  u32 offset      relative to the start of THIS entry (for split paks: header-relative, body in .pab)
  u32 size
  u32 pak_name_key
  u32 full_name_key
  u32 name_key
  u32 parent_key
  u32 flags       0x20 => 160-byte filename follows
"""
import os
import struct
import sys

LAST = 0x2CB3EF3B  # ".last"
EXT = {0xa7f505c4: '.qb', 0x72a6d78c: '.col', 0x8bfa5e8e: '.tex', 0x7ea7357b: '.geom', 0x49875607: '.nqb',
       0x5d796624: '.sqb', 0x745dcd45: '.ska', 0x7330095c: '.ske', 0x9bcc234d: '.mdl', 0x2f1a6a09: '.shd',
       0xdad5e950: '.img', 0xa7dea591: '.pfx', 0xff2d0e91: '.gap', 0x2b0a3095: '.stex', 0x64112e85: '.skin'}
EXT = {0xa7f505c4: '.qb', 0x72a6d78c: '.col', 0x8bfa5e8e: '.tex', 0x7ea7357b: '.geom', 0x49875607: '.nqb',
       0x5d796624: '.sqb', 0x745dcd45: '.ska', 0x7330095c: '.ske', 0x9bcc234d: '.mdl', 0x2f1a6a09: '.shd',
       0xdad5e950: '.img', 0xa7dea591: '.pfx', 0xff2d0e91: '.gap', 0x2b0a3095: '.stex', 0x64112e85: '.skin'}


def qbkey(s: str) -> int:
    """Neversoft CRC32 (reflected, poly 0xEDB88320, no final xor), lowercase, '/'->'\\'."""
    crc = 0xFFFFFFFF
    for ch in s.lower().replace('/', '\\').encode('latin-1'):
        crc ^= ch
        for _ in range(8):
            crc = (crc >> 1) ^ 0xEDB88320 if crc & 1 else crc >> 1
    return crc


def read_entries(hdr: bytes):
    pos = 0
    out = []
    while pos + 0x20 <= len(hdr):
        typ, off, size, pakkey, fullkey, namekey, parent, flags = struct.unpack_from('<8I', hdr, pos)
        if typ in (LAST, 0, 0xCDCDCDCD, 0xB524565F):
            break
        name = None
        nxt = pos + 0x20
        if flags & 0x20:
            name = hdr[nxt:nxt + 160].split(b'\0', 1)[0].decode('latin-1')
            nxt += 160
        out.append(dict(type=typ, offset=pos + off, size=size, pakkey=pakkey, fullkey=fullkey,
                        namekey=namekey, parent=parent, flags=flags, name=name, entry_pos=pos))
        pos = nxt
    return out, pos


def open_pak(path: str):
    """Returns (entries, blob) where entry['offset'] indexes into blob."""
    with open(path, 'rb') as f:
        hdr = f.read()
    entries, _ = read_entries(hdr)
    pab = path[:-len('.pak.wpc')] + '.pab.wpc' if path.lower().endswith('.pak.wpc') else None
    if pab and os.path.exists(pab):
        with open(pab, 'rb') as f:
            body = f.read()
        # split pak: offsets are relative to a virtual file of header+body
        blob = hdr + body
        return entries, blob
    return entries, hdr


def extract(path: str, outdir: str, verbose=False):
    entries, blob = open_pak(path)
    n = 0
    for i, e in enumerate(entries):
        name = e['name'] or ('_noname\\%03d%s' % (i, EXT.get(e['type'], '.%08x' % e['type'])))
        dst = os.path.join(outdir, name.replace('\\', os.sep))
        os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(blob[e['offset']:e['offset'] + e['size']])
        n += 1
        if verbose:
            print('%08x %9d %s' % (e['type'], e['size'], name))
    return n


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: pak.py list <pak> | extract <pak> <outdir>')
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'list':
        entries, blob = open_pak(sys.argv[2])
        print('blob', len(blob))
        for e in entries:
            print('%08x off=%9d size=%9d flags=%02x %s' % (e['type'], e['offset'], e['size'], e['flags'], e['name']))
    elif cmd == 'extract':
        print(extract(sys.argv[2], sys.argv[3]), 'files')
