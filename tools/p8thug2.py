"""THUG2 Remix's skater feel on Project 8 PSP: physics values and cameras, written in place.

  p8thug2.py <qb.pak.psp> <qb.pab.psp> <Remix physics.qb> [--dry]

P8's skater physics tables (game\\skater\\physics.qb: the six "versions" 0x256ce8fe, 0x09039fde,
0x6daa5608, 0x98a4cf9b, 0x01ad9e21, 0x76aaaeb7; 0x6bbc7cba names the active one) use THUG2's parameter
names. Every parameter both have takes THUG2 Remix's skater_physics / stat-global value (a stat is
a struct whose first component is the [low, high] pair). P8's own extras stay.

Cameras: P8 PSP drives the skater with its own tables (0xfdce80cd 'standard', 0x66276ac0 'near',
0x9cbe76ca 'far', 0xb48d7267 'standard ltg'; standard is 7.7 ft behind, FOV 80). Each takes the
matching THUG2 Skater_Camera_Standard_* values, and P8's balance-trick camera fields 0x15814c70
(amount) and 0x48f0a316 (offset) go to 0: the zoom-in on manuals.

Values are written in place (floats, ints, pair floats): the file keeps its size.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pak  # noqa: E402
import p8qb  # noqa: E402
import qb2  # noqa: E402

PHYSICS = ('0x256ce8fe', '0x09039fde', '0x6daa5608', '0x98a4cf9b', '0x01ad9e21', '0x76aaaeb7')
CAMERAS = {'0xfdce80cd': 'Skater_Camera_Standard_Medium', '0x66276ac0': 'Skater_Camera_Standard_Near',
           '0x9cbe76ca': 'Skater_Camera_Standard_Far', '0xb48d7267': 'Skater_Camera_Standard_Medium_LTG'}
BALANCE_CAM = {0x15814c70: 0.0, 0x48f0a316: (0.0, 0.0, 0.0)}


def remix_tables(path):
    """{table or global name: value} from a THUG2 token-stream .qb; structs as [(name, value)]."""
    d = open(path, 'rb').read()
    names = {}
    for o, t, pl in qb2.tokens(d):
        if t == 0x2B:
            names[struct.unpack_from('<I', pl)[0]] = pl[4:].split(b'\0')[0].decode('latin-1')
    toks = list(qb2.tokens(d))
    key = lambda pl: struct.unpack('<I', pl)[0]  # noqa: E731

    def val(i):
        o, t, pl = toks[i]
        if t == 0x1A:
            return struct.unpack('<f', pl)[0], i + 1
        if t == 0x17:
            return struct.unpack('<i', pl)[0], i + 1
        if t == 0x16:
            return ('key', key(pl)), i + 1
        if t == 0x1F:
            return list(struct.unpack('<2f', pl)), i + 1
        if t == 0x1E:
            return list(struct.unpack('<3f', pl)), i + 1
        if t in (3, 5):
            close, out, i = (4 if t == 3 else 6), [], i + 1
            while toks[i][1] != close:
                if toks[i][1] in (1, 2):
                    i += 1
                elif toks[i][1] == 0x16 and toks[i + 1][1] == 7:
                    k = key(toks[i][2])
                    v, i = val(i + 2)
                    out.append((k, v))
                else:
                    v, i = val(i)
                    out.append((None, v))
            return out, i + 1
        return None, i + 1
    out, i = {}, 0
    while i < len(toks) - 2:
        o, t, pl = toks[i]
        if t == 0x16 and toks[i + 1][1] == 7:
            v, j = val(i + 2)
            out[key(pl)] = v
            i = j
            continue
        i += 1
    return out, names


def numbers(v):
    """A THUG2 value as the numbers P8's field takes: a float/int, or a stat's [low, high] pair."""
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v):
        return v
    if isinstance(v, list):
        for k, x in v:
            if k is None and isinstance(x, list) and len(x) == 2 and all(isinstance(y, float) for y in x):
                return x
    return None


class File:
    def __init__(self, d):
        self.d = bytearray(d)

    def u(self, o):
        return struct.unpack_from('<I', self.d, o)[0]

    def fields(self, s):
        """(component offset, type, name key) of a struct."""
        out, c = [], self.u(s + 4)
        while c:
            out.append((c, self.d[c + 1] >> 1, self.u(c + 4)))
            c = self.u(c + 12)
        return out

    def write(self, c, t, value):
        """In place: returns (old, new) or None when the shapes do not match."""
        if t == 2 and isinstance(value, (int, float)):
            old = struct.unpack_from('<f', self.d, c + 8)[0]
            struct.pack_into('<f', self.d, c + 8, float(value))
            return old, float(value)
        if t == 1 and isinstance(value, (int, float)):
            old = struct.unpack_from('<i', self.d, c + 8)[0]
            struct.pack_into('<i', self.d, c + 8, int(round(value)))
            return old, int(round(value))
        if t in (5, 6) and isinstance(value, (list, tuple)) and len(value) == (2 if t == 5 else 3):
            v = self.u(c + 8)
            old = list(struct.unpack_from(f'<{len(value)}f', self.d, v + 4))
            struct.pack_into(f'<{len(value)}f', self.d, v + 4, *value)
            return old, list(value)
        if t == 10 and isinstance(value, (list, tuple)) and len(value) == 2:  # stat: first component the pair
            sub = self.fields(self.u(c + 8))
            if sub and sub[0][1] == 5 and sub[0][2] == 0:
                return self.write(sub[0][0], 5, value)
        return None


def apply(pakp, pabp, remix_path, dry=False):
    tables, names = remix_tables(remix_path)
    k = pak.qbkey
    rem = {kk: v for kk, v in tables[k('skater_physics')] if kk}
    for kk, v in tables.items():  # stat globals (Physics_Jump_Speed_Stat, ...) outside the table
        if names.get(kk, '').endswith('_Stat') or names.get(kk, '').startswith('Physics_'):
            rem.setdefault(kk, v)
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    e = next(e for e in pak.read_entries(bytes(p))[0] if e['name'].lower().endswith('skater' + chr(92) + 'physics.qb.psp'))
    start = e['offset'] - len(p)
    f = File(b[start:start + e['size']])
    top = {kk: v for at, t, kk, v in p8qb.pointer_sites(bytes(f.d))[1] if t == 10}
    nm = lambda kk: names.get(kk, '0x%08x' % kk)  # noqa: E731
    changed = 0
    for table in PHYSICS:
        for c, t, kk in f.fields(top[int(table, 16)]):
            want = numbers(rem.get(kk)) if kk in rem else None
            if want is None:
                continue
            r = f.write(c, t, want)
            if r and r[0] != r[1]:
                changed += 1
                if table == '0x09039fde':
                    print(f'physics {nm(kk)}: {r[0]} -> {r[1]}')
    for table, src in CAMERAS.items():
        cam = {kk: v for kk, v in tables[k(src)] if kk}
        for c, t, kk in f.fields(top[int(table, 16)]):
            want = BALANCE_CAM.get(kk, numbers(cam.get(kk)) if kk in cam else None)
            if want is None:
                continue
            r = f.write(c, t, want)
            if r and r[0] != r[1]:
                changed += 1
                if table == '0xfdce80cd':
                    print(f'camera {nm(kk)}: {r[0]} -> {r[1]}')
    print(f'{changed} values changed ({len(PHYSICS)} physics tables, {len(CAMERAS)} cameras)')
    if not dry:
        b[start:start + e['size']] = f.d
        open(pabp, 'wb').write(b)


if __name__ == '__main__':
    apply(sys.argv[1], sys.argv[2], sys.argv[3], '--dry' in sys.argv)
