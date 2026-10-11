"""THUG2/Remix token-stream .qb scripts: find, print and replace whole scripts.

  qbscripts.py show <file.qb> <script name or 0xchecksum> [...]
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import qb  # noqa: E402
import qb2  # noqa: E402
from pak import qbkey  # noqa: E402
from thawqbdump import fmt  # noqa: E402


def key(name):
    return int(name, 16) if name.startswith('0x') else qbkey(name)


def scripts(d):
    """{checksum: (start offset of the 0x23 token, end offset just past the 0x24 token)}"""
    out, start, name = {}, None, None
    toks = list(qb2.tokens(d))
    for i, (p, t, pl) in enumerate(toks):
        if t == 0x23 and i + 1 < len(toks) and toks[i + 1][1] == 0x16:
            start, name = p, struct.unpack_from('<I', toks[i + 1][2])[0]
        elif t == 0x24 and start is not None:
            out[name] = (start, p + 1)
            start = None
    return out


def show(d, k):
    s, e = scripts(d)[k]
    return ' '.join(fmt(t, pl) for p, t, pl in qb2.tokens(d, s, e)).replace(' \n ', '\n')


if __name__ == '__main__':
    qb.load_names(os.path.join(os.path.dirname(__file__), '..', 'extracted', 'dbg'))
    if sys.argv[1] == 'show':
        d = open(sys.argv[2], 'rb').read()
        for n in sys.argv[3:]:
            print(show(d, key(n)), '\n')
