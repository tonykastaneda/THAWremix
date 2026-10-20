"""Move every restart in work/out/tr.qb (and rebuild the pre) to one test spot: x y z yaw."""
import sys, struct
sys.path.insert(0, 'tools')
import qb2
from pak import qbkey
x, y, z, yaw = map(float, sys.argv[1:5])
d = open('work/out/tr.qb', 'rb').read()
start = qb2.find_item(d, struct.unpack_from('<I', d, 1)[0])
arr, end = qb2.parse_value(d, start)
bases = {}


def cls_of(n):
    c = qb2.get(n, qbkey('Class'))
    if c:
        return c[1]
    for k, v in n[1]:
        if k is None and v[0] == 'name':
            if v[1] not in bases:
                p = qb2.find_item(d, v[1])
                bases[v[1]] = qb2.parse_value(d, p)[0] if p else None
            c = bases[v[1]] and qb2.get(bases[v[1]], qbkey('Class'))
            if c:
                return c[1]


n_set = 0
for n in arr[1]:
    if cls_of(n) == qbkey('Restart'):
        for i, (k, v) in enumerate(n[1]):
            if k == qbkey('Pos'):
                n[1][i] = (k, ('vec', (x, y, z)))
            if k == qbkey('Angles'):
                n[1][i] = (k, ('vec', (0.0, yaw, 0.0)))
        n_set += 1
out = d[:start] + qb2.encode_value(arr) + d[end:]
open('work/out/tr.qb', 'wb').write(out)
qb2.replace_in_pre('extracted/remix_data/pre/tr_scripts.pre', 'work/out/tr_scripts.pre', r'levels\TR\TR.qb', out)
print('restarts moved', n_set)
