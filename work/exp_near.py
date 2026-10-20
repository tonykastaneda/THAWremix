import sys
sys.path.insert(0, 'tools')
import numpy as np
import thawscene, thaw2psp
at = np.array([-3020.952880859375, -765.405029296875, -3511.32470703125])
R, TESS = float(sys.argv[1]), float(sys.argv[2])
materials, meshes, textures, pieces, restarts = thawscene.load_zone('THAW CLEAN/Game', 'z_ho')
p1 = np.array(next(r for r in restarts if r[0] == 'P1: Restart')[1])
delta = np.round((at - p1) * 16) / 16
keep = [m for m in meshes if np.linalg.norm(np.array(m.center) - p1) < R + m.radius and m.radius < 6000]
print('meshes kept', len(keep))
lvl = thaw2psp.build_level(keep, materials, textures, delta, 64, TESS)
open('work/out/tr.psp_level', 'wb').write(lvl)
print(len(lvl))
