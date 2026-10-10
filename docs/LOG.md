# Overnight log, 2026-10-10

Goal for the night: a playable THAW slice in Bevy (load one level from the clean install, skater
rolling, ollie, grind), plus BMX XXX unpacked and loaded into Ghidra.

## Decisions I made on my own

| Question | Decision | Why |
|---|---|---|
| Which THAW executable to analyse | `D:\Games\THAW\Game\reTHAWed.exe` (read-only) | The clean `THAW.exe` is SecuROM-protected: its code sections are encrypted on disk (entropy 8.00, none of the physics parameter hashes appear in it). I did not try to defeat that. The mod's executable is plain x86 and contains the same engine. Formulas taken from it may include mod changes; all *values* come from the clean install's data. |
| Which level first | Hollywood (`z_ho`), `--zone` picks another | It is the game's first level; Skate Ranch (`z_sr`) also loads. |
| What to render | The game's own textured geometry (`--collision-view` shows the collision mesh instead; F1 toggles rail lines) | Decoded `.geom` and `.tex` later in the night; see formats. |
| Which zones to load together | Every area that shares the chosen area's space, with tunnel pieces and shops (`--area-only` loads just the one) | Loading every zone at once overlapped. Measured from collision: Hollywood, Beverly Hills, Santa Monica, Downtown, the casino and the oil rig do not overlap each other, so they share one space; East LA sits on top of Downtown, the Vans park on Hollywood and the Skate Ranch across Beverly Hills, so those have their own origin and load alone. For neighbouring areas I drop the far backdrop shell (bounding radius over 6,000 in) and the props stored at the origin. An overhead screenshot shows the six areas as separate neighbourhoods joined by tunnels. |
| Skater stats | All stats at 5 | That is `Skater_Default_Stats` in the game's scripts. |
| Auto-kick | On | The series default; without it you would have to hold a push button. |
| Units | Inches and seconds, +Y up, 60 Hz fixed step | The game's own; the executable multiplies several per-frame terms by 60. |
| Bevy version | 0.15 | API I could write reliably unattended. Builds on the GNU toolchain already installed. |
| BMX XXX version | Xbox as the main target, PS2 and GameCube also unpacked | See the BMX XXX section. |
| Tools installed | `extract-xiso` (downloaded into `bin/xiso`, not installed system-wide) | You offered it; nothing else was needed. Nothing was installed globally. |

## THAW: what is understood

Formats (readers in `tools/*.py` and `thaw-bevy/src/formats`):

- **`.pak.wpc` / `.pab.wpc`**: archive header of 0x20-byte entries (extension hash, offset relative to
  the entry, size, name hashes, flags; 160-byte name when `flags & 0x20`).
- **`.qb`**: script data. Top-level items are sequential; structs are linked lists; arrays hold
  inline values or pointers. Script bytecode is located but not interpreted.
- **`.col` v10**: 0x50-byte header, 0x40-byte objects, float and 1/16-inch fixed verts, 8- or 10-byte
  faces with flags and terrain type. Validated on two levels: 0 bad indices, 0 verts outside bboxes.
- **Node arrays**: restarts and rail nodes with links. "Compressed" nodes inherit shared fields from a
  named top-level struct.
- **`.geom`**: 963-1,528 materials of 0x120 bytes (texture checksum at +0x40), then a `BABEFACE` scene
  block with 0xE0-byte mesh headers (material, vertex stride and attribute offsets, counts, buffer
  offsets). Vertices are position, normal, BGRA colour (0x80 = full) and UVs; indices are 16-bit
  triangle strips. All 2,390 Skate Ranch and 3,027 Hollywood meshes pass index checks.
- **`.tex`**: `ABADD00D`-tagged textures, DXT1/DXT5 (a few raw), with mip chains. Uploaded to the GPU
  still compressed.
- **Sectors**: each named level piece owns a consecutive run of meshes (count at +0x4C of its 0x68
  record); the counts sum exactly to the mesh total. Every sector and collision object has a node.
  Pieces without `CreatedAtStart` (320 of 1,041 in Hollywood: story and script variants) are
  dropped from rendering and collision; `LevelObject`s are moved from the origin to their node
  position.
- **`dbg.pak.wpc`** holds 139,692 hash-to-name pairs, which is why every parameter has its real name.

Physics values are read at runtime from `scripts\game\skater\physics.qb` inside `qb.pak.wpc`.
Stat-driven values evaluate as `lo + (hi - lo) * stat * 0.1`.

Read out of the executable (function addresses in `reTHAWed.exe`):

| Behaviour | Function | Result |
|---|---|---|
| Parameter lookup | `0058ee20`, `0058f270`, `0058f070` | Stat formula above; `limit` clamps |
| Air/heavy friction | `005c89a0` | `v -= v̂ · dt · |v|² · c · 60` |
| Rolling friction | `005c8ca0` | `v -= v̂ · dt · c · 60` |
| Speed limit | `005ca8f0` | Horizontal speed clamped at max-max; heavy friction above max |
| Kick | `005caef0`, `005cb050` | Push along forward while below the kick speed, on ground within 85° of level |
| Brake | `005caca0` | `Physics_Brake_Acceleration`; stop when below two frames of braking |
| Turning | `005d61f0` | Rate lerps from sharp (slow) to normal (at max speed); velocity turns with the board |
| Ground gravity | `005e4200` | World-down gravity, doubled when moving downhill, then kept in the ground plane |
| Air gravity | `005c8df0` | `Physics_Air_Gravity / hang stat` (vert uses the vert hang stat) |
| Ollie | `005dddc0` | Speed lerps min→max over `Skater_max_tense_time`; added to world +Y |
| Balance meter | `00587970` | Instability grows with time; lean accelerates; random drift when no input |
| Trick value | `0056a3e0`, `0056c0c0` | `base � spin/2 � repeat%`; spin factors 2,3,4,5,6,7 per 180�; repeats 100/75/50/25/10 %; switch +20 % |
| Ground stick | `005d4ef0` | Leaves the ground on a convex edge sharper than `Ground_stick_angle` unless the drop is small (structure matches mine; not ported line by line) |
| Wallride entry | `005d6f00` | Grind button within its window, `Wall_Ride_Delay` since the last one, min speed, max incident angle |
| Rail search | `0058cee0` | Nearest rail segment to the frame's movement segment, within `Rail_Max_Snap` |

Reimplemented from the series' known behaviour, not yet checked against the executable: wall bounce, landing alignment and sideways bails, vert re-entry,
rail corner following, manual input window, grind type selection, the revert window
(0.3 s) and its 100 points, the wallride's 200 points and how it ends.

## THAW: verified results

`thaw-bevy.exe --headless roll|grind|vert` runs scripted scenarios without a window:

- **roll**: spawns at "P1: Restart", settles at 454 in/s on the flat (kick speed limit is 445),
  ollie peaks 72.7 in (432 in/s at −1350 in/s² predicts 69), kickflip scores 100.
- **grind**: 6.4 s on the Capitol Records rail chain round a corner, flies off the end, lands, banks 866.
- **vert**: rides up a vert face, Indy in vert air, lands on the same face, reverts into a nose manual
  with the combo still open.
- **lip**: vert air, grind button on the way down stalls on the coping for 1.5 s on the lip balance
  meter (Invert, 500), drops back in, lands, banks 676.
- **wall**: glancing airborne approach to a wall-ridable face, wallride, ollie off, land, combo banked.

`--screenshot <png>` runs a short scripted session in the window and saves a frame.

## Known gaps

- Six areas load as one world, but nobody has ridden a tunnel end to end yet, so seams are unchecked.
  East LA, the Vans park and the Skate Ranch still need a teleport from their tunnels.
- Pieces that scripts create or kill later (story changes, breakables) stay in their level-start
  state. The two ends of a tunnel are different geometry, so the offset cannot be read off them. A kill plane resets you if you leave the map.
- A few additive effects (light cones) render as solid shards. The Skate Ranch loads in its
  level-start state, which is mostly bare dirt: the park pieces arrive through the story.
- The sky is `default_sky` for every area. No animated or multi-pass materials, no level objects, no translucency sorting.
- No skater model or animation: a capsule on a board.
- Lip tricks use four of the game's definitions (Invert, Axle Stall, Rock to Fakie, Blunt to Fakie)
  with their real scores; which direction picks which is my mapping. No wallplants, spine transfers, acid drops, walking, BMX, or special tricks.
- Nobody has played it by hand yet: the scenarios check that mechanics work, not that they feel right.
- Level objects with their own collision (`data\models\*.col.wpc`) are not placed.
- Script bytecode is not run, so triggers, gaps and goals do nothing.

## BMX XXX

All three discs are unpacked under `extracted/`:

| Version | How | Executable | State |
|---|---|---|---|
| PS2 | 7-Zip | `SLUS_204.15`, MIPS ELF, no symbols | Imported into Ghidra; stock MIPS support fails on most functions, needs the Emotion Engine extension |
| GameCube | DolphinTool (`.rvz` works directly) | `main.dol`, PowerPC | Unpacked only; includes test levels (`TST_FLAT`, `TST_GRND`, `TST_VERT`) |
| Xbox | extract-xiso | `default.xbe`, x86 | Flattened to a memory image (`tools/xbe2img.py`), imported into Ghidra with a raw loader, 2,876 functions decompiled to `extracted/decomp_bmx_xbox` with no decode failures |

The game is Z-Axis's engine ("Zge4"), written in C. Assert strings name the source files
(`\bmx3\src\com\action\physics.c`, `camera.c`, `game.c`), and the discs carry plain-text config
(`scene.txt`, level `objctv.txt`, editor `.txt`).
