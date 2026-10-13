"""A zone ped pak (worlds\\worldzones\\<zone>\\<zone>ped.pak.psp) holding the parts of given ped profiles.

  p8pedpak.py <qb.pak.psp> <qb.pab.psp> <datap.hed> <datap.wad> <template ped pak> <out> <profile> ...
             [--also <datap.hed> <datap.wad>]   (another archive to take parts from: Project Mod's)

P8 loads a level's ped pak into the PedParts heap at level load; a ped can only be built from parts in
it (a profile whose parts are missing crashes ped creation, 0x088b2670). Each part is two entries:
the model (.skin, key qbkey(<mesh path>)) and its texture stub (.stex, key qbkey(<mesh path less
.skin>.tex)), the mesh path as P8's part lists give it (cas_ped_m / cas_ped_f desc_id -> mesh).
Parts are taken from P8's own zone ped paks, or from the loose models in datap
(models\\...\\<name>.skin.psp and .tex.psp). The template supplies the entry header layout.
Prints the pak's size: the PedParts heap must hold it.
"""
import os
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))
import hed  # noqa: E402
import pak  # noqa: E402
import qb  # noqa: E402

SKIN, STEX = 0x8fa2a3ef, 0x0  # filled from the template


def items(pakp, pabp, fname):
    p, b = open(pakp, 'rb').read(), open(pabp, 'rb').read()
    e = next(e for e in pak.read_entries(p)[0] if (e['name'] or '').lower().endswith(fname))
    return qb.QB(b[e['offset'] - len(p):e['offset'] - len(p) + e['size']]).items()


def part_meshes(pakp, pabp, profiles):
    """{profile: [mesh path]} from profile_ped and the cas_ped part lists."""
    B = chr(92)
    meshes = {}
    for fn in ('cas_ped_m.qb.psp', 'cas_ped_f.qb.psp'):
        for k, v in items(pakp, pabp, 'scripts' + B + fn):
            if isinstance(v, list):
                for ent in v:
                    if isinstance(ent, list):
                        d = dict(x for x in ent if isinstance(x, tuple) and x[0])
                        if d.get('desc_id') and d.get('mesh'):
                            meshes[d['desc_id']] = d['mesh']
    prof = dict(items(pakp, pabp, 'scripts' + B + 'profile_ped.qb.psp'))
    out = {}
    for name in profiles:
        v = prof.get(name) or prof.get('0x%08x' % pak.qbkey(name))
        if v is None:
            raise SystemExit(f'{name}: no such profile')
        out[name] = []
        for k, pv in v:
            if isinstance(pv, list):
                d = dict(x for x in pv if isinstance(x, tuple))
                if 'desc_id' in d:
                    if d['desc_id'] not in meshes:
                        raise SystemExit(f'{name}: part {d["desc_id"]} has no mesh in cas_ped_m/f')
                    out[name].append(meshes[d['desc_id']])
    return out


def build(pakp, pabp, hedp, wadp, template, out, profiles, also=()):
    B = chr(92)
    want = part_meshes(pakp, pabp, profiles)
    tmpl, tblob = open(template, 'rb').read(), None
    tents, _ = pak.read_entries(tmpl)
    hdr_of = {e['type']: tmpl[e['entry_pos']:e['entry_pos'] + 0x20] for e in tents}
    skin_t = next(t for t in hdr_of if pak.EXT.get(t) == '.skin')
    stex_t = next(t for t in hdr_of if pak.EXT.get(t) == '.stex')
    # every part in P8's own ped paks, by key
    found = {}
    tmp = tempfile.mkdtemp(prefix='pedpak_')
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'hed.py'), 'extract', hedp, wadp, tmp,
                    '--sectors', '--match', 'ped.pak.psp'], check=True, capture_output=True)
    for root, _, files in os.walk(tmp):
        for f in files:
            d = open(os.path.join(root, f), 'rb').read()
            for e in pak.read_entries(d)[0]:
                found.setdefault(e['pakkey'], d[e['offset']:e['offset'] + e['size']])
    loose = {}
    for h, w in reversed([(hedp, wadp), *also]):  # the first archive wins
        loose.update({n.lower(): (w, o, s) for n, o, s in hed.read_hed(h, sectors=True)})
    entries, missing = [], []
    for name, meshes in want.items():
        for m in meshes:
            ks, kt = pak.qbkey(m), pak.qbkey(m[:-len('.skin')] + '.tex')
            if any(e[1] == ks for e in entries):
                continue
            skin, stex = found.get(ks), found.get(kt)
            if skin is None:
                path = B + m.replace('/', B).lower() + '.psp'
                if path in loose:
                    wp, o, s = loose[path]
                    with open(wp, 'rb') as w:
                        w.seek(o)
                        skin = w.read(s)
                    tpath = path[:-len('.skin.psp')] + '.tex.psp'
                    if tpath in loose:
                        wp, o, s = loose[tpath]
                        with open(wp, 'rb') as w:
                            w.seek(o)
                            stex = w.read(s)
            if skin is None:
                missing.append(f'{name}: {m}')
                continue
            entries.append((stex_t, kt, stex if stex is not None else bytes(4), 0))
            entries.append((skin_t, ks, skin, kt))  # a .skin's parent field is its .stex's key
    if missing:
        raise SystemExit('parts not on the disc: ' + '; '.join(missing))
    hdr = bytearray()
    for t, k, d, parent in entries:
        h = bytearray(hdr_of[t])
        struct.pack_into('<I', h, 12, k)
        struct.pack_into('<I', h, 24, parent)
        hdr += h
    # the template's end entry (type 0xb524565f, a 4-byte block at the end of the file) and padding
    _, tend = pak.read_entries(tmpl)
    first = min(e['offset'] for e in tents)
    end_at = len(hdr)
    hdr += tmpl[tend:first]
    tail = tmpl[tend + struct.unpack_from('<I', tmpl, tend + 4)[0]:][:struct.unpack_from('<I', tmpl, tend + 8)[0]]
    data = bytearray(hdr)
    for i, (t, k, d, parent) in enumerate(entries):
        data += bytes(-len(data) % 16)
        struct.pack_into('<II', data, i * 0x20 + 4, len(data) - i * 0x20, len(d))
        data += d
    data += bytes(-len(data) % 16)
    struct.pack_into('<I', data, end_at + 4, len(data) - end_at)
    data += tail
    data += bytes(-len(data) % 16)
    open(out, 'wb').write(data)
    print(f'{out}: {len(entries) // 2} parts for {len(profiles)} profiles, {len(data):,} bytes')
    return len(data)


if __name__ == '__main__':
    qb.load_names(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'extracted', 'dbg'))
    args = sys.argv[1:]
    also = []
    while '--also' in args:
        i = args.index('--also')
        also.append((args[i + 1], args[i + 2]))
        del args[i:i + 3]
    build(*args[:6], args[6:], also)
