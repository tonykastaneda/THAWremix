"""A THAW zone in a Project 8 PSP (Tony Hawk's Project Mod) zone slot.

  p8zone.py <THAW PS2 data dir> <zone> <slot zone .pak.psp> <converted .psp_level> <outdir> [--slot z_sc] [--template <zone of the pak>]

P8 PSP is THAW's engine generation: its zone pak holds THAW's own formats (v10 collision, THAW QB
node array and scripts), and its render geometry is the Remix-style v11 .psp_level that
tools/thaw2psp.py writes. Built here, on the slot zone's pak (its sounds and other entries kept):

  .geom  the sector list, one record per .psp_level box (see write_geom)
  .col   THAW's collision, as is
  .nqb   THAW's <zone>.qb node array
  .sqb   THAW's <zone>_scripts.qb, .qb THAW's <zone>_peds.qb, .gap THAW's gap list

The engine finds a zone's node array (and its sorted name/index tables), Setup and Goals scripts by
the zone's own name, so those keys are renamed to the slot's; every other name stays THAW's.
Writes <slot>.pak.psp and <slot>.psp_level.
"""
import argparse
import os
import shutil
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import pak  # noqa: E402
import psplevel  # noqa: E402
import qb  # noqa: E402
from pak import qbkey  # noqa: E402

# keys the engine derives from the zone name
ZONE_KEYS = ('NodeArray', 'NodeArray_SortedNames', 'NodeArray_SortedIndices', 'Setup', 'Goals')
GEOM_HEADER = 0x64      # file header, then records linked from the word at 0x34 (offsets are +0x10)
GEOM_RECORD = 0x50
SECTOR_FLAGS = 0xFF00FF00  # the common value in P8's own zones (0xFFC0FF00 and 0xFF01FF00 also seen)


def box_points(lvl):
    pts = {}
    for first, vert in lvl.passes():
        for mat, box, off, count, stride in lvl.strips(first, vert):
            pts.setdefault(box, []).extend(lvl.vertex(off + j * stride, stride)[0] for j in range(count))
    return pts


def write_geom(lvl, header):
    """Sector records: centre xyz, radius, half extents xyz (world inches, as psplevel.vertex gives),
    5, -1, -1, next record (-0x10; -1 ends), 0, sector name, 0, -1, 0x80808080, flags, 0, 1e7, -1."""
    names = struct.unpack_from(f'<{lvl.n_boxes}I', lvl.data, lvl.boxnames)
    pts = box_points(lvl)
    out = bytearray(header[:GEOM_HEADER])
    struct.pack_into('<I', out, 0x34, GEOM_HEADER - 0x10)
    for i, name in enumerate(names):
        if i in pts:
            a = np.array(pts[i])
            lo, hi = a.min(0), a.max(0)
            c = (lo + hi) / 2
            r = float(np.sqrt(((a - c) ** 2).sum(1)).max())
            half = (hi - lo) / 2
        else:
            c, r, half = np.zeros(3), 0.0, np.zeros(3)
        nxt = len(out) + GEOM_RECORD - 0x10 if i + 1 < len(names) else 0xFFFFFFFF
        out += struct.pack('<7f', *c, r, *half)
        out += struct.pack('<6I', 5, 0xFFFFFFFF, 0xFFFFFFFF, nxt, 0, name)
        out += struct.pack('<5IfI', 0, 0xFFFFFFFF, 0x80808080, SECTOR_FLAGS, 0, 1e7, 0xFFFFFFFF)
    return bytes(out)


def read_geom(d):
    recs, p = [], struct.unpack_from('<I', d, 0x34)[0] + 0x10
    while True:
        fl = struct.unpack_from('<7f', d, p)
        nxt, _, name = struct.unpack_from('<3I', d, p + 0x28)
        recs.append((name, fl, d[p + 0x34:p + 0x50]))
        if nxt == 0xFFFFFFFF:
            return recs
        p = nxt + 0x10


# compass blip types P8's compass_bliptypes has (compass.qb); a node naming another type makes the
# compass read a non-struct as one (a crash). THAW's shop types become P8's skateshop, the rest goal.
P8_BLIPS = {'goal_important', 'goal', 'bonus_goal', 'skateshop', 'transition_unlocked'}
BLIP_FALLBACK = {'barbershop': 'skateshop', 'cas': 'skateshop'}
THAW_BLIPS = ('cash', 'bike_training', 'tagger', 'bus', 'bike', 'CAT', 'barbershop', 'cas')


def fix_blips(data):
    """Rewrites unknown CompassBlipType values; a struct field is [type word][name][value][next]."""
    data = bytearray(data)
    key = struct.pack('<I', qbkey('CompassBlipType'))
    bad = {qbkey(n): qbkey(BLIP_FALLBACK.get(n, 'goal')) for n in THAW_BLIPS if n not in P8_BLIPS}
    i, fixed = data.find(key), 0
    while i >= 0:
        v = struct.unpack_from('<I', data, i + 4)[0]
        if v in bad:
            struct.pack_into('<I', data, i + 4, bad[v])
            fixed += 1
        i = data.find(key, i + 1)
    return bytes(data), fixed


def top_items(data):
    """{key: (type, value word)} of a QB file's top-level items."""
    q, out, p = qb.QB(data), {}, 0x1C
    while p + 0x14 <= q.u32(4):
        t = data[p + 2]
        idk, _, v, _ = struct.unpack_from('<4I', data, p + 4)
        q.hi = p + 0x14
        if t == 7:
            q.touch(v + 12 + q.u32(v + 8))
        else:
            q.value(t, v)
        out[idk] = (t, v)
        p = (q.hi + 3) & ~3
    return out


# THAW's peds and traffic name its own models and ped profiles, which P8 lacks; spawned, a ped's
# instance request comes back empty (a crash). Not created at start, they stay in the node array.
# On vanilla P8 GameObject, LevelObject and LevelLight must go too (--no-spawn): the converted
# .psp_level has no level objects (nObjs 0) for them to attach to.
NO_SPAWN = ('Pedestrian', 'Vehicle')


def unspawn(data, zone, no_spawn=NO_SPAWN):
    """Turns CreatedAtStart into AbsentInNetGames (inert offline) in the node array's ped and vehicle
    structs and in the compressed shared structs that give a node those classes. A struct is
    [?][first field]; a field is [type word][name][value][next]. Fields stay linked: P8's loader
    reads a struct's fields in file order, so an unlinked one derails it."""
    data = bytearray(data)
    u = lambda o: struct.unpack_from('<I', data, o)[0]  # noqa: E731
    items = top_items(bytes(data))
    shared = {k: v for k, (t, v) in items.items() if t == 10}
    arr = items[qbkey(f'{zone}_NodeArray')][1]
    n, base = u(arr + 4), u(arr + 8)
    cls_key, type_key, cas = qbkey('Class'), qbkey('Type'), qbkey('CreatedAtStart')
    # entries are a class, or class:type for one type of it (e.g. GameObject:Ghost)
    classes = {(qbkey(c.split(':')[0]), qbkey(c.split(':')[1]) if ':' in c else None) for c in no_spawn}
    structs = set()
    for i in range(n):
        s = u(base + 4 * i)
        structs.add(s)
        f = u(s + 4)
        while f:
            if u(f + 4) == 0 and u(f + 8) in shared:
                structs.add(shared[u(f + 8)])
            f = u(f + 12)
    fixed = 0
    for s in structs:
        f, fields = u(s + 4), []
        while f:
            fields.append(f)
            f = u(f + 12)
        cls = next((u(f + 8) for f in fields if u(f + 4) == cls_key), None)
        typ = next((u(f + 8) for f in fields if u(f + 4) == type_key), None)
        if (cls, None) not in classes and (cls, typ) not in classes:
            continue
        for f in fields:
            if u(f + 4) == 0 and u(f + 8) == cas:
                struct.pack_into('<I', data, f + 8, qbkey('AbsentInNetGames'))
                fixed += 1
    return bytes(data), fixed


def rename(data, renames):
    for old, new in renames.items():
        data = data.replace(struct.pack('<I', old), struct.pack('<I', new))
    return data


def load_pak(path):
    hdr = open(path, 'rb').read()
    ents, _ = pak.read_entries(hdr)
    pab = path.replace('.pak.', '.pab.')
    blob = hdr + (open(pab, 'rb').read() if os.path.exists(pab) else b'')
    return ents, blob


def write_pak(slot_path, payloads, drop=()):
    """The slot pak with entry i's data replaced by payloads[i] and the entries in drop left out;
    data re-laid 16-aligned after the header, in the original order."""
    hdr = open(slot_path, 'rb').read()
    ents, end = pak.read_entries(hdr)
    first = min(e['offset'] for e in ents)
    keep = [(i, e) for i, e in enumerate(ents) if i not in drop]
    out, pos = bytearray(), []
    for i, e in keep:
        size = 0xC0 if e['flags'] & 0x20 else 0x20
        pos.append(len(out))
        out += hdr[e['entry_pos']:e['entry_pos'] + size]
    out += hdr[end:first]  # the end entry and padding
    for (i, e), p in zip(keep, pos):
        d = payloads.get(i, hdr[e['offset']:e['offset'] + e['size']])
        out += bytes(-len(out) % 16)
        struct.pack_into('<II', out, p + 4, len(out) - p, len(d))
        out += d
    out += bytes(-len(out) % 16)
    return bytes(out)


# the template zone's own props: models, their textures, skeletons, animations, object scripts and
# particles; they belong to the template's nodes (Houses' playground), not the zone put in its place
TEMPLATE_PROPS = {'.mdl', '.stex', '.ske', '.ska', '.pfx', '4bc1e85e', '6290993b', '91e1028d'}


# entries of a zone pak whose key is qbkey('worlds\worldzones\<zone>\<zone><suffix>') (the entry
# path less .psp); the named ones also carry that path, plus .psp, as their name
ZONE_SUFFIXES = ('.geom', '.col', '.gap', '.tex', '.pfx', '.scn', '.qb', '_scripts.qb', '_peds.qb',
                 '_sfx_dat_psp.qb', '_sfx_scripts.qb')


def retarget(data, old, new):
    """Moves a zone pak built from zone <old>'s pak over to zone <new>: entry names, and every key
    field (pak key, full key, name key) holding a key of the zone's paths. Shipped paks key on the
    path less .psp; the Project Mod's own on the path with .psp, and give unnamed entries the zone's
    base path (worlds\\worldzones\\<zone>\\<zone>) as name key. All of those forms are mapped."""
    data = bytearray(data)
    ents, _ = pak.read_entries(bytes(data))
    path = lambda z, s: f'worlds\\worldzones\\{z}\\{z}{s}'  # noqa: E731
    keys = {}
    for s in ZONE_SUFFIXES + ('',):
        for tail in ('', '.psp'):
            keys[qbkey(path(old, s) + tail)] = qbkey(path(new, s) + tail)
    bare = lambda n: n[:-4] if n.lower().endswith('.psp') else n  # noqa: E731
    for e in ents:
        if e['name'] and e['name'].lower().startswith(path(old, '').lower()):
            name = path(new, e['name'][len(path(old, '')):])
            data[e['entry_pos'] + 0x20:e['entry_pos'] + 0x20 + 160] = name.encode('latin-1').ljust(160, b'\0')
            keys[qbkey(e['name'])] = qbkey(name)  # the entry's own path keys, whatever its suffix
            keys[qbkey(bare(e['name']))] = qbkey(bare(name))
    moved = 0
    for e in ents:
        for field in (12, 16, 20):
            k = struct.unpack_from('<I', data, e['entry_pos'] + field)[0]
            if k in keys:
                struct.pack_into('<I', data, e['entry_pos'] + field, keys[k])
                moved += 1
    return bytes(data), moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('thaw_data')
    ap.add_argument('zone')
    ap.add_argument('slot_pak')
    ap.add_argument('level')
    ap.add_argument('outdir')
    ap.add_argument('--slot', default='z_sc', help='zone the output is for')
    ap.add_argument('--template', help="zone of slot_pak when it is not --slot (e.g. z_houses's pak for a new z_ho)")
    ap.add_argument('--strip', action='store_true', help="leave out the slot pak's own props (TEMPLATE_PROPS)")
    ap.add_argument('--no-peds', action='store_true', help="keep the slot's peds file")
    ap.add_argument('--keep-scripts', action='store_true',
                    help="keep the slot's zone scripts (THAW's crash vanilla P8 as they stand)")
    ap.add_argument('--spawn-peds', action='store_true', help="keep THAW's peds and vehicles CreatedAtStart")
    ap.add_argument('--no-spawn', default=','.join(NO_SPAWN), help='node classes left uncreated (comma list)')
    a = ap.parse_args()
    zone, slot = a.zone.lower(), a.slot.lower()
    tz = (a.template or slot).lower()

    tents, tblob = load_pak(os.path.join(a.thaw_data, 'worlds', 'worldzones', zone, f'{zone}.pak.ps2'))
    sents, sblob = load_pak(a.slot_pak)
    ext = lambda e: pak.EXT.get(e['type'], '%08x' % e['type'])  # noqa: E731

    def thaw(kind, suffix=None):
        """The THAW zone's largest entry of a type (named <zone><suffix>.qb.ps2 when given)."""
        c = [e for e in tents if ext(e) == kind and (suffix is None or (e['name'] or '').lower().endswith(f'{zone}{suffix}.qb.ps2'))]
        e = max(c, key=lambda e: e['size'])
        return tblob[e['offset']:e['offset'] + e['size']]

    renames = {qbkey(f'{zone}_{k}'): qbkey(f'{slot}_{k}') for k in ZONE_KEYS}
    lvl = psplevel.Level(a.level)
    payloads = {}
    for i, e in enumerate(sents):
        k, n = ext(e), (e['name'] or '').lower()
        if k == '.geom':
            payloads[i] = write_geom(lvl, sblob[e['offset']:e['offset'] + e['size']])
        elif k == '.col':
            payloads[i] = thaw('.col')
        elif k == '.nqb' and n.endswith(f'{tz}.qb.psp'):
            payloads[i], fixed = fix_blips(rename(thaw('.nqb', ''), renames))
            print(f'compass blips moved to P8 types: {fixed}')
            if not a.spawn_peds:
                payloads[i], fixed = unspawn(payloads[i], slot, a.no_spawn.split(','))
                print(f'{a.no_spawn} left uncreated: {fixed} CreatedAtStart flags')
        elif k == '.sqb' and n.endswith(f'{tz}_scripts.qb.psp') and not a.keep_scripts:
            payloads[i] = rename(thaw('.sqb', '_scripts'), renames)
        elif k == '.qb' and n.endswith(f'{tz}_peds.qb.psp') and not a.no_peds:
            payloads[i] = thaw('.qb', '_peds')
        elif k == '.gap':
            payloads[i] = thaw('.gap')
    os.makedirs(a.outdir, exist_ok=True)
    drop = {i for i, e in enumerate(sents) if a.strip and ext(e) in TEMPLATE_PROPS}
    if drop:
        print(f'left out {len(drop)} of the slot pak\'s own prop entries')
    out = write_pak(a.slot_pak, payloads, drop)
    if tz != slot:
        out, moved = retarget(out, tz, slot)
        print(f'entries moved from {tz} to {slot}: {moved}')
    open(os.path.join(a.outdir, f'{slot}.pak.psp'), 'wb').write(out)
    shutil.copyfile(a.level, os.path.join(a.outdir, f'{slot}.psp_level'))
    print(f'{slot}.pak.psp: {len(payloads)} entries replaced ({", ".join(ext(sents[i]) for i in sorted(payloads))}); '
          f'{lvl.n_boxes} sectors; renamed {", ".join(ZONE_KEYS)}')


if __name__ == '__main__':
    main()
