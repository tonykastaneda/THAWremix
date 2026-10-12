"""Print Project 8's memory heaps (name, size, free bytes) from the running hidden test copy.

  p8heaps.py

Reads them as the DisplayFreeMem CFunc does (module 0x15e554): the memory manager pointer is at
0x08b64358 (DAT_00360358), its heap array starts at the manager with the count at +0xC0; per heap
the name pointer is at +0x30 and the region at +0x20; a region is [start, ?, ?, ?, end, low block,
high block], free = (high block ? high.+0x28 : end) - (low block ? low.+0x28 : start), the gap
between the bottom-up and top-down allocations. Run it while the game sits where you want to
measure (e.g. after tools/p8boot.py leaves it at the pause menu). TopDown and BottomUp share one
region, so they show the same numbers.
"""
import base64
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import ppsspp_ws as p  # noqa: E402

MANAGER = 0x08b64358


def heaps(ws):
    def rd(a, n):
        return base64.b64decode(ws.call({'event': 'memory.read', 'address': a, 'size': n})['base64'])

    def u(a):
        return struct.unpack('<I', rd(a, 4))[0]

    def cs(a):
        return rd(a, 40).split(b'\0')[0].decode('latin-1') if 0x08000000 <= a < 0x0A000000 else '?'

    mm = u(MANAGER)
    out = []
    for i in range(u(mm + 0xC0)):
        h = u(mm + 4 * i)
        if not h:
            continue
        rg = struct.unpack('<7I', rd(u(h + 0x20), 28))
        lo = u(rg[5] + 0x28) if rg[5] else rg[0]
        hi = u(rg[6] + 0x28) if rg[6] else rg[4]
        out.append((cs(u(h + 0x30)), rg[4] - rg[0], hi - lo))
    return out


def main():
    for name, size, free in heaps(p.WS()):
        print('%-24s size %9d  free %9d' % (name, size, free))


if __name__ == '__main__':
    main()
