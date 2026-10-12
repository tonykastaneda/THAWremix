# THAW Remix

Tony Hawk's American Wasteland on the PSP: THAW's areas, story, menus and look running in place of
THUG2 Remix's content, whose engine already runs there (and on a Vita through Adrenaline). Hollywood
loads, renders and is skateable, with story goals, THAW's HUD, menus, pause map, loading screens and
movies; `tools/mkumd.py` builds a bootable UMD image. Work has started on the same for the Project 8
PSP mod, which shares THAW's engine generation (`tools/p8zone.py`).

No game data is in this repository. Status, findings and open gaps are in [docs/LOG.md](docs/LOG.md).

## Local inputs (not committed)

| Path | Holds |
|---|---|
| `isos/` | THUG2 Remix, THAW PS2 and Project 8 disc images |
| `THAW CLEAN/Game` | THAW PC install, read by the converters (a junction to `..\THX\THAW CLEAN`) |
| `extracted/` | The images unpacked (`remix_psp`, `remix_data`, `thaw_ps2`, `thaw_ps2_data`), `dbg` names, Ghidra decompilation |
| `work/` | Builds, patched game trees, screenshots |
| `bin/pyenv` | Python venv with capstone, for `tools/mipsdis.py` |
| `bin/atracdenc` | ATRAC3plus encoder, for `tools/pmfmux.py` |

PPSSPP is at `E:\SYSTEMS\PPSSPP`; `tools/ppsspp_ws.py` drives a test copy of it.

## Layout

- `tools/thaw2psp.py` converts a THAW zone to Remix level files; `thawui.py`, `thawhud.py`,
  `thawscreens.py`, `casbackdrop.py` and `pmfmux.py` bring over its menus, HUD, screens and movies;
  `hostory.py` its story goals.
- `tools/hed.py` patches files into a game's `.hed`/`.wad`; `mkumd.py` builds the ISO.
- Format readers: `pak.py`, `qb.py`, `col.py`, `thawscene.py`, `thawqbdump.py` (THAW PC);
  `psplevel.py`, `psptex.py`, `pspimg.py`, `qb2.py`, `qbc.py`, `qbscripts.py` (Remix).
- `tools/prx2img.py`, `mipsdis.py`, `ghidra/scripts/DecompAll.java` for reading the Remix executable.
