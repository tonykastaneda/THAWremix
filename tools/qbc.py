"""QB text -> THUG2 / Remix token-stream compiler (the syntax tools/qbscripts.py and
tools/thawqbdump.py print), for porting THAW's menu scripts and writing new ones.

  qbc.py patch <in.qb> <out.qb> <source.q> [...]   replace scripts of the same name, append the rest

Source syntax:
  script name [default params]  ...  endscript      name = value     (top-level global)
  names, 0x1234abcd checksums, 12 / -3 ints, 1.5 floats, "string" and 'local string',
  (x, y) pairs and (x, y, z) vectors of literals, { struct } [ array ], <> name or <name> params,
  <...> all params, = . , - + / * ( ) < <= > >= : operators,
  if / else / endif, while / repeat [n], break, return, not / and / or.
  A '-' directly before a digit is a negative literal; '; ' to end of line is a comment.
"""
import re
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import qb2  # noqa: E402
from pak import qbkey  # noqa: E402

OPS = {'{': 0x03, '}': 0x04, '[': 0x05, ']': 0x06, '=': 0x07, '.': 0x08, ',': 0x09, '-': 0x0A, '+': 0x0B,
       '/': 0x0C, '*': 0x0D, '(': 0x0E, ')': 0x0F, '<': 0x12, '<=': 0x13, '>': 0x14, '>=': 0x15, ':': 0x42}
WORDS = {'return': 0x29, 'not': 0x39, 'or': 0x32, 'and': 0x33}
CONTROL = {'if', 'else', 'endif', 'endscript', 'while', 'repeat', 'break', 'switch', 'case', 'default',
           'endswitch'}
NUM = r'-?\d+(?:\.\d*)?(?:[eE][-+]?\d+)?'
TOKEN = re.compile(r"""
    (?P<nl>\n) |
    (?P<ws>[ \t\r]+) |
    (?P<comment>;[^\n]*) |
    (?P<str>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*") |
    (?P<tuple>\(\s*""" + NUM + r"""\s*,\s*""" + NUM + r"""\s*(?:,\s*""" + NUM + r"""\s*)?\)) |
    (?P<all><\.\.\.>) |
    (?P<param><>|<(?=[A-Za-z_]\w*>)) |
    (?P<hex>0x[0-9a-fA-F]+\b) |
    (?P<num>""" + NUM + r""") |
    (?P<name>[A-Za-z_][\w]*) |
    (?P<op><=|>=|[{}\[\]=.,\-+/*()<>:])
""", re.X)


def lex(src):
    for m in TOKEN.finditer(src):
        kind = m.lastgroup
        yield kind, m.group()
    # (unmatched characters are skipped by finditer; check() below catches them)


def check(src):
    pos = 0
    for m in TOKEN.finditer(src):
        if m.start() != pos:
            raise SyntaxError(f'cannot read {src[pos:m.start()]!r} at {pos}')
        pos = m.end()
    if pos != len(src):
        raise SyntaxError(f'cannot read {src[pos:pos + 20]!r} at {pos}')


def name_tok(n):
    k = int(n, 16) if n.lower().startswith('0x') else qbkey(n)
    return bytes([qb2.NAME]) + struct.pack('<I', k)


def compile_source(src):
    """Returns {checksum: (kind, bytes)}: kind 'script' (0x23 .. 0x24 incl.) or 'global' (name = value line)."""
    check(src)
    toks = [(k, v) for k, v in lex(src) if k not in ('ws', 'comment')]
    out = {}
    i = 0
    n = len(toks)

    def skip_nl(i):
        while i < n and toks[i][0] == 'nl':
            i += 1
        return i

    while True:
        i = skip_nl(i)
        if i >= n:
            break
        k, v = toks[i]
        if k == 'name' and v == 'script':
            name = toks[i + 1][1]
            body, i = compile_body(toks, i + 2)
            out[qbkey(name) if not name.lower().startswith('0x') else int(name, 16)] = (
                'script', bytes([0x23]) + name_tok(name) + body)
        elif k in ('name', 'hex'):
            j = i
            while j < n and toks[j][0] != 'nl':
                j += 1
            # a global may run over lines inside braces/brackets
            depth = 0
            j = i
            while j < n:
                if toks[j][1] in ('{', '['):
                    depth += 1
                elif toks[j][1] in ('}', ']'):
                    depth -= 1
                elif toks[j][0] == 'nl' and depth == 0:
                    break
                j += 1
            if j < i + 3 or toks[i + 1][1] != '=':
                raise SyntaxError(f'top-level {v!r} is not a script or a global (name = value)')
            line = emit(toks[i:j])
            out[qbkey(v) if k == 'name' else int(v, 16)] = ('global', line + bytes([qb2.NEWLINE]))
            i = j
        else:
            raise SyntaxError(f'unexpected {v!r} at top level')
    return out


def compile_body(toks, i):
    """From just after the script name to endscript (inclusive). Returns (bytes, next index)."""
    body = bytearray()
    stack = []
    n = len(toks)
    while i < n:
        k, v = toks[i]
        if k == 'name' and v == 'endscript':
            assert not stack, f'unclosed {stack[-1][0]}'
            body.append(0x24)
            return bytes(body) + bytes([qb2.NEWLINE]), i + 1
        if k == 'name' and v == 'if':
            body.append(0x47)
            stack.append(('if', len(body)))
            body += bytes(2)
            i += 1
            continue
        if k == 'name' and v == 'else':
            kind, at = stack.pop()
            assert kind == 'if', 'else without if'
            body.append(0x48)
            else_at = len(body)
            body += bytes(2)
            struct.pack_into('<H', body, at, len(body) - at)
            stack.append(('else', else_at))
            i += 1
            continue
        if k == 'name' and v == 'endif':
            kind, at = stack.pop()
            assert kind in ('if', 'else'), 'endif without if'
            body.append(0x28)
            struct.pack_into('<H', body, at, len(body) - at)
            i += 1
            continue
        # loops and switches: break is 0x22 in a loop, a 0x49 jump past endswitch in a switch.
        # case/default carry a 0x49 jump (from the offset field) to the next case, default or
        # endswitch; default's goes to endswitch itself.
        if k == 'name' and v == 'while':
            body.append(0x20)
            stack.append(('while', None))
            i += 1
            continue
        if k == 'name' and v == 'repeat':
            kind, _ = stack.pop()
            assert kind == 'while', 'repeat without while'
            body.append(0x21)
            i += 1
            continue
        if k == 'name' and v == 'switch':
            body.append(0x3C)
            stack.append(('switch', {'case': None, 'breaks': []}))
            i += 1
            continue
        if k == 'name' and v in ('case', 'default'):
            sw = next(x for kk, x in reversed(stack) if kk == 'switch')
            if sw['case'] is not None:
                struct.pack_into('<H', body, sw['case'], len(body) - sw['case'])
            body += bytes([0x3E if v == 'case' else 0x3F, 0x49])
            sw['case'] = len(body)
            body += bytes(2)
            i += 1
            continue
        if k == 'name' and v == 'break':
            inner = next((kk for kk, x in reversed(stack) if kk in ('while', 'switch')), None)
            if inner == 'switch':
                sw = next(x for kk, x in reversed(stack) if kk == 'switch')
                body.append(0x49)
                sw['breaks'].append(len(body))
                body += bytes(2)
            else:
                body.append(0x22)
            i += 1
            continue
        if k == 'name' and v == 'endswitch':
            kind, sw = stack.pop()
            assert kind == 'switch', 'endswitch without switch'
            if sw['case'] is not None:
                struct.pack_into('<H', body, sw['case'], len(body) - sw['case'])
            body.append(0x3D)
            for at in sw['breaks']:
                struct.pack_into('<H', body, at, len(body) - at)
            i += 1
            continue
        # one plain token run up to the next control word
        j = i
        while j < n and not (toks[j][0] == 'name' and toks[j][1] in CONTROL):
            j += 1
        body += emit(toks[i:j])
        i = j
    raise SyntaxError('missing endscript')


def unescape(s):
    """\\\\ -> \\, \\' -> ', \\" -> ", \\xNN -> that byte; any other backslash stays (QB's own \\n, \\b0)."""
    return re.sub(r"\\(\\|'|\"|x[0-9a-fA-F]{2})", lambda m: chr(int(m.group(1)[1:], 16)) if m.group(1)[0] == 'x' else m.group(1), s)


def emit(toks):
    out = bytearray()
    i = 0
    while i < len(toks):
        k, v = toks[i]
        if k == 'nl':
            out.append(qb2.NEWLINE)
        elif k == 'str':
            s = unescape(v[1:-1]).encode('latin-1') + b'\0'
            out += bytes([qb2.STRING if v[0] == '"' else qb2.LSTRING]) + struct.pack('<I', len(s)) + s
        elif k == 'tuple':
            vals = [float(x) for x in v.strip('()').split(',')]
            out += (bytes([qb2.VEC]) + struct.pack('<3f', *vals)) if len(vals) == 3 else (bytes([0x1F]) + struct.pack('<2f', *vals))
        elif k == 'all':
            out.append(0x2C)
        elif k == 'param':
            out.append(0x2D)
            if v == '<':  # <name>
                out += name_tok(toks[i + 1][1])
                assert toks[i + 2][1] == '>'
                i += 2
        elif k == 'hex':
            out += name_tok(v)
        elif k == 'num':
            if re.fullmatch(r'-?\d+', v):
                out += bytes([qb2.INT]) + struct.pack('<i', int(v))
            else:
                out += bytes([qb2.FLOAT]) + struct.pack('<f', float(v))
        elif k == 'name':
            if v in WORDS:
                out.append(WORDS[v])
            else:
                out += name_tok(v)
        elif k == 'op':
            out.append(OPS[v])
        i += 1
    return bytes(out)


def patch(qb_data, compiled):
    """Replace same-named scripts/globals in a compiled .qb; append the rest before its name table."""
    import qbscripts
    d = bytes(qb_data)
    have = qbscripts.scripts(d)
    edits = []
    rest = []
    for k, (kind, b) in compiled.items():
        if kind == 'script' and k in have:
            s, e = have[k]
            edits.append((s, e, b[:-1]))  # the existing range ends at the 0x24
        else:
            rest.append(b)
    out = bytearray()
    pos = 0
    for s, e, b in sorted(edits):
        out += d[pos:s] + b
        pos = e
    out += d[pos:]
    end_tok = next(p for p, t, pl in qb2.tokens(bytes(out)) if t in (0x2B, 0x00))
    out = out[:end_tok] + bytes([qb2.NEWLINE]) + b''.join(rest) + out[end_tok:]
    list(qb2.tokens(bytes(out)))
    return bytes(out)


def main():
    if sys.argv[1] == 'patch':
        src = ''.join(open(f, encoding='utf-8').read() + '\n' for f in sys.argv[4:])
        out = patch(open(sys.argv[2], 'rb').read(), compile_source(src))
        open(sys.argv[3], 'wb').write(out)
        print(sys.argv[3], len(out))


if __name__ == '__main__':
    main()
