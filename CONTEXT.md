# Start here — THAWremix

Backup/handoff updated 2026-10-20. Private remote: `tonykastaneda/THAWremix`.

## Read order and current state

1. `README.md` for the format tools and local input layout.
2. `docs/CONTEXT.md` for the Project 8 workflow, mission chain and build switches.
3. **The end of `docs/LOG.md` takes precedence over the older context.** The latest logged
   build is **Q THAW P8 decal depth bias.iso** (2026-10-14). It uses per-material viewport
   depth bias for distant crosswalk flicker. Hardware results for Q are not recorded here.
4. `docs/memorybudget.md` before increasing geometry, texture or ped memory.

This ports THAW Hollywood to PSP Project 8, using the older THUG2 Remix port as a
reference. Current open rendering problems include near-camera geometry dropping out,
decal flicker and the diner's sign/mipmap behavior. Do not assume the older F/G ISO
status in `docs/CONTEXT.md` describes the latest work.

## What the remote contains

All tracked conversion, archive, QB, executable and emulator tools in `tools/`,
Ghidra's `ghidra/scripts/DecompAll.java`, documentation/history, and selected original
build/debug scripts at their original `work/` paths. Those scripts were previously
hidden by the broad work-directory ignore. They are explicitly tracked now; other
generated work stays ignored. The logo-generation script is included too.

Dependencies: Python with `numpy`, `Pillow` and `capstone` (`requirements.txt`),
PPSSPP, FFmpeg for movie work, and the patched ATRAC encoder described in
`tools/atracdenc_thaw/README.md`. The existing encoder binaries and supporting files
are backed up under `bin/atracdenc/`; the Python virtual environment is excluded.
Some scripts use hardcoded paths to this machine or
the former `THX` folder; inspect those before running on another machine.

## Build and restore

Run from the repository root. Active build entry point:

```powershell
python -m pip install -r requirements.txt
$env:P8V_NOINTRO = '1'
python work/p8v/build.py
```

**A clone alone is not a ready-to-run build.** Restore original disc images and the
THAW PC `THAW CLEAN/Game` input; unpack to the paths in README. Restore/recreate
`work/p8v/tree` from vanilla Project 8 v1.00. The build saves and restores pristine
`datap.hed.orig`, `datap.wad.orig`, `BOOT.BIN.orig`, and `EBOOT.BIN.orig` beside itself.
It also consumes previous conversion outputs under `work/p8mod`, front-end inputs
under `work/p8v`, backdrop/logo images, and converted movies. These generated data
are local only. Follow the build script and LOG to regenerate them; this backup has
not been tested as an automated fresh-machine rebuild.

Use `tools/mkumd.py` and the ISO command in `docs/CONTEXT.md` after building. Use the
isolated `work/ppsspp_test` emulator for checks. Older `work/run_bg.py` targets THX
and is preserved for reference, not the current P8 build. `work/p8v/calib.py` is a
menu-backdrop experiment. `work/catch_*.py` are breakpoint/debug helpers;
`work/exp_*.py` and `work/mklayers.py` are experiments.

## Backup boundary

ISOs, extracted game data, generated trees, local emulator/encoder installations,
screenshots and other bulky work remain on this PC. Nothing was moved or deleted
during this backup. Keep those directories until separately backed up. Notification
scripts and local automation settings are not required for building and remain local.

Next: obtain Q's PSP/software-renderer results, continue the rendering fixes from
the end of LOG, and record the exact build switches with each new hardware ISO.
