"""THAW's own Create-A-Skater parts on Project 8 PSP (the male skater, PUNK body style).

  p8cas.py <THAW data dir> <P8 cas.pak.psp> <out dir> [--tex 128]

P8 keeps its skater part lists in pak/cas/cas.pak (cas_scripts.qb, loaded once at boot), one set per
body style: cas_punk_hair, cas_punk_torso, ... (the arrays P8's 0x989b60dd builds from a style
prefix and the part name). P8's skater parts are loose models (models/skater_male/*.skin.psp, with a
4-byte .tex.psp beside each). THAW's lists are in pak/CAS/cas_wpc.pak.wpc (skater_m_hair, ...) and
its models sit at the same kind of paths. P8's and THAW's skaters are built the same way (body/arms,
head, hands, bare torso, lower legs, shirt, pants, hair; one skeleton), so THAW's parts take the
PUNK style's place piece for piece:
  - every model is converted (thaw2p8skin.py) and added as a loose file at THAW's own path;
    THAW's texture variants of one mesh ('replace' / 'with') are baked into their own skins
    (models/skater_male/<desc_id>.skin), so nothing depends on P8's run-time texture swap;
  - cas_punk_hair gets THAW's male hair list (the Hollywood barbershop sells all of it),
    cas_punk_torso / cas_punk_legs the shirts and pants THAW's Hollywood clothing store sells,
    and the body pieces (CAS_BODY's punk entries, cas_punk_head, _hands, _bare_torso, _lower_legs)
    THAW's body. P8's own fields stay where THAW has none (head skeletons, the style's flags).
Writes <out>/cas.pak.psp and <out>/files/<archive path> (the loose files); <out>/files.txt lists
them. The new pak is bigger: its pak_sizes_psp entry ('cas', 137,264) has to follow.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import p8qb  # noqa: E402
import pak  # noqa: E402
import qb  # noqa: E402
import thaw2p8skin  # noqa: E402
from pak import qbkey  # noqa: E402

B = chr(92)

# ---- typed QB data (P8 PSP / THAW PC binary .qb): (type, value) trees -------------------------------
# types: 1 int, 2 float, 3 string, 4 local string, 5 pair, 6 vector, 10 struct, 12 array, 13 checksum;
# a struct is [(name key or 0, (type, value))], an array (element type, [values])


def read_typed(d, t, v):
    u = lambda o: struct.unpack_from('<I', d, o)[0]  # noqa: E731
    if t in (1, 2, 13):
        return v
    if t in (3, 4):
        return d[v:d.index(b'\0', v)]
    if t in (5, 6):
        n = 2 if t == 5 else 3
        return d[v + 4:v + 4 + 4 * n]
    if t == 7:  # a script inside a struct: raw tokens of unknown length; such entries are not re-encoded
        return ('script', v)
    if t == 10:
        out, p = [], u(v + 4)
        while p:
            ft = d[p + 1] >> 1
            out.append((u(p + 4), (ft, read_typed(d, ft, u(p + 8)))))
            p = u(p + 12)
        return out
    if t == 12:
        et, n = d[v + 2], u(v + 4)
        if n == 0:
            return (0, [])
        base = v + 8 if n == 1 else u(v + 8)
        return (et, [read_typed(d, et, u(base + 4 * i)) for i in range(n)])
    raise ValueError(f'type {t}')


def pad4(b):
    return b + bytes(-len(b) % 4)


def encode_typed(t, val, at):
    """(word for the value slot, data bytes placed at file offset at)."""
    if t in (1, 2, 13):
        return val, b''
    if t in (3, 4):
        return at, pad4(val + b'\0')
    if t in (5, 6):
        return at, bytes((0, 1, 0, 0)) + val
    if t == 10:
        data = bytearray(struct.pack('<II', 0x00010000, at + 8 if val else 0))
        for i, (k, (ft, fv)) in enumerate(val):
            fpos = at + len(data)
            word, extra = encode_typed(ft, fv, fpos + 16)
            nxt = 0 if i == len(val) - 1 else fpos + 16 + len(extra)
            data += struct.pack('<BBBBIII', 0, ft << 1 | 1, 0, 0, k, word, nxt) + extra
        return at, bytes(data)
    if t == 12:
        et, items = val
        n = len(items)
        if n == 0:
            return at, struct.pack('<4BII', 0, 1, 0, 0, 0, 0)
        if n == 1:
            word, extra = encode_typed(et, items[0], at + 12)
            return at, struct.pack('<4BII', 0, 1, et, 0, 1, word) + extra
        data = bytearray(struct.pack('<4BII', 0, 1, et, 0, n, at + 12)) + bytes(4 * n)
        for i, it in enumerate(items):
            word, extra = encode_typed(et, it, at + len(data))
            struct.pack_into('<I', data, 12 + 4 * i, word)
            data += extra
        return at, bytes(data)
    raise ValueError(f'type {t}')


def globals_of(d):
    """{name key: (item offset, type, value offset, end of its data)}"""
    _, items = p8qb.pointer_sites(d)
    out = {}
    for i, (p, t, k, v) in enumerate(items):
        end = items[i + 1][0] if i + 1 < len(items) else struct.unpack_from('<I', d, 4)[0]
        out[k] = (p, t, v, end)
    return out


def set_global(d, key, t, val):
    """d with the value of top-level global key (an array or struct) replaced, offsets moved."""
    p, ot, v, end = globals_of(d)[key]
    assert ot == t, (hex(key), ot, t)
    _, data = encode_typed(t, val, v)
    return p8qb.resize(d, v, end - v, data)


def get_global(d, key):
    p, t, v, end = globals_of(d)[key]
    return t, read_typed(d, t, v)


# ---- THAW's lists ----------------------------------------------------------------------------------


def thaw_lists(data_dir):
    pd = open(os.path.join(data_dir, 'pak', 'CAS', 'cas_wpc.pak.wpc'), 'rb').read()
    e = pak.read_entries(pd)[0][0]
    d = pd[e['offset']:e['offset'] + e['size']]
    out = {}
    for p, t, k, v, end in ((p, t, k, v, end) for k, (p, t, v, end) in globals_of(d).items()):
        if t in (10, 12):
            out[k] = read_typed(d, t, v)
    return out


def field(ent, name, default=None):
    k = qbkey(name)
    for fk, (ft, fv) in ent:
        if fk == k:
            return fv
    return default


def flags(ent):
    return {fv for fk, (ft, fv) in ent if fk == 0 and ft == 13}


def store_flags(ent):
    v = field(ent, 'store_flags')
    return {x for x in v[1]} if v else set()


K = qbkey
HO_BARBER, HO_CLOTHING = K('Z_HO_BarberShop'), K('z_ho_clothingshop')
STR, LSTR, KEY, ARR, STRUCT, INT = 3, 4, 13, 12, 10, 1


class Builder:
    def __init__(self, data_dir, out, tex):
        self.data, self.out, self.tex = data_dir, out, tex
        self.files = {}  # archive path -> local file
        self.thaw_models = {}
        for root, _, fs in os.walk(os.path.join(data_dir, 'models')):
            for f in fs:
                if f.lower().endswith('.skin.wpc'):
                    full = os.path.join(root, f)
                    self.thaw_models[os.path.relpath(full, data_dir).replace(B, '/').lower()[:-4]] = full
        self.thaw_images = {}
        for root, _, fs in os.walk(os.path.join(data_dir, 'textures')):
            for f in fs:
                if f.lower().endswith('.img.wpc'):
                    full = os.path.join(root, f)
                    self.thaw_images[os.path.relpath(full, data_dir).replace(B, '/').lower()[:-8]] = full

    def model(self, mesh, retex=None, as_path=None):
        """Converts THAW's mesh (a 'models/.../x.skin' path), with textures replaced
        ({png name: 'textures/.../y.png'}), to the loose file as_path (default: the mesh's own path).
        Returns the path the part list names, or None if THAW lacks the model."""
        src = self.thaw_models.get(mesh.lower())
        if not src:
            print(f'  no THAW model {mesh}')
            return None
        path = (as_path or mesh)
        arch = B + path.replace('/', B).lower() + '.psp'
        if arch not in self.files:
            rt = {}
            for name, img in (retex or {}).items():
                f = self.thaw_images.get(img.lower().rsplit('.', 1)[0])
                if f:
                    rt[qbkey(name)] = f
                else:
                    print(f'  no THAW image {img}')
            local = os.path.join(self.out, 'files', arch.strip(B))
            os.makedirs(os.path.dirname(local), exist_ok=True)
            thaw2p8skin.convert(src, local, os.path.basename(local), self.tex, 8, (), rt)
            self.files[arch] = local
            stub = local[:-len('.skin.psp')] + '.tex.psp'
            open(stub, 'wb').write(bytes(4))  # P8's skater parts carry an empty 4-byte .tex.psp
            self.files[arch[:-len('.skin.psp')] + '.tex.psp'] = stub
        return path

    def part(self, ent, keep=(), extra_flags=()):
        """A THAW part entry as a P8 one: desc_id, frontend_desc, the model (texture variants baked),
        default colour; keep = P8 fields to carry over [(key, (type, value))]."""
        desc = field(ent, 'desc_id')
        out = [(K('desc_id'), (KEY, desc))]
        fd = field(ent, 'frontend_desc')
        if fd is not None:
            out.append((K('frontend_desc'), (STR, fd.strip())))
        mesh = field(ent, 'mesh')
        if mesh is not None:
            mesh = mesh.decode('latin-1')
            retex = {}
            for a, b in (('replace', 'with'), ('replace2', 'with2'), ('replace3', 'with3')):
                r, w = field(ent, a), field(ent, b)
                if r is not None and w is not None:
                    retex[r.decode('latin-1')] = w.decode('latin-1')
            as_path = None
            if retex:
                name = qb.nm(desc) if qb.nm(desc)[:2] != '0x' else '%08x' % desc
                as_path = mesh.rsplit('/', 1)[0] + '/' + name.replace(' ', '_') + '.skin'
                if as_path.lower() in self.thaw_models:  # never over a real model of that name
                    as_path = mesh.rsplit('/', 1)[0] + '/v_' + name.replace(' ', '_') + '.skin'
            path = self.model(mesh, retex, as_path)
            if path is None:
                return None
            out.append((K('mesh'), (LSTR, path.encode('latin-1'))))
        h, s, v = (field(ent, 'default_' + c) for c in 'hsv')
        if h is not None:  # P8: 0xa3db78cb = [{ h s v }]
            out.append((0xa3db78cb, (ARR, (STRUCT, [[(K('h'), (INT, h)), (K('s'), (INT, s)), (K('v'), (INT, v))]]))))
        out += list(keep)
        have = flags(ent)
        for f in sorted(have | set(extra_flags)):
            if f in (K('hidden'), *extra_flags):
                out.append((0, (KEY, f)))
        return out


def common_flags(arr):
    """Flags every meshed entry of a P8 list carries (the style's own, e.g. 0xe3787efa on hair)."""
    meshed = [e for e in arr if field(e, 'mesh') is not None]
    return set.intersection(*(flags(e) for e in meshed)) if meshed else set()


def p8_field(ent, key):
    return [(fk, fv) for fk, fv in ent if fk == key]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('thaw_data')
    ap.add_argument('cas_pak')
    ap.add_argument('out')
    ap.add_argument('--tex', type=int, default=128)
    a = ap.parse_args()
    qb.load_names(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'extracted', 'dbg'))
    os.makedirs(a.out, exist_ok=True)
    pd = open(a.cas_pak, 'rb').read()
    e = pak.read_entries(pd)[0][0]
    d = pd[e['offset']:e['offset'] + e['size']]
    T = thaw_lists(a.thaw_data)
    bld = Builder(a.thaw_data, a.out, a.tex)
    lst = lambda name: T[K(name)][1]  # noqa: E731

    sold = {}  # P8 list -> THAW desc_ids now in it

    def replace_list(p8name, entries, keep_first=True, flag_if=None, append=False):
        """flag_if: {P8 flag: THAW flags that call for it}; append: keep all of P8's entries (a list
        other styles share) and add THAW's after them"""
        nonlocal d
        t, (et, old) = get_global(d, K(p8name))
        cf = common_flags(old)
        new = list(old) if append else [old[0]] if keep_first else []
        for ent in entries:
            ef = set(cf) if field(ent, 'mesh') is not None else set()
            ef |= {f for f, need in (flag_if or {}).items() if flags(ent) & {K(n) for n in need}}
            p = bld.part(ent, extra_flags=ef)
            if p:
                new.append(p)
                sold.setdefault(p8name, set()).add(field(ent, 'desc_id'))
        d = set_global(d, K(p8name), 12, (10, new))
        print(f'{p8name}: {len(old)} -> {len(new)} entries')

    # hair: THAW's male list (Bald first, as in P8's own); the barbershop sells all of it
    hair = [x for x in lst('skater_m_hair') if field(x, 'mesh') is not None]
    replace_list('cas_punk_hair', hair)
    # shirts and pants THAW's Hollywood clothing store sells, P8's 'none' entry first; shorts (THAW's
    # force_lower_legs_calves / _rip) get the flag P8's own shorts carry (0x9b421c33: the bare lower
    # legs show)
    replace_list('cas_punk_torso', [x for x in lst('skater_m_torso') if HO_CLOTHING in store_flags(x)])
    replace_list('cas_punk_legs', [x for x in lst('skater_m_legs') if HO_CLOTHING in store_flags(x)],
                 flag_if={0x9b421c33: ('force_lower_legs_calves', 'force_lower_legs_rip')})
    shorts = {field(x, 'desc_id') for x in lst('skater_m_legs')
              if flags(x) & {K('force_lower_legs_calves'), K('force_lower_legs_rip')}}
    # socks and shoes: P8's PUNK socks and P8's shoes are shaped for P8's legs and float around THAW's
    # calves. The PUNK socks list becomes THAW's male socks; the shoes list is shared by every style,
    # so it keeps P8's and gains the THAW shoes the three presets below wear
    presets = ('appearance_custom_skater_male_01', 'appearance_custom_skater_male_02',
               'appearance_custom_skater_male_03')
    replace_list('cas_punk_socks', [x for x in lst('socks') if b'skater_male' in (field(x, 'mesh') or b'')])
    worn = {field(dict(T[K(a)])[K('shoes')][1], 'desc_id') for a in presets if K('shoes') in dict(T[K(a)])}
    replace_list('cas_shoes', [x for x in lst('shoes') if field(x, 'desc_id') in worn], append=True)

    # P8's three PUNK presets (0xee5fffac is the style's default appearance, skater_helpers 0xa58cd6ef)
    # become THAW's default custom skaters 1-3: hair, shirt, pants, socks and shoes with their colours, no
    # P8 scalp; the lower legs show under shorts
    for p8app, thawapp in zip((0xee5fffac, 0x7756ae16, 0x00519e80), presets):
        t, app = get_global(d, p8app)
        tapp = dict(T[K(thawapp)])
        new = []
        for pk, (pt, pv) in app:
            for p8name, thawname in (('cas_punk_hair', 'skater_m_hair'), ('cas_punk_torso', 'skater_m_torso'),
                                     ('cas_punk_legs', 'skater_m_legs'), ('cas_punk_socks', 'socks'),
                                     ('cas_shoes', 'shoes')):
                if pk == K(p8name) and K(thawname) in tapp:
                    tv = tapp[K(thawname)][1]
                    if field(tv, 'desc_id') in sold[p8name]:
                        pv = tv
                    elif field(tv, 'desc_id') == K('none'):  # THAW wears none (no socks)
                        pv = [(K('desc_id'), (KEY, K('none')))]
            if pk == K('cas_punk_scalp'):  # P8's scalp piece pokes through THAW's hair; THAW's head has its own
                pv = [(K('desc_id'), (KEY, K('none')))]
            new.append((pk, (pt, pv)))
        legs = dict(new).get(K('cas_punk_legs'))
        bare = legs is not None and field(legs[1], 'desc_id') in shorts
        new = [(pk, (pt, [(K('desc_id'), (KEY, 0x7018d991 if bare else K('none')))]))
               if pk == K('cas_punk_lower_legs') else (pk, (pt, pv)) for pk, (pt, pv) in new]
        d = set_global(d, p8app, 10, new)
        print(f'{qb.nm(p8app)} <- {thawapp}')

    # body pieces: P8's entries keep their ids and fields, their models become THAW's (variants dropped:
    # P8's skin-tone textures do not exist on THAW's models)
    def repoint(p8name, mesh, only=None):
        nonlocal d
        t, (et, old) = get_global(d, K(p8name))
        path = bld.model(mesh)
        new = []
        for ent in old:
            m = field(ent, 'mesh')
            if m is not None and (only is None or only in m.decode('latin-1').lower()):
                ent = [(fk, (LSTR, path.encode('latin-1'))) if fk == K('mesh') else (fk, fv) for fk, fv in ent
                       if fk not in [K(x) for x in ('replace', 'with', 'replace2', 'with2', 'replace3', 'with3')]]
            new.append(ent)
        d = set_global(d, K(p8name), 12, (et, new))
        print(f'{p8name}: models -> {path}')

    repoint('CAS_BODY', 'models/skater_male/Body_M_Arms.skin', only='punk_body_arms01')
    repoint('cas_punk_head', 'models/skater_male/Body_M_Head.skin')
    repoint('cas_punk_hands', 'models/skater_male/Body_M_Hands.skin')
    repoint('cas_punk_bare_torso', 'models/skater_male/Body_M_Torso.skin')
    repoint('cas_punk_lower_legs', 'models/skater_male/Body_M_Calves.skin')

    pd = bytearray(pd[:e['offset']]) + d
    struct.pack_into('<I', pd, e['entry_pos'] + 8, len(d))
    pd += bytes(-len(pd) % 16)
    open(os.path.join(a.out, 'cas.pak.psp'), 'wb').write(pd)
    with open(os.path.join(a.out, 'files.txt'), 'w') as f:
        for arch, local in sorted(bld.files.items()):
            f.write(f'{arch}\t{local}\n')
    total = sum(os.path.getsize(x) for x in bld.files.values())
    print(f'cas.pak.psp {len(pd)} bytes; {len(bld.files)} loose files, {total} bytes')


if __name__ == '__main__':
    main()
