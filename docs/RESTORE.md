# Restore after local cleanup

Audited against the source and local inputs on 2026-10-20. This is a staged
restoration procedure, not a claim that the whole port rebuilds with one command.
Start with root `CONTEXT.md`; historical research is in LOG.

## What must be supplied

- Original Project 8 **PSP USA v1.00** for the base tree. Preserve its original
  unmodified files before invoking the build. Other releases may have incompatible
  script sizes and executable offsets.
- THAW PC install under `THAW CLEAN/Game` (including `data/models`), and unpacked
  THAW PS2 data at `extracted/thaw_ps2_data` for missions, scripts and cutscenes.
- Unpacked THUG2 Remix data under `extracted/remix_data` for physics and camera
  conversion, and its unpacked disc tree at `extracted/remix_psp` for the older port.
- **Project Mod** input, not just vanilla P8: the existing build explicitly reads
  `work/p8mod/tree/PSP_GAME/USRDIR/datap.hed` and `datap.wad` as additional ped assets.
  The local source image was `isos/thpm_mod_public-BMX.iso` (721348608 bytes).
  Extract that image to `work/p8mod/tree`. The input hash inventory identifies it.
- Debug-name tables under `extracted/dbg`. Converter name lookups use these; retain
  or regenerate them from the matching original debug inputs.

`docs/local-files.tsv` inventories the original excluded inputs/outputs by path and
size. `docs/input-hashes.json` fingerprints important original files and build
inputs. These inventories are not backups of those files.

## Restore sequence

1. Clone the private remote, restore the inputs above, and install `requirements.txt`.
   `work/p8v/build.py` currently hardcodes
   `C:\Users\tonyk\Documents\GitHub\THAWremix`; adjust its `R` on another machine.
2. Extract a **pristine** Project 8 disc tree to `work/p8v/tree`. Do not seed it
   from the patched Project Mod tree. Ensure `PSP_GAME/SYSDIR/BOOT.BIN` is the
   expected unencrypted executable. Verify the original-file hashes against the
   inventory before modifying anything. The build duplicates BOOT.BIN to EBOOT.BIN.
3. At first run the build creates `.orig` copies beside itself: archive HED/WAD,
   BOOT/EBOOT, PARAM.SFO, icons, sound and startup movies. Restoring originals into
   a tree that already has incompatible `.orig` files will not reset those backups.
   A clean work directory avoids this mismatch.
4. Restore the tracked custom logos and menu backdrop at their original `work/`
   paths. They are included in this remote; the former broad ignore rule hides
   other work outputs, but explicitly tracked work files still clone normally.
5. The **latest logged Q geometry is backed up** at
   `work/lifttest/q4/z_sc.psp_level` (2832690 bytes), with its collision output.
   Regenerate if needed using:

   ```powershell
   python tools/thaw2psp.py build "THAW CLEAN/Game" z_ho work/lifttest/q4 z_sc --at -2336.48974609375 96.596923828125 -2482.915283203125 --texel 4 --tess 800 --decal-lift 5 --decal-bias 4
   ```

   This command is reconstructed from the audited tool interface and LOG; it was
   not rerun during backup. Existing output and its hash are preserved instead.
6. Restore/recreate THAW startup PMFs at `work/p8mod/movies/start/`:
   `atvilogo.pmf`, `ns_logo.pmf`, `g_intro.pmf`. The current build **copies these
   even with P8V_NOINTRO=1**. That switch suppresses playback, not this dependency.
   See `tools/pmfmux.py` and the movie/ATRAC sections of LOG. The patched encoder is
   backed up at `bin/atracdenc/thaw/atracdenc.exe` with its source patch and base commit.
7. Build from the repo root with a clean environment (remove leftover P8V test
   switches first). For a no-intro PSP-1000 build using Q's geometry:

   ```powershell
   $env:P8V_LEVEL = 'work/lifttest/q4/z_sc.psp_level'
   $env:P8V_NOINTRO = '1'
   python work/p8v/build.py
   python tools/mkumd.py work/p8v/tree work/THAW-restored.iso --like "path/to/original-Project8-v1.00.iso" --compact-wad PSP_GAME/USRDIR/datap --sectors
   ```

   Set P8V_BIG=1 separately for PSP-2000/3000. **The build's default geometry path
   is older `work/p8mod/ho/z_sc.psp_level`; it does not automatically select Q.**
   The latest Q ISO used intros; this no-intro restore command is a practical test
   variant, not a claim to reproduce the historical ISO byte for byte.
8. Recreate isolated PPSSPP at `work/ppsspp_test`, including executable/assets and
   portable `memstick/PSP/SYSTEM/ppsspp.ini`. Set debugger startup and port 45678.
   Use SoftwareRenderer=True for reproducing the PSP rendering issues described
   at the end of LOG, and PSPModel=0 for the 1000 memory budget. The helper's older
   D3D11-only docstring predates that software-renderer finding. Do not point test
   scripts at the user's main emulator installation.

## Status and next work

Q applied 4 depth units of decal bias, with 322 biased lists. Distant crosswalk
flicker, near-camera dropped geometry and sign/mipmap behavior need follow-up.
The latest Q hardware outcome is not recorded. Earlier ISO N improved the worst
flicker on the user's PSP-3000 but left posters and crosswalks flickering.

The existing `docs/CONTEXT.md` is older: it predates the rendering work and says
cutscenes are skipped. Current `build.py` attempts `HO_LevelEvent_Dino` conversion
via `p8cut.py`; do not infer that it is successfully tested from its presence.
Read the later LOG and current code before continuing mission/cutscene work.

Generated mission/model/QB caches are rebuilt by `build.py` as needed. A missing
cache is normal after a clean clone; a missing source archive, Project Mod input,
movie input or backdrop is not. Do not substitute another game version silently.
