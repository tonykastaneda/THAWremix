# THAW on Project 8 (PSP): session context

Where the port stands, how the work is done, and what comes next. The detailed history is in
`docs/LOG.md` (newest at the end); the memory plan is in `docs/memorybudget.md`.

## The project

- Base: vanilla Project 8 v1.00 (PSP). THAW's Hollywood replaces Houses' slot (`z_houses`); all of P8's
  story and maps get replaced by THAW's. The THUG2 Remix build (THX) is frozen and is the reference for
  how a problem was solved before.
- Scope right now: Hollywood only, until it is feature complete (story, goals, geometry, grinding).
  Story missions through the dinosaur head:
  1. Change Your Look (barber, `z_ho_goal_gaps15`)
  2. Change Your Clothes (clothing store, `gaps30`)
  3. Learn to Caveman (`counter` -> children `Gaps40`, `Gaps4`)
  4. Do a Sponsor Challenge (`gaps31`)
  5. Kickflip Whofleck (`gaps2`, then `Counter2`, `Gaps8`)
  6. Learn to Revert (`counter4`, `Gaps16`)
  7. Get Your Stuff Back (`gaps5`, `Gaps6`)
  8. Dinosaur head / protest (`highcombo`, `Highcombo2`, `Highcombo3` -> dino level event)
- Two ISOs per hardware tier is fine: PSP-1000, and PSP-2000/3000 (`P8V_BIG=1`). No runtime model detection.

## Workflow

### Build

- `python work/p8v/build.py` builds the unpacked test tree `work/p8v/tree` (about 20-60 s; `work/` is
  gitignored, so `build.py` changes are not in git: describe them in `docs/LOG.md`).
- Switches (environment variables):
  - `P8V_AUTO=1`: boot straight into Hollywood (tests).
  - `P8V_TESTGOAL=<goal id>`: the story opens with that goal instead of the barber.
  - `P8V_STORYRUN=1`: test build where the story plays itself (`p8goals.py storyrun`): it wins the active
    goal or activates the next one in `STORY_RUN`, with a panel naming the step.
  - `P8V_BIG=1`: PSP-2000/3000 build (MEMSIZE = 1 in PARAM.SFO, 4x ped heaps).
  - `P8V_NOINTRO=1`: no intro movies (they crash on hardware; use it for every hardware ISO).
  - `P8V_P8MODELS=1`, `P8V_P8PHYSICS=1`: keep P8's own models / physics (comparisons).
- Mission paks are cached in `work/p8v/missions_out`; delete it after changing `p8goals.missions`.
- Hardware ISO: `python tools/mkumd.py work/p8v/tree "work/iso/<name>.iso" --like "isos/Tony Hawk's Project 8 (USA) (v1.00).iso" --compact-wad PSP_GAME/USRDIR/datap --sectors`.
  ARK-4 needs "use extra memory" forced on for the big ISO.

### Test (always yourself, in the hidden emulator)

- Only the hidden test copy `work/ppsspp_test` (never visible, never `E:\SYSTEMS\PPSSPP`). PSP-1000
  memory (`PSPModel = 0` in its ppsspp.ini; set 1 only for a big-ISO run, then back to 0).
- `python tools/ppsspp_ws.py start work/p8v/tree` (or an .iso), `seq "wait:105000,circle:200,shot:work/shots/x.png,stick:0:-1:500,..."`, `stop`.
  Hollywood is in play about 105 s after start with `P8V_AUTO=1`.
- `python tools/p8trace.py <tree> "<steps>" <seconds> --arm-after <ms> --funcs LoadPak,GoalManager_WinGoal,... --out trace.txt`
  logs CFunc calls with their parameters (no `stick:` steps; use `up:`).
- Crashes: `work/ppsspp_test/ppsspp.log` shows `Bad memory access ... <pc>` (size-check it, then
  `tail`/`grep` only; never read whole logs). Function = pc - 0x08804000 in `extracted/decomp_p8`
  (`_index.txt`). For the caller of a generic null call, `python work/catch_at.py <pc hex> <arm s> "<steps>"`
  (breakpoint with `a0 == 0`, prints ra and stack).
- Hardware ISOs only for big batches of finished work.

### Edit tools

- `tools/p8goals.py`:
  - `shops`: the store and stats-board scripts.
  - `zone_script` / `zonescript`: replace a zone or mission pak script with qbc source.
  - `zone_append`: add lines before a script's endscript.
  - `scriptstr`: string literals inside a packed qb.pak script.
  - `igcpaks`, `storyrun`, `protesters`, `missions`.
- `tools/p8qb.py`: `rekey`, `rekeyall` (keys in packed scripts), `setdata` (keys or shorter strings in
  data, never in script bodies), `setstr`, `setfield`.
- `tools/thaw2p8skin.py <THAW .skin.wpc> <out> [--also <more parts>]`: THAW model -> P8 skin.
  `tools/p8zone.py` holds `PROFILES` (THAW ped profile -> P8 profile), `REPOINT` (P8 profile mesh path ->
  THAW model), `MERGE` (extra parts merged in) and `PED_PAK`.
- P8 qb dumps for reading: `work/p8v/qbdump/*.txt`, THAW's in `work/thaw_qbdump/`, Hollywood's zone
  scripts in `work/p8v/missions/z_ho_scripts.txt`.

### Report

- Commit each working step (message ends with the Co-Authored-By line), log it in `docs/LOG.md`, and
  text progress with screenshots: `python work/notify.py "<text>" [images]`.

## Done (2026-10-12/13 sessions)

- Emulator plumbing: log rotation and cap, a scheduled task to launch from SSH, CPU-ready wait.
- Level: Hollywood at 2.81 MB (`--texel 4 --tess 800`), decals lifted, grinding (THAW rails in the
  zone pak's rail asset), dinosaur building node flags (289).
- Big build (MEMSIZE), boot screens in P8's TGA layout, ISOs with sector-based .hed.
- THUG2 Remix physics and cameras by default (`tools/p8thug2.py`).
- Model converter (`thaw2p8skin.py`, strips, palettes, CLUT4; `--also` merges parts). THAW models for
  Mindy, the Barber, Boone, Murphy, DV guy, skaters, Reynolds, Rick Thorne, bums, Vato, Joey B. (dino
  head seller), the PETA protesters and the FallingDown guy (gaps13). PSP-1000 PedParts heap 1,152 KB
  (ped pak 1,087,584 bytes).
- Missions 1-2: Circle at the shop door opens THAW's store options in P8's own in-level CAS menus
  (Hair, Hair Color, Facial Hair / Shirt, Shirt Color, Pants, Pants Color), camera in front of the
  skater, live look change, Done wins the goal.
- Story chain: the whole sequence above runs in order to the dino level event and chapter 2. Fixes:
  - chapter_info success-pak folders made flat;
  - THAW mission `_text` paks converted;
  - IGC asset paks (`pak/igc/...`) skipped;
  - the dino event's flags (DINO_BEFORE 0, DINO_AFTER 1, DINO_BLDG_AFTER 1) set in the success pak's
    startup.
- Mission 4: the stats board is a poll in front of the skate shop ("O stat challenges"). The Sponsor
  Challenges menu opens and accepts. Fixes: Z_HO -> Z_Houses in stats.qb, missing poster sprites ->
  white2.
- PETA protesters created at the dinosaur while the dino step is not won.
- Hardware ISOs `work/iso/F THAW P8 stores.iso` (PSP-1000) and `G THAW P8 stores big (PSP-2000 3000).iso`
  (both no intro), checked in the emulator from the real menus. Not yet tested by the user on the PSP.
  They predate the protesters and the FallingDown model.

## Known gaps / not verified

- Winning the sponsor step by actually completing a stat challenge (THAW's M_ZHOGAPS31 gameplay pak
  waits for StatsManager_GetTotalGoalsComplete > 0).
- The dinosaur's after state on screen (flags traced only; THAW node positions are object origins, so
  cameras aimed from them missed), and the protesters disappearing at the event.
- The FallingDown giver not seen on screen (model extents match Joey B.'s).
- An occasional screenshot right after entering the barber shows the shop interior with no menu
  (likely another render pass); watch for it on hardware.
- Cutscenes and IGC scenes are skipped (THAW's .cut / IGC assets are not on P8's disc).

## Next session

1. Read the user's PSP results for ISOs F and G; fix anything hardware-only.
2. Stores with THAW's own parts: right now the barber and clothing stores offer P8's hair, shirts and
   pants. Convert THAW's CAS parts with the converter and give P8 part lists for them, as the THUG2
   Remix build did (check how Remix did it first). Mind PedParts / TopDown memory (`docs/memorybudget.md`).
3. Verify the sponsor win (complete one stat challenge in the emulator) and the dinosaur's after state
   on screen (find where the dino is drawn, e.g. from the level geometry, then place a camera).
4. Character select when starting a new story: right now Story -> Start New Story -> difficulty goes
   straight into Hollywood with the current skater. Add THAW's character select (pick a skater or
   create one) before the story starts, checking how the THUG2 Remix build handled it first.
5. Remaining Hollywood content: graffiti-goal taggers and other ambient peds (Pedestrians are left
   uncreated), Rick Thorne bike goals (Project Mod's BMX), vehicles, cutscenes.
6. A new hardware ISO batch once 2-5 land.

The overnight stop hook (`.claude/keep_working.py`) is switched off by `work/autopilot.off`.
