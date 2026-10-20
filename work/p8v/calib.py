"""Calibrate the menu backdrop: which texel of the 512x256 card each screen pixel shows.

  calib.py make <out dir>        writes cols.psp_level / rows.psp_level (stripes 32 texels wide)
  calib.py fit <cols.png> <rows.png>   fits the perspective map from two screenshots; prints CORNERS
"""
import os, struct, sys
import numpy as np
from PIL import Image
R = r'C:\Users\tonyk\Documents\GitHub\THAWremix'
sys.path.insert(0, os.path.join(R, 'tools'))
PAL = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255), (255, 128, 0), (128, 0, 255),
       (0, 128, 0), (128, 128, 128), (255, 255, 255), (0, 0, 0), (128, 0, 0), (0, 0, 128), (255, 160, 200), (120, 80, 40)]


def make(out):
    import p8menubg, psptex
    src = open(os.path.join(R, r'work\p8v\mm\worlds\worldzones\z_mainmenu\z_mainmenu.psp_level'), 'rb').read()
    for name, axis in (('cols', 1), ('rows', 0)):
        g = np.zeros((256, 512, 4), np.uint8)
        g[:, :, 3] = 255
        n = 16 if axis else 8
        for i in range(n):
            sl = (slice(None), slice(i * 32, i * 32 + 32)) if axis else (slice(i * 32, i * 32 + 32), slice(None))
            g[sl[0], sl[1], :3] = PAL[i]
        open(os.path.join(out, f'{name}.psp_level'), 'wb').write(psptex.replace(p8menubg.regrow(src, 512, 256), 0, g))


def labels(png, n):
    """Per-pixel stripe index (nearest palette colour after normalising brightness), -1 if unsure."""
    a = np.array(Image.open(png).convert('RGB')).astype(float)
    pal = np.array(PAL[:n], float)
    d = ((a[:, :, None, :] - pal[None, None]) ** 2).sum(-1)
    lab = d.argmin(-1)
    lab[d.min(-1) > 9000] = -1
    return lab


def boundary_points(lab, along):
    """(x, y, k) where stripe k-1 meets stripe k, scanning rows (along='x') or columns (along='y')."""
    pts = []
    H, W = lab.shape
    if along == 'x':
        for y in range(4, 240, 6):
            row = lab[y]
            for x in range(3, W - 3):
                a, b = row[x - 3:x].tolist(), row[x:x + 3].tolist()
                if len(set(a)) == 1 and len(set(b)) == 1 and a[0] >= 0 and b[0] == a[0] + 1:
                    pts.append((x, y, b[0]))
    else:
        for x in range(4, W - 4, 6):
            col = lab[:, x]
            for y in range(3, 240):
                a, b = col[y - 3:y].tolist(), col[y:y + 3].tolist()
                if len(set(a)) == 1 and len(set(b)) == 1 and a[0] >= 0 and abs(b[0] - a[0]) == 1:
                    pts.append((x, y, max(a[0], b[0])))  # rows run upward on screen (card upside down)
    return pts


def fit(cols_png, rows_png):
    # screen point -> (u, v): each column boundary k gives u = 32k, each row boundary j gives v = 32j;
    # solve the 8 homography parameters by least squares on both kinds of constraint
    cp = boundary_points(labels(cols_png, 16), 'x')
    rp = boundary_points(labels(rows_png, 8), 'y')
    A, b = [], []
    for x, y, k in cp:  # u = (h0 x + h1 y + h2) / (h6 x + h7 y + 1)
        A.append([x, y, 1, 0, 0, 0, -32 * k * x, -32 * k * y]); b.append(32 * k)
    for x, y, j in rp:
        A.append([0, 0, 0, x, y, 1, -32 * j * x, -32 * j * y]); b.append(32 * j)
    h, *_ = np.linalg.lstsq(np.array(A, float), np.array(b, float), rcond=None)

    def uv(x, y):
        w = h[6] * x + h[7] * y + 1
        return (h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w
    err = [abs(uv(x, y)[0] - 32 * k) for x, y, k in cp] + [abs(uv(x, y)[1] - 32 * j) for x, y, j in rp]
    print(f'{len(cp)} column and {len(rp)} row points; mean error {np.mean(err):.2f} texels, max {np.max(err):.2f}')
    print('CORNERS =', tuple(tuple(round(c, 1) for c in uv(x, y)) for x, y in ((0, 0), (480, 0), (0, 272), (480, 272))))


if __name__ == '__main__':
    if sys.argv[1] == 'make':
        make(sys.argv[2])
    else:
        fit(sys.argv[2], sys.argv[3])
