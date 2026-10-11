"""THAW scripts -> tools/qbc.py source, for porting THAW's UI to Remix.

  thaw2q.py <THAW .qb.wpc> <out.q> [script name ...]

THAW keeps a script's default parameters as a struct at the head of its body; THUG2 / Remix put
them on the script line (script name a = 1 b = 2). Everything else is printed as tools/thawqbdump.py
prints it, which tools/qbc.py reads back.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import qb  # noqa: E402
import qb2  # noqa: E402
import thawscene  # noqa: E402
from thawqbdump import text  # noqa: E402


def defaults_split(code):
    """(default params as one line, body bytes): a leading { ... } struct is the defaults."""
    toks = list(qb2.tokens(code))
    i = 0
    while i < len(toks) and toks[i][1] in (0x01, 0x02):
        i += 1
    if i >= len(toks) or toks[i][1] != 0x03:
        return '', code
    depth = 0
    for j in range(i, len(toks)):
        if toks[j][1] == 0x03:
            depth += 1
        elif toks[j][1] == 0x04:
            depth -= 1
            if depth == 0:
                inner = code[toks[i][0] + 1:toks[j][0]]
                end = toks[j][0] + 1
                return ' '.join(text(inner).split('\n')).strip(), code[end:]
    raise ValueError('unclosed defaults')


def convert(path, names=None):
    d = open(path, 'rb').read()
    out = []
    for n, v in qb.QB(d).items():
        if not (isinstance(v, tuple) and v[0] == 'script'):
            continue
        if names and n not in names:
            continue
        off, usz, csz = v[1], v[2], v[3]
        code = thawscene.lzss(d[off:off + csz], usz) if csz < usz else d[off:off + csz]
        head, body = defaults_split(code)
        body = text(body).strip('\n ')  # ends with the script's own endscript
        out.append(f'script {n} {head}'.rstrip() + '\n' + body + '\n')
    return '\n'.join(out)


def main():
    qb.load_names(os.path.join(os.path.dirname(__file__), '..', 'extracted', 'dbg'))
    src = convert(sys.argv[1], set(sys.argv[3:]) or None)
    open(sys.argv[2], 'w', encoding='utf-8').write(src)
    print(sys.argv[2], src.count('\nendscript'), 'scripts')


if __name__ == '__main__':
    main()
