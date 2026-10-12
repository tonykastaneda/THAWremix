# THAW on Project 8: memory budget plan

Goal: know, with numbers, how much memory each part of the THAW story port costs on Project 8 PSP,
and how much is left, before adding the heavy pieces (cutscenes, THAW ped and prop models,
GameObjects, store paks, the Project Mod physics/camera). Targets: PSP-3000 and Vita (64 MB).

## What is known (2026-10-12)

- Memory is per area, not cumulative: only the current zone, its goals and the current mission pak
  are loaded. Each THAW area has to fit on its own, as P8's own levels do.
- Heaps at the story's pause menu in Hollywood (default build, before the save fixes;
  `tools/p8heaps.py`):

  | heap | size | free |
  |---|---|---|
  | TopDown / BottomUp (one shared main region) | 20,115,456 | 422,416 |
  | COIMHeap | 652,288 | 652,288 (unused) |
  | GoalHeap (mission paks) | 306,000 | 276,160 |
  | PedParts | 401,472 | 48 (full) |
  | skatergeomheap0 | 473,088 | 220,064 |
  | AnimHeap | 131,072 | 59,392 |
  | Network / FrontEnd | 240,640 | 83,744 |
  | skaterheap0 | 70,000 | 1,272 |
  | Script cache small | 51,200 | 248 |

- In-game saving needs ~440 KB of temporary script pools on the main heap (20000 CComponent, 9000
  CStruct, 3000 CVector). Fixed for now by stripping Houses' unused props from the Hollywood pak
  (-273 KB) and releasing the COIM heap during saves (docs/LOG.md, "In-game saving fixed").
- Hollywood's zone pak is 1,744,976 bytes now (Houses' stock: 1,545,920); its collision is 1.1 MB
  (Houses: 0.7 MB); its .psp_level is 3.9 MB (Houses: 2.85 MB).
- **The hidden test copy emulates a PSP-1000** (`PSPModel = 0` in
  work/ppsspp_test/memstick/PSP/SYSTEM/ppsspp.ini): 32 MB. Every number above was measured on the
  smallest model. P8's executable has a `GotExtraMemory` script CFunc, so it may use the extra
  32 MB of the PSP-2000/3000 (and Vita): unverified.

## Tools

- `tools/p8boot.py <tree> <tag> "<seq>"`: boot the hidden test copy, press buttons, take shots
  (work/shots/<tag>_NN.png); the emulator keeps running for measuring.
- `tools/p8heaps.py`: print every heap's size and free bytes from the running game.
- `tools/p8trace.py`: trace script calls (Printf, LoadPak, goals, any CFunc by name or address,
  `--arm-after <ms>` to set breakpoints late), with return address and call chain.
- `python work/p8v/build.py` rebuilds the default build (THAW story); `P8V_NOGOALS=1` builds
  without THAW's goals, `P8V_ZONE='houses\worlds\worldzones\z_houses'` puts P8's own Houses back.
- Stop the emulator before a build: `python -c "import sys;sys.path.insert(0,'tools');import
  ppsspp_ws as p;p.kill()"`. Never touch E:\SYSTEMS (the user's emulators); test copy only.

## Plan

### 1. Which PSP model, and does P8 use the extra memory? (first)

1. Find what `GotExtraMemory` does (CFunc table lookup as in p8trace.cfunc; read its function in
   extracted/decomp_p8) and where scripts or the executable use it (grep the qbdump for
   GotExtraMemory; look for sceKernel extra-memory/partition calls in the decompile).
2. Set the test copy to a PSP-2000/3000 (`PSPModel = 1`; test copy only), boot, and compare
   `p8heaps.py` at the same points. If the main region grows, the 32 MB numbers are the floor, not
   the budget. Decide whether PSP-1000 support matters (the stated targets are PSP-3000 and Vita).
3. If P8 does not use the extra memory on its own, find out whether it can be made to (a heap
   size constant, a model check in the executable) and what that would take. Record it.

### 2. Measure the current state at fixed points (both models)

Same build, same button sequence, `p8heaps.py` at each point, saved as a table in docs/LOG.md:
- main menu; Story start (in Hollywood, no goal active); a goal running (caveman lesson via
  `P8V_TESTGOAL=z_ho_goal_counter`); the save screen; Free Skate in Hollywood; Free Skate in P8's
  Houses (reference).
- Also note the free main heap during the barber/clothing goals and with the mission paks loaded.

### 3. Find the big consumers

- Zone pak per entry type (`p8zone.load_pak`, as in the save investigation): collision, node
  array, scripts, peds file.
- Node array: count nodes of classes never created (Pedestrian, Vehicle, GameObject leftovers);
  what removing them would save (they shift node indices: check what refers to them first).
- Collision: compare THAW's Hollywood .col layout with P8's levels (sector count, face data);
  whether anything can go (e.g. net-only or hidden sectors).
- The .psp_level (3.9 MB): which heap holds the scene, and whether texture sizes can drop.
- COIM heap: what uses it in P8 (peds/objects streaming?), whether Hollywood ever fills it during
  play (watch it with p8heaps over a few minutes of skating and goals). If never, shrink it
  permanently at level start (`ResizeCOIMHeap newsize = <n>`), not only during saves.
- PedParts (full): what is in it with THAW's goal peds mapped to P8 profiles.

### 4. Budget the remaining THAW work

For each, estimate (from THAW PS2 file sizes) and where it would live:
- THAW cutscenes (P8 unloads goals during cutscenes: check what it frees).
- THAW ped models for goal givers (PedParts budget) and a small crowd.
- THAW props and GameObjects (chairs, tables, letters, tape, shop doors, bus).
- Store paks (z_ho_barbershop_data 267 KB, clothingshop 1.16 MB, skateshop 598 KB; loaded into
  UnloadableAnim only inside a shop).
- The Project Mod physics/camera scripts (qb.pab growth; script pools).
- The other areas (largest THAW zones' pak/col/scene sizes against Hollywood's).

### 5. Write the budget

docs/memorybudget.md gets a table: per heap, what fits, what is reserved for saves, what each
planned feature costs, and the order to add them. Then decide: Project Mod physics/camera, shops
(option B: THAW shop scripts with P8's in-level CAS parts), cutscenes, models.

## Rules for every step

- Verify in the hidden PPSSPP test copy and look at the screenshots; never count them.
- After any change that adds memory: re-check in-game saving (story save prompt Yes, pause Save
  Game) and a goal (caveman via P8V_TESTGOAL).
- Remove test saves from the test copy's memory stick afterwards
  (work/ppsspp_test/memstick/PSP/SAVEDATA/ULUS10197THP8-*).
- Commit working steps, log them in docs/LOG.md, text progress with work/notify.py.
