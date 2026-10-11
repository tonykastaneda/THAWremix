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
  A piece exists if it has `CreatedAtStart`, or its `CreatedFromVariable` node flag is on. Flag
  values come from the game's own free-skate script (`game_progress_set_non_story_mode_nodeflags`
  in `chapter_info.qb`, LZSS-compressed bytecode: 273 flags, 124 on), so the world is in its
  unlocked state and the Skate Ranch is fully built. Everything else is dropped from rendering,
  collision and rails; `LevelObject`s are moved from the origin to their node
  position.
- **`dbg.pak.wpc`** holds 139,692 hash-to-name pairs, which is why every parameter has its real name.

Manual triggers come from `manualtricks.qb`: up then down (or down then up for a nose manual)
within 400 ms, valid for 700 ms before landing; from rolling, within 220 ms.

Grind base scores sit inside script bytecode in `grindscripts.qb`: 50-50, Nosegrind and 5-0 are 100,
Crooked, Overcrook and Smith 125, Tailslide and Noseslide 150, Boardslide and Lipslide 200. Eight of these
are triggered, named FS or BS by which side the rail is on; which stick direction gives which grind
is the series convention, not read from the game.

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
rail corner following, grind type selection and FS/BS side, the revert window
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
- **boneless**: up, up, then jump gives a Boneless: 99.5 in high against 72.7 for an ollie, 250 points.
- **shove / impossible / varial / heelflip**: each flip trick fires from its direction and spins the
  board its own way (checked in screenshots). Landing before the board is back under the feet bails.
- **wall**: glancing airborne approach to a wall-ridable face, wallride, ollie off, land, combo banked.

`--headless soak` feeds 120,000 frames (33 minutes) of random input: no panics and no non-finite
state in Hollywood, Beverly Hills, Skate Ranch or the Vans park. Hollywood never left the level; the
others did 11 to 40 times, mostly by launching off ramps at the map edge.

`--screenshot <png>` runs a short scripted session in the window and saves a frame.

## Known gaps

- Six areas load as one world, but nobody has ridden a tunnel end to end yet, so seams are unchecked.
  East LA, the Vans park and the Skate Ranch still need a teleport from their tunnels.
- Objects built from separate model files (`data\models`, 723 of them: doors, shop interiors, props
  with their own collision) are not loaded. Example: the Roosevelt hotel entrance in Hollywood has
  no floor or wall in any level collision. Rolling toward a bottomless gap now bounces you back as
  if it were a wall; jumping into one still falls to the kill plane.
- Pieces that scripts create or kill later (story changes, breakables) stay in their level-start
  state. The two ends of a tunnel are different geometry, so the offset cannot be read off them. A kill plane resets you if you leave the map.
- A few additive effects (light cones, spotlight beams) render as solid shards.
- The sky is `default_sky` for every area. No animated or multi-pass materials, no level objects, no translucency sorting.
- The rider is modelled on the character sheet you supplied (green hoodie, black baggy trousers,
  backwards cap with lime brim, red hair and sunglasses, lime-wheeled board with a bolt graphic).
- He is built in code from rounded lofted parts with flat colour, one shadow tone and thin ink
  outlines (inverted shells), plus a 48x16 pixel sheet for face, hoodie print and board graphic,
  and is posed procedurally
  (stand, crouch, tuck, grab, balance, bail, board flip). By your choice it is not the game's model;
  the game's `.skin`/`.mdl` files do parse with the level-geometry reader if that changes.
- Trick slots follow the game's default mapping in `protricks.qb` (16 air tricks with diagonals,
  8 lip tricks) with real names and scores; double-tap and special tricks are not in. No wallplants, spine transfers, acid drops, walking, BMX, or special tricks.
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

## THAW on THUG2 Remix (PSP), started 2026-10-10

Goal: THAW's areas and trick feel running on a PSP (and on a Vita through Adrenaline) by replacing
the content of THUG2 Remix, whose engine already runs there. Areas become separate levels. The Bert
slide is cut; its two story uses (Iggy's lesson at the ranch, the Santa Monica pier goal) get another
move. Milestone 1 is Hollywood loading in Remix under PPSSPP, skateable.

Inputs (not committed): `THAWremix/` holds the Remix and THAW PS2 images; PPSSPP is at
`E:\SYSTEMS\PPSSPP`. Unpacked to `extracted/remix_psp`, `extracted/remix_data`, `extracted/thaw_ps2`,
`extracted/thaw_ps2_data`.

What is understood:

- **`.hed`/`.wad`** (`tools/hed.py`): offset, size, path. Remix uses byte offsets, THAW PS2 sector
  numbers. `replace` patches a file into the unpacked Remix folder, which PPSSPP boots directly.
- **Remix executable**: `BOOT.BIN` is an unencrypted ELF linked at 0. `tools/prx2img.py` flattens it
  for Ghidra's raw loader; 9,631 functions are in `extracted/decomp_remix`. Stock Ghidra cannot
  decode the VFPU routines, so those are read with `tools/mipsdis.py` (capstone in `bin/pyenv`).
- **`.psp_level`** (`tools/psplevel.py`, layout in its header comment): one file holds a level's
  textures, visibility boxes, vertices, per-material GE display lists and a stream of triangle
  strips. Read from the loader at `0005fcb0` and the strip interpreter at `00061690`. The reader
  accounts for every vertex byte in all 80 shipped files.
- **Collision** is version 10 in both games with the same 0x40-byte object records; THAW's header
  is 0x30 bytes longer.

Verified in the running game (`tools/ppsspp_shot.ps1` boots, presses keys and saves frames): with
every vertex colour in `tr.psp_level` set to red and patched into the wad, the training level
renders red. The key sequence `25:z,6:ENTER,6:ENTER,6:ENTER,8:z,18:z,10:z,3:z` reaches gameplay
through "Continue Story Mode" on the existing save, which opens the training level.

Budget, Boston against THAW PS2 Hollywood: 53,000 triangles and 1.2 MB of 16-colour 64x64 textures
in a 2.5 MB `.psp_level` plus 0.9 MB collision, against 3.3 MB textures, 3.0 MB geometry and 1.1 MB
collision. Geometry outside the 16-bit range (8,192 in either side of the level offset) uses the
20-byte float vertex format, as Remix's own backdrops do.

Still to do for milestone 1: a `.psp_level` writer; THAW geometry to strips of at most 31 vertices
with boxes; textures to swizzled 16- or 256-colour; the `.geom.psp` sector list (not yet read);
collision header conversion; a THUG2-format level `.qb` with restarts and rails, repacked into its
`.pre`.

### Milestone 1 reached, 2026-10-10 evening

THAW PC Hollywood (`z_ho`) loads in THUG2 Remix under PPSSPP in place of the training level, renders
fully (streets, buildings, signs, translucent decals) and is skateable on its own collision.
`tools/thaw2psp.py build "THAW CLEAN/Game" z_ho work/out tr --at <tr P1 restart>` writes
`tr.psp_level` (3.8 MB) and `tr.col.ps2` (1.1 MB); `hed.py replace` patches both into the unpacked
game (it now repoints every index entry with the name; `tr.psp_level` is listed twice).
`tools/ppsspp_ctl.ps1` drives a running PPSSPP one key or capture at a time.

How the conversion works (`tools/thawscene.py` reads THAW, `tools/thaw2psp.py` writes Remix):

- **Placement.** The zone is shifted so its "P1: Restart" lands on the training level's
  (-3020.95, -765.41, -3511.32), so the training level's scripts load unchanged. The shift is a
  whole number of sixteenths (the collision grid) and there is no rotation, so you spawn facing
  the other way.
- **Visibility boxes were misread before.** They are 8 half floats, (min xyz, 0, max xyz, 0) in
  vertex space / 32768, converted with `vh2f` in the VFPU box test at `0006154c`. Checked on `tr`
  and `sz`: every vertex lies inside the box its strip names. Boxes written as integers culled
  almost everything. `psplevel.py`'s header comment is corrected.
- **Boxes**: one per piece (sector) per 4,096-inch cell; 877 for Hollywood (limit 2,045).
- **Material lists**: one per distinct THAW material state, each setting all texture and blend
  state (lists run back to back and only change what they name). Material switches are signed
  16-bit word indices, so the list block must stay under 32,768 words; identical lists are shared.
  Blend from the material record: +0x90 pass-0 blend mode (0 opaque, 1/2 add, 5 blend, 6 fixed
  blend, alpha at +0x93), +0xA0/+0xA2 UV clamp. Alpha textures in mode 0 and hard-edged mode 5
  are alpha-tested in the opaque pass; the rest go to the translucent pass.
- **Textures**: DXT decoded, longest side 64, quantised to 16 colours (CLUT4, 32-bit palette),
  swizzled, up to 4 mips: 746 textures in 1.4 MB.
- **Geometry**: THAW strips cut to at most 31 vertices; triangles over 400 inches tessellated (the
  PSP drops triangles crossing the near plane rather than clipping). Vertex colour 0x80 maps to
  nibble 8 because the texture function doubles colour (`TEXFUNC 0x00010100` in the render setup
  at `000608dc`). Culling is off in every list. Strips beyond the 16-bit range use the wide format.
- **Collision**: THAW's header is 0x30 bytes longer; dropping those bytes keeps every offset valid.
  The block order is objects, vertices (aligned 16), intensities, faces (aligned 4), one byte per
  large face (padded to 4), BSP node array size, nodes, face indices. Bounding boxes, float
  vertices and BSP split points (sixteenths, axis in the low two bits) are shifted; fixed-point
  vertices are relative to the object box and need nothing. Pieces absent at level start and
  LevelObjects (modelled at the origin) get `mFD_NON_COLLIDABLE` on every face; the trigger bit is
  cleared. A checker walked all 7,091 BSP leaves after conversion: every face lies in its cell.
  Terrain types (max 32) are inside Remix's range.

Not done yet: rails and other nodes (the training level's node array still loads, so no grinds on
Hollywood rails, and the training goals' positions are meaningless), LevelObject collision, the
`.geom.psp` sector list (the training level's is left in place and nothing has complained), the
sky (training level's), and memory headroom has not been measured on real hardware.

The test path in the unpacked game: `work/datap.hed.orig` is the untouched index; restoring it
restores the stock game (patched files were appended to the wad, original data untouched;
`work/datap.wad.size` holds the original wad size for truncating).

Project Mod (`E:\ROMS\PSP\Tony Hawk Project Mod.chd`) turned out to be a community build on Page 44's
Project 8 PSP engine (`Skate8c`), carrying Remix levels and THUG1's Hawaii in the same `.psp_level`
v11 format (they pass `psplevel.py check`), so someone else has also imported foreign levels into
this format. The THUG source port at github.com/iwannagooutside/thug-vita-port supplied the
collision loader and BSP layout used above.

### Rails, level objects and sky, same evening

- **Rails grind.** `build ... --qb <tr.qb> --pre <tr_scripts.pre> --pre-entry levels\TR\TR.qb`
  rewrites the training level's node array (`tools/qb2.py` reads and writes the THUG2 token
  stream; the array round-trips byte-exactly in meaning): its 449 rail and 177 climbing nodes
  are sunk 100,000 inches below the map, keeping every index, name and link its scripts rely on,
  and Hollywood's 1,530 rail nodes that exist at level start are appended with links
  renumbered. The new `TR.qb` goes into `pre\tr_scripts.pre` uncompressed (other entries keep
  their original bytes) and over the loose `levels\tr\tr.qb`. In game: FS 50-50 on a Hollywood
  ledge, 128 points. THUG2 nodes come in two forms: full, and compressed (Pos, Angles, Name plus
  an unnamed reference to a shared struct holding Class and the rest).
- **LevelObjects with collision** (fans, signs, posts, the crane): the 28 that exist at start and
  are unrotated (three posts at 1 degree count as unrotated) are moved to their node in the
  collision too: box, float vertices and their own BSP subtree. The leaf checker still finds
  every face inside its cell.
- **Sky**: `thaw2psp.py sky "THAW CLEAN/Game" default_sky <out>` converts THAW's dome, scaled to
  the 7,800-inch compact dome Remix skies use (offset 0); patched over `levels\tr_sky`.
- `.pre` header word at 0x0C is not the plain sum of entry sizes (some buffer size hint); it is
  grown by however much the replaced entry grew.

Still missing in Hollywood: GameObject props (39 chairs, 13 tables, 7 plants, barricades built
from separate model files), pedestrians and goals (the training level's still run, at training
coordinates), rotated LevelObjects' collision.
