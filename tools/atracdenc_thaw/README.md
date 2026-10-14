# atracdenc for PSP movies

pmfmux needs ATRAC3plus at the PSP movie player's rates. Upstream atracdenc fixes the ATRAC3plus frame at
2048 bytes (352 kbps), and P8's movie player crashes on it on hardware (ISO I, 2026-10-13). This
patch adds `AT3P_FRAME_BYTES` (default 2048): 744 = 128 kbps (`0F D0 28 5C`, P8's movies), 560 = 96
kbps (`28 45`, Remix's). The encoder's bit allocation already follows the frame size.

`pcm_io_rawwav.cpp` is a minimal 16-bit WAV reader backend, so it builds with MinGW alone (no
libsndfile, no MSVC).

Build (base commit in `BASE_COMMIT`):

    git clone https://github.com/dcherednik/atracdenc.git && cd atracdenc
    git checkout <BASE_COMMIT> && git submodule update --init --recursive
    git apply atracdenc_thaw.patch && cp pcm_io_rawwav.cpp src/
    mkdir build && cd build
    cmake .. -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release -DATRACDENC_PCM_IO_BACKEND=rawwav \
      -DCMAKE_EXE_LINKER_FLAGS="-static -static-libgcc -static-libstdc++"
    mingw32-make atracdenc   # -> src/atracdenc.exe, copied to bin/atracdenc/thaw/
