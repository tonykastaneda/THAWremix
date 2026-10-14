# THAW Remix log

Split out of the THX repository on 2026-10-11, with these files' history. THX keeps the Rust/Bevy
port and the BMX XXX work.

## THAW formats

Formats of the THAW PC data, as worked out for the THX port (readers in `tools/*.py`):

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

## THAW on THUG2 Remix (PSP), started 2026-10-10

Goal: THAW's areas and trick feel running on a PSP (and on a Vita through Adrenaline) by replacing
the content of THUG2 Remix, whose engine already runs there. Areas become separate levels. The Bert
slide is cut; its two story uses (Iggy's lesson at the ranch, the Santa Monica pier goal) get another
move. Milestone 1 is Hollywood loading in Remix under PPSSPP, skateable.

Inputs (not committed): `isos/` holds the Remix and THAW PS2 images; PPSSPP is at
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

### Building a PSP ISO

- `tools/mkumd.py` builds a UMD-style ISO9660 image from the unpacked tree (`extracted/remix_psp`).
  It matches the shipped Remix image: system and application id "PSP GAME", blank volume id,
  plain names (no `;1`), every file on a 16-sector (32 KB) boundary, and (with `--like`) the
  original's file order and PVD date. Files missing from the tree (ICON1.PMF and SND0.AT3, dropped
  for the save icon work) are left out.
- `--compact-wad` repacks `datap.hed/.wad` into a temp copy first. `hed.py replace` appends files
  that outgrow their slot, so the test tree's wad had grown to 794 MB with stale copies; packed it is
  595 MB (12,918 files for 12,922 index entries, 2048-aligned, in index order). Only offsets in the
  index change.
- Build: `python tools/mkumd.py extracted/remix_psp "work/iso/THX Hollywood.iso" --like
  "isos/Tony Hawk's Underground 2 Remix (USA).iso" --compact-wad PSP_GAME/USRDIR/datap`
  (1.24 GB, 8 s). Verified: 7-Zip lists the 48 files; every file and all 12,922 archive entries are
  byte-identical to the tree; PPSSPP boots the ISO to the main menu, story mode in Hollywood and the
  pause menu.
- Performance at 333 MHz in PPSSPP (gpu.stats.get, 16 views each): stock `sz` (Remix's largest
  level) 6.2k draws and 60k vertices per frame typical, 21k / 173k peak; Hollywood 10.2k / 133k
  typical, 20.4k / 357k peak. Both hold 30 fps in PPSSPP, which does not time the GE; Hollywood
  asks about twice stock's vertex load.

### First real-PSP boot: black screen

- Report (PSP 3000, custom firmware): game chime, 40 s of black, then the console switches off.
  The ISO itself loads (the executable runs); the first thing the game does is play its launch
  videos, which are ours.
- Our H.264 differed from Sony's encodes in Remix's own movies: B-frames with weighted
  bi-prediction, 2 reference frames, picture order type 0, and no HRD / pic_struct SEI. Sony's:
  I and P only (picture order type 2), 1 reference frame, nal_hrd and pic_struct present, buffering
  period and picture timing SEI on every frame. pmfmux now asks x264 for exactly that
  (bframes=0, ref=1, weightp/weightb off, nal-hrd=vbr, pic-struct, one slice); all eight movies are
  re-encoded (`work/vid2`, copied into the tree).
- Still unverified: the audio is atracdenc's ATRAC3plus at 352.8 kbps (2048-byte frames), where
  Remix's movies use 560-byte frames (~96 kbps).
- PPSSPP with PSPModel 0 (PSP-1000 memory) logs a BREAK two seconds into boot for both the
  original and the modified ISO, then plays on; not the cause.
- Two ISOs for the hardware test: A (all changes, re-encoded videos) and B (all changes, Remix's
  original videos, via mkumd `--file`). If A fails and B boots, the videos are still the problem
  (next: the audio); if both fail, it is something else in the data.
- Git Bash rewrites arguments that start with `/` into Windows paths; use MSYS_NO_PATHCONV=1 when
  passing `--file /PSP_GAME/...`.

### ISO builder now reproduces the original byte for byte

- Both test ISOs (re-encoded videos, stock videos) crashed the same way on the PSP 3000, so the
  videos were not the cause. The builder was then checked on its own: rebuilding the untouched
  Remix tree differed from the original ISO in several places the PSP's UMD filesystem may rely on.
  - Every directory record carries a 14-byte CD-XA system use field: owner 0, attributes 0x8D55
    (directory) / 0x0D55 (file), "XA", file number 0.
  - The PVD application use area holds the disc id (`ULUS-10014|C1259CF10598D6E2|0001`) and the
    CD-XA marker; the copyright field reads ACTIVISION.
  - There are optional L and M path tables (L at 18, its copy at 19, M at 20, its copy at 21;
    directories from 22).
  - Dates carry a +09:00 timezone byte, and each file and directory has its own date.
  - Directory records are not sorted: each directory keeps its own order (EBOOT.BIN before
    BOOT.BIN, files before subdirectories in USRDIR).
  - UMD_DATA.BIN follows EBOOT.BIN unaligned (sector 1607); everything else is 16-sector aligned.
- `mkumd.py --like` now copies the original's system area, PVD and terminator (patching only the
  layout fields), writes the XA fields and both path table copies, and keeps the original's record
  order, dates and sectors for every file that has not moved. The untouched tree rebuilds
  byte-identical to the original ISO.
- `work/mklayers.py` builds cumulative hardware test layers from the stock archive: L1 boot and
  load screens, videos, icons; L2 + HUD; L3 + Hollywood and story; L4 everything. L4's archive
  entries are byte-identical to the test tree's, and it boots in PPSSPP to the menu, Hollywood and
  the pause menu.
- Hardware results with the fixed builder: L4 shows THAW's title and disclaimer (`legal.tga`), then
  crashes; L1 (screens, videos, icons on stock) boots and plays our videos and loading screens;
  L4-SV (everything but stock videos) crashes at the same place. So the videos, title and load
  screens are fine on hardware; the crash is in data L2-L4 add, loaded at boot.
- The .pre size field (0x0C) of our files sits within the stock files' range against an estimate
  of entry headers plus 16-aligned data, so it is not obviously short.
- Bisection switches in `tools/thawui.py`: THX_NO_SPRITES (Remix's menu sprites kept) and
  THX_NO_MAP (no pause map: no appended sprites, no load list change, no call). `work/mklayers.py`
  builds L4-NOMAP and L4-NOSPR from those outputs; both boot in PPSSPP.
- Strict PPSSPP: `IgnoreBadMemAccess = False` in the test copy's ini makes PPSSPP halt on the bad
  reads a real PSP dies on. With it, all three hardware crashes reproduced, and each was fixed.
- Crash 1, boot (after the disclaimer): the Remix .pre loader (FUN_0000e76c) reads the whole file to
  the end of its buffer and unpacks entries forward. A plain (unpacked) entry needs about twice its
  size of room (`end <= dest_end + dsz + 0x14`), and unpacked data must not pass the next packed
  entry. If a check fails, the loader prints "FATAL ERROR:Decompression data has overrun" and hits
  `break`, which crashes a real PSP; PPSSPP carries on. Our replaced and appended entries were stored
  plain. `qb2.replace_in_pre` / `append_to_pre` now store LZSS-packed entries (`lzss_pack`:
  Neversoft/Okumura, 4096 ring, writes from 0xFEE) when that is smaller. `tools/precheck.py` models
  the loader's checks; every pack we write passes.
- Crash 2, Start New Story: tr_scripts.pre held a 414 KB plain TR.qb (fixed by crash 1's packing).
  After that, training-level nodes used TrickObject/Cluster names, often inherited from a template
  node, whose sectors are not in the level; the trick-object manager's sector lookup returns null.
  `hostory.py` resolves templates and strips TrickObject/Cluster when the cluster is not a level
  sector (638 nodes), and drops CreatedAtStart from LevelGeometry/LevelObject pieces with no sector
  (735).
- Crash 3, pause: THAW sets `rot_angle` on the "P A U S E D" TextElement. On a real PSP that reads a
  null string (FUN_0007b710). The rotation now sits on a ContainerElement (`paused_text_anchor`,
  Pos (395, 78)) holding the text; the label menu title gets the same fix.
- The pause map and arrow now replace two panel sprites the game never shows (`shrek_logo`, `hoop`)
  rather than adding names to Remix's boot sprite list (sprites.qb 0xB5F55941). This was a
  suspect during the hunt; it turned out not to be the cause, but it is kept.
- Strict run on the new `work/iso/THX Hollywood.iso` (L4): boot, menu, new story, Hollywood, pause
  (map, rotated title), View Goals, unpause. No halt.
- `isos/Tony Hawk Project Mod.chd` (a Project 8 PSP mod, disc ULUS-10197, "Tony Hawk's Project
  Mod") is extracted to `work/p8mod` (`chdman extractcd`, a MODE1/2048 track, i.e. a plain ISO). Its
  engine is THAW's generation, not Remix's:
  - zone layout (`worlds/worldzones/z_*`, `missions/`, `pak/qb.pak` + `qb.pab`), as THAW PS2 uses;
  - the `qb.pak` header matches THAW's, and `thawqbdump` decodes 295 of 297 of its script files
    (5,294 scripts); 205 of THAW's 266 script files exist under the same names;
  - the `.psp_level` is Remix's format with a 0x1C header, and `psplevel.info` parses it to the
    exact file end;
  - 994 of the 1,051 THAW engine function names its scripts call are named in this EBOOT; most of
    the missing ones are park editor and keyboard functions.
  - The mod ships 43 zones, including Remix's levels (z_ap, z_au, z_ba, ...) and z_mainmenu.

### THAW boot and loading screens on Project 8

- P8's load screens are per zone: `images\raw\us\loadscrn_us\loadscrn_<zone>.img.psp` (plus
  `loadscrn_generic`). Each is a 0x20 header (format 2, 512x274) then 512x274 linear RGBA8888; the
  picture is 480x272 at the top left with alpha 0x80 (some files use 0xFF), and columns 480-511 are
  alpha 0. The boot screen is `images\raw\us\legal\loadscrn_us.tga` (and `_uk`), 480x272 24-bit
  bottom-up, like Remix's `legal.tga`. Saves use `disc0:/PSP_GAME/ICON0.PNG` and `PIC1.PNG`.
- `tools/p8screens.py <THAW install> <outdir> [p8=thaw ...]` writes `loadscrn_z_sc` <- THAW
  `hollywood` (the slot Hollywood is in), `loadscrn_generic` <- `generic`, and both boot TGAs <-
  THAW's title (`x`), at their archive paths; each is patched in with `hed.py replace ... --sectors`.
  `ICON0.PNG`/`PIC1.PNG` are copied from the Remix build's THAW icons.
- PPSSPP: THAW's title shows at boot (under P8's yellow wipe) and the Hollywood screen while z_sc
  loads, full screen; no memory faults. The test copy's `ppsspp.log` accumulates across runs; count
  faults only after the last "Booted" line.

### THAW intro movies on Project 8

- Retail P8 keeps movies as loose disc files, `PSP_GAME/USRDIR/movies/<dir>/<name>.pmf` (155 in
  v1.00); the Project Mod ships none. On PSP, `startup_loading_screen` (misc/loading_screens.qb)
  plays `start\atvilogo`, `start\p44`, `start\shaba`, `start\NS_logo`, `start\g_intro`; a missing
  file is skipped (sceIoOpen fails, the game carries on).
- But neither retail nor the mod ever runs that script: the function at module 0x1db910 runs
  `0x36932fca` and `startup_loading_screen` once, and returns first when FUN_000927fc is non-zero,
  which it is on every call (breakpoint in PPSSPP: v0 = 1, four calls in the first second). So
  P8 PSP never shows an intro, even on the retail disc. `tools/p8eboot.py` nops that branch
  (0x1db920, bnez -> nop); it checks the original word first. The mod's SYSDIR has the same PRX
  as both EBOOT.BIN and BOOT.BIN; both are patched. Original: `work/p8mod/EBOOT.mod.orig`.
- The mod's executable differs from retail's unencrypted BOOT.BIN only in a few strings (title,
  version); no code changes.
- P8's movies are PSMF0014 (Remix's are 0012); the header layout is otherwise the same, so
  `pmfmux.py --template <retail start\atvilogo.pmf>` gives P8's header. THAW's PC videos are 640x480
  holding a 16:9 picture at 640:360:0:60, which pmfmux used to fit whole (bars on all four sides,
  also in the Remix build); `--crop 640:360:0:60` fills the screen.
- Installed in `work/p8mod/tree/PSP_GAME/USRDIR/movies/start/` (built in `work/p8mod/movies/start`):
  `atvilogo` <- ATVI.bik, `ns_logo` <- intro.bik first 11.5 s, `g_intro` <- intro.bik from 11.5 s;
  p44 and shaba left out. PPSSPP: Activision, Neversoft, THAW intro, then the language menu, main
  menu and Hollywood; no memory faults. P8's yellow menu wipe draws over the first second of the
  Activision movie. Sound unconfirmed (the test copy is muted); `mkumd.py` must carry the new
  `movies` directory when the ISO is built.

### Project Mod vs vanilla Project 8 (which base for the story port)

- The mod is built on vanilla v1.00 (ULUS-10197): its executable is v1.00's unencrypted BOOT.BIN with
  37 bytes of strings changed. v2.03 is a different build (3.3 MB of the executable differs).
- datap (by content hash, `work/p8vanilla/diff_*.txt`): of vanilla's 7,036 entries the mod keeps
  2,321, changes 77, removes 4,638 and adds 4,425. Music is replaced (138 tracks out, 53 in);
  streams are replaced wholesale (4,550 out; in: THPS/THUG/THUG2/Remix/THAW level sounds, 582
  voices). Removed: 111 mission zones (career goals), 804 animsaves (career cameras), 955 textures,
  skater models; localized globals (_f/_g/_i/_s, _net). Added: Remix/THUG2 zones, ped and cutscene
  models, themes, `global_thpm`.
- qb.pak: 373 script files in vanilla, 297 in the mod; 150 same, 139 changed, 84 removed, 8 added
  (`scripts\thpm\ih_*`, levelselect, bike_sfx). The story machinery is what was cut:
  - emptied: igc_player and igc_utils (in-game cutscenes, 15 KB/9 KB -> 28 bytes), chapter_info
    (20 KB -> 360), cas_stores, ui_shop_specials, mainmenu_strings, global_sfx_dat_psp,
    shaba_classic_tiers, zone_sizes_psp and pak_sizes_psp;
  - removed: goal_descriptions, goal_cross_zone_scripts, goal_info, view_goals_menu,
    ui_view_missions, zone_transport, cutscene_subtitles, movie_subtitles, igc_templates,
    cutscenemenu, pedaievents (81 KB), propedaievents, sk6ped_uniquestatelogic, shaba_goal_data,
    game_rewards, level_strings, the per-zone *_scripts_text;
  - heavily cut: cutscene (13 KB -> 4.6), goal_scores, goal_piece_goals, stats, cheats,
    shaba_goalutils (84 -> 47 KB), skater_profile.
  - grown (the mod's own features): gamemenu_options (THPM options), gamemenu_levelselect,
    cas_parts (7 KB -> 429 KB), skater_vehicle, airtricks, walking_control, physics (rewritten).
- Vanilla's zone_sizes_psp / pak_sizes_psp hold a Size per zone and pak (largest zone ~1.5 MB,
  plus a total of 2,211,008); the mod empties both. A new zone on vanilla needs an entry there (or
  the tables emptied as the mod does).
- Conclusion: the mod is a level pack on P8's engine with the career/story systems stripped; the
  THAW story port needs exactly those systems (cutscenes, chapters, view goals, ped AI, zone
  transport, cross-zone goals). Vanilla v1.00 is the base; the mod's THPM physics and THAW HUD theme
  can be brought over as data if wanted.

### Switching to vanilla P8 v1.00: first findings (Hollywood does not load yet)

- `work/p8v/tree` is the unpacked v1.00 disc; `work/p8v/build.py` rebuilds it from pristine copies
  (datap, BOOT/EBOOT): `p8eboot.py` intro patch (the unencrypted BOOT.BIN serves as EBOOT.BIN too),
  the Houses zone memory budget, and the zone files. Vanilla with only the executable patch boots and
  loads Suburbs (Free Skate and New Career) in strict mode.
- Vanilla still carries THAW's level definitions and loaders: `Level_Z_HO` (Z_HO_Setup/Z_HO_Goals,
  ho_level_map, map_offset (-265, -1395), scale 2.4), `load_z_ho`, `load_Z_BH`, `load_Z_DT`, ...;
  `chapter_info` still names THAW story cutscenes (HO_2.cut, HO_3.cut, HO_LevelEvent_Dino.cut, BH_4,
  SR_5, ...); the executable compares a script parameter against z_ho (module 0x232b4c, a zone flag).
  Leftover THAW loading screens (`images\loadscrn_hollywood.img.psp`, ...) are in the archive.
- Pak entry keys: pak key = qbkey(entry path less .psp) in shipped paks; the Project Mod's own paks
  use the path with .psp and give unnamed entries qbkey('worlds\worldzones\<z>\<z>') as name key.
  `p8zone.py --template <zone>` builds a zone from another zone's pak and maps all those forms
  (`retarget`); `--strip` leaves out the template's prop models/anims/particles.
- `hed.py add` appends a new archive entry (the index is unsorted, ends 0xFFFFFFFF).
- `p8qb.py` edits the script pack in place: `setkey` (a key inside an LZSS-packed script, checked by
  unpacking), `setdata` (keys, ints, inline strings in data), `setfield` (one field of a struct).
- Native z_ho: CreateZoneMap needs the zone in `SkateZones` (zone_links.qb; a missing zone reads a
  null array: module 0x1878cc from 0x186768). Renaming Houses' SkateZones entry to Z_HO (with or
  without zone_sizes entries for z_ho/z_hoped) crashes one second into boot (heap setup under the
  .qb OnLoad path, module 0x18e7ec -> 0x13ed0); not solved.
- Hollywood in Houses' slot (zone files named z_houses, Level_Z_Houses unchanged) crashes when the
  level loads, in Free Skate and in a new career alike:
  - on Houses' own pak: scene setup gets a null object (module 0xae674, from the zone loader 0x6cbe0
    via 0x62e74); stripping Houses' props does not change it;
  - on the mod's School pak (retargeted): a null field (+0x10) of the scene's geometry object
    (module 0x18df40);
  - with is_streaming_level 0: AddScene/LoadCollision get a null scene (module 0x76f54), since the
    non-streaming path loads scenes from pre files.
- The Project Mod rewrote `load_level` (levels.qb 44 KB -> 29 KB): levels default to streaming, the
  Change_Sky block is gone, the scene pre-file loads and level-load movies are removed, path memory
  differs. That is probably what lets converted (Remix-format) levels load in the mod, and what
  vanilla lacks.

### Hollywood loads and skates in vanilla P8 v1.00

- Test harness: `work/p8v/build.py` with `P8V_AUTO=1` points startup's retail autolaunch
  (`default_system_startup`: Load_Z_MainMenu) at the Houses loader, so the game boots through the
  intro straight into the level; menu driving by timed button presses proved unreliable (runs that
  "did not crash" had never left the menus, so earlier no-crash results were discarded).
- Bisection (Houses' own pak as the template, one part swapped at a time):
  - converted geometry loads in vanilla: Houses' pak + the mod's School .psp_level renders and skates;
  - our .psp_level has no level objects (header nObjs 0; Houses has 28, School 45): Houses' nodes
    against it crash (null at +0x10, module 0x7beb4), and so do Hollywood's own GameObject /
    LevelObject / LevelLight nodes (scene setup, module 0xae674);
  - THAW's zone scripts (z_ho_scripts) crash vanilla too: StructureContains gets a garbage struct
    (0xbef2deeb, module 0xc70cc);
  - the mod's whole script pack does not run on vanilla data (it loads the mod's own paks).
- Working build: `p8zone.py ... --slot z_houses --keep-scripts --no-spawn
  Pedestrian,Vehicle,GameObject,LevelObject,LevelLight` on Houses' pak (THAW geometry, collision,
  nodes, gaps and peds file; Houses' zone scripts), Houses' zone_sizes entry set to the pak size.
  Autolaunch: loads, rides, airs, ollies; no faults in strict mode. No sky yet (night backdrop).
- Next for this base: level objects in the converter (or nodes rewired), THAW's zone scripts made
  to run on P8 (or rewritten), the sky, then the story (Houses is where a new career starts).
- `p8qb.py swapscript` replaces one script in a pack file with another build's, relocating every
  later pointer (item values, struct fields and links, array bases and elements) and checking the
  other items read the same; the file moves to the end of the .pab. The mod's whole load_level
  breaks vanilla's front end (the menu never shows), so it is not used.

### THAW Remix look on vanilla P8: screens, title, icons, intro

- Vanilla's load screens are the Remix-style 480x272 RGBA8888 with a 0x20 header (4, 'seSV', 8, 8,
  ..., 480, 272), each twice: `images\loadscrn_<name>.img.psp` and
  `images\raw\us\loadscrn_us\loadscrn_<name>.img.psp` (localized copies under `raw\figs`). Vanilla
  still has THAW leftovers there (`loadscrn_hollywood`, `_hollywood_2`, `generic_1..7`).
- `p8screens.py --vanilla --logo work/THAW_American_Wasteland_Remix.png` (the THAW logo with the
  Remix tape, made by tools/make_remix_logo.py): loadscrn_houses <- THAW hollywood, loadscrn_generic
  <- THAW generic, the boot TGAs and loadscrn_x <- the logo on black over THAW's legal text (lifted
  from its title screen, white text only), and the icons <- the logo on black: disc ICON0/PIC1 and
  `images\raw\icon\icon0/icon1/pic1.png` (save data). SND0.AT3 (P8's XMB music) is kept aside.
- Intro: THAW's atvilogo, ns_logo and g_intro replace P8's in `movies\start`; P8's Page 44 and
  Shaba logos stay between them.
- Revised after review: the boot/legal screen is THAW's own title (as in the Remix build), not the
  Remix logo; the Remix logo is only for the XMB (disc ICON0/PIC1) and the save data icons.
- PPSSPP (strict): intro plays (Activision, Page 44, Shaba, Neversoft, THAW intro); autolaunch shows
  THAW's generic load screen, then P8's own career-opening cutscene plays in Hollywood. The legal
  screen does not show under PPSSPP for vanilla's own TGA either, so the new title is unverified;
  the Hollywood load screen shows only when Houses loads from the menus (not yet driven).
- `work/p8v/build.py` does all of this from pristine copies.

### Hollywood's nodes on vanilla P8: only GameObjects must stay uncreated

- Redone with autolaunch (the earlier menu-driven class bisection was unreliable): with Pedestrian,
  Vehicle and GameObject left uncreated, Hollywood loads and skates with its LevelObjects and
  LevelLights created. GameObject alone is the problem: its CreatedAtStart ones are Ghost triggers
  (bus, skate shop, barber, clothing shop) and four Transition_Markers; without the markers it still
  crashes in scene setup (module 0xae674), without the Ghosts it hangs. They name THAW models and
  types P8 does not have. The Remix build never used THAW's GameObjects either (hostory.py places
  selected nodes; the shop goals use a distance check at the doors).
- The "no level objects in the .psp_level" theory was wrong: the converted level loads with zero
  objects once GameObjects are off (a placeholder object changed nothing and was dropped).
- p8zone.py --no-spawn takes Class or Class:Type entries.
- The props those GameObjects stand for (bouncy chairs, tables, flower pots, SKATE/COMBO letters,
  the tape, CTF flags) are created later by goals; they need THAW models converted to P8's format.
- Prop collision, as in the Remix build: `thaw2psp.py build ... --col-base <THAW PS2 z_ho .col>`
  also writes `<name>.props.col`, THAW's own collision (which P8 loads as is) with the 67 baked
  GameObject props appended (`append_col_objects`, now taking the header size: 0x50 for THAW's
  files, whose grid/bounds words are kept; 0x20 for Remix). The converter's Remix-format .col.ps2
  crashes vanilla in collision code (module 0xe2f00) and is not used. `p8zone.py --col` takes the
  props file. CORRECTION: that build does not load. The level never draws (black, no logged fault);
  the shots were black and were wrongly counted as a pass. Not used; the build keeps THAW's own
  collision without the props until this is understood.

### THAW HUD on vanilla P8

- Starting from the Remix port (thawhud.py: THAW sprites + THAW theme colours + SPECIAL layout):
  P8 already uses THAW's HUD. panelstuff.qb has the same elements and sprite names, the DE_* theme
  colours equal THAW's, and the score banner, special bar, SPECIAL letters and sponsor stroke are
  THAW's art. Only the balance meter differs (P8: thin arcs and an arrowhead).
- The HUD sprites are in `worlds\global\global.pak/.pab` (and the _f/_g/_i/_s copies), keyed by
  bare name. P8's .img.psp is Remix's with version 4, 'seSV' in the checksum word, flags 0 and the
  pixels NOT swizzled; `pspimg.read_psp` reads both, `make_psp(..., p8=True)` writes P8's.
- `tools/p8hud.py` converts THAW's balancemeter, balancemeter_2, balancemeter_bg and
  balancearrow_glow at the stock sizes and palette depth and rewrites global.pab in place.
  PPSSPP: a manual shows THAW's black arc with arrow ends and the ball.
- Testing lesson: always look at (or measure) screenshots; a run's shot count says nothing.

### THAW main menu look on vanilla P8: the alley and the logo

- Remix did: THAW's label menu and items (compiled to Remix bytecode), THAW sprites and colours, and
  the alley pre-rendered from THAW's menu camera onto panels (casbackdrop.py).
- P8 already has THAW's label menu system (`scripts\mainmenu\labelmenu.qb` equals THAW's but for
  spacing 4 vs 6). Loading THAW's whole z_mainmenu zone (converted alley + THAW's z_mainmenu
  scripts) crashes in the .psp_level loader (module 0x97b94): THAW's menu scripts load
  `Worlds\worldZones\Z_StorySelect\Z_StorySelect.psp_level`, which vanilla does not have (caught
  with a breakpoint after the failing read; it is not a memory limit: a 175 KB menu level loads).
- So, as in Remix, P8's menu logic stays and the look changes (`tools/p8menubg.py`):
  - P8's z_mainmenu level is one 408x223 card behind the menu, 128x64 8-bit, upside down; a
    calibration grid showed texels x 18.9..97.3, y 5.55..49.96 on screen. The texture is rebuilt
    at 512x256 (256 colours, 3 mips; material list addresses/sizes rewritten) holding the Remix
    alley render (work/backdrops/mainmenu.png) in that window.
  - The bar's title art (image 0xC1F52B7E in the zone pak, 480x272 RGBA, format 0) gets THAW's
    default logo on the bar's red.
- `pspimg.read_psp` reads P8's format 0 (32-bit RGBA, stored at the used size).
- Open: the bar and tab strip keep P8's red/blue; THAW's label menu layout itself needs a script
  compiler for P8's (THAW's) bytecode, which does not exist yet (Remix's qbc writes THUG2's).

### THAW front end on vanilla P8: label menus, THAW's main menu items, story start

- The global `0x44689337` in `scripts\game\menu\gamemenu_helpers.qb` (1 in the shipped game) turns
  on P8's PSP UI (tab bar, P8 pause). At 0 the game runs the THAW-style label menus:
  `create_main_menu`'s label path and THAW's `create_pause_menu`. `change_gamemode_career` and
  `change_gamemode_classic` set it back to 1, so they now set a dummy (`p8qb rekey`).
- `p8qb.py` gained `setglobal`, `rekey` (swap one checksum in one script; the body is stored
  unpacked and the file moves to the end of the .pab) and `copyfield`. `qb.py` reads empty arrays.
- Main menu items: THAW PS2's `create_base_main_menu` replaces P8's in the zone's
  z_mainmenu_scripts (same QB format; `p8menubg.py --scripts`). STORY MODE, CLASSIC MODE,
  CREATE-A-MODES, 2 PLAYER, HIGH SCORE / FREE SKATE, OPTIONS; their sub menus (story options,
  difficulty, classic options, create-a-modes, game options, skater select, initials) work.
- Backdrop: `main_menu_camera_control` (P8 kept THAW's) flies a camera along the 3D alley per
  screen. With one card, every view but cam_main/skater/cas/taunt/cag is pinned to cam_main's
  Pos/Quat, and `z_mainmenu_setup` sets `main_menu_very_first = 0` so the first menu uses cam_main
  too (not `spin_menu_camera_init`). The card is resized to what cam_main sees
  (`scale_card(0.9785, 1.1367, (263.3, -288.1))`) and the render warped onto it with corners from
  `work/p8v/calib.py` (stripe screenshots, perspective fit to 529 points, mean error 0.20 texels).
  Every menu screen shows the alley full-screen.
- Start New Story: THAW's `story_options_change_level` records `load_z_ho` and
  `Zone_LoadLastPlayed` loads `load_Z_storyselect` on the first run; P8 has neither (crash). Both
  are rekeyed to the Houses slot's load script (0x16a10a9a). A new career now plays P8's intro
  cutscene, loads Hollywood, and Start opens THAW's PAUSED menu.
- Build: `P8V_THAWUI=1 python work/p8v/build.py`.

### THAW pause-menu map on vanilla P8 (Hollywood)

- P8 kept THAW's `pause_menu_map` (gamemenu_pause.qb): in a career the pause screen draws the level
  struct's `level_map` texture with the skater's arrow (`Bike_arrow`) placed by `map_offset`,
  `map_conversion` and `map_scale`. With the THAW front end (0x44689337 = 0) the pause screen is
  THAW's PAUSED menu, so only the data was missing.
- Level struct (Houses slot, 0xdb6cc528): `p8qb copyfield` turns spare fields into copies of
  Level_Z_HO's: loading_time -> level_map, num_m_legs -> map_scale (inline values), no_sky (the
  renamed sky) -> map_offset, ambient_track -> map_conversion. Pairs live out of line, and the
  game's QB loader reads a file's data in layout order: a field pointing into Level_Z_HO's data
  (later in the file), or pair data parked in an unlinked field record, crashed at boot (a raw
  file offset freed as a pointer). So the pair replaces the destination string's data and the
  rest of the file is relocated (`p8qb.resize`, which swap_script now uses too). Without
  ambient_track the level has no ambience (THAW's z_ho_bg is not on the disc anyway).
- The level's Name is "Hollywood" (`setfield ... str:`), shown by the pause clock.
- Sprites (`tools/p8map.py`): as in Remix, two unused global.pak slots: 0x77b96927 (128x128,
  16 colours) becomes `ho_level_map`, mouse_cursor (32x16, 16 colours, debugger only) becomes
  `Bike_arrow` (THAW's 16x32 arrow turned a quarter counter-clockwise). Keys renamed in the pak
  header, data replaced in the .pab, sizes unchanged. The script's `rot_angle = heading + 90`
  becomes `heading + 0` (`p8qb rekey ... 0x5a 0x0`): a positive rot_angle turns a sprite
  counter-clockwise (at the spawn, + 90 drew the turned arrow pointing left, + 180 down; the label
  menus' title_rotation is no guide), so the drawn arrow equals THAW's. With + 0 the spawn arrow
  points up the map, the way the skater moved in a run that got free of the spawn ledge.
- `p8qb rekey`/`copyfield` move the edited file to the end of qb.pab and leave the old copy; with
  four moved files the .pab was 165 KB over stock. `p8qb compact` now rewrites the .pab with live
  files only (3,094,912 bytes vs 3,094,016 stock).
- Open: starting a story crashed twice in a zone-map allocation (FUN_001b6548 -> 00186768, null
  array with a non-zero count: an allocation that failed, so memory is short while Hollywood loads),
  once before compaction and once after, in about 15 starts since. Not reproduced since (6 plain runs,
  6 with a breakpoint). Watch for it; less memory at load is the likely fix.

### THAW's story runs on vanilla P8: Hollywood goals and the opening atoms

- Script tracing: the engine's `Printf` CFunc is a stub in retail (0x0896bfb4, from the CFunc
  table {name, func} in the image), but a PPSSPP breakpoint on it gets each call's parameter struct
  (a0 + 4: first component; component = [?][type][?][?] name, value, next; in memory string 6,
  int 2, checksum 26, struct 7). The scratchpad tracer `bpprintf.py` prints them, plus calls to
  PlayMovie, PlayCutscene, ScriptAssert, GoalManager_AddGoal/ActivateGoal, CareerFunc and LoadPak.
- P8 kept THAW's whole story machinery: the goal templates (AddGoal_Gaps, ...), goal_utilities,
  view goals, and THAW's chapter_info atom structure (barber `z_ho_goal_gaps15`, clothing shop,
  HO_2.cut, caveman, sponsor, ...). With THAW's own zone scripts (p8zone without --keep-scripts)
  `Z_HO_Goals` adds all 31 Hollywood story goals. Fixes needed, all in `P8V_GOALS=1` builds:
  - Ped profiles THAW's nodes name and P8 lacks crash ped creation (StructureContains on a bare
    checksum): `p8zone.PROFILES` maps Ped_Mindy, Ped_ShopOwner, Ped_SurPlus to P8 profiles.
  - THAW's Start New Story sets `CAREER_ONETIMEINTRO` (its story-select opening). While set, the
    zone map comes from `SkateZonesStoryOpening` (no Z_Houses: CreateZoneMap crash, module
    0x1878cc; this was also the intermittent story-start crash, now fixed for every build by using
    `SkateZones`), load_level loads the zone as freeskate2p (only multiplayer goals get added) and
    `game_progress_process_status` returns at once. The story start now sets CAREER_STARTED instead.
  - P8's career opening clip (`c\C_s_int`, script 0x5ea3b6b7) runs out of memory with THAW's
    goals loaded (movie player crash, module 0x1aa298): not played.
  - P8's `goal_load_pak` takes a flat `pak_short_name`; THAW's goals pass prefix/suffix (LoadPak of
    an empty name, module 0xf480). `p8goals.py loadpak` prepends `if not GotParam pak_short_name /
    FormatText pak_short_name "%p_%s" / endif` (hand-assembled bytecode; an if's u16 is the
    distance to its endif).
  - `p8goals.py missions` repacks THAW PS2's 80 Hollywood mission paks
    (`missions\worldzones\<m>\<m>_<part>\...`) flat as `missions\worldzones\<m>_<part>\<m>_<part>.pak.psp`
    with their node arrays and scripts (models and anims not converted yet), each with P8's 72-byte
    empty `.psp_level` (on PSP goal_load_pak also loads the mission's scene; a missing one stops
    the game in the level loader, module 0x97b94). `hed.py add` puts them in the archive.
  - THAW's in-game cutscenes need its character paks (`Pak/IGC/IGC_Mindy`, ...): `p8goals.py
    igcskip` cuts `igc_player_run` to its defaults, start_script, end_script, igc_playing = 0 and
    the igc_scene_finished broadcast.
- Result (PPSSPP, Story Mode > Start New > Normal): Hollywood loads as career, THAW's progression
  runs (UpdateAtoms, the starting $120, ActivateGoal z_ho_goal_gaps15, its start and gameplay
  mission paks). The skater stands on foot at the barber shop door, "Change your hair" on the HUD,
  the goal star on the pause map, View Missions "Go to the barber shop."
- Next: the barber and clothing goals finish by walking into the shop (THAW's Ghost GameObjects,
  which P8 cannot create): as in the Remix build, a door check opening Create-A-Skater.

### Story progression through the opening atoms (P8V_GOALS)

- The barber and clothing goals (`z_ho_goal_gaps15`/`gaps30`) are won by their mission's door
  trigger in THAW (a LevelGeometry trigger in the gameplay mission's collision, whose script checks
  the look changed in the shop). Mission collision without a mission scene crashes (module
  0x18e330), and P8 has no THAW shop scripts (its cas_stores.qb is empty), so for now: the win
  script calls GoalManager_WinGoal instead of the look check, and each goal runs it as its
  goal_start_script (`p8goals.py zonerekey` in THAW's zone scripts: the AddGoal's fail_scene key and
  value renamed). Both steps pass as soon as they start. To do: real shop entry.
- Cutscene atoms (`cutscenes\HO_2.cut`, not on P8's disc): `p8goals.py cutsceneskip` keeps
  game_progress_process_cutscene up to its PlayCutscene call and spawns
  `game_progress_process_status { wait_time = 1 }` instead (the atom counts as done when no cutscene
  plays; the C side: vtable 0x3763ac, start 0x2368c0, update 0x236964 checks 'cutscene').
- The save prompt atom blocks on `ingame_save_finished`; P8's No handler (0xe345fc6b) never sends it:
  THAW's `ingame_save_return_to_game` is back, and `p8goals.py saveprompt` spawns the progression
  again after the prompt.
- PPSSPP: Start New Story -> barber -> clothing -> (HO_2) -> save prompt (No) -> View Missions
  "Learn from the Hollywood skaters.", the caveman lesson's star on the map.

### First THAW story goal played on P8: the caveman lesson

- `P8V_TESTGOAL=<goal>` (test aid) swaps `z_ho_goal_gaps15` in chapter_info, so the story opens with
  that goal. With `z_ho_goal_counter`: intro skipped, the goal runs with THAW's HUD (2:00 timer,
  counter, "Switch to walk: press L R and then switch back to skating"); three cavemen (L+R, walk,
  L+R) win it and the child stage `Z_HO_Goal_Gaps40` starts at once at the red ropes ("Grind the red
  ropes", new timer), the skater moved to its restart node. THAW's goal templates, HUD and staging
  run unchanged on P8.
- Pause menu crash in the goals build: THAW's create_pause_menu calls P8's SET/GOTO RESTART adder
  (0x1523a6fe), which makes P8 tab-UI items (0x59486bf2) inside the label menu; moving past them
  morphs a missing element (DoScreenElementMorph, module 0x24074). Not called any more (all builds).
- `p8goals.py rekeynth` swaps one occurrence of a key in a script (not used by the build now).

### THAW story is the default build; Free Skate and Classic fixed

- `work/p8v/build.py` now builds THAW's story by default (`P8V_NOGOALS=1` for Houses' zone scripts);
  it runs p8zone itself for the THAW-scripted zone (`zone_thaws`).
- Free Skate crashed in its level select (CreateScreenElement, module 0x82cb0): the level select
  uses sprite 0x77b96927, the global.pak slot taken over for `ho_level_map`. `p8map.py` now adds
  ho_level_map as a new global.pak entry (one 0x20-byte entry before the end marker, every other
  data offset +0x20, data appended to the .pab) and leaves 0x77b96927 alone. THAW's
  launch_level_select_menu also loaded its pak into the UnloadableAnim heap (`heap` key renamed).
  Free Skate: level select (the Houses slot is "SUBURBS"), Hollywood loads, pause works.
- Classic: the first start asks for initials on THAW's keyboard, which takes no input on P8;
  `gamemode_options_menu_exit` compares the initials with the default (0x3bfd8eb7), renamed so it
  never matches. Classic: single/co-op, skater select, Play Level, P8's classic level select,
  Classic Goals difficulty, the run starts.

### Goal peds visible

- THAW's Hollywood ped profiles (z_ho_peds.qb, e.g. the caveman teacher's `Z_HO_ped_Skater_02`) use
  parts from THAW's z_hoped pak, which P8 does not load. Mapped in `p8zone.PROFILES` to P8 profiles
  whose parts this zone has: Ped_HippieF01 and Ped_DVGuy (Houses' own). ped_Skater_02 crashed
  (module 0x8b25fc, parts not loaded). PPSSPP: the caveman teacher stands by the skater at the
  goal's restart node (P8's DV guy). Real THAW ped models are still to do.

### Hollywood sky

- A level struct's fields are laid out record by record, each followed by its data (strings inline
  after their record), and the loader reads them in that order. `p8qb addfield` inserts a new string
  field (record + text) after a given field with `resize`, then relinks. The Houses slot gets
  `sky = "Default_sky"` after `level` (THAW's Level_Z_HO names TestLevel_Sky, which load_level turns
  into default_sky; P8 has skies\default_sky). PPSSPP: Free Skate and Story show a daytime sky with
  clouds where it was black; no faults.
- The ambient track the map data displaced is back (`addfield ... Name ambient_track
  music\vag\backgrounds\z_houses_bg`, P8's Houses loop). Story and Free Skate load without faults;
  the sound itself is not checked (screenshots only).

### More goals checked with P8V_TESTGOAL

- Sponsor challenge (`z_ho_goal_gaps31`): runs at the skate shop ("Do a Sponsor Challenge").
- High combo (`z_ho_goal_highcombo`): crashed with 'Ped has no skeleton!' (ScriptAssert from
  ped_add_components): its mission pak creates peds with mission-local profiles (M_Ped_Cop,
  M_ZHOHIGHCOMBO_start_Ped_Bum01, ...) built from THAW parts. `p8goals.py missions` now maps every
  ped profile in the mission paks to Ped_HippieF01 (Mindy) or Ped_DVGuy. The goal then runs ("Land a
  2000 point combo", timer). Default build re-checked: story start to the caveman lesson, no faults.
- Free Skate's level select lists the Houses slot as HOLLYWOOD (`p8qb setstr`: a pointed-to
  string replaced at any length, the file relocated). Its picture is still P8's Suburbs art.
- Its picture is THAW's `levelposter_hollywood` (`tools/p8lsel.py`, into levelselect.pak's
  0x61406c1d, P8's Suburbs picture; same 128x128 256-colour size).

### State at the end of the 2026-10-12 run (vanilla P8, default build)

- Front end: THAW label menus over the alley; Story, Classic, Free Skate, Create-A-Modes, Options work.
- Story: Hollywood loads as career with THAW's zone scripts and all 31 Hollywood goals; the opening
  atoms run (barber and clothing goals pass at once: shop entry not done; HO_2 cutscene skipped;
  save prompt) up to "Learn from the Hollywood skaters"; goal peds appear (P8 stand-in models).
  Checked with P8V_TESTGOAL: caveman lesson (wins, chains to the red ropes), sponsor challenge,
  high combo.
- Pause: THAW's PAUSED menu with the Hollywood map and arrow, level name, goal stars.
- Level: THAW Hollywood geometry and collision, daytime sky, HUD balance meter, Houses ambience.
- To do: shop entry (barber/clothing via CAS, as in Remix), THAW cutscenes and in-game scenes
  (character paks), THAW ped and prop models, GameObjects (shops, bus, transition markers),
  mission collision/scenes, the rest of the story beyond Hollywood.

### Open: saving in game crashes

- The story's save prompt "Yes", and Save Game in the pause menu, both crash (module 0x334b00, null
  + 0x10). The prompt's Yes handler was P8's tab-UI state script (0x9510a3cb); it is now THAW's
  `launch_ingame_menu_save_game_sequence` (ingame_confirm_save's default), which still crashes, so
  the fault is further on (P8's memcard UI under the THAW front end?). Saving from the main menu's
  Options works. Answer No at the prompt for now. Next: trace with tools/p8trace.py (start it at
  the pause menu so the breakpoints do not slow the story start).
- The crash function (module 0x334b00) takes no argument: it returns field +0x10 of the entry
  `DAT_003620d0[byte DAT_003620d9]`, a global table indexed by a current-device/slot byte; that
  entry is null in game (likely a save/memcard context P8's own in-game flow sets up and THAW's does
  not). Next: break at 0x08b38b00 unconditionally once the pause menu is up, read ra and the
  stack, and find which setup P8's tab-UI save path calls first.
- A breakpoint condition on entry 0 (`[0x08b660d0] == 0`) does not catch it, so the slot byte is
  not 0 when it crashes; read 0x08b660d9 first, then break on that entry.
- Read at the pause menu: `0x08b660d0` = [0x08dc2b90, 0, ...], slot byte `0x08b660d9` = 0. Entry 0 is
  set and entry 1 is empty, so the save path switches the byte to 1 (another context, e.g. a second
  device or player) before it crashes. Next: find what writes 0x08b660d9 (memory breakpoint) on
  Save Game, and what P8's own save path sets up for entry 1.
- `DAT_003620d0` is a context stack: 0x33acd0 pushes (index byte +1), 0x33ace4 pops, 0x32e07c
  stores an entry, 0x32dbe0/0x32e128 read the current one. Saving pushes a context whose entry was
  never created (entry 1 empty), so 0x334b00 reads a null. The pushes come from 0x1c36b0,
  0x1c37a0 and 0x1c39c8 (save code). Next: see which of those runs on Save Game and what P8's own
  path creates first (likely a save/memcard heap set up by its tab-UI flow).
- The stack holds the script engine's component pools: 0x1c37a0 creates reserve pools
  (`Reserve CComponent` 20000, `Reserve CStruct` 9000, `Reserve CVector` 3000, via 0x32e07c / 0x32e41c
  / 0x32e1a0). Saving pushes to that reserve without it having been created. Next: find the script
  CFunc that leads to 0x1c37a0 (P8's save path calls it, THAW's does not) and call it before saving.
- 0x1c37a0 is reached from the CFuncs `PushTemporaryMemCardPools`, `SaveToMemoryCard` and
  `LoadFromMemoryCard`. The pools come from memcard.qb's `UnloadAnimsAndCreateMemCardPools`
  (PushTemporaryMemCardPools; undone by `RemoveMemCardPoolsAndLoadAnims`). Likely fix: make the
  in-game save path (launch_ingame_menu_save_game_sequence / launch_pause_menu_save_game_sequence)
  call UnloadAnimsAndCreateMemCardPools before saving, as P8's own path must; check where P8's
  tab-UI save calls it.
- Correction: the pause save path (launch_pause_menu_save_game_sequence) does create the pools, in
  launch_files_menu (UnloadAnimsAndCreateMemCardPools). But `check_card FileType = OptionsAndPros
  Save` runs before it, so the crash may come from check_card in game (in the front end it works).
  Next: break on the CFunc of check_card's card query, or call UnloadAnimsAndCreateMemCardPools
  before check_card and test.
- Tried: check_card skipped in the pause save path: still crashes, so it is not check_card. The
  pools are pushed in launch_files_menu; the fault may be inside the files menu/save itself under
  the THAW front end. Next: break at 0x08b38b00 with ra logged after Save Game is pressed (start
  the breakpoint from the pause menu) and walk the stack. (Experiment not kept.)
- Caught with `p8trace.py --funcs 0x08b38b00 --arm-after 74000`: the crashing read comes from
  0x15ee04 (return 0x08963084), the engine's script pool usage report ("Script pool usage",
  "CStruct %5d of %5d (max %5d)", "Permanent Strings ..."), which the engine prints when a script
  pool runs out. So the in-game save most likely exhausts a script pool (CStruct/CComponent) with
  THAW's 31 Hollywood goals and their data loaded, and the report then reads the empty reserve
  entry. Next: check P8V_NOGOALS saves in game (if it does, it is pool size); then make the save
  path free goal data first, or load fewer goals at once.
- Tried the P8V_NOGOALS in-game save check: inconclusive, the test copy stopped answering input
  (ppsspp_ws TimeoutError on input.buttons.send) during the run, no screenshots. Repeat it.
  The default build was rebuilt afterwards.

### Main menu matched to the Remix build's look

- Side by side with the Remix build's THAW main menu (work/shots/ns3_menu.png) the layout matched
  (same THAW label menu, item positions within a few pixels), but our alley was much brighter: the
  same render (work/backdrops/mainmenu.png), lit by the menu room in Remix and drawn unlit on P8.
  Measured 0.54x on wall, bench and floor; `p8menubg.DIM = 0.54` darkens the card (main menu and
  the submenus that share it). After: the ratios are ~1.0.
- The legend's lowercase "Accept" (`\m0 Accept` in mainmenu_strings.qb) is "ACCEPT", as THAW's own
  submenus have it (`p8qb setstr`).

### In-game saving fixed

- Cause: saving pushes temporary script pools (20000 CComponent, 9000 CStruct, 3000 CVector, ~440
  KB; PushTemporaryMemCardPools -> FUN_001c37a0) onto the main heap. Heaps read at the pause menu
  (manager at 0x08b64358, heap array count at +0xC0; per heap name +0x30, region +0x20; free as
  DisplayFreeMem): TopDown/BottomUp share one 20 MB region with 422 KB free. A pool came back null
  and the engine's pool report (0x15ee04) crashed reading it. On P8's own Houses the same in-game
  save worked; Hollywood's zone pak took 470 KB more (its zone_sizes budget = the pak).
- Fixes:
  - `p8zone --strip` for the Hollywood zone: Houses' own props (models, anims, particles: 52 entries,
    273 KB) leave the pak (2,018,416 -> 1,744,976 bytes). Free Skate saves after this alone.
  - Story (THAW goals loaded) was still short (the CVector pool failed). The COIM heap (652,288
    bytes) is empty at the pause menu: `p8goals.py savecoim` inserts `ResizeCOIMHeap newsize = 0`
    before the in-game PushTemporaryMemCardPools (UnloadAnimsAndCreateMemCardPools) and
    `ResizeCOIMHeap newsize = 652288` after the in-game PopTemporaryMemCardPools
    (RemoveMemCardPoolsAndLoadAnims). `insert_code` inserts bytecode, growing the if/else/case
    jumps that span the insertion, padded to 4 for the inline structs after it.
  - Moving the pools to the TopDownHeap instead (one load offset in FUN_001c37a0) did not help: not
    kept.
  - After an in-game save, P8's back_to_pause_menu opened P8's options menu (0x8075d1aa): it calls
    THAW's ingame_save_return_to_game now (back to the game, ingame_save_finished for the prompt).
- PPSSPP: story save prompt Yes -> save list -> Save completed -> back to skating, the story goes on
  ("Learn from the Hollywood skaters"); pause menu Save Game in the story, the same; Free Skate save;
  Continue Story Mode loads the save into Hollywood with its progress ($120, goal stars, objective).

### Hollywood level under Houses' size

- `thaw2psp.py build --texel <inches>`: each texture is shrunk (power of two, down to 32) while one
  texel stays at most that many world inches across. The world size of one texture repeat is the
  square root of (world area / UV area) summed over every triangle using it.
- Hollywood, `--texel 4 --tess 800`: .psp_level 3,890,688 -> 2,813,002 bytes (Houses: 2.85 MB),
  textures 1,436,416 -> 893,952 bytes; .col unchanged. Alone, `--texel 3/4/6` give 3.47/3.35/3.20 MB
  and `--tess 800` 3.36 MB; `--tess 0` (no splitting) 3.25 MB but long triangles drop out.
- PPSSPP, same route from story start (5 shots each, work/shots/red_cmp_NN.png side by side):
  textures and signs look the same; TopDown free 422,288 -> 1,502,000 bytes at the end of the route.
- Now the default: work/p8mod/ho/z_sc.psp_level (the old one is z_sc.full.psp_level).
  `work/p8v/build.py` takes `P8V_LEVEL=<.psp_level>` to try another.
- The test runs broke for a while: PPSSPP's log had reached 43 GB (it appends on every boot); reading
  it whole used up system memory and restarted herdr under SSH (session 0, where D3D11 fails).
  `ppsspp_ws.start` now keeps one log per boot and launches through the scheduled task
  "THX PPSSPP test" (desktop session) when it runs in session 0.

### How many peds load in Hollywood (vanilla P8, PSP-1000 test copy)

- Hollywood's node array has 63 Pedestrians and 4 Vehicles. THAW creates only 12 at start: 3 people
  (a skater, a BMX rider, the construction "goat lover"), 5 pigeons and 4 cars; the other 55 peds
  belong to goals. P8's Houses has no crowd or traffic at all: 5 goal peds, and its Vehicles are
  playground props (swings, seesaw, merry-go-round, boat mast). No P8 car models load in this slot.
- `p8zone.py --create <classes>` (tests: AbsentInNetGames -> CreatedAtStart, shared structs too) and
  `--map THAW=P8,...` (extra profile stand-ins); `work/p8v/build.py` takes `P8V_NOSPAWN` and
  `P8V_ZONEARGS`. `Ped_BMX` -> `Ped_DVGuy` added to PROFILES.
- Same route as the level reduction (TopDown free at the end; reduced level, default build 1,502,000):
  - THAW's 3 start people on (pigeons and cars off): loads, no faults; TopDown 1,471,520 (-30 KB),
    COIM heap 86 KB used (empty before): about 29 KB per ped there.
  - Every non-pigeon ped on (21 CreatedAtStart flips, shared structs included; Rick Thorne, Murphy,
    the barber and Boone mapped to Ped_DVGuy): loads, no faults; TopDown 1,315,392 (-187 KB), COIM
    50 KB free of 652 KB (about 21 peds' worth), AnimHeap 2 KB free of 128 KB. Likely (not counted:
    estimated from COIM use) peds beyond what COIM holds are not created, with no crash.
- So with P8 stand-in models about 20 peds fit at once, bounded by the COIM heap (and AnimHeap close
  behind); each distinct THAW model would also need room in PedParts (full now). Cars need their
  models converted or another P8 level's.

### PSP-2000/3000 build: extra memory with MEMSIZE

- P8's heap setup (FUN_000158dc): main region = `sceKernelMaxFreeMemSize() - 0xA2800`, split into
  TopDown/BottomUp. Imports (tools via module info stubs): AllocPartitionMemory, GetBlockHeadAddr,
  MaxFreeMemSize, TotalFreeMemSize, VolatileMemTryLock; no sceKernelGetModel (vanilla or Project Mod).
- `tools/sfo.py`: list or set PARAM.SFO integer keys. PPSSPP as PSP-2000 with `MEMSIZE = 1`: TopDown
  53,669,888 bytes (PSP-1000 or PSP-2000 without it: 20,115,456).
- `p8goals.py heaps`: COIM (coim.qb global 0xcfae4518), Houses' PedParts (load_level's 401472
  literal), AnimHeapSize (load_permanent_assets' 131072 literal). `savecoim` takes the COIM size so
  the save's heap swap remakes the same size.
- `P8V_BIG=1` build (MEMSIZE + heaps 4x) with every non-pigeon Hollywood ped on, as PSP-2000: loads,
  no faults; COIM 1,548,288 used of 2,609,152, PedParts 401,424 used of 1,605,888, AnimHeap 148 KB used
  of 512 KB, TopDown 30,978,240 free. More peds on screen than the PSP-1000 run.
- ISOs for a real PSP-3000 (ARK-4): `mkumd.py` compacted P8's datap.wad with byte offsets, but P8's
  .hed counts 2048-byte sectors (as `hed.py --sectors`), so the game read far past the disc ("Could
  not read 192 blocks, at block offset 99656400", BREAK at boot). `mkumd.py --compact-wad ...
  --sectors` fixes it. work/iso/THAW P8 normal.iso (default build, PSP-1000 run: Hollywood, story)
  and work/iso/THAW P8 big test.iso (`P8V_BIG=1`, every non-pigeon ped on; PSP-2000 run: TopDown
  53,669,888, same heaps as the tree). The big build run as a PSP-1000 hangs while loading (TopDown
  3 KB free), so on hardware: reaching Hollywood = the extra memory was granted.
- Real PSP-3000 (ARK-4), THAW P8 normal.iso: boot chime, black screen, crash after about 10 s; the
  legal screen never showed. Suspect: our boot screens (images\raw\us\legal\loadscrn_us/_uk.tga) were
  PIL TGAs, 391,724 bytes (bottom-up, 26-byte footer, colour-map depth byte 0); P8's are 391,698 (18-byte
  header with depth byte 0x18 and descriptor 0x20 = top-down, BGR rows, nothing after). p8screens
  `boot_tga` now writes P8's exact layout. For the PSP: work/iso/A THAW P8 normal.iso (fixed) and
  work/iso/B P8 baseline.iso (P8V_BASELINE: shipped data + the p8eboot patch only); both boot in PPSSPP.
- PSP-3000, A: the THAW legal screen shows briefly (the boot TGA was one problem), then black and a
  crash about 5 s later, where the intro movies start. p8eboot's boot_movies patch turns on an intro
  path the shipped game always skips, and three of the movies are ours (pmfmux, ATRAC3plus). New:
  `P8V_NOINTRO=1` (unpatched executable, as shipped) -> work/iso/C THAW P8 no intro.iso (PPSSPP: reaches
  Hollywood). On the PSP: B (P8's own movies with the patch) and C tell the intro path from the rest.
- PSP-3000: C (no intro) works. So the hardware crash is in the intro path (B, P8's own movies with
  the patch, still to report). work/iso/D THAW P8 big test (no intro).iso: P8V_NOINTRO + P8V_BIG with
  every non-pigeon ped on (PPSSPP as PSP-2000: reaches Hollywood).
- PSP-3000, ARK-4: D (P8V_BIG, MEMSIZE = 1) stalls on the loading bar with ARK-4's "use extra memory"
  on Auto (THX and C, which do not ask for it, run fine on Auto). Forced on, D loads Hollywood and
  plays: the extra memory works on real hardware. Shipping note for the 2000/3000 build: ARK-4's
  extra memory set to forced (unless a PBP package or another PARAM.SFO CATEGORY gets it on Auto:
  untested).
- PSP-3000, D: more peds visible than in C (the 4x heaps hold them on hardware too). Saving on the big
  build is untested (in PPSSPP too); left for when the game is complete.

### Hollywood feature complete first; grinding (open)

- Decision (2026-10-12): Hollywood is finished (story beats, goals, geometry, grinding) before any
  other area. The user reports on hardware: grinding does not work, some geometry broken or missing,
  floor textures fight with geometry (z-fighting), story beats and goals incomplete.
- Grinding was only ever tested on the THX (Remix) build. On P8 the zone pak carries THAW's own
  node array: 1,579 RailNodes, 1,420 CreatedAtStart, the rest on NODEFLAG_Z_HO_DINO_BEFORE/AFTER,
  DT_EVENT, TOWERWIRES. Fields match P8's Houses rails (Class, Type, TerrainType TERRAIN_GRIND*,
  Cluster, TrickObject, Links); THAW's are partly compressed nodes (shared structs).
- Test aid: the skater's live position (PPSSPP, default build, story start) at 0x0997F190 with copies
  at 0x0931EE40, 0x0997E8F0, 0x0997F1A0, 0x09982430, 0x09984040 (writing all of them teleports). The
  story starts on foot (board in hand); L+R gets on the board. A drop onto Rail_Kodak133/134
  (-1748, 175, -2478) with triangle held landed standing on the ledge top (y 142.8), not grinding:
  inconclusive (no speed along the rail).
- **Cause found: no rails at all.** P8 PSP runs with RAILNODE_ASSETS_ENABLED (0x725bce21): its rail
  manager's node-array path (FUN_0023eb1c, "add rails from node array") returns at once, and rails
  come from the zone pak's 0x91e1028d entries ([count][1] then (x, y, z, 1.0) points; the level's is
  the largest, small ones belong to models). `p8zone --strip` dropped Houses' (as a "prop") and nothing
  put Hollywood's in. Memory check: a rail point appears twice in vanilla Houses (script vector
  `00010000` and the rail manager's x,y,z,1.0) but only once in our Hollywood (script only).
- Fix: p8zone puts THAW's own z_ho rail asset (152,552 bytes, 1,589 points) in the slot's level rail
  entry. After it the rail manager's copy is in memory (Rail_Kodak29's point at 0x095275C0). The
  asset's heights can differ from the node Pos (Kodak29: 95.3 in the asset, 35.3 in the node).
- The emulator drop test was not reliable (teleport addresses change per boot); grinding to be
  confirmed on the PSP with work/iso/E THAW P8 rails.iso (no intro). Test-aid notes: P8V_BASELINE +
  P8V_AUTO boots shipped data straight into Houses (reference runs); P8V_NOGOALS builds crash about
  20 s in (stale path). The ppsspp_ws log cap (20 MB on kill) came from a crash loop writing 1.8 GB.
- User reports to fix next: the dinosaur building is missing (NODEFLAG_Z_HO_DINO_BEFORE/AFTER pieces),
  and floor z-fighting between the bleachers across the street from the theater entrance.
- **Grinding confirmed in PPSSPP** (no PSP needed): `P8V_TESTGOAL=z_ho_goal_gaps40` opens the story at
  "Grind the red ropes" with the skater on the board beside the ropes; stick forward, a little left,
  ollie, triangle: BS 50-50 on a rope with the balance meter, 247-point combo, the goal wins and
  "Follow my line" starts. Teleporting by writing memory was unreliable (a "position" copy was the
  velocity); starting at a goal's restart node is the dependable way to put the skater somewhere.
- **Missing dinosaur building: THAW's node flags never existed.** P8's create_node_flags
  (nodeflags.qb) creates only its own 4 node flags; THAW's (291 in
  game_progress_set_initial_story_mode_nodeflags; Hollywood's nodes are gated on 30 of them:
  DINO_BEFORE 47 nodes, DINO_AFTER 47, DT_EVENT 26, TOWERWIRES 15, ...) were never created, so
  ChangeNodeFlag on them did nothing and every piece/rail on one stayed hidden. Also, chapter_1_startup
  applies the story's flags (CareerFunc SetAppropriateNodeFlags) only when autolaunched.
  `p8goals.py nodeflags` creates the 289 distinct THAW flags at boot (list read from the qbdump of
  chapter_info); `p8goals.py storyflags` makes chapter_1_startup call SetAppropriateNodeFlags always.
  Either alone changed nothing; both: the high-combo goal's rooftop start (beside the dinosaur) goes
  from dark boarded walls to the open roof with the dinosaur's red foot beside the skater.
- Cost: TopDown free at the end of the standard route 1,502,000 -> 1,280,992; COIM 230 KB used there
  (flag-gated nodes, e.g. NODEFLAG_PERMANENT_PEDS, now created). Story start and route unchanged.
- **Floor z-fighting: THAW's layered decals.** THAW lays decals in the plane of the surface under
  them (window and shadow decals, road reflections, stickers; e.g. Kodak_shad06 on kodak_stairs,
  road_reflection04 on HO_Ground_New_04) and draws them with a depth bias; the PSP has none.
  `thaw2psp.py build --decal-lift <in>` (`lift_decals`): every triangle of a decal mesh (blended
  material, or a texture with alpha) coplanar with an overlapping opaque triangle moves that far
  along its own normal. Hollywood at 1.0 in: 7,067 vertices in 539 meshes; size and collision
  unchanged. PPSSPP, story start: a red poster on the shop wall (shop_stickers) that lost to the wall
  now shows. The default level is rebuilt with it (old one: work/p8mod/ho/z_sc.nolift.psp_level).

### Hollywood story through the dinosaur head (the user's scope, 2026-10-12)

- Missions -> THAW atoms/goals: Change Your Look gaps15 (barber), Change Your Clothes gaps30, Learn to
  Caveman counter (+ red ropes gaps40, follow my line), Sponsor Challenge gaps31, Kickflip Whofleck
  gaps2, Learn to Revert counter4, Get Your Stuff Back gaps5 ("Beat down the punk skater"), Stop the
  wool protest highcombo (unlock_bh), then HO_LevelEvent_Dino (the dinosaur head falls).
- PPSSPP with P8V_TESTGOAL: gaps31 reaches the skate shop door ("Press O to look at stat challenges";
  the menu not seen yet), counter4 runs (revert instructions, timer), gaps5 runs (Joe Skater vs You
  score race), highcombo runs on the dinosaur roof, gaps2 runs after the fixes below ("Failed! Out of
  time!" when left alone). Whofleck's limo is not there (vehicle models not converted).
- Test aid bug: P8V_TESTGOAL used `p8qb setdata`, which swapped the goal key's bytes everywhere,
  also inside LZSS-packed script bodies (chapter_info's atoms are built by scripts) and corrupted
  them for some keys (gaps2: boot-time crash 0x088ca734). `p8qb setdata` now skips script bodies;
  `p8qb rekeyall` rekeys (unpack, swap, store unpacked) every script holding a key; P8V_TESTGOAL uses it.
- Whofleck crash (scene setup, 0x088b2670): its mission paks create a Limo Vehicle and a Ghost
  GameObject whose models were dropped. `p8goals missions` now turns their CreatedAtStart off
  (MISSION_NO_SPAWN Vehicle, GameObject): 14 Hollywood mission paks. p8zone.unspawn/create read a
  one-node array's node inline. Mission paks are cached in work/p8v/missions_out (delete to rebuild).
- ppsspp_ws.start waits for the CPU to run before returning (inputs failed with "CPU not started").

### Research: THUG2 Remix physics, camera and animations on P8 (no changes made)

- Project Mod's "Physics: THPM" option (setting 0x5c2fa040.0xf2aed113, thpm/IH_globalvalues) only
  points the skater's physics table global 0x6bbc7cba at 0xd61b77d4 (THPM) instead of 0xcd1ad2af (P8).
  The two tables differ in 7 values: max speed 625-750 -> 950, max-max 1100-1300 -> 1500, vert and two
  more caps 750-850 -> 1050, Physics_Heavy_Air_Friction 8.3e-5 -> 1e-5, Rail_Speed_Boost 115 -> 150.
  Faster P8, not THUG2. The mod keeps P8's cameras.
- THUG2 Remix physics (extracted/remix_data/scripts/game/skater/physics.qb, read with qb2 tokens):
  skater_physics (37) + stat globals. 40 keys shared with P8's table, same names; differences: air
  gravity -1350 vs -1150, ground -1000 vs -200, rail -2000 vs -860, max speed 757-900 vs 625-750,
  jump 414-450 vs 405-425, boneless 489-525 vs 450-485, ground rotation 1.8 vs 3.6, frictions higher,
  crouched kick 532-675 vs 425-500. P8-only: air/vert hang stats, heavy air friction, bert, wallplant
  exit speeds, point rail boost (set to THUG2-like neutral values if ported).
- Cameras: P8 PSP's default is its own 0xfdce80cd "standard" (behind 7.72 ft, above 3.58, FOV 80,
  origin_offset 2.4); THUG2's Skater_Camera_Standard_Medium is behind 12, above 4.3, FOV 72. P8 also
  has THUG2-like Standard_Medium (11.2 / 4.1) that the PSP camera cycle does not use by default.
- Animations: P8's skater skeleton is thps7_human; THUG2's is thps5_human (55 bones; Remix also has
  thps6_human, 50). Different skeletons and anim formats (P8 compressed q48/t48 keys): THUG2 skater
  anims would need retargeting and re-encoding. Project Mod's airtricks.qb grew 468 -> 1356 lines
  (trick lists) on P8's own animations.

### Research: characters in vanilla P8 and Project Mod (no changes made)

- Vanilla P8's datap already has THAW story character models (loose .skin.psp): ped_mindy (+_full,
  _xen), ped_iggy body/head, ped_boone (+full, legs, underwear), ped_murphy (+full), ped_mega,
  ped_barber, ped_cholo/cholo2, ped_clover, gped_bum, gped_dad. The Hollywood goal peds use
  Ped_DVGuy/Ped_HippieF01 stand-ins only because the zone does not load these: real models are a
  matter of loading them and pointing THAW's profiles at them (PedParts budget applies).
- Project Mod adds 765 .skin.psp vanilla lacks: secret skaters (skater_barker, billyjoe, butterbody/
  heads, clover, cod, cutchemist, eddie, jango, jenna, jimbo, liljohn, shrek, sk8hand, skaboto),
  THUG2 story characters (nigel_full, phil_full/gagged, paulie_full, ped_jordan, cut_bodyguard_full),
  THUG2 ped sets (ped_male\barcelona, skatopia, australia, boston, ...), ~100 GameObject props
  (GameObjects\THUG, THUG2, THUG2Remix) and 578 THAW CAS textures (tex\models\skater_male_aw).
  All in P8 PSP format; usable on our build with the mod's profile/select scripts.

### THUG2 Remix feel is the default (physics and cameras)

- `tools/p8thug2.py` writes THUG2 Remix's values into P8's physics.qb in place: every parameter P8's
  six skater physics tables share with Remix's skater_physics and stat globals (active table
  0x09039fde: 23 values, e.g. air/ground/rail gravity -1150/-200/-860 -> -1350/-1000/-2000, max speed
  625-750 -> 757-900, jump 405-425 -> 414-450, ground rotation 3.6 -> 1.8), and P8 PSP's own skater
  cameras from Skater_Camera_Standard_* (standard 0xfdce80cd: behind 7.72 -> 12, above 3.58 -> 4.3,
  FOV 80 -> 72, origin_offset 2.4 -> 0.2, lerps), with the balance-trick fields 0x15814c70 (1.6) and
  0x48f0a316 ([30, 12.5, -10]) at 0. 150 values in all. `work/p8v/build.py` runs it by default;
  P8V_P8PHYSICS=1 keeps P8's.
- PPSSPP, story start, side by side: rolling, P8's camera sits on the skater, THUG2's is back at
  normal distance; nose manual: P8 zooms right in, THUG2's camera stays where it was.

### Real THAW characters for the goal peds (Hollywood's own ped pak)

- P8 builds peds only from parts in the level's ped pak (worlds\worldzones\z_houses\z_housesped.pak,
  loaded into the PedParts heap; Houses' holds DV guy + P8 goal peds). P8 PSP's part lists
  (cas_ped_m/f, profile_ped) name many models the disc lacks (generic skater parts, bums, pros,
  protesters, even models/ped_male/Ped_Skateboard). On the disc: loose ped_mindy(_full), ped_barber,
  ped_boone(_full), ped_murphy, ped_skateboards. Project Mod adds generic skater parts and SI_BMX,
  but its skater parts are a newer model format (header word 0x80; vanilla 0x60) and crash P8.
- `tools/p8pedpak.py` builds a ped pak for a list of profiles: part = .stex (key qbkey(<mesh less
  .skin>.tex)) + .skin (key qbkey(<mesh>), parent field = its .stex key: copying the template's
  parent crashed loading, 0x0899335c), parts from P8's ped paks, loose datap models, or `--also`
  another archive. `p8zone.REPOINT` (p8qb setstr on cas_ped_m) points the board at
  ped_skateboard_01 and the full-body protester profiles 04/03/02 at Mindy, the Barber and Boone;
  `p8zone.PROFILES` maps THAW's Ped_Mindy, Ped_Barber, ped_boone to them; ped_murphy is P8's own;
  everyone else (skaters, bums, pros, protesters, shop owners) stays the DV guy.
- The ped pak's own zone_sizes_psp entry (z_housesped 0x33802d55, 399,920) must be its size: a bigger
  pak overran the space set aside (same crash). PedParts on the PSP-1000 build: 802,944 (pak 445,664
  for DVGuy, Mindy, Barber, Boone, Murphy, BMX: 356 KB free).
- PPSSPP: standard route, no faults; gaps12's start: Mindy in her own model beside the skater
  ("Mindy: O to talk").

### THAW -> P8 PSP model converter (first working character: Mindy)

- P8 PSP skins (`tools/p8skin.py`, read): magic 0xC0EDBABE; 0x40 header ([3] radius, [5]/[6] texture
  block, [8]/[9] vertices, [11]/[12] display list, [14] highest bone + 1), name at 0x40 ('`' + file
  name), 16-byte records (1 material: list offset, material checksum, 0x808080; 4 hook: BASE/RET
  patched at run time, keyed by the THAW texture checksum; 2 draw: list offset, vertex offset),
  CLUT texture block, display list (per material a state block ending in the next VTYPE + RET; per
  draw BASE, VTYPE, BONE NUM 0, CALL 0x40 * bone per palette slot (<= 8), PRIM 3/4 with FFACE,
  0xff000000), GE hardware-skinning vertices (u8 weights summing to 0xf8 for every palette bone, s16
  UV raw/256-128, 4444 colour, s8 normal, s16 position in 1/16 inch).
- THAW PC skins (.skin.wpc, same scene container as levels; mesh +0x26 = weight count): 40-byte
  vertex: position 3 floats, weights 11/11/10-bit signed-normalized, bone indices 4 x u16 (bone * 3),
  normal 11/11/10 signed-normalized, BGRA colour, UV floats; strips. Same skeleton (thps7_human):
  P8 bone = THAW index / 3; P8 position = 16 * (x, -z, y) (point-set match against P8's own Mindy:
  median 0.87 in on a subsample; extents match within half an inch).
- `tools/thaw2p8skin.py`: THAW skin -> P8 skin (triangle lists, palettes of <= 8 bones, textures
  via thaw2psp.TexBlock CLUT4 + mips). THAW's ped_mindy_full: 11 meshes -> 38 draws, 142 KB (P8's own
  89 KB: strips would close the gap). `p8pedpak.py --file <mesh path>=<skin>` puts a converted model in
  the ped pak; `work/p8v/build.py` converts and uses it (P8V_P8MODELS=1 keeps P8's).
- PPSSPP (gaps12 start): THAW's Mindy stands and animates in Hollywood, same pose and size as P8's,
  with THAW's look (the red streak in her hair, the brighter skirt). Ped pak 499,344 bytes.
- Strips: thaw2p8skin keeps THAW's strips (cut at degenerate triangles and where a run outgrows the
  palette, pieces overlapping by two vertices; FFACE 0x9b by the run's parity): THAW Mindy 142 -> 96 KB
  (P8's own 89 KB).
- Every part P8 PSP's profiles name but its disc lacks exists in THAW at the same path (generic
  skater heads/torsos/pants/hair, Ped_Skateboard, bums, Pro_Reynolds, Pro_Thorne, Ped_Vato, Murphy,
  DV guy). `work/p8v/build.py` now converts THAW's model of every part of the ped pak's profiles
  (`p8zone.PED_PAK`: DV guy, Mindy, Barber, Boone, Murphy, BMX, ped_Skater_02/03, Pro_Reynolds,
  Pro_Rick_Thorne, Ped_Bum01, ped_SkaterSelect_vato) and `p8zone.PROFILES` maps THAW's Hollywood
  profiles to them (skaters, Reynolds, the jerk skater as Vato, bums). Ped pak 879,504 bytes; PSP-1000
  PedParts 950,272 (928 KB). Standard route: no faults, TopDown free at the end 696,416 (was 1.28 MB).
- PPSSPP: the caveman lesson's teacher and the punk skater race's "Joe Skater" are THAW's skaters.

### Barber and clothing steps: walk to the door (missions 1-2)

- THAW's flow: the goals' door triggers (mission collision, not loadable on P8) call
  Z_HO_EnterBarberShop / Z_HO_EnterClothingShop -> Ped_Utils_SetupCASStore (THAW's in-level shop UI,
  absent on P8), and Z_HO_ChangeYourLookWin checks the look changed.
- `p8goals.py shops` (zone_script: a zone script replaced by qbc-compiled source, qbc's 0x23 + name
  dropped; P8 bodies start with a newline token and end in 0x24): the goals' start scripts
  (Z_HO_ChangeYourLookWin/Win2, already goal_start_script via zonerekey) spawn a poll on the skater
  (Z_HO_EnterBarberShop/EnterClothingShop, never referenced on P8): within 160 in of THAW's
  *_Ext door node, "Press \m5 to go in" (\m5 is P8's circle glyph), Circle wins the goal. Replaces
  the instant pass.
- PPSSPP: story start at the barber door with the prompt; Circle -> "Change your clothes" at the
  clothing store door; Circle -> save prompt -> No -> skating, story on.
- Not yet: the look change. P8 has no load_cas level (pause_launch_level load_cas -> change_level
  freezes the screen) and no in-level CAS (create_pre_cas_menu is undefined, cas_stores.qb empty);
  P8's CAS is a front-end screen, so the look change needs a round trip through the front end.

### Barber and clothing stores: the look change (missions 1-2 done)

- P8 keeps THAW's in-level store machinery except its scripts: pak/CAS_common (Integrated_CAS_*
  menus, the item lists built from master_editable_list), the store cleanup in
  cleanup_before_changing_level_unload_all_paks (entering_cas_store, cas_store_pak_file), and P8's own
  barber leftovers (skutils' Integrated_CAS_Ped_Script, "Press \m5 to select hairstyle"). THAW's
  cas_stores.qb scripts (enter_cas_store, cas_store_enter: teleport into the store interior, load
  CAS_common and the store pak, options menu) are gone, and so is cas_store_params.
- `p8goals.py shops` now runs those steps in place (qbc-compiled, in two of the zone's unused scripts):
  Circle at the door -> HO_Ped_Barbershop: skater on the *_Ext door node, input off, HUD hidden,
  LoadPak pak/CAS_common (localized), RememberTemporaryAppearance, P8's
  Integrated_CAS_create_options_menu with THAW's barbershop (Hair, Hair Color, Facial Hair) or clothing
  (Shirt, Shirt Color 1, Pants, Pants Color) options; DONE/back -> HO_Ped_Graphicshop: menu gone, pak
  unloaded, skater back at the door walking, input on, GoalManager_WinGoal (goal id carried in the
  P8 global last_cas_item_id).
- Two P8 gaps fixed on the way: (1) DoScreenElementMorph (CFunc at 0x24074) on a missing element is a
  null read (PPSSPP "Bad memory access 00000004" at 0x088280ac): P8's menu maker (nextmenu_cas.qb
  0xfb625126) no longer makes THAW's current_scrolling_menu / edit_skater_menu arrows, which the CAS
  menu scripts morph; stand-ins are created first. (2) P8's cas_setup_rotating_camera plays fixed
  world cameras of its front-end CAS room (cas_scripts.qb in pak/cas, per body type), which land on
  the Walk of Fame in Hollywood: the store calls none (no cam_anim / cam_anim_sub) and plays its own
  PlayIGCCam in front of the door node. IGC camera quats: a yaw-only (0, sin(a/2), 0) looks down
  (-sin a, 0, -cos a); a node's yaw a faces (sin a, 0, cos a) (found with a 4-yaw test shot).
- THAW's barbershop and clothing interiors (*_Int / *_Edit nodes near y = 0) are in the converted level
  but unused for now.
- PPSSPP: story start -> barber door -> Circle -> BARBERSHOP menu with the skater framed on the right ->
  Hair -> P8's styles (Short Mohawk, Long Mohawk, Devillock...) change the model live -> DONE -> goal
  won, "Change your clothes" -> clothing door -> Circle -> Shirt (Baseball T) and Pants (Cargo Pants)
  live -> DONE -> save prompt -> skating with the new look, input back.

### Joey B. (dino head seller, story mission 8) in THAW's model

- Hollywood's node profiles: the story goal givers still on the DV guy were Joey B. (Gap23 "Buy the
  dino head", Z_HO_Ped_FatConstruction) and the cop-car bank drop's FallingDown guy (gaps13, not a
  story step). THAW builds Joey from two parts (Ped_FatConstruction + _HEAD).
- `thaw2p8skin.py --also <skin>...` merges more THAW parts into one P8 skin (same skeleton); `p8zone.MERGE`
  lists them and work/p8v/build.py passes them. P8's last unused full-body protester profile
  (Ped_HippieF_FullBody01) is repointed at the merged model (81 KB) and Z_HO_Ped_FatConstruction maps to it.
- Ped pak 960,608 bytes: the PSP-1000 PedParts heap goes from 928 KB to 1 MB (TopDown had ~696 KB free).
- PPSSPP (P8V_TESTGOAL=z_ho_goal_gaps23): "Buy the dino head $200" dialog; Joey B. stands by the
  skater ("Joey B.: O to talk") in THAW's look (work pants, tool belt, brown jacket).

### Story chain test: the whole Hollywood story through the dinosaur event

- `P8V_STORYRUN=1` (test build, `p8goals.py storyrun`): chapter_1_startup spawns a driver (in the zone's
  Z_HO_GapStart_Bob2Bob) that wins whatever goal runs (GoalManager_GetActiveGoalId, plus THAW's series
  children by name: GetActiveGoalId misses some, e.g. the caveman series' Gaps40/Gaps4) or activates
  the first of STORY_RUN not won unless locked; a panel names the step. Once Highcombo3 is won it also
  cuts to world cameras for a look at the dinosaur. The emulator test presses X every 11 s (save
  prompts default to No).
- Chain seen in PPSSPP: gaps15 (look) -> save -> gaps30 (clothes) -> counter / Gaps40 / Gaps4 (caveman,
  "New Trick: Caveman") -> gaps31 (sponsor) -> gaps2 (Whofleck) -> Counter2 / Gaps8 -> counter4 / Gaps16
  (revert, "New Trick: Manual", "Revert") -> gaps5 / Gaps6 (get your stuff back) -> highcombo /
  Highcombo2 / Highcombo3 (the dino pool) -> dino level event -> save -> chapter 2 (gaps23 "Buy the dino
  head" stays locked behind it, as in THAW).
- Fixes found on the way (all were null reads in LoadPak, FUN_0018ce2c: it reads the size of a file it
  failed to open; caught with a PPSSPP breakpoint on FUN_0000f480 with condition a0 == 0, ra 0x08990f9c):
  - chapter_info's level-event atoms name their mission pak's folder THAW's way
    (missions/worldzones/M_ZHOHIGHCOMBO3/M_ZHOHIGHCOMBO3_SUCCESS; also GAPS13, Chinese); P8's are flat.
    `p8goals.py scriptstr` swaps string literals inside a packed script (here
    chapter_info_register_structure), and the build points them at missions/worldzones/<m>_SUCCESS.
  - game_progress_process_igc also loads <pak>_text.pak (localized): `p8goals missions` now converts
    THAW's mission _text paks too (80 of them; delete work/p8v/missions_out to rebuild the cache).
  - Twelve chapter_info IGC atoms load THAW IGC asset paks (pak/igc/z_ho_post_dino, z_bh_intro, ...),
    none on P8's disc; IGC scenes are skipped anyway, so `p8goals.py igcpaks` renames their Pak param
    (thx_igc_pak_absent): nothing loads, PlayIGCScene still runs, the story order holds.
  - The dino event's state change is in its IGC shot script (M_ZHOHIGHCOMBO3_SUCCESS_Shot2), never run
    with the IGC skipped: `p8goals.py zonescript` (zone_script on any zone or mission pak) puts
    DINO_BEFORE 0, DINO_AFTER 1, DINO_BLDG_AFTER 1 in the success pak's startup. Traced in PPSSPP right
    after Highcombo3's win.
- Not seen yet: the dinosaur building in its after state on screen (the test cameras missed it), and
  the cutscenes (HO_LevelEvent_Dino.cut and the IGCs) are still skipped.

### Sponsor challenge (mission 4): the stat challenges menu

- THAW's stats board is a Ghost GameObject (Z_HO_TRG_Stats_Ghost, created by the sponsor step's start
  script) inside the skate shop, behind the shop front the converted level closes; its ped speech
  ("Press \ms to look at stat challenges") never went away on P8 (no ObjectOutOfRadius for it), so it
  stayed on screen everywhere and kept Circle.
- `p8goals shops` now also replaces its trigger script (Z_HO_TRG_Stats_GhostScript, in the zone's node
  qb: `zone_script` searches every .qb of the pak now) with a poll spawned on the skater, as for the shop
  doors: within 160 in of the sponsor step's spot in front of the shop, while that step is active or
  won, "\m5 stat challenges"; Circle runs THAW's stats_selection_menu_create.
- Two more P8 gaps: (1) stats.qb's spots name Hollywood Z_HO while its level structure is Houses'
  (level = Z_Houses): StatsManager_GetGroupNumFromLevel found no group, so the menu returned at once;
  build: `p8qb setdata stats.qb Z_HO=Z_Houses`. (2) build_stats_poster draws THAW sprites P8 lacks
  (heart: CreateScreenElement null read at 0x08886cb0, called from 0x0882b768; spazzburst: a jump to 0);
  heart, spazzburst and new_bg_2 become white2 (`p8qb rekeyall gamemenu_stats.qb`).
- PPSSPP (P8V_TESTGOAL=z_ho_goal_gaps31): at the shop front "O stat challenges"; Circle -> SPONSOR
  CHALLENGES, Stats 1 (Grind for 2 seconds, Land a 2,000 point combo, Caveman 1 times in one combo, Ollie
  up 5 feet), Accept; Triangle out; skating again, the prompt gone away from the shop.
- Not verified: winning by completing a stat challenge (THAW's M_ZHOGAPS31 gameplay pak spawns
  Z_HO_Goal_SponsorChallenge_WinGoal, which waits for StatsManager_GetTotalGoalsComplete > 0).

### Hardware batch (2026-10-13 morning)

- work/iso/F THAW P8 stores.iso (PSP-1000 build, P8V_NOINTRO) and work/iso/G THAW P8 stores big
  (PSP-2000 3000).iso (P8V_BIG + P8V_NOINTRO; ARK-4 needs "use extra memory" forced on). Both through
  `mkumd.py --like <P8 v1.00> --compact-wad PSP_GAME/USRDIR/datap --sectors`.
- PPSSPP on the ISOs themselves: F (PSP-1000): menu -> Story -> Start New Story -> Normal -> Hollywood
  at the barber door -> Circle -> BARBERSHOP -> Hair -> Long Mohawk applied. G (as PSP-2000, the test
  copy's PSPModel set to 1 for the run and back to 0): same, store menus and submenus.
- One G screenshot 6 s after Circle showed THAW's barbershop interior with no menu; a rerun with shots
  at 1.5-14 s showed the store normally every time (likely a capture of another render pass; the same
  frame appeared once on the PSP-1000 tree). Watch for it on hardware.

### PETA protesters at the dinosaur (story mission 8's protest)

- THAW's protesters (Z_HO_TRG_Ped_Protester_01/04/05, profile Z_HO_ped_hippie_01: random hippie head,
  torso and legs, node flag DINO_BEFORE so the dino event removes them) were never created: the port
  leaves Pedestrian nodes uncreated (p8zone NO_SPAWN) and their CreatedAtStart sits in compressed node
  structs other peds share.
- `p8goals.py protesters` (`zone_append`: compiled lines added before a zone script's endscript) makes
  the zone's goals script (Houses' key 0xb58ff31f) create the three while Z_HO_Goal_Highcombo3 is not won.
- Model: P8's unused Ped_OldLady_Fullbody profile is repointed (REPOINT) at THAW's hippie torso, merged
  with head01 and legs01 (MERGE, 66 KB); PROFILES maps Z_HO_ped_hippie_01(_roaming) to it. Ped pak
  1,026,272 bytes; PSP-1000 PedParts 1,152 KB.
- PPSSPP (P8V_TESTGOAL=z_ho_goal_highcombo): the protesters stand on the street below the dinosaur in
  THAW's look (paisley tops, jeans, long blonde hair). Not checked yet: their removal at the dino event
  (DINO_BEFORE 0 is traced, the peds' disappearance is not).

### The cop-car bank drop's goal giver (gaps13) as THAW's model

- Z_HO_Ped_FallingDown (body + head) -> P8's unused Ped_Welder full-body profile, repointed at THAW's
  Ped_FallingDown_body with the head merged (61 KB). Ped pak 1,087,584 bytes (PSP-1000 PedParts 1,152 KB).
- PPSSPP (P8V_TESTGOAL=z_ho_goal_gaps13): the goal runs, no faults. The giver himself was not seen (the
  goal starts in gameplay, he stands elsewhere); the converted model's extents match Joey B.'s (72 in
  tall). Hollywood's goal givers are now all THAW models except the DV guy's own goal (gap7, THAW's DV
  guy converted already) and the graffiti-goal taggers (Ped_MexicanGraffiti, peds left unspawned).

### THAW's own CAS parts in the stores (missions 1-2 with THAW's hair and clothes)

- P8 keeps its skater part lists in pak/cas/cas.pak (cas_scripts.qb, loaded at boot; its pak_sizes_psp
  entry 'cas' = 137,264 is the memory set aside, so it follows the pak's size), one set per body style:
  cas_punk_hair, cas_punk_torso, cas_punk_legs, cas_punk_head, _hands, _bare_torso, _lower_legs, ...
  (0x989b60dd: style prefix + part name). Parts are loose models (models/skater_male/*.skin.psp + a
  4-byte .tex.psp). The THUG2 Remix build never had THAW's parts (it used Remix's CAS as is).
- P8's and THAW's skaters are built the same way (arms/body, head, hands, bare torso, lower legs, shirt,
  pants, hair; one skeleton). `tools/p8cas.py` makes the PUNK style THAW's male skater: every model
  converted (thaw2p8skin, 128 px textures) and added at THAW's own path; THAW's 'replace'/'with'
  texture variants baked into their own skins (thaw2p8skin `retex`); cas_punk_hair = THAW's 25 male
  hairs, cas_punk_torso / _legs = what THAW's Hollywood clothing store sells (29 shirts, 15 pants;
  shorts carry P8's show-legs flag 0x9b421c33), body pieces repointed to Body_M_*; P8's three PUNK
  presets (0xee5fffac is the style's default) become THAW's appearance_custom_skater_male_01..03.
  cas.pak 137,264 -> 139,744; 136 loose files (about 2 MB on disc). `work/p8v/build.py` runs it
  (cached in work/p8v/casout; P8V_P8CAS=1 keeps P8's parts).
- `p8cas.py` writes QB data in place (typed read/encode, `p8qb.resize`). Every untouched global reads
  the same afterwards (checked). Found on the way: P8 stores a struct field's script as plain tokens
  right after the field; qb.py did not count them, so the item walk lost sync after the URBN torso list
  and resize missed pointers (crash loading Hollywood, null read in FUN_0004ce68, a global array
  lookup). `qb.script_end` fixes the walk.
- Converter: alpha cutouts (THAW's frayed sleeveless armholes) drew black: textures with both clear
  and opaque texels now get the GE alpha test and a palette with entry 15 transparent
  (thaw2psp.quantize15_cutout).
- Facial hair is not THAW's yet: THAW's beards are a second texture pass on the head material
  (the converter keeps one texture per material). Same for jeans logos.
- PPSSPP: story start as THAW's default skater (mullet, sleeveless); barber Hair lists Bald, Buzzed,
  Devil Lock, Dead Guy Doo, Mullet, McSqueeb, Mohawk A/B...; choosing Mohawk B puts THAW's red mohawk
  on; clothing store Shirt (Sleeveless, Sweater ...) and Pants (Jeans Ripped ...) change the model.
  No faults. Heaps in the barber: skatergeomheap0 271 KB free (was 220 KB with P8's parts), TopDown
  382 KB free.

### Sponsor challenge (mission 4): won by a completed stat challenge

- THAW starts the step's win poll (Z_HO_Goal_SponsorChallenge_WinGoal: every 5 frames
  `skater : StatsManager_GetTotalGoalsComplete`, > 0 wins z_ho_goal_gaps31) from the TriggerScript of a
  Ghost GameObject in M_ZHOGAPS31_gameplay (TRG_G_GAPS31_StatsDummy). P8 creates no Ghosts, so it
  never ran. `p8goals sponsor` (build.py): the step's start script spawns it, its cleanup
  (goal_deactivate_script, also run first by the start) kills it. The StatsManager member functions
  are all in P8's executable (their checksums appear as lui/ori pairs).
- Test switch P8V_STATTEST=1: stats.qb's 'Land a 2,000 point combo' becomes 100.
- PPSSPP (P8V_TESTGOAL=z_ho_goal_gaps31, P8V_STATTEST=1): O stat challenges -> Accept (the board then
  offers only Exit) -> right, up into the quarter pipe beside the skate shop, kickflip, land ->
  GoalManager_WinGoal z_ho_goal_gaps31, goal_success_messages, goal_unload_pak (p8trace). The same
  path runs at the real 2,000.

### The dinosaur's after state, on screen (story mission 8)

- THAW's dino event sets its node flags in two places P8 skips: the IGC shot script
  (M_ZHOHIGHCOMBO3_SUCCESS_Shot2: DINO_BEFORE 0, AFTER 1, BLDG_AFTER 1) and the end script of the
  cutscene after it (cutscenemenu.qb's HO_LevelEvent_Dino_end, `#4a` structs in the old dump, decoded by
  the current thawqbdump: AFTER 1, HEAD 1, BLDG_AFTER 1, and the two streetlights its begin script had
  killed created again). The port set only the shot script's three, so the fallen head (its own flag,
  NODEFLAG_Z_HO_DINO_HEAD) never appeared. build.py's DINO_EVENT_FLAGS (the net state, HEAD 1 added)
  go into M_ZHOHIGHCOMBO3_Success_startup.
- Test switches (build.py): P8V_DINOAFTER=1 sets DINO_EVENT_FLAGS from the first step's start script
  (Z_HO_ChangeYourLookWin, which runs after chapter startup has applied the story's flags; from the zone's
  goals script they were overwritten), P8V_CAM=x,y,z,yaw holds a world camera there, P8V_CREATE=<nodes>
  creates nodes there. `p8goals zoneappend` adds lines to a zone script (zone_append now also takes
  qbc-compiled scripts, and no longer leaves a second endscript after the added lines).
- Cameras: a yaw-only PlayIGCCam quat (0, sin(a/2), 0) looks along (-sin a, 0, +cos a); the old note
  (-cos a) went unnoticed because the shop doors face +-x.
- PPSSPP, fixed cameras, without and with the event's flags: from (-1500, 300, 1700) yaw 1.62 the red
  dinosaur with its globe stands on the diner roof / is gone, the roof broken in; from (-1900, -100, 2400)
  yaw 1.093 the PETA protesters line the street in front of the scaffold / the fallen head lies on the
  street and the protesters are gone. The pieces built hidden in the .psp_level (STORY_START 'hidden')
  do show once their flag is on: P8 is not Remix here.

### THAW's dino cutscene played by P8 (big build only, so far)

- `tools/p8cut.py` converts a THAW cutscene to P8 PSP cutscene paks: THAW PS2's paks as the source
  (.ska / .ske / .qb carry over unchanged), models converted from THAW PC's (`thaw2p8skin`: skins, and
  now rigid .mdl with a 0xC0 header and no weights), .stex stubbed, .shd dropped, ps2 -> psp paths.
  `p8cut.py sizes` adds the paks to `pak_sizes_psp` (PlayCutscene reads a null struct without them).
  build.py: `CUTSCENES` (cached in `cutout/`), test switch `P8V_PLAYCUT=<name>` plays one from the
  first step's start script.
- HO_LevelEvent_Dino: `_main` 877,776 bytes (6 character skins 338 KB, 60 rigid props 294 KB, dino
  skins 172 KB, skeletons 51 KB), `_cam0` 491,008 (the .ska animation 485 KB). P8's largest stock
  cutscene is about 300 KB in total.
- PSP-1000 build: crash (null pak in the pak entry loader 0x18bb9c, called from 0x18a8c8): the
  `_main` pak's allocation fails. PlayCutscene's heap is made in 0x171174 as the main heap's largest
  free block less 0x32000; measured at the cutscene start: 421,504 free, so the cutscene heap is
  216,704 bytes. GoalHeap (271 KB free), COIMHeap (337 KB free, peds in it) and PedParts are separate
  heaps, so the gap cannot simply take them.
- PSP-2000/3000 build (`P8V_BIG=1`, PSPModel 1): cutscene heap 30.9 MB; the cutscene plays through in
  PPSSPP (dinosaur with globe falls, bus, back to play with no fault). The rigid props draw (the
  converter's "0 draws" count is for skinned draws only). Textures at the 64-texel cap look blocky.
- `ppsspp_ws.start` now always launches through the scheduled task: launched directly from Claude
  Code's shell, PPSSPP opened without loading the game.

### In-level movies (the pre-rendered cutscene route): hardware test ISO H

- P8 plays its own story clips in-level through script 0x287fb55a (`Name = "c\C_s_int"`, PlayMovie
  on `movies\<dir>\<name>.pmf`). build.py test switch `P8V_PLAYMOVIE=<name>,<name>`: the first step's
  start plays them in turn. `p8goals zoneappend` no longer reads the `\n` in a path ("start\ns_logo")
  as a line break.
- PSP-1000 build (P8V_AUTO, P8V_NOINTRO), PPSSPP PSPModel 0: PlayMovie `c\c_mug_th` (retail) then
  `start\ns_logo` (ours, pmfmux) both run in Hollywood with THAW's goals loaded; ours shows (THAW's
  Neversoft logo) and play resumes, no fault. (P8's C_s_int, 0x5ea3b6b7, is still the one noted to
  crash the movie player with the goals loaded.)
- work/iso/H THAW P8 movie test.iso (that build): on the PSP it tells whether our encoding plays on
  hardware without p8eboot's intro patch, and whether in-level movies fit in PSP-1000 memory. ISO B
  (P8 baseline: retail data + the intro patch) still to report: it tells whether the intro crash is
  the patch rather than our movies.
- PSP-3000 result for H (ARK-4 extra memory forced): the retail clip plays, then a crash when ours
  starts. So in-level movies fit and the problem is our movie file (as A's intro crash).

### pmfmux: Sony's PSMF layout (hardware test ISO I)

Every stock movie (P8's and Remix's) differs from what pmfmux wrote:
- A private stream 2 (0xBF) packet starts each GOP's sector, before the video PES:
  `01 E0`, four u16 sector offsets (from this sector) where the GOP's first four pictures end,
  u32 0, u16 2 + 4n, u16 n, then per picture u32 size | 0x800000 if it is a reference picture
  (nal_ref_idc != 0). Checked against 961 pictures of three stock movies, no mismatch. A GOP
  starts at an access unit carrying an SPS (a scene-cut IDR inside a GOP does not start one).
  pmfmux wrote none.
- The first sector already carries the system header, the 0xBF packet and video (ours: padding).
- Video PTS + DTS only on a GOP's first packet and then about every 16 frames; other video
  packets are full (PES length 2028) with no timestamps. Sony's streams decode one frame early
  (DTS = PTS - 3003); x264's without B-frames have DTS = PTS, so DTS now comes from the source.
- Pacing: the system header declares the decoder buffers (P8: video 251 KB, audio 8 KB; Remix:
  4 KB audio). Sony's packets go out earliest deadline first, video about 0.9-1.0 s and audio
  about 0.2 s ahead of their decode time, the SCR jumping when nothing is due. pmfmux sent audio
  0.5 s ahead (about 10 KB of our 352 kbps audio before the first frame: over the 8 KB buffer).
- Our first access unit began with x264's version SEI before its delimiter; now dropped (Sony's:
  AUD, SPS, PPS, SEI..., slice).
- Still different: our audio is atracdenc's 352 kbps ATRAC3plus (2048-byte frames); P8's movies use
  128 kbps (744-byte frames, `0F D0 28 5C`), Remix's 96 kbps. atracdenc has no other ATRAC3plus rate.
pmfmux rewritten to do all of the above (mux(), buffer_sizes, gop_info; `--video-from` /
`--audio-from` reuse a movie's streams). Remuxing P8's c_mug_th gives the same GOP sectors
(0, 161, 269) and the same first-GOP end sectors (10, 13, 17, 21) as Sony's file.

work/iso/I THAW P8 movie mux test.iso (PSP-1000 build, P8V_AUTO, P8V_NOINTRO, build.py
`P8V_PLAYMOVIE=t\t_mux,t\t_vid,t\t_all`, movies in `movies\t` from work/movtest) plays in Hollywood:
1. t_mux: P8's Tony Hawk mugshot clip, remuxed by the new pmfmux (tests the muxer alone);
2. t_vid: our THAW Neversoft video (x264) with P8 retail audio (c_s_iscg's) (tests our video);
3. t_all: our Neversoft video with our 352 kbps audio (tests our audio).
PPSSPP (PSP-1000): all three play, then Hollywood.
- PSP-3000 result for I (extra memory forced): the Tony clip and one Neversoft logo (t_vid: our
  video, retail audio) play, then black screen and a crash at t_all. So the new mux and our x264
  video work on hardware; our 352 kbps ATRAC3plus audio (2048-byte frames) crashes the player.

### ATRAC3plus at P8's rate: patched atracdenc (hardware test ISO J)

- Upstream atracdenc (checked at master, 2026-09) still fixes ATRAC3plus at 2048-byte frames; its
  --bitrate is ATRAC3-only. Its bitstream writer already takes the frame size (TAt3PBitStream
  frameSz, bit allocation from it), so `tools/atracdenc_thaw/atracdenc_thaw.patch` adds
  AT3P_FRAME_BYTES for it and both output containers, plus `pcm_io_rawwav.cpp` (16-bit WAV reader)
  so it builds with MinGW alone (CMake from scoop; static link). Built into bin/atracdenc/thaw.
- 744-byte frames give `0F D0 28 5C` (P8's movies, 128 kbps), 560 give `28 45` (Remix's, 96 kbps).
  ffmpeg decodes both; their loudness envelopes follow the source as the 352 kbps encode does.
- pmfmux uses it (`--abytes`, default 744). Template for P8: a retail PSMF0014 movie (c_mug_th:
  system header video 251 KB / audio 8 KB; the video entry is stream 0xB9, all video streams).
- work/iso/J THAW P8 movie audio test.iso (PSP-1000 build, P8V_AUTO, P8V_NOINTRO,
  `P8V_PLAYMOVIE=t\t_new744,t\t_new560`): THAW's Neversoft logo encoded fresh from intro.bik
  (first 11.5 s) with 128 kbps audio, then the same at 96 kbps, then Hollywood. PPSSPP: both play.
