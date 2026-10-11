"""Flatten a PSP PRX-style ELF (e_type 0xFFA0) to a memory image based at 0.

  prx2img.py <BOOT.BIN> <out.img>

Stock Ghidra has no loader for this ELF type. The file is linked at base 0, so with the segments
laid out at their virtual addresses the code and data references are already correct and the image
imports as raw MIPS:LE:32 at address 0. Prints the section table for orientation.
"""
import struct
import sys


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = open(src, 'rb').read()
    phoff, shoff = struct.unpack_from('<II', d, 28)
    phentsize, phnum, shentsize, shnum, shstrndx = struct.unpack_from('<HHHHH', d, 42)
    segs = []
    for i in range(phnum):
        p_type, off, vaddr, paddr, filesz, memsz, flags, align = struct.unpack_from('<8I', d, phoff + i * phentsize)
        print(f'seg {i}: type {p_type:x} off {off:x} vaddr {vaddr:x} filesz {filesz:x} memsz {memsz:x} flags {flags:x}')
        if p_type == 1:
            segs.append((vaddr, off, filesz, memsz))
    size = max(v + m for v, _, _, m in segs)
    img = bytearray(size)
    for vaddr, off, filesz, _ in segs:
        img[vaddr:vaddr + filesz] = d[off:off + filesz]
    open(dst, 'wb').write(img)
    secs = [struct.unpack_from('<10I', d, shoff + i * shentsize) for i in range(shnum)]
    strtab = secs[shstrndx][4]
    for s in secs:
        name = d[strtab + s[0]:d.index(b'\0', strtab + s[0])].decode('latin-1')
        if s[5]:
            print(f'{name:24s} type {s[1]:8x} addr {s[3]:8x} off {s[4]:8x} size {s[5]:8x}')
    print(f'image {size:x} bytes')


if __name__ == '__main__':
    main()
