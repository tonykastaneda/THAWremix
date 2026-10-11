"""Disassemble a range of a flat MIPS image (for code Ghidra's stock MIPS cannot decode).

  mipsdis.py <image> <startHex> <endHex>

Needs capstone (bin/pyenv). Words capstone rejects are VFPU/Allegrex-only and print as .word.
"""
import struct
import sys

from capstone import CS_ARCH_MIPS, CS_MODE_LITTLE_ENDIAN, CS_MODE_MIPS32, Cs


def main():
    img = open(sys.argv[1], 'rb').read()
    lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
    for a in range(lo, hi, 4):
        w = img[a:a + 4]
        ins = next(md.disasm(w, a), None)
        if ins:
            print(f'{a:06x}: {ins.mnemonic:8s} {ins.op_str}')
        else:
            print(f'{a:06x}: .word    {struct.unpack("<I", w)[0]:08x}')


if __name__ == '__main__':
    main()
