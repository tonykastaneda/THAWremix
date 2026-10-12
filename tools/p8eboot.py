"""Code patches to Project 8 PSP's executable (the Project Mod's SYSDIR/EBOOT.BIN, an unencrypted PRX).

  p8eboot.py <EBOOT.BIN in> <EBOOT.BIN out>

Offsets are module addresses (file offset - 0x74; loaded at 0x08804000). Each patch checks the
original word first, so running it on an already patched file fails instead of patching blind.

  boot_movies  0x1db920: the function that runs the scripts 0x36932fca and startup_loading_screen
               once (startup_loading_screen plays movies\\start\\{atvilogo,p44,shaba,ns_logo,g_intro}
               on PSP) returns early when FUN_000927fc is non-zero, which it always is, so the
               shipped game never shows its intro. The branch becomes a nop.
"""
import struct
import sys

TEXT = 0x74
PATCHES = {  # name: (address, original word, new word)
    'boot_movies': (0x1db920, 0x14400015, 0x00000000),  # bnez v0, +0x15 -> nop
}


def main():
    src, dst = sys.argv[1:3]
    d = bytearray(open(src, 'rb').read())
    for name, (addr, old, new) in PATCHES.items():
        cur, = struct.unpack_from('<I', d, addr + TEXT)
        if cur != old:
            raise SystemExit(f'{name}: {addr:#x} holds {cur:#010x}, expected {old:#010x}')
        struct.pack_into('<I', d, addr + TEXT, new)
        print(f'{name}: {addr:#x} {old:#010x} -> {new:#010x}')
    open(dst, 'wb').write(d)


if __name__ == '__main__':
    main()
