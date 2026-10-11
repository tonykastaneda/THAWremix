"""Will Remix load this .pre? A model of its loader (FUN_0000e76c in the executable).

  precheck.py <file.pre> [...]

The loader allocates one buffer: ((size field at 0x0C + 0xC03) & ~3) + name area + 0x80F, rounded
down to 2048 (the name area is the pre's own file name length + 16, 16-aligned). It reads the whole
file into the END of that buffer (2048-aligned) and unpacks entries forward from the start: each
entry's 16-byte header, its name, then its data at a 16-byte boundary (LZSS-expanded, or copied
when stored plain). It stops with "FATAL ERROR" (a break instruction, which a real PSP does not
survive; PPSSPP ignores it) when the unpacked side reaches the end of the buffer or passes the next
packed entry it has not read yet. Prints the smallest margin per file; negative means the game dies.
"""
import os
import struct
import sys


def check(path, pre_name=None):
    d = open(path, 'rb').read()
    fsize, ver, magic, n = struct.unpack_from('<IHHI', d, 0)
    hint = struct.unpack_from('<I', d, 12)[0] if ver == 4 else 0
    name = pre_name or os.path.basename(path)
    name_area = (len(name) + 0x10) & ~0xF
    buf = (((hint + 0xC03) & ~3) + name_area + 0x80F) & ~0x7FF
    end = buf
    src = buf - ((len(d) + 0x7FF) & ~0x7FF)  # where the file starts in the buffer
    dest = name_area + 16
    s = src + 16
    worst = None
    for _ in range(n):
        dsz, csz, nlen, cks = struct.unpack_from('<IIII', d, s - src)
        nxt_src = s + 16 + nlen + (((csz or dsz) + 3) & ~3)
        data_at = (dest + 16 + nlen + 15) & ~15
        # a plain (stored) entry is checked from the END of its copied data plus its size again
        # (the loader adds the size to the already advanced pointer), so it needs about twice its
        # size of room before the buffer end; Remix's own plain entries are all small
        if not csz and end <= data_at + ((dsz + 3) & ~3) + dsz + 0x14:
            return end - (data_at + ((dsz + 3) & ~3) + dsz + 0x14), \
                f'plain entry {_} ({dsz:,} bytes) trips the overrun check (it needs about twice its size)'
        dest_next = data_at + ((dsz + 3) & ~3)
        margin = min(end - dest_next, nxt_src - dest_next)
        worst = margin if worst is None else min(worst, margin)
        if margin < 0:
            return margin, f'unpacked data passes the packed data at entry {_} ({dsz} bytes, {"plain" if not csz else "lzss"})'
        dest, s = dest_next, nxt_src
    return worst, 'ok'


def main():
    for p in sys.argv[1:]:
        m, why = check(p)
        print(f'{"OK  " if m >= 0 else "FAIL"} {os.path.basename(p):28s} smallest margin {m:>9,}  {why}')


if __name__ == '__main__':
    main()
