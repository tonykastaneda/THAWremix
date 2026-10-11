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

### THAW HUD on Remix

`tools/thawhud.py "THAW CLEAN/Game" extracted/remix_data work/hudout` gives Remix THAW's score
banner, special meter and balance meter. Both games build these with the same `panelstuff.qb`
elements (`the_score_sprite`, `the_special_bar_special`, `the_special_bar_sprite`,
`the_balance_meter` and its arrow, with the same arc path for the arrow), so the port is:

- textures, in `pre\panelsprites.pre` and loose: `score_small` (green "SCORE:" banner),
  `special`, `specialbar`, `balancemeter` (THAW's `balancemeter_bg` arc with down arrows),
  `balancearrow` and `balancearrow_glow` (THAW's glowing ball); and in `pre\themes.pre` the
  theme's sponsor logo, which sits at the left end of the banner (Remix's star, THAW's brush
  stroke)
- theme colours in `scripts\game\menu\themes.qb` (inside `pre\qb_scripts.pre`): THAW leaves the
  art untinted (128,128,128) where Remix tints the banner yellow and meters blue; the arrow is
  dark grey and the special bar gold
- `panelstuff.qb`: the SPECIAL letters at THAW's scale (1.73, 1.4) and position (10, 30); same-size
  tokens patched in place (THAW also tilts them by -0.5 degrees, not done)

Sprite formats (`tools/pspimg.py`): Remix `.img.psp` is a 0x20-byte header (format 0x14 = 16
colours, 0x13 = 256), a 32-bit palette, swizzled 4/8-bit pixels. THAW `.img.wpc` sprites are the
ABADD00D texture record, stored bottom row first.

Testing note: PPSSPP's Start is Space, not Enter (the pause menu only opens with Space).
Balance Meters is On in the save's display options. The THAW meter shows mid-grind.

### Props

`build` now also places the zone's GameObject props (`--no-props` leaves them out): GameObjects
present at level start whose `Type` has a model folder under `data\models\Props\<Type>` (the
profile in `profile_levelobj.qb` points there). In Hollywood: 39 `Chair_Iron_01`, 13
`Table_Iron_01`, 8 `barricade_01`, 7 `plant_big_01`. The `.mdl.wpc` parses as level geometry;
meshes are rotated and placed at their node and get their own visibility boxes.

Collision: each prop's `.col.wpc` object is rotated into place and appended to the level
collision as a new object (`append_col_objects`): float vertices, small faces (8 bytes, so the
one-byte-per-large-face block after the faces stays untouched), one BSP leaf holding every face.
Every block grows at its end, so existing offsets stay valid; the leaf checker passes on all 976
objects. Seen in game: chairs and table render under the arch at Hollywood & Highland.
Collision against a prop has not been bumped into yet.

Testing note: the training level's story spawn is not always "P1: Restart"; `work/exp_spawn.py`
moves all 46 of its restart nodes to one spot. Yaw 0 faces -Z.

### Story phase 1: Hollywood story goals

`tools/hostory.py "THAW CLEAN/Game" work/out extracted/remix_data work/story` rebuilds THAW's
Hollywood story chain on the training level with Remix's own goal templates (`AddGoal_Counter`,
`AddGoal_Gaps`, `AddGoal_HighCombo`): learn caveman, sponsor challenge, kickflip Ben Whofleck,
learn revert, beat the punk's score, and the three wool-protest combos, each the child of the one
before. The training level's 37 story goals are replaced (their scripts emptied, except the caveman
goal, which is kept and retexted). Goal peds and restart nodes are the training level's own
(`TRG_G_COUNTER7_Pro` and so on, Remix pros standing in for THAW's characters), moved to THAW's goal
positions. Writes `tr.qb`, `tr_scripts.qb` and `tr_scripts.pre`.

Verified in game: View Goals lists all eight; the caveman goal's ped stands at THAW's spot with
"Hollywood Skater: O to talk", the intro text box shows, and three caveman switches complete it.
The other seven are untested.

Learned on the way:
- Remix goal ids are `tr_goal_<type><version>`; `AddGoal_*` fill in `TRG_G_<TYPE><version>_Pro` and
  `_RestartNode` when not given. The training level's story master script calls one script per goal.
- `SkaterExitWalking`, `SkaterEnterRevert` and the like are broadcast events (`SetEventHandler`), not
  exceptions. Even so, a handler for leaving walk mode never fired (the skater's switch scripts clear
  handlers at that moment), so the caveman counter polls `skater : walking` every two frames.
- Getting off the board on PSP is L1 alone (`SwitchControl_Trigger = { Press, L1, 10 }`); PPSSPP maps
  L1 to Q here.
- Script control flow: `if` (0x47) and `else` (0x48) carry a 16-bit offset counted from the offset
  field to just past the matching `else` field or `endif` (0x28); `while`/`repeat` are 0x20/0x21;
  the random token 0x2F carries a count, u16 weights and u32 offsets.
- THAW scripts have an inline binary struct token (0x4A: u16 size, padding, struct);
  `tools/thawqbdump.py` prints THAW scripts as text, `tools/qbscripts.py` Remix ones.

Testing aids (environment variables for `hostory.py`): `HW_SPAWN="x y z yaw"` moves the level's other
restarts to one spot; `HW_DEBUG=1` adds an on-screen position readout and messages from the goal
helper scripts.

New story: Remix's chapter 1 opens with the training intro cutscenes (TR_1A-1C), which play inside
the training level; with Hollywood in that slot the first one hung the game (stock data plays them
fine). `hostory.py` now drops chapter 1's cutscene list from `chapter_info.qb` (loose and in
`pre\qb_scripts.pre`, built on top of the HUD port's copy via `HW_QB_BASE`). "Start New Story Mode"
then plays the chapter intro camera text and drops into Hollywood with the Hollywood goals listed.

Goal peds: with "Continue Story Mode" only the caveman goal's ped appeared; the save holds per-goal
state keyed by goal id, and the new ids are not in it. The moved ped nodes are now `CreatedAtStart`,
and all six exist in game (checked with `ObjectExists`); talking to the non-caveman ones has not been
tested yet. Testing aids added: `HW_UNLOCK_ALL=1` (no `Unlocked_By_Another`), `HW_NOPOS=1`, and with
`HW_SPAWN` the debug build teleports the skater there 1.5 s after load.

### Caveman lesson complete (3 parts)

THAW's "learn caveman" is three chained goals, all from the same skater: switch to walk and back
(counter), grind the red ropes (`z_ho_goal_gaps40`), follow my line (`z_ho_goal_gaps4`). Parts 2
and 3 are rail triggers: THAW's red-rope node `VelvetRope37` runs `CavemanSeriesEasy_Check` (win)
and `CavemanCombo_Gap_Start` (win if `GetNumberOfTrickOccurrences` finds a Caveman in the combo).
Here `hw_rope_trigger` sits on all 20 red-rope rail nodes along the Walk of Fame and does both, the
second with Remix's trick text `'CaveMan'`. Both goals restart at THAW's `GAPS4_RESTARTNode`, beside
the ropes (the unused training node `TRG_G_GAP7_RestartNode` moved there). Verified: a separate
Caveman then grind does not count; walk, jump, Caveman (L in the air) straight into a rope grind
(Caveman + FS 50-50) wins. The punk goal is retitled "Get your stuff back". Testing aid:
`HW_START_GOAL=<type><version>` (e.g. gaps42) starts that goal 2 s after load.

### Sponsor challenge, and why goals never counted as won

- **`child` versus `reward_goal`.** In the THUG engine (`CGoal::Win`), only a goal with no `child`
  is ever marked won. A goal with a child is a stage: winning it deactivates it and starts the
  child at once, wherever its giver stands. The story chain used `child` everywhere, so no goal
  after the caveman lesson could ever count as won. Now the three caveman parts stay stages (THAW
  chains them with `child` too) and every other link is `reward_goal`, which unlocks the next goal
  on a real win (`UnlockRewardGoals`).
- **Combo goals.** Remix's `AddGoal_HighCombo` story goals are silent area challenges: started
  from a ped, a landed combo deactivates them instead of winning. The sponsor challenge, the punk
  and the three wool-protest stages are now gaps goals with a watcher on the skater: when a combo
  ends, `SkaterLastScoreLandedGreaterThan` decides whether `got_1` is set. Verified with a
  100-point test target: "combo target reached", the game's goal-complete banner, and
  `GoalManager_HasWonGoal` true. Shipped targets: 1,500 sponsor, 3,000 the punk, 2,000 / 5,000 /
  10,000 the wool protest. Testing aid: `HW_COMBO_SCORE=<n>` overrides every target.
- **Goal peds were never missing.** All six show up; they were locked behind goals that could not
  be won.

Background testing (`tools/ppsspp_ws.py`, `work/run_bg.py`): a portable test copy of PPSSPP in
`work/ppsspp_test` (own settings: D3D11, 1x, muted, remote debugger on port 45678) launches on a
separate hidden Windows desktop, so it is never drawn on the user's screen and cannot take focus;
buttons and screenshots go through PPSSPP's WebSocket debugger. Lessons: screenshots need the CPU
paused (`cpu.stepping`), reading GPU buffers that way under Vulkan lost the device, a second
debugger connection after one closed hung, so a whole test runs on one connection, and any helper
process started without a console must not start console programs (each opened a visible window).
The user's own PPSSPP and its settings are never touched.

### THAW look: boot screen, loading screens, save icon

- Boot screen is `\legal.tga` (480x272 24-bit TGA, bottom-up; listed twice), now THAW's title screen
  (`loadscrn_x`). The original is kept at `work/orig_files/legal.tga`.
- `tools/thawscreens.py` converts THAW load screens (640x448) into Remix's `images\loadscrn_*.img.psp`
  (0x20 header, format 0, then 480x272 linear RGBA8888): the training slot gets Hollywood, plus
  generic, 2-player, online, created and editor screens (19 files, `work/screens`).
- Save and XMB icon: Remix's saves use `disc0:/PSP_GAME/ICON0.PNG` and `PIC1.PNG` (strings in the
  executable). Both are now the THAW logo cut from the title screen onto black (144x80, 480x272).
  `ICON1.PMF` (animated icon) and `SND0.AT3` (XMB music) are moved to `work/orig_psp_game` so the
  static icon shows. Saves made from now on carry the new icon.
- Launch videos: Remix's `Movies\*.pmf` are PSMF (H.264 Main 4.2... 480x272 plus ATRAC3plus audio in
  private stream 1). ffmpeg reads them and THAW's Bink files but cannot write PSMF or encode
  ATRAC3plus, so THAW's videos are not in yet.

### THAW videos as PSP movies (with ATRAC3plus audio)

`tools/pmfmux.py <video> <out.pmf> [--start s] [--seconds s] [--vbitrate 700k]` writes PSMF from
anything ffmpeg reads. Video: libx264 Main 2.1, 480x272, 29.97, access unit delimiters, B-frames,
timestamps from an intermediate MP4 (raw H.264 has none). Audio: atracdenc 0.2.3
(github.com/dcherednik/atracdenc, LGPL, Windows build in `bin/atracdenc`), ATRAC3plus 44.1 kHz
stereo at its fixed 352.8 kbps (2048-byte frames, codec params 28 FF); each frame is preceded by
0F D0 <params> 00 00 00 00, as in Remix's own movies (which use 560-byte frames, params 28 45).
Container layout copied from the stock movies: 0x800 header from `atvi.pmf` with data size and end
timestamp patched; 2048-byte sectors, each a pack header and one PES packet (stuffing bytes in the
PES header or a padding packet fill a sector); audio packets start 00 00 <u16 offset of the first
whole frame>; the system header goes in a sector of its own.

Installed (originals in `work/orig_movies`): `atvi` (THAW Activision), `nslogo` (the Neversoft
logo, first 11.5 s of THAW's intro), `intro` (the rest of THAW's intro), `demo_1`, `nsbails`,
`credits`, `probail1`, `probail2`. Verified in the hidden test copy: the boot plays THAW's title,
Activision and Neversoft videos (Remix's Shaba Games logo still plays between them). The test copy
is muted, so the sound itself is not yet confirmed. Remix's in-game warning screen still says THUG2.

Testing note: during movies the debugger's render target is stale; `dshot:` steps capture the
window's display instead (the test copy runs unminimized but on the hidden desktop).

### Stop the wool protest and the dinosaur head

- The three protest combos (2,000 / 5,000 / 10,000, from Mindy at THAW's `HIGHCOMBO_RestartNode` on
  the roof) are stages linked by `child`, as in THAW. Stage goals must NOT carry
  `Unlocked_By_Another`: the engine's ActivateGoal on a locked child does nothing (Remix's own
  staged goals leave it off). The same fix applies to caveman parts 2 and 3.
- Remix has no `goal_post_success_script`; `goal_success` runs `goal_outro_script`. The last stage's
  outro (`hw_dino_fall`) kills the standing dinosaur pieces and creates the fallen ones.
- Story start state (`STORY_START` in `thaw2psp.py`): THAW's free-skate node flags show the world
  after the story, so `NODEFLAG_Z_HO_DINO_BEFORE`/`POOL_BEFORE` are forced on and the DINO_AFTER,
  BLDG_AFTER and HEAD pieces are built in hidden: box flag bit 0 (not drawn) and collision objects
  flagged killed and non-collidable. `build_qb` adds LevelGeometry nodes for the nine dino pieces
  so scripts can kill and create them by name. Box flags turn out to be the per-piece visibility
  `Kill`/`create` drive, keyed by the box name (piece checksum).
- Verified in the hidden test copy: all three stages chain and read as won; the readout shows the
  standing dino gone and the fallen head created; from the same roof spot the red dinosaur stands
  beside the skater before the win and is gone after it. Not yet checked: the fallen head on the
  street visually, and that created pieces gain collision.

### The barber and clothing store steps (Create-A-Skater with THAW's shop interiors)

- Two goals now open the chain: the barber (`tr_goal_gaps48`, Remix ped GAP18) and the clothing
  store clerk (`tr_goal_gaps49`, GAP19), each standing at THAW's shop door (`*_Ext` restart nodes).
  With the goal active, Triangle within 160 in of the door sets the global `hw_shop_pending`
  (defined in `chapter_info.qb`, which stays loaded) and calls the pause menu's own Edit Appearance
  path, `pause_launch_level level = load_cas`. CAS's Done or Back (`exit_cas`) reloads Hollywood; the
  level's startup (`hw_shop_return`) sees the pending step and wins it with `GoalManager_WinGoal`,
  which needs no active goal (activating it would bring the giver's intro box back).
- Backdrops (`tools/casbackdrop.py`): THAW's shop rooms are rendered offline from THAW's own data.
  The barber is the streamed zone `z_ho_barbershop`; the clothing store is the `g_c_ho_*` pieces in
  `z_ho`. The renderer is a small numpy rasteriser with perspective-correct UVs and THAW vertex
  colours. The camera is Remix's CAS full-body camera (`cas_setup_rotating_camera`: position
  (-60, 60, 80) and target (-40, 45, 0) from the skater) on THAW's CAS spot (`*_Edit` restarts), at
  Remix's 88.18-degree widescreen field of view.
- The image goes into `levels\mainmenu\mainmenu.psp_level` (the CAS room) as a 512x256 CLUT8 texture,
  projected from the CAS camera onto a wall 60 in behind the skater and a floor sheet 0.5 in above the
  room's floor. The CAS camera in that level looks along +Z (the offsets apply turned 180 degrees);
  found with four tinted test walls.
- Showing one backdrop: depth test off draws over the skater too (Remix draws the skater before the
  world), and Kill/Create act only on the level's scene sectors (`*.geom.psp`). The engine finds a
  sector's box by name, first match (FUN_00076da4 sets the per-box hidden flag; FUN_0005f79c applies
  it each frame). So each backdrop box takes the name of a small room piece the CAS camera never sees
  (`0x978F60B1`, `0xE0885027`, always behind the backdrop wall), and that piece's own box is renamed.
  `hw_cas_backdrop` (end of `init_cas_skater_and_cam`, and two frames after the main menu startup)
  kills every room piece but the floor `Box01` and the wanted host when a shop step is pending, and
  both hosts otherwise.
- New boxes added with their own node, collision object or appended `geom.psp` record did not respond
  to Kill. A box flagged hidden in the file stays hidden after Create. Hollywood's dinosaur swap
  relies on exactly that (fallen pieces built hidden, then `create`), so the fallen head probably
  never appears; it needs checking.
- Verified in the hidden test copy, at the real 160 in radius: the prompt shows at each door;
  Triangle there opens CAS with that shop behind the skater; Back returns to Hollywood with the goal
  won; the main menu looks as stock.
- `tools/ppsspp_ws.py` retries calls while the emulated CPU is starting ('CPU not started').

### THAW main menu and menu look (UI phase 1)

- `tools/qbc.py`: a QB text compiler for the syntax the dump tools print (scripts with default
  params, globals, if/else, while/repeat, switch/case/default with their 0x49 jumps, "string" 0x1B
  vs 'local string' 0x1C). It rebuilds 469 of Remix's 478 main-menu-pre scripts byte for byte; the
  other 9 use random tokens (#2f), not supported. The dump printers now keep the string types apart
  and print floats with a point. `tools/thaw2q.py` turns THAW scripts into that source (THAW keeps
  default params as a struct at the head of the body; its bodies already end in endscript).
- THAW's main menu (`z_mainmenu_scripts`, `create_base_main_menu`) is a label menu: tilted strips
  built from `roundbar_tip_left` / `roundbar_middle` / `roundbar_tip_right` (31 px segments) with the
  text on top. Its scripts (`scripts\mainmenu\labelmenu.qb`) port to Remix with two changes:
  `exclusive_device` dropped, and `current_menu` holds the alignment tag (Remix has no GetParentID).
  They go into `scripts\game\menu\gamemenu_helpers.qb` (always loaded).
- `tools/ui/mainmenu.q` replaces Remix's `create_main_menu`. It keeps Remix's setup and every
  item's handler (`main_menu_exit` with `no_spin_animation`), in THAW's order and wording, with
  Remix's Horse in THAW's 2-Player slot and WiFi Play in Online Play's. The Wheel of Loogies is
  level geometry (`wol_pie_*`, `wol_lightbulb_*`), hidden with `0x0a167145 On = 0`.
- Sprites: Remix's menus use THUG2's image names, which THAW redrew (WDT is THUG2's World
  Destruction Tour; THAW's `WDT_logo_big` is the American Wasteland logo). 103 main menu sprites
  and the menu's panel sprites (`roundbar_*`, `snaz_*` dialog boxes, `options_bg`, arrows) are
  THAW's now, at Remix's palette depths.
- Theme colours: Remix highlights menu text in black at 118 alpha (`DE_HIGHLIGHTED_TEXT_COLOR_NEW`),
  which vanishes on THAW's dark strips. THAW's pink (123, 4, 93), its white, its dark highlight bar
  and its white pause bar are ported.
- The main menu room's sign (`mainmenu.psp_level` texture 61, 256x128, upside down, with 3 mip
  levels) now carries THAW's logo from its own main menu zone (`z_mainmenu` texture 72).
  `tools/psptex.py` lists, exports and rewrites level textures in place; mip levels must be
  rewritten too, or their old indices read the new palette as noise.
- A stray top-level word in a .qb (from a doubled endscript) hangs Remix at the main menu's loading
  screen; qbc now refuses top-level words that are not `name = value`.

### THAW's alley behind the main menu

- THAW's main menu background is its own zone, `z_mainmenu` (the back alley wall: poster collage,
  stencils, the bench with the Neversoft sticker). Its main menu camera is `cam_main` in
  `main_menu_camera_control`: Pos (42.6, 12.1, -983.8) and quaternion x, y, z (0.000138, 0.999862,
  0.011832), looking along the rotated +Z. `tools/casbackdrop.py` renders the zone from there.
- The render goes on a third backdrop panel in the menu room (host name `0xC6ED5A77`), 20 in in
  front of a fixed camera that the main menu sets (`hw_main_menu_view` in `tools/ui/mainmenu.q`,
  the CAS camera's position and target). The menu also hides the skater, and creates the panel
  again in case CAS killed it.
- Remix's main menu camera frames 72 degrees across (the 4:3 angle), not CAS's 88.18. A numbered
  grid on the panel showed a uniform 1.4x zoom, so the panel and its UVs are built for 72 degrees.
- `hw_cas_backdrop cas` (from `init_cas_skater_and_cam`) kills the alley panel; the shop branches
  kill it with the rest of the room. Verified: the main menu shows the alley with no skater;
  Create-A-Modes → CAS shows the normal room; Back returns to the alley; the barber trip still shows
  the barber shop.

### Submenu backgrounds from THAW's alley

- THAW moves its menu camera along the alley per screen (`main_menu_camera_control` states: main,
  story, classic, cam, options, settings, skater, level, ...). Three of those views are rendered
  (`SUB_PANELS` in `tools/casbackdrop.py`: `cam_story` for Story/Classic Mode Options, `cam_cam` for
  Create-A-Modes, `cam_options` for Game Options) onto panels in the same place as the main menu's.
- Each panel's host is a room piece hidden behind the shop backdrops; all six such pieces are now
  used (two shops, the main menu, three submenus). More views would need another way to switch
  textures.
- `hw_menu_view bg = <host>` (tools/ui/mainmenu.q) kills all four menu panels, creates the one
  given, hides the skater, and sets the fixed camera. `tools/thawui.py` appends that call to the end
  of `create_gamemode_options_menu`, `create_createamodes_menu` and `create_setup_options_menu`,
  after they set their own cameras. CAS kills all four; skater select and the other menus keep
  Remix's room.
- Verified: main menu, Story Mode Options, Create-A-Modes and Game Options each show their own
  view, and Back returns to the main view. Skater select and CAS from Create-A-Modes show the room
  with no panel in the way.

### THAW pause menu

- THAW's inline struct token (0x4A) is a binary struct in the .qb.wpc item layout, offsets from its
  own header (00 00 01 00, first item offset). The header is aligned in THAW's memory, not in the
  script; the old fixed alignment rule misread it and everything after it in the script.
  `qb2.tokens` now finds the header in the padding, and `thawqbdump` prints the struct as
  `{ ... }` source (3 more of THAW's pause scripts now decode).
- `tools/ui/pause.q` (generated once from both games' scripts, then kept as source) is Remix's
  `create_pause_menu` with its own items, conditions and handlers, built as THAW's label menu:
  `make_label_menu` at THAW's (410, 75), `add_label_menu_item` with THAW's scale 0.85 and its
  tilt / offset pattern, and `label_menu_finish`.
- THAW's `white_poly_bg_effect` (white wash, purple and black bars, dark side panels) and
  `paused_title_text` ("P A U S E D", black, rotated 11 degrees) replace THUG2's side gradient and
  yellow sign. The sign is a theme piece that `build_pause_menu_parts` brings in, so it is faded
  out after the menu is built. THAW's faint stars (`hud_comp_goal`) and dirt strip (`strip_2`) are
  left out; Remix has no such textures.
- Verified: pause shows the THAW layout; View Goals, Game Options (and Back to the pause menu) and
  Continue (HUD back) work. Not ported: THAW's area map, clock/cash and combo records.

### Pause menu map (Hollywood)

- THAW draws each area's map in the pause menu (`pause_menu_map`) from the level struct:
  Level_Z_HO has `level_map` ho_level_map (panelsprites, 128x128; `_x` is a 256x256 Xenon copy),
  `map_offset` (-265, -1395), `map_conversion` 0.013 per inch and `map_scale` 2.4. The skater
  arrow (`Bike_arrow`) sits at (world x, z - map_offset) * conversion from the map's centre, turned
  by GetHeading + 90.
- `tools/ui/pausemap.q` ports it for story mode in Hollywood (`LevelIs load_tr`). The offset gains
  the level's build shift (`thawui.level_shift`, the same rounding as hostory.py), so Remix
  positions map as THAW's do: (-949.4375, -2423.4375). THAW's compass blips are left out.
- New sprites: `qb2.append_to_pre` adds entries to a .pre (keyed by the checksum of the path, size
  hint grown); the names go into the permanent panel sprite list (sprites.qb array 0xB5F55941,
  loaded with panelsprites.pre at boot). Image headers carry the constant 0x12FC7C; the texture
  name comes from the load list. New entries have no loose copy (not in datap).
- Verified: the map shows left of the pause list; at Remix (-1411, -1756) the arrow sits where the
  formula puts it (about 11 px left of and 12 px below the map centre).
