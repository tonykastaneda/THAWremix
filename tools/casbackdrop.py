"""Pre-rendered THAW shop interiors as Create-A-Skater backdrops on Remix.

  casbackdrop.py render <THAW install> <outdir> [yaw offsets in degrees ...]

THAW's barber shop is its own streamed zone (z_ho_barbershop) and its Hollywood clothing store sits
inside z_ho (the g_c_ho_* pieces); Remix has neither. Each room is rendered here, from THAW's own
geometry and textures, with the camera Remix's CAS uses (cas_setup_rotating_camera, full body:
position (-60, 60, 80) and target (-40, 45, 0) from the skater, turned with the skater) placed on
THAW's own CAS spot in the shop (the *_Edit restart node), at Remix's widescreen field of view
(88.18 degrees across, 480x272). The renderer is a small z-buffered rasteriser: perspective-correct
UVs, THAW's vertex colours (0x80 = 1), alpha test for cut-outs, translucent pieces blended last.
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import thawscene  # noqa: E402
from thaw2psp import classify  # noqa: E402

W, H, SS = 480, 272, 2
HFOV = np.radians(88.18)
CAS_CAM, CAS_LOOK = np.array([-60.0, 60, 80]), np.array([-40.0, 45, 0])

SHOPS = {
    # name: (zone, restart node for the skater's spot, filter box (lo, hi) or None)
    'barber': ('z_ho_barbershop', 'Z_HO_TRG_Restart_BarberShop_Edit', None),
    'clothing': ('z_ho', 'Z_HO_TRG_Restart_CASShop_Edit',
                 (np.array([-4800.0, -200, -3750]), np.array([-4100.0, 260, -2600]))),
}


def rot_y(v, th):
    c, s = np.cos(th), np.sin(th)
    return np.array([v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c])


def node_pos(install, zone, name):
    from pak import open_pak, qbkey
    entries, blob = open_pak(os.path.join(install, 'data', 'worlds', 'worldzones', zone, f'{zone}.pak.wpc'))
    e = next(e for e in entries if (e['name'] or '').lower().endswith(f'\\{zone}.qb.wpc'))
    tmp = os.path.join(os.environ.get('TEMP', '.'), f'{zone}_bd_nodes.qb')
    open(tmp, 'wb').write(blob[e['offset']:e['offset'] + e['size']])
    for d in thawscene.expanded_nodes(tmp, zone):
        if isinstance(d.get('Name'), str) and thawscene._key(d['Name']) == qbkey(name):
            return np.array(d['Pos'], float), float(d.get('Angles', [0, 0, 0])[1])
    raise KeyError(name)


def camera(cam, look):
    f = look - cam
    f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return np.stack([r, u, f])


def clip_near(tri, near=2.0):
    """tri: 3 x (view xyz + attrs). Returns a list of triangles in front of the near plane."""
    inside = tri[:, 2] >= near
    if inside.all():
        return [tri]
    if not inside.any():
        return []
    poly = []
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        if a[2] >= near:
            poly.append(a)
        if (a[2] >= near) != (b[2] >= near):
            t = (near - a[2]) / (b[2] - a[2])
            poly.append(a + (b - a) * t)
    return [np.array([poly[0], poly[i], poly[i + 1]]) for i in range(1, len(poly) - 1)]


class Raster:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.color = np.zeros((h, w, 3), np.float32)
        self.depth = np.full((h, w), np.inf, np.float32)
        self.fx = (w / 2) / np.tan(HFOV / 2)
        ys, xs = np.mgrid[0:h, 0:w]
        self.px, self.py = xs + 0.5, ys + 0.5

    def tri(self, t, tex, mode):
        """t: 3 x [x, y, z (view), u, v, r, g, b, a]."""
        z = t[:, 2]
        sx = self.w / 2 + t[:, 0] / z * self.fx
        sy = self.h / 2 - t[:, 1] / z * self.fx
        x0, x1 = int(max(0, np.floor(sx.min()))), int(min(self.w, np.ceil(sx.max())))
        y0, y1 = int(max(0, np.floor(sy.min()))), int(min(self.h, np.ceil(sy.max())))
        if x0 >= x1 or y0 >= y1:
            return
        area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if abs(area) < 1e-9:
            return
        px, py = self.px[y0:y1, x0:x1], self.py[y0:y1, x0:x1]
        w0 = ((sx[1] - px) * (sy[2] - py) - (sx[2] - px) * (sy[1] - py)) / area
        w1 = ((sx[2] - px) * (sy[0] - py) - (sx[0] - px) * (sy[2] - py)) / area
        w2 = 1 - w0 - w1
        m = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not m.any():
            return
        iz = w0 / z[0] + w1 / z[1] + w2 / z[2]
        zz = 1 / iz
        dep = self.depth[y0:y1, x0:x1]
        m &= zz < dep
        if not m.any():
            return
        attr = (w0[..., None] * (t[0, 3:] / z[0]) + w1[..., None] * (t[1, 3:] / z[1])
                + w2[..., None] * (t[2, 3:] / z[2])) * zz[..., None]
        th, tw = tex.shape[:2]
        u = np.floor(attr[..., 0] * tw).astype(np.int64) % tw
        v = np.floor(attr[..., 1] * th).astype(np.int64) % th
        texel = tex[v, u].astype(np.float32) / 255
        rgb = np.clip(texel[..., :3] * attr[..., 2:5] / 128, 0, 1)
        a = np.clip(texel[..., 3] * attr[..., 5] / 128, 0, 1)
        col = self.color[y0:y1, x0:x1]
        if mode in ('opaque', 'cutout'):
            if mode == 'cutout':
                m &= a > 0.5
            col[m] = rgb[m]
            dep[m] = zz[m]
        elif mode == 'add':
            col[m] = np.clip(col[m] + rgb[m] * a[m, None], 0, 1)
        else:
            col[m] = col[m] * (1 - a[m, None]) + rgb[m] * a[m, None]


def render(materials, meshes, textures, cam, look, w=W * SS, h=H * SS):
    R = camera(cam, look)
    ras = Raster(w, h)
    white = np.full((8, 8, 4), 255, np.uint8)
    jobs = []
    for m in meshes:
        rec = materials.get(m.material)
        tcks = struct.unpack_from('<I', rec, 0x40)[0] if rec else 0
        tex = textures[tcks][0] if tcks in textures else white
        info = {'has_alpha': bool((tex[..., 3] < 250).any()),
                'soft_alpha': bool(((tex[..., 3] > 24) & (tex[..., 3] < 232)).mean() > 0.02)}
        pas, kind, ascale, _ = classify(rec, info) if rec else (0, 'opaque', 1.0, None)
        view = (m.pos - cam) @ R.T
        col = m.col.astype(np.float64)
        attr = np.concatenate([view, m.uv, col[:, :3], np.clip(col[:, 3:4] * ascale, 0, 255)], 1)
        for s in m.strips:
            for i in range(len(s) - 2):
                a, b, c = s[i], s[i + 1], s[i + 2]
                if a == b or b == c or a == c:
                    continue
                tri = attr[[a, b, c]]
                d = tri[:, 2].mean()
                jobs.append((pas, -d if pas else 0, tri, tex, kind))
    jobs.sort(key=lambda j: (j[0], j[1]))
    for pas, _, tri, tex, kind in jobs:
        for t in clip_near(tri):
            ras.tri(t, tex, kind)
    img = Image.fromarray((ras.color * 255).astype(np.uint8))
    return img.resize((W, H), Image.Resampling.LANCZOS)


def shop_view(install, shop, yaw_off=0.0):
    zone, node, box = SHOPS[shop]
    materials, meshes, textures, _, _ = thawscene.load_zone(install, zone)
    if box is not None:
        lo, hi = box
        meshes = [m for m in meshes if ((m.pos >= lo) & (m.pos <= hi)).all(1).mean() > 0.5]
    spot, yaw = node_pos(install, 'z_ho', node) if zone == 'z_ho' else node_pos(install, 'z_ho', node)
    th = yaw + np.radians(yaw_off)
    return materials, meshes, textures, spot + rot_y(CAS_CAM, th), spot + rot_y(CAS_LOOK, th)


# ---------------------------------------------------------------- into Remix's CAS room

# the facing each shop is rendered from (offset from its *_Edit node's yaw), picked by eye
VIEW = {'barber': 0.0, 'clothing': 270.0}
# the CAS skater's node in levels\mainmenu (P1: Restart), facing 0
CAS_SPOT = np.array([84.83287048339844, -63.73978042602539, 61.70404052734375])
# Kill and Create work on the level's own scene sectors (built from mainmenu.geom.psp): the engine
# finds a sector's box by its name, first match (FUN_00076da4). Each backdrop box takes the name of
# a small room piece that the CAS camera never sees (always behind the backdrop wall); that piece's
# own box is renamed, so killing the name hides the backdrop instead.
BD_HOST = {'barber': 0x978F60B1, 'clothing': 0xE0885027}
# THAW's main menu backdrop (the alley wall in z_mainmenu, seen from its main menu camera cam_main:
# Pos and the x, y, z of its rotation quaternion, from main_menu_camera_control) on a panel 50 in in
# front of the same camera; the main menu sets that camera and hides the skater
MENU_HOST = 0xC6ED5A77
MENU_HFOV = 72.0
THAW_MENU_CAM = (np.array([42.6, 12.1, -983.8]), (0.000138, 0.999862, 0.011832))
BD_SIZE = (512, 256)


def thaw_menu_view(install):
    """THAW's main menu backdrop, rendered from cam_main (its camera looks along +Z rotated by the
    quaternion)."""
    materials, meshes, textures, _, _ = thawscene.load_zone(install, 'z_mainmenu')
    pos, (x, y, z) = THAW_MENU_CAM
    w = np.sqrt(max(0.0, 1 - x * x - y * y - z * z))
    q = np.array([x, y, z])
    t = 2 * np.cross(q, [0.0, 0, 1])
    fwd = np.array([0.0, 0, 1]) + w * t + np.cross(q, t)
    return render(materials, meshes, textures, pos, pos + fwd * 100)


def clut8(img):
    """RGBA image -> (palette 256 x RGBA bytes, swizzled 8-bit pixels)."""
    from thaw2psp import swizzle
    q = img.convert('RGB').quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    pal = np.array(q.getpalette()[:768], np.uint8).reshape(-1, 3)
    pal = np.vstack([pal, np.zeros((256 - len(pal), 3), np.uint8)])
    pal = np.concatenate([pal, np.full((256, 1), 255, np.uint8)], 1)
    idx = np.array(q, np.uint8)
    return pal.tobytes(), swizzle(idx, idx.shape[1], idx.shape[0])


def cas_camera():
    """Remix's CAS camera in the main menu level: the skater there faces away from +Z (found with test
    walls), so the offsets apply turned half round."""
    return CAS_SPOT + rot_y(CAS_CAM, np.pi), CAS_SPOT + rot_y(CAS_LOOK, np.pi)


def project(p, cam, look, hfov=HFOV):
    """World points -> UV of the rendered image (the camera's screen at hfov across, 0..1)."""
    R = camera(cam, look)
    v = (p - cam) @ R.T
    fx = (W / 2) / np.tan(hfov / 2)
    return np.stack([(W / 2 + v[:, 0] / v[:, 2] * fx) / W, (H / 2 - v[:, 1] / v[:, 2] * fx) / H], 1)


def grid_strips(corner, a, b, n, m):
    """A grid over corner + s*a + t*b (s, t in 0..1), as n strips of 2(m+1) points."""
    for i in range(n):
        pts = []
        for j in range(m + 1):
            pts += [corner + a * (i / n) + b * (j / m), corner + a * ((i + 1) / n) + b * (j / m)]
        yield np.array(pts)


def backdrop_mesh(wall_d=None, floor=True, hfov=HFOV):
    """Strips (world points) a rendered image is projected onto from the CAS camera: a wall filling
    the view (60 in behind the skater, or wall_d in front of the camera) and, for the shops, a floor
    sheet just above the room's floor from in front of the camera to that wall. From the camera
    they read as the one picture."""
    cam, look = cas_camera()
    r, u, f = camera(cam, look)
    d = np.dot(CAS_SPOT - cam, f) + 60 if wall_d is None else wall_d
    hw = d * np.tan(hfov / 2) * (1.05 if floor else 1.0)
    hh = hw * H / W
    c = cam + f * d
    wall = list(grid_strips(c - r * hw + u * hh, r * 2 * hw, -u * 2 * hh, 4, 4))
    if not floor:
        return wall
    # floor: horizontal, at the skater's feet, from 40 in ahead of the camera to the wall's foot
    y = CAS_SPOT[1] + 0.5
    fh = np.array([f[0], 0, f[2]])
    fh /= np.linalg.norm(fh)
    rh = np.cross(fh, [0, 1, 0])
    near = np.array([cam[0], y, cam[2]]) + fh * 40
    far_d = np.dot(c - near, fh) + 20
    floor = list(grid_strips(near - rh * 2 * hw, rh * 4 * hw, fh * far_d, 8, 8))
    return wall + floor


def inject(level, panels):
    """mainmenu.psp_level with a backdrop box per panel (host checksum, PIL image, strips, the
    camera's field of view across), the image projected from the CAS camera (see backdrop_mesh and BD_HOST), its strips at the end of
    the opaque pass."""
    import psplevel
    from thaw2psp import ge, GE_RET, encode_strip, to_vertex_space, box_flags_len
    from pak import qbkey
    L = psplevel.Level(level)
    d = L.data
    off = np.array(L.offset, np.float64)
    tex = bytearray(d[L.tex:L.tex + L.tex_bytes])
    tex += bytes(-len(tex) % 64)
    texcmds = list(struct.unpack_from(f'<{L.n_texcmds}I', d, L.texcmds))
    boxes = bytearray(d[L.boxes:L.boxes + L.n_boxes * 16])
    names = list(struct.unpack_from(f'<{L.n_boxes}I', d, L.boxnames))
    flags = bytearray(d[L.boxflags:L.boxflags + L.n_boxes])
    verts = bytearray(d[L.verts:L.verts + L.vert_bytes])
    prims = list(struct.unpack_from(f'<{L.n_prims}H', d, L.prims))
    assert prims[-2:] == [0, 0], 'last pass must end the prim stream'
    for pas in L.passes():  # strips must end in the compact format
        st = 12
        for *_, stride in L.strips(*pas):
            st = stride
        assert st == 12
    tail, new_verts = [], bytearray()
    cam, look = cas_camera()
    for host, img, strips, hfov in panels:
        names = [0x48570000 + i if n == host else n for i, n in enumerate(names)]  # the host's own box
        pal, pix = clut8(img.resize(BD_SIZE, Image.Resampling.LANCZOS))
        clut_at = len(tex)
        tex += pal
        pix_at = len(tex)
        tex += pix + bytes(-len(pix) % 64)
        w, h = BD_SIZE
        word = len(texcmds)
        texcmds += [ge(0xB0, clut_at), ge(0xC4, 0x20), ge(0xD0, 0x4141C9)]
        texcmds += [ge(0xA0 + i, pix_at) for i in range(4)] + [ge(0xA8 + i, w) for i in range(4)]
        texcmds += [ge(0xB8 + i, (w.bit_length() - 1) | (h.bit_length() - 1) << 8) for i in range(4)]
        texcmds += [ge(0xC2, 1), ge(0x1D, 0), ge(0xC7, 0x101),
                    ge(0x48, 0x410000), ge(0x49, 0x410000), ge(0x4A, 0xC10000), ge(0x4B, 0xC10000),
                    ge(0xC3, 5), ge(0xC6, 0x101), ge(0xDB, 0xFF0007), ge(0x21, 0),
                    ge(0x47, 0x46FFDC), ge(0xCB, 0), GE_RET]
        box = len(names)
        allv = to_vertex_space(np.concatenate(strips)) - off
        lo, hi = allv.min(0) - 8, allv.max(0) + 8
        boxes += np.concatenate([lo / 32768, [0], hi / 32768, [0]]).astype('<f2').tobytes()
        names.append(host)
        flags.append(0)  # shown at load; scripts kill the ones not wanted
        tail += [0, word]
        for pts in strips:
            uv = np.clip(project(pts, cam, look, hfov), 0, 1)
            rows = np.concatenate([to_vertex_space(pts) - off, uv, np.full((len(pts), 4), 128.0)], 1)
            for seq in (rows, rows[np.arange(len(rows)) ^ 1]):  # both windings
                rec, wide = encode_strip(seq)
                assert not wide
                new_verts += rec
                tail.append(len(seq) << 11 | (box + 2))
    # at the end of the opaque pass
    tp, tv = L.trans_prim, L.trans_vert
    if tp or tv:
        assert prims[tp - 2:tp] == [0, 0]
        prims = prims[:tp - 2] + tail + prims[tp - 2:]
        verts = verts[:tv] + new_verts + verts[tv:]
        trans = (tp + len(tail), tv + len(new_verts))
    else:
        prims = prims[:-2] + tail + [0, 0]
        verts += new_verts
        trans = (0, 0)
    n_boxes = len(names)
    h = list(L.h)
    h[2], h[3], h[4], h[5], h[9] = len(tex), n_boxes, len(verts), len(texcmds), len(prims)
    h[13], h[14] = trans
    out = bytearray(struct.pack('<15i', *h) + b'7777')
    out += d[L.objs:L.objs + L.n_objs * 0x40]
    out += tex + boxes + verts + struct.pack('<I', GE_RET)
    out += struct.pack(f'<{len(texcmds)}I', *texcmds)
    out += d[L.objcmds:L.objwords]  # object lists, uv anims, object vertices
    out += d[L.objwords:L.objwords + L.n_objs * 4]
    out += struct.pack(f'<{n_boxes}I', *names)
    out += bytes(flags) + bytes(box_flags_len(n_boxes) - n_boxes)
    out += struct.pack(f'<{len(prims)}H', *prims)
    return bytes(out)


def main():
    cmd, install, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    if cmd == 'render':
        offs = [float(x) for x in sys.argv[4:]] or [0.0]
        for shop in SHOPS:
            for o in offs:
                mats, meshes, texs, cam, look = shop_view(install, shop, o)
                img = render(mats, meshes, texs, cam, look)
                path = os.path.join(out, f'{shop}_{int(o)}.png')
                img.save(path)
                print(path, len(meshes), 'meshes', cam.round(1), look.round(1))
    elif cmd == 'build':
        # build <install> <outdir> <Remix data dir>
        import qb2
        import qbscripts
        from hostory import script, tok_name
        from pak import qbkey
        data = sys.argv[4]
        panels = []
        for shop, o in VIEW.items():
            mats, meshes, texs, cam, look = shop_view(install, shop, o)
            img = render(mats, meshes, texs, cam, look)
            img.save(os.path.join(out, f'{shop}.png'))
            panels.append((BD_HOST[shop], img, backdrop_mesh(), HFOV))
        img = thaw_menu_view(install)
        if os.environ.get('BD_GRID'):  # testing aid: a numbered grid, to see what the menu camera frames
            from PIL import ImageDraw
            img = Image.new('RGB', (W, H), (20, 20, 20))
            dr = ImageDraw.Draw(img)
            for gx in range(0, W + 1, 40):
                dr.line([(gx, 0), (gx, H)], fill=(255, 255, 0) if gx % 120 == 0 else (90, 90, 90), width=2)
            for gy in range(0, H + 1, 34):
                dr.line([(0, gy), (W, gy)], fill=(0, 255, 255) if gy % 68 == 0 else (90, 90, 90), width=2)
            for gx in range(0, W, 40):
                for gy in range(0, H, 34):
                    dr.text((gx + 4, gy + 4), f'{gx // 40},{gy // 34}', fill=(255, 255, 255))
        img.save(os.path.join(out, 'mainmenu.png'))
        # the main menu's camera frames 72 degrees across (the 4:3 angle, measured with a grid), not
        # CAS's 88.18; the panel fills exactly that, close enough to sit in front of the room's walls
        mh = np.radians(MENU_HFOV)
        panels.append((MENU_HOST, img, backdrop_mesh(wall_d=20, floor=False, hfov=mh), mh))
        lvl = inject(os.path.join(data, 'levels', 'mainmenu', 'mainmenu.psp_level'), panels)
        open(os.path.join(out, 'mainmenu.psp_level'), 'wb').write(lvl)
        print('mainmenu.psp_level', len(lvl), 'bytes')
        # CAS start shows the backdrop for the shop the story sent the skater from (hw_shop_pending,
        # see hostory.py): 48 the barber, 49 the clothing store. The room's loose objects (boards on
        # the floor) and the pieces in front of the backdrop go too; Box01, the floor the skater
        # stands on, stays (its collision holds the skater up; the backdrop's floor sheet covers it).
        mq = open(os.path.join(data, 'levels', 'mainmenu', 'mainmenu.qb'), 'rb').read()
        arr = qb2.parse_value(mq, qb2.find_item(mq, struct.unpack_from('<I', mq, 1)[0]))[0]
        room = [qb2.get(n, qbkey('Name'))[1] for n in arr[1]
                if qb2.get(n, qbkey('Class')) in (('name', qbkey('LevelObject')), ('name', qbkey('LevelGeometry')))
                and qb2.get(n, qbkey('Name')) and qb2.get(n, qbkey('Name'))[1] != qbkey('Box01')
                and (None, ('name', qbkey('CreatedAtStart'))) in n[1]]
        assert all(h in room for h in list(BD_HOST.values()) + [MENU_HOST])
        # from CAS (init_cas_skater_and_cam passes cas) the main menu's panel goes; the main menu
        # creates it again (create_main_menu)
        body = [['if', 'GotParam', 'cas'], ['Kill', 'Name', '=', tok_name(MENU_HOST)], ['endif']]
        for v, shop in ((48, 'barber'), (49, 'clothing')):
            body += [['if', bytes([0x0E]), 'hw_shop_pending', '=', v, bytes([0x0F])]]
            body += [['Kill', 'Name', '=', tok_name(k)] for k in room if k != BD_HOST[shop]]
            body += [['endif']]
        # anywhere else (the main menu, CAS from the menus) neither backdrop shows
        body += [['if', bytes([0x0E]), 'hw_shop_pending', '=', 0, bytes([0x0F])]]
        body += [['Kill', 'Name', '=', tok_name(k)] for k in BD_HOST.values()] + [['endif']]
        _, _, _, ents = qb2.read_pre(os.path.join(data, 'pre', 'mainmenu_scripts.pre'))
        cas = next(d for n, c, d in ents if n.lower() == r'levels\mainmenu\mainmenu_cas.qb')
        s, e = qbscripts.scripts(cas)[qbscripts.key('init_cas_skater_and_cam')]
        assert cas[e - 1] == 0x24
        cas = cas[:e - 1] + tok_name('hw_cas_backdrop') + tok_name('cas') + bytes([0x01]) + cas[e - 1:]
        end_tok = next(p for p, t, pl in qb2.tokens(cas) if t in (0x2B, 0x00))
        cas = cas[:end_tok] + bytes([0x01]) + script('hw_cas_backdrop', body) +             script('hw_cas_backdrop_late', [['wait', 2, 'gameframes'], ['hw_cas_backdrop']]) + cas[end_tok:]
        list(qb2.tokens(cas))
        mm = next(d for n, c, d in ents if n.lower() == r'levels\mainmenu\mainmenu_scripts.qb')
        s0, e0 = qbscripts.scripts(mm)[0x1994c8df]  # 'Main Menu Startup'
        assert mm[e0 - 1] == 0x24
        # the startup runs before the level's sectors exist: kill a moment later
        mm = mm[:e0 - 1] + tok_name('spawnscript') + tok_name('hw_cas_backdrop_late') + bytes([0x01]) + mm[e0 - 1:]
        list(qb2.tokens(mm))
        open(os.path.join(out, 'mainmenu_cas.qb'), 'wb').write(cas)
        open(os.path.join(out, 'mainmenu_scripts.qb'), 'wb').write(mm)
        pre = os.path.join(out, 'mainmenu_scripts.pre')
        qb2.replace_in_pre(os.path.join(data, 'pre', 'mainmenu_scripts.pre'), pre, r'levels\mainmenu\mainmenu_cas.qb', cas)
        qb2.replace_in_pre(pre, pre, r'levels\mainmenu\mainmenu_scripts.qb', mm)
        print('mainmenu_scripts.pre', os.path.getsize(pre))


if __name__ == '__main__':
    main()
