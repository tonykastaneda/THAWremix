"""THAW cutscene -> Project 8 PSP cutscene paks.

  p8cut.py <THAW PS2 data> <THAW PC data> <name> <out dir> [--tex 64]

P8 PSP plays cutscenes with THAW's own system and file formats (its level events, e.g.
cf_legarage, have the same paks: <name>_text, psp\\<name>_cam<n> with the animations, psp\\<name>_main
with skeletons, models, textures and scripts). What carries over unchanged:
  .ska  animations: same format (version 0x28, same standardkeyQ/T tables); 1,145 of the 1,240
        skater animations both games ship are byte-identical. THAW's long scenes set flag 0x100.
  .ske  skeletons: same format (thps7_human: 52 bones).
  .qb / .sqb  scripts: THAW PS2's load in P8 (as the zone scripts do).
So the PS2 paks are the source (their camera paks are already cut into memory-sized pieces) and only
the models change, converted from the PC paks (same entries in the same order):
  .skin  thaw2p8skin.build
  .mdl   P8's .mdl: a 0xC0-byte header (model name checksum at 0x94, bounding sphere and box half
         extents in model inches at 0x64) then a rigid skin body (thaw2p8skin.build rigid=True)
  .stex  a 4-byte stub (P8 keeps textures in the model)
  .shd   left out (P8 PSP has none)
Paths change from ps2 to psp (entry names and keys, the camera pak paths in <name>_cam_pak_info);
the scripts' own asset paths are kept (they only name pak entries by checksum).
Writes <out>/cutscenes/<name>/... and <out>/files.txt (hed path, file) for the build, and
<out>/sizes.txt for

  p8cut.py sizes <qb.pak.psp> <qb.pab.psp> <sizes.txt> ...

which adds the paks to pak_sizes_psp (PlayCutscene reserves their memory from it).
"""
import argparse
import os
import re
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import pak  # noqa: E402
import qb  # noqa: E402
import thaw2p8skin  # noqa: E402
import thawscene as ts  # noqa: E402

B = chr(92)
SKIN, MDL, STEX, SHD, QB, SQB = 0x64112e85, 0x9bcc234d, 0x2b0a3095, 0x2f1a6a09, 0xa7f505c4, 0x5d796624


def find_dir(root, name):
    """root's entry named name, any case."""
    for n in os.listdir(root):
        if n.lower() == name.lower():
            return os.path.join(root, n)
    raise FileNotFoundError(os.path.join(root, name))


def script_strings(d):
    """Every quoted string in a qb's scripts (decompressed)."""
    out = []
    for _, v in qb.QB(d).items():
        if isinstance(v, tuple) and v[0] == 'script':
            off, usz, csz = v[1], v[2], v[3]
            code = ts.lzss(d[off:off + csz], usz) if csz < usz else d[off:off + csz]
            out += [m.decode('latin-1') for m in re.findall(rb'cutscenes[^\x00"]+', code)]
    return out


def mdl_header(meshes, name):
    pos = np.array([p for m in meshes for p in m['pos']] or [(0.0, 0.0, 0.0)])
    lo, hi = pos.min(0), pos.max(0)
    c = (lo + hi) / 2
    r = float(np.linalg.norm(pos - c, axis=1).max())
    h = struct.pack('<8I', 16, 16, 0, 0xC0, 4, 0, 0, 0) + struct.pack('<4I', *[0x7149F2CA] * 4)
    h += struct.pack('<13I', 1, 0x54, 0xFFFFFFFF, 0xFFFFFFFF, 0, 0x14000008, 0, 0xFFFFFFFF, 0x80808080, 0xFF00FF00,
                     0, 0x4B189680, 0xFFFFFFFF)
    h += struct.pack('<7f', *c, r, *((hi - lo) / 2))
    h += struct.pack('<13I', 5, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0, pak.qbkey(name), 0, 0xFFFFFFFF, 0x80808080,
                     0xFF00FF00, 0, 0x4B189680, 0xFFFFFFFF)
    h += bytes(12)
    assert len(h) == 0xC0
    return h


def model(pc_blob, e, tex_e, name, max_side, rigid):
    d = pc_blob[e['offset']:e['offset'] + e['size']]
    textures = ts.parse_tex(pc_blob[tex_e['offset']:tex_e['offset'] + tex_e['size']]) if tex_e else {}
    materials, textures, meshes = thaw2p8skin.read_thaw_scene(d, textures, rigid=rigid)
    body, info = thaw2p8skin.build(materials, textures, meshes, name + ('.mdl.psp' if rigid else '.skin.psp'),
                                   max_side, rigid=rigid)
    return (mdl_header(meshes, name) + body if rigid else body), info


def write_pak(entries, tail):
    """entries: [(header bytes 0x20 or 0xC0, data)] -> pak bytes (data 16-aligned after the header)."""
    out, pos = bytearray(), []
    for h, _ in entries:
        pos.append(len(out))
        out += h
    out += tail
    for (h, data), p in zip(entries, pos):
        out += bytes(-len(out) % 16)
        struct.pack_into('<II', out, p + 4, len(out) - p, len(data))
        out += data
    out += bytes(-len(out) % 16)
    return bytes(out)


def convert_pak(ps2_path, pc_path, max_side, log):
    hdr = open(ps2_path, 'rb').read()
    ents, end = pak.read_entries(hdr)
    first = min(e['offset'] for e in ents)
    pc_ents, pc_blob = pak.open_pak(pc_path) if pc_path else ([], b'')
    pc_by_key = {(e['type'], e['pakkey']): e for e in pc_ents}
    same_order = [e['type'] for e in pc_ents] == [e['type'] for e in ents]
    strings = [s for e in ents if e['type'] in (QB, SQB) for s in script_strings(hdr[e['offset']:e['offset'] + e['size']])]
    mdl_names = [s.split(B)[-1].rsplit('.', 1)[0] for s in strings if s.lower().endswith('.mdl')]
    skin_names = [s.split(B)[-1].rsplit('.', 1)[0] for s in strings if s.lower().endswith('.skin')]
    out, sizes = [], {}
    n_mdl = n_skin = 0
    for i, e in enumerate(ents):
        hsize = 0xC0 if e['flags'] & 0x20 else 0x20
        h = bytearray(hdr[e['entry_pos']:e['entry_pos'] + hsize])
        data = hdr[e['offset']:e['offset'] + e['size']]
        t = e['type']
        if t == SHD:
            continue
        if e['name']:  # ps2 -> psp: the name and its key (the path less .psp)
            name = e['name'].replace(B + 'ps2' + B, B + 'psp' + B)
            name = name[:-4] + '.psp' if name.lower().endswith('.ps2') else name
            h[0x20:0xC0] = name.encode('latin-1').ljust(160, b'\0')
            struct.pack_into('<I', h, 0x0C, pak.qbkey(name[:-4]))
            if name.lower().endswith('_cam_pak_info.qb.psp'):
                data = data.replace(B.encode() + b'ps2' + B.encode(), B.encode() + b'psp' + B.encode())
        if t in (SKIN, MDL):
            pc = pc_by_key.get((t, e['pakkey'])) or (pc_ents[i] if same_order else None)
            assert pc and pc['type'] == t, f'{ps2_path}: no PC model for entry {i}'
            tex = next((x for x in pc_ents if x['type'] == STEX and x['pakkey'] == pc['parent']), None)
            if t == MDL:
                nm = mdl_names[n_mdl] if n_mdl < len(mdl_names) else f'{e["pakkey"]:08x}'
                n_mdl += 1
            else:
                nm = skin_names[n_skin] if n_skin < len(skin_names) else f'{e["pakkey"]:08x}'
                n_skin += 1
            data, info = model(pc_blob, pc, tex, nm, max_side, t == MDL)
            log(f'  {nm}: {info}')
        elif t == STEX:
            data = bytes(4)
        key = pak.EXT.get(t, '%08x' % t)
        sizes[key] = sizes.get(key, 0) + len(data)
        out.append((bytes(h), data))
    blob = write_pak(out, hdr[end:first])  # the end entry and padding
    log('  ' + ', '.join(f'{k} {v:,}' for k, v in sorted(sizes.items())))
    return blob


def pak_sizes(pakp, pabp, sizes):
    """P8's PlayCutscene sets aside each pak's memory from pak_sizes_psp (scripts\\pak_sizes_psp.qb):
    <name>_main, <name>_text<language suffix> and every camera pak's name, each { Size = bytes }
    (without an entry it reads a null struct and crashes). sizes: {pak name: bytes}, added or
    updated; the file moves to the end of the .pab (its pack entry repointed)."""
    import p8cas
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(bytes(p))
    e = next(e for e in ents if e['name'].lower().endswith(B + 'pak_sizes_psp.qb.psp'))
    start = e['offset'] - len(p)
    d = bytes(b[start:start + e['size']])
    top = pak.qbkey('pak_sizes_psp')
    t, fields = p8cas.get_global(d, top)
    size_key = pak.qbkey('Size')
    have = {k: i for i, (k, _) in enumerate(fields)}
    for name, n in sizes.items():
        ent = (pak.qbkey(name), (10, [(size_key, (1, n))]))
        if ent[0] in have:
            fields[have[ent[0]]] = ent
        else:
            fields.append(ent)
    d = p8cas.set_global(d, top, t, fields)
    b += bytes(-len(b) % 16)
    pos = len(p) + len(b)
    b += d
    struct.pack_into('<II', p, e['entry_pos'] + 4, pos - e['entry_pos'], len(d))
    open(pakp, 'wb').write(p)
    open(pabp, 'wb').write(b)
    print(f'pak_sizes_psp: ' + ', '.join(f'{k} {v:,}' for k, v in sizes.items()))


def main():
    if sys.argv[1:2] == ['sizes']:  # p8cut.py sizes <qb.pak.psp> <qb.pab.psp> <sizes.txt> ...
        sizes = {}
        for f in sys.argv[4:]:
            for line in open(f):
                k, v = line.split()
                sizes[k] = int(v)
        return pak_sizes(sys.argv[2], sys.argv[3], sizes)
    ap = argparse.ArgumentParser()
    ap.add_argument('ps2')
    ap.add_argument('pc')
    ap.add_argument('name')
    ap.add_argument('out')
    ap.add_argument('--tex', type=int, default=64)
    a = ap.parse_args()
    name = a.name.lower()
    ps2 = find_dir(os.path.join(a.ps2, 'cutscenes'), name)
    pc = find_dir(os.path.join(a.pc, 'cutscenes'), name)
    files = []

    def emit(rel, data):
        dst = os.path.join(a.out, rel.replace(B, os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data)
        files.append((B + rel, dst))
        print(f'{B}{rel}: {len(data):,} bytes')

    for f in sorted(os.listdir(ps2)):
        if f.lower().endswith('_text.pak.ps2'):
            emit(f'cutscenes{B}{name}{B}{f[:-4]}.psp', convert_pak(os.path.join(ps2, f), None, a.tex, print))
    for sub in sorted(os.listdir(os.path.join(ps2, 'ps2'))):
        src = os.path.join(ps2, 'ps2', sub, f'{sub}.pak.ps2')
        pcp = os.path.join(pc, 'wpc', sub, f'{sub}.pak.wpc')
        print(f'{sub}:')
        blob = convert_pak(src, pcp if os.path.exists(pcp) else None, a.tex, print)
        emit(f'cutscenes{B}{name}{B}psp{B}{sub}{B}{sub}.pak.psp', blob)
    with open(os.path.join(a.out, 'files.txt'), 'w') as f:
        for rel, dst in files:
            f.write(f'{rel}\t{dst}\n')
    with open(os.path.join(a.out, 'sizes.txt'), 'w') as f:  # pak_sizes_psp entries (p8cut.py sizes)
        for rel, dst in files:
            f.write(f'{os.path.basename(dst)[:-len(".pak.psp")]} {os.path.getsize(dst)}\n')


if __name__ == '__main__':
    main()
