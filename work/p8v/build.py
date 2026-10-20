"""Rebuild the vanilla Project 8 v1.00 test tree (work/p8v/tree) from pristine copies plus our changes.
Pristine: datap.hed.orig / datap.wad.orig / BOOT.BIN.orig / EBOOT.BIN.orig here (made on first run).

Switches: P8V_AUTO=1 boots straight into the Houses slot (tests; no menu driving), P8V_NOGOALS=1 keeps
Houses' zone scripts (no THAW story), P8V_TESTGOAL=<goal> opens the story with that goal, P8V_P8UI=1 P8's front end,
P8V_ZONE=<dir under work/p8v> for another z_houses build, P8V_LEVEL=<.psp_level> another converted
Hollywood scene, P8V_BASELINE=1 the executable patch only,
P8V_NOSPAWN=<p8zone --no-spawn list> which of Hollywood's node classes stay uncreated,
P8V_ZONEARGS=<more p8zone arguments> (tests: --create, --map), P8V_BIG=1 the PSP-2000/3000 build,
P8V_NOINTRO=1 no intro movies (the executable unpatched, as shipped),
P8V_P8PHYSICS=1 P8's own skater physics and cameras (default: THUG2 Remix's),
P8V_PEDPAK=<profiles> another ped pak set, P8V_ORIGPEDPAK=1 Houses' own ped pak (tests),
P8V_P8MODELS=1 P8's own models instead of the THAW conversions."""
import os, shutil, subprocess, sys

R = r'C:\Users\tonyk\Documents\GitHub\THAWremix'
W = os.path.join(R, r'work\p8v')
T = os.path.join(W, r'tree\PSP_GAME')
U = os.path.join(T, 'USRDIR')
HED, WAD = os.path.join(U, 'datap.hed'), os.path.join(U, 'datap.wad')
PY = sys.executable
B = chr(92)


def run(*a):
    print('>', ' '.join(os.path.basename(x) if os.path.isabs(x) else x for x in a))
    subprocess.run([PY, *a], check=True, cwd=R)


def tool(name, *a):
    run(os.path.join(R, 'tools', name), *a)


def pristine(src, keep):
    if not os.path.exists(keep):
        shutil.copyfile(src, keep)
    shutil.copyfile(keep, src)


# archive and executable back to the shipped state
pristine(HED, os.path.join(W, 'datap.hed.orig'))
pristine(WAD, os.path.join(W, 'datap.wad.orig'))
for f in ('BOOT.BIN', 'EBOOT.BIN'):
    pristine(os.path.join(T, 'SYSDIR', f), os.path.join(W, f + '.orig'))

# executable as shipped; the unencrypted BOOT.BIN serves as EBOOT.BIN too, as in the mod. (p8eboot's
# boot_movies patch, which started the intro while P8's legal screen was still up, crashes on the PSP
# even with P8's own movies (ISO B); the intro now plays from the main menu's setup script, below.)
if os.environ.get('P8V_EBOOTINTRO'):  # the old way, for comparison only
    tool('p8eboot.py', os.path.join(W, 'BOOT.BIN.orig'), os.path.join(T, 'SYSDIR', 'BOOT.BIN'))
else:
    shutil.copyfile(os.path.join(W, 'BOOT.BIN.orig'), os.path.join(T, 'SYSDIR', 'BOOT.BIN'))
shutil.copyfile(os.path.join(T, 'SYSDIR', 'BOOT.BIN'), os.path.join(T, 'SYSDIR', 'EBOOT.BIN'))

if os.environ.get('P8V_BASELINE'):
    if os.environ.get('P8V_AUTO'):  # shipped data straight into Houses (reference tests: P8's own level)
        qbdir = os.path.join(W, 'qb')
        tool('hed.py', 'extract', HED, WAD, qbdir, '--sectors', '--match', 'qb.pa')
        qpak, qpab = os.path.join(qbdir, 'pak', 'qb.pak.psp'), os.path.join(qbdir, 'pak', 'qb.pab.psp')
        tool('p8qb.py', 'setkey', qpak, qpab, r'game\startup.qb.psp', 'default_system_startup', 'Load_Z_MainMenu', '0x16a10a9a')
        tool('hed.py', 'replace', HED, WAD, r'\pak\qb.pab.psp', qpab, '--sectors')
        tool('hed.py', 'replace', HED, WAD, r'\pak\qb.pak.psp', qpak, '--sectors')
    sys.exit(print('baseline'))

# Hollywood in Houses' slot (where a new career starts):
#   p8zone.py extracted/thaw_ps2_data z_ho <vanilla z_houses.pak.psp> <converted .psp_level> work/p8v/zone_slot
#     --slot z_houses --keep-scripts --no-spawn Pedestrian,Vehicle,GameObject
# with the geometry from thaw2psp.py build "THAW CLEAN/Game" z_ho <out> <name> --at -2336.48974609375
#   96.596923828125 -2482.915283203125 --texel 4 --tess 800 --decal-lift 1.0 (2.81 MB, under Houses' 2.85 MB; the full
#   3.89 MB build is kept as work/p8mod/ho/z_sc.full.psp_level). (--col with the props appended loads to a black level; not used.)
# (THAW's GameObjects name models P8 lacks: Ghost triggers crash scene setup, transition markers hang;
# the Remix build never used them either. LevelObjects and LevelLights are created.)
# A native z_ho zone crashed at boot once SkateZones named it; see docs/LOG.md.
qbdir = os.path.join(W, 'qb')
tool('hed.py', 'extract', HED, WAD, qbdir, '--sectors', '--match', 'qb.pa')
qpak, qpab = os.path.join(qbdir, 'pak', 'qb.pak.psp'), os.path.join(qbdir, 'pak', 'qb.pab.psp')
# P8V_BIG=1: the PSP-2000/3000 build. MEMSIZE = 1 in PARAM.SFO gives P8 the extra memory (its main
# region is MaxFreeMemSize - 0xA2800: 20.1 -> 53.7 MB in PPSSPP as a PSP-2000); the ped heaps are
# script numbers (p8goals heaps): COIM, Houses' PedParts, AnimHeap
BIG = bool(os.environ.get('P8V_BIG'))
BIG_HEAPS = (652288 * 4, 401472 * 4, 131072 * 4)
PEDPARTS_1000 = 1152 * 1024  # Hollywood's ped pak of THAW characters (about 1.05 MB)
pristine(os.path.join(T, 'PARAM.SFO'), os.path.join(W, 'PARAM.SFO.orig'))
if BIG:
    tool('sfo.py', os.path.join(T, 'PARAM.SFO'), 'set', 'MEMSIZE', '1')
    tool('p8goals.py', 'heaps', qpak, qpab, *map(str, BIG_HEAPS))
else:  # THAW's goal characters as P8's real models: their parts outgrow Houses' 401,472 bytes
    tool('p8goals.py', 'pedparts', qpak, qpab, str(PEDPARTS_1000))
# Mindy's own model for THAW's Ped_Mindy (p8zone.PROFILES maps it to this full-body profile)
sys.path.insert(0, os.path.join(R, 'tools'))
import p8zone  # noqa: E402
for old, new in ([] if os.environ.get('P8V_NOREPOINT') else p8zone.REPOINT):  # (test switch)
    tool('p8qb.py', 'setstr', qpak, qpab, 'cas_ped_m.qb.psp', old, new)
PED_PROFILES = os.environ['P8V_PEDPAK'].split(',') if os.environ.get('P8V_PEDPAK') else p8zone.PED_PAK
# THAW's own character models converted to P8's skin format (thaw2p8skin.py), used in place of P8's:
# every part of the ped pak's profiles that THAW has at the same path (P8 PSP lacks most of them)
CONV = os.path.join(W, 'conv')
THAW_DATA = os.path.join(R, 'THAW CLEAN', 'Game', 'data')
CONVERTED = []
if not os.environ.get('P8V_P8MODELS'):
    import p8pedpak, qb  # noqa: E402
    qb.load_names(os.path.join(R, 'extracted', 'dbg'))
    thaw_files = {}
    for root, _, fs in os.walk(os.path.join(THAW_DATA, 'models')):
        for f in fs:
            if f.lower().endswith('.skin.wpc'):
                full = os.path.join(root, f)
                thaw_files[os.path.relpath(full, THAW_DATA).replace('\\', '/').lower()] = full
    os.makedirs(CONV, exist_ok=True)
    parts = sorted({m for ms in p8pedpak.part_meshes(qpak, qpab, PED_PROFILES).values() for m in ms})
    for m in parts:
        src = thaw_files.get((m + '.wpc').lower())
        if src:
            dst = os.path.join(CONV, os.path.basename(m) + '.psp')
            also = [thaw_files[(x + '.wpc').lower()] for x in p8zone.MERGE.get(m.lower(), ())]
            tool('thaw2p8skin.py', src, dst, '--name', os.path.basename(dst), *(['--also', *also] if also else []))
            CONVERTED.append((m, dst))
# Hollywood's own ped pak (THAW's characters as P8 models; parts from vanilla and Project Mod)
MOD = os.path.join(R, 'work', 'p8mod', 'tree', 'PSP_GAME', 'USRDIR')
pedd = os.path.join(W, 'pedpak')
if not os.path.exists(os.path.join(pedd, 'z_housesped.pak.psp.orig')):
    tool('hed.py', 'extract', os.path.join(W, 'datap.hed.orig'), os.path.join(W, 'datap.wad.orig'), pedd,
         '--sectors', '--match', 'z_housesped.pak.psp')
    shutil.copyfile(os.path.join(pedd, 'worlds', 'worldzones', 'z_houses', 'z_housesped.pak.psp'),
                    os.path.join(pedd, 'z_housesped.pak.psp.orig'))
tool('p8pedpak.py', qpak, qpab, os.path.join(W, 'datap.hed.orig'), os.path.join(W, 'datap.wad.orig'),
     os.path.join(pedd, 'z_housesped.pak.psp.orig'), os.path.join(pedd, 'z_housesped.pak.psp'), *PED_PROFILES,
     '--also', os.path.join(MOD, 'datap.hed'), os.path.join(MOD, 'datap.wad'),
     *[a for path, f in CONVERTED for a in ('--file', f'{path}={f}')])
PEDPAK_SIZE = os.path.getsize(os.path.join(pedd, 'z_housesped.pak.psp'))
assert PEDPAK_SIZE <= (BIG_HEAPS[1] if BIG else PEDPARTS_1000), f'ped pak {PEDPAK_SIZE} outgrows PedParts'
if not os.environ.get('P8V_ORIGPEDPAK'):  # (test switch)
    tool('hed.py', 'replace', HED, WAD, '\\worlds\\worldzones\\z_houses\\z_housesped.pak.psp',
    os.path.join(pedd, 'z_housesped.pak.psp'), '--sectors')
    # its zone_sizes_psp entry (z_housesped, 0x33802d55) is the memory P8 sets aside for it: a bigger
    # pak than Houses' 399,920 bytes overran it (a crash loading Hollywood, 0x0899335c)
    tool('p8qb.py', 'setdata', qpak, qpab, r'scripts\zone_sizes_psp.qb.psp', f'int:399920={PEDPAK_SIZE}')
# THAW's own skater parts (p8cas.py): THAW's male body, hair and Hollywood store clothes as the PUNK style,
# loose models at THAW's paths, P8's part lists in pak/cas/cas.pak rewritten (cached in casout; rebuilt
# when the tools change). P8V_P8CAS=1 keeps P8's own parts.
if not os.environ.get('P8V_P8CAS'):
    casd, caso = os.path.join(W, 'casx'), os.path.join(W, 'casout')
    if not os.path.exists(os.path.join(casd, 'pak', 'cas', 'cas.pak.psp')):
        tool('hed.py', 'extract', os.path.join(W, 'datap.hed.orig'), os.path.join(W, 'datap.wad.orig'), casd,
             '--sectors', '--match', r'pak\cas\cas')
    newest = max(os.path.getmtime(os.path.join(R, 'tools', f)) for f in ('p8cas.py', 'thaw2p8skin.py'))
    if not os.path.exists(os.path.join(caso, 'cas.pak.psp')) or os.path.getmtime(os.path.join(caso, 'cas.pak.psp')) < newest:
        shutil.rmtree(caso, ignore_errors=True)
        tool('p8cas.py', THAW_DATA, os.path.join(casd, 'pak', 'cas', 'cas.pak.psp'), caso)
    for line in open(os.path.join(caso, 'files.txt')):
        arch, local = line.rstrip('\n').split('\t')
        tool('hed.py', 'add', HED, WAD, arch, local, '--sectors')
    tool('hed.py', 'replace', HED, WAD, r'\pak\cas\cas.pak.psp', os.path.join(caso, 'cas.pak.psp'), '--sectors')
    # pak_sizes_psp's 'cas' entry is the memory set aside for it (as zone_sizes_psp's for zone paks)
    tool('p8qb.py', 'setdata', qpak, qpab, r'scripts\pak_sizes_psp.qb.psp',
         f"int:137264={os.path.getsize(os.path.join(caso, 'cas.pak.psp'))}")
# THAW's cutscenes as P8 cutscenes (p8cut.py: THAW PS2's paks, models converted from PC; cached in
# cutout/<name>, rebuilt when the tools change), added at the paths P8's PlayCutscene loads
CUTSCENES = ('HO_LevelEvent_Dino',)
newest = max(os.path.getmtime(os.path.join(R, 'tools', f)) for f in ('p8cut.py', 'thaw2p8skin.py', 'thaw2psp.py'))
for cut in CUTSCENES:
    cuto = os.path.join(W, 'cutout', cut.lower())
    listing = os.path.join(cuto, 'files.txt')
    if not os.path.exists(listing) or os.path.getmtime(listing) < newest:
        shutil.rmtree(cuto, ignore_errors=True)
        tool('p8cut.py', os.path.join(R, 'extracted', 'thaw_ps2_data'), THAW_DATA, cut, cuto)
    for line in open(listing):
        arch, local = line.rstrip('\n').split('\t')
        tool('hed.py', 'add', HED, WAD, arch, local, '--sectors')
if CUTSCENES:  # their paks' memory sizes (pak_sizes_psp; PlayCutscene crashes without them)
    tool('p8cut.py', 'sizes', qpak, qpab, *(os.path.join(W, 'cutout', c.lower(), 'sizes.txt') for c in CUTSCENES))
# THUG2 Remix's skater feel (physics values and cameras, no balance-trick zoom); P8V_P8PHYSICS=1 keeps P8's
if not os.environ.get('P8V_P8PHYSICS'):
    tool('p8thug2.py', qpak, qpab, os.path.join(R, 'extracted', 'remix_data', 'scripts', 'game', 'skater', 'physics.qb'))
# the dino level event's net node flags (THAW: its IGC shot script, then the cutscene's end script)
DINO_EVENT_FLAGS = (r'ChangeNodeFlag { NODEFLAG_Z_HO_DINO_BEFORE 0 }\nChangeNodeFlag { NODEFLAG_Z_HO_DINO_AFTER 1 }\n'
                    r'ChangeNodeFlag { NODEFLAG_Z_HO_DINO_HEAD 1 }\nChangeNodeFlag { NODEFLAG_Z_HO_DINO_BLDG_AFTER 1 }')
GOALS = not os.environ.get('P8V_NOGOALS')  # THAW's own zone scripts and story goals (P8V_NOGOALS=1: Houses' scripts)
zone = os.path.join(W, os.environ.get('P8V_ZONE', 'zone_thaws' if GOALS else 'zone_slot'))
if GOALS and not os.environ.get('P8V_ZONE'):
    # Hollywood with THAW's own zone scripts (its Z_HO_Goals adds the story goals)
    tool('p8zone.py', os.path.join(R, 'extracted', 'thaw_ps2_data'), 'z_ho',
         os.path.join(W, 'houses', 'worlds', 'worldzones', 'z_houses', 'z_houses.pak.psp'),
         os.environ.get('P8V_LEVEL', os.path.join(R, 'work', 'p8mod', 'ho', 'z_sc.psp_level')), zone, '--slot', 'z_houses',
         '--no-spawn', os.environ.get('P8V_NOSPAWN', 'Pedestrian,Vehicle,GameObject'), '--strip',
         *os.environ.get('P8V_ZONEARGS', '').split())
    # the barber and clothing goals: Circle at the shop door opens the store (THAW's store options in
    # P8's in-level CAS menus, pak/CAS_common); leaving it wins the step (p8goals shop_sources)
    tool('p8goals.py', 'shops', os.path.join(zone, 'z_houses.pak.psp'))
    tool('p8goals.py', 'protesters', os.path.join(zone, 'z_houses.pak.psp'))  # the PETA protesters at the dinosaur
    tool('p8goals.py', 'sponsor', os.path.join(zone, 'z_houses.pak.psp'))  # the sponsor step's win poll (no Ghosts on P8)
    if os.environ.get('P8V_DINOAFTER'):  # test: the dino event's node flags (as the success pak's startup sets
        # them) from the first step's start script, which runs after chapter startup applies the story's flags
        tool('p8goals.py', 'zoneappend', os.path.join(zone, 'z_houses.pak.psp'), 'Z_HO_ChangeYourLookWin',
             DINO_EVENT_FLAGS)
    if os.environ.get('P8V_PLAYCUT'):  # test: the first step's start plays this cutscene (p8cut), e.g. HO_LevelEvent_Dino
        tool('p8goals.py', 'zoneappend', os.path.join(zone, 'z_houses.pak.psp'), 'Z_HO_ChangeYourLookWin',
             f'PlayCutscene {{ Name = "cutscenes\\\\{os.environ["P8V_PLAYCUT"]}.cut" unload_anims = 1 reload_anims = 1 '
             'unload_goals = 0 reload_goals = 0 skippable = 1 }')
    if os.environ.get('P8V_PLAYMOVIE'):  # test: the first step's start plays these movies in turn (P8's in-game
        # movie script 0x287fb55a, as P8's story clips), e.g. c\c_mug_th,start\ns_logo
        for m in os.environ['P8V_PLAYMOVIE'].split(','):  # one call each: zoneappend reads \n as a line break
            if m.lower().startswith('t\\'):  # test movies: work/movtest/<name>.pmf -> movies\t
                os.makedirs(os.path.join(U, 'movies', 't'), exist_ok=True)
                shutil.copyfile(os.path.join(R, 'work', 'movtest', m[2:] + '.pmf'), os.path.join(U, 'movies', 't', m[2:] + '.pmf'))
            tool('p8goals.py', 'zoneappend', os.path.join(zone, 'z_houses.pak.psp'), 'Z_HO_ChangeYourLookWin',
                 '0x287fb55a Name = "%s"' % m.replace('\\', '\\\\'))
    if os.environ.get('P8V_CREATE'):  # test: the first step's start creates these nodes (comma list)
        tool('p8goals.py', 'zoneappend', os.path.join(zone, 'z_houses.pak.psp'), 'Z_HO_ChangeYourLookWin',
             r'\n'.join(f'create name = {n}' for n in os.environ['P8V_CREATE'].split(',')))
    if os.environ.get('P8V_DINOVIEW'):  # test: the first step's start puts the skater on THAW's dino IGC spot
        tool('p8goals.py', 'zoneappend', os.path.join(zone, 'z_houses.pak.psp'), 'Z_HO_ChangeYourLookWin',
             'ResetSkaters node_name = ' + os.environ['P8V_DINOVIEW'])
    if os.environ.get('P8V_CAM'):  # test: the first step's start holds a world camera, P8V_CAM=x,y,z,yaw
        # (a yaw-only quat (0, sin(a/2), 0) looks along (-sin a, 0, cos a); checked on the dino head)
        import math
        # optional fifth value: pitch (radians), yaw then pitch about the camera's own x axis
        cx, cy, cz, cyaw, *cp = map(float, os.environ['P8V_CAM'].split(','))
        p = cp[0] if cp else 0.0
        qx, qy, qz = (math.cos(cyaw / 2) * math.sin(p / 2), math.sin(cyaw / 2) * math.cos(p / 2),
                      -math.sin(cyaw / 2) * math.sin(p / 2))
        tool('p8goals.py', 'zoneappend', os.path.join(zone, 'z_houses.pak.psp'), 'Z_HO_ChangeYourLookWin',
             f'PlayIGCCam {{ LockTo = world Pos = ({cx:.2f}, {cy:.2f}, {cz:.2f}) '
             f'Quat = ({qx:.6f}, {qy:.6f}, {qz:.6f}) FOV = 72.0 time = 0 play_hold }}')
    # The door trigger itself is in the mission's collision, which needs a mission scene (not converted
    # yet): for now each goal runs its win script as its goal_start_script (its fail_scene key and
    # value renamed), so the barber and clothing steps pass as soon as they start
    for add, win, n in (('Z_HO_ADDGOAL_ChangeYourLook', 'Z_HO_ChangeYourLookWin', 15),
                        ('Z_HO_ADDGOAL_ChangeYourLook2', 'Z_HO_ChangeYourLookWin2', 30)):
        tool('p8goals.py', 'zonerekey', os.path.join(zone, 'z_houses.pak.psp'), add, 'fail_scene', 'goal_start_script')
        tool('p8goals.py', 'zonerekey', os.path.join(zone, 'z_houses.pak.psp'), add, f'M_ZHOGAPS{n}_Fail_IGC_Scene', win)
if GOALS and os.environ.get('P8V_STORYRUN'):  # test: the story plays itself (p8goals story_run)
    tool('p8goals.py', 'storyrun', qpak, qpab, os.path.join(zone, 'z_houses.pak.psp'))
# zone memory budget (zone_sizes_psp: Size = the zone pak's size)
tool('p8qb.py', 'setdata', qpak, qpab, r'scripts\zone_sizes_psp.qb.psp',
     f"int:1545920={os.path.getsize(os.path.join(zone, 'z_houses.pak.psp'))}")
# no sky for now (Houses names Center_Sky; untested with Hollywood since the load crashes were fixed)
tool('p8qb.py', 'setfield', qpak, qpab, r'game\levels.qb.psp', '0xdb6cc528', 'sky', 'name:no_sky')
if os.environ.get('P8V_AUTO'):
    tool('p8qb.py', 'setkey', qpak, qpab, r'game\startup.qb.psp', 'default_system_startup', 'Load_Z_MainMenu', '0x16a10a9a')
if not os.environ.get('P8V_P8UI'):
    # P8's PSP front end (tab bar, its own pause) runs while the global 0x44689337 is 1; at 0 the menus
    # are the THAW-style label menus (create_main_menu's label path, THAW's create_pause_menu).
    # change_gamemode_career/classic set it back to 1: they now set a dummy instead.
    helpers = r'menu\gamemenu_helpers.qb.psp'
    tool('p8qb.py', 'setglobal', qpak, qpab, helpers, '0x44689337', '0')
    for s in ('change_gamemode_career', 'change_gamemode_classic'):
        tool('p8qb.py', 'rekey', qpak, qpab, helpers, s, '0x44689337', 'thx_p8_ui_unused')
    # THAW's Start New Story path (story_options_change_level, Zone_LoadLastPlayed) loads THAW's story
    # select, then z_ho; P8 has neither: both go to the Houses slot's load script (Hollywood)
    tool('p8qb.py', 'rekey', qpak, qpab, r'menu\skateshop.qb.psp', 'story_options_change_level', 'load_z_ho', '0x16a10a9a')
    # THAW's pause menu calls P8's SET/GOTO RESTART adder (0x1523a6fe), which makes P8 tab-UI items
    # (0x59486bf2) inside the label menu; moving the cursor past them morphs an element that is not
    # there (DoScreenElementMorph, module 0x24074): not called
    tool('p8qb.py', 'rekey', qpak, qpab, r'menu\gamemenu_pause.qb.psp', 'create_pause_menu', '0x1523a6fe', 'NullScript')
    # THAW's level select (Free Skate) loads its pak into the UnloadableAnim heap, which P8 PSP has not
    # set up in the front end (crash, module 0x82cb0); P8's own loads it without a heap there
    tool('p8qb.py', 'rekey', qpak, qpab, r'menu\gamemenu_levelselect.qb.psp', 'launch_level_select_menu', 'heap', 'thx_unused')
    tool('p8qb.py', 'rekey', qpak, qpab, r'game\zone_management.qb.psp', 'Zone_LoadLastPlayed', 'load_Z_storyselect', '0x16a10a9a')
    # It also sets CAREER_ONETIMEINTRO (P8 plays its own opening with it), and while that is set
    # Zone_SetAppropriateMap builds the zone map from SkateZonesStoryOpening (THAW's Z_HO_Net and
    # Z_STORYSELECT), which lacks Z_Houses: CreateZoneMap crashes (module 0x1878cc; intermittent with
    # Houses' zone scripts, every time with THAW's). The opening uses SkateZones too.
    tool('p8qb.py', 'rekey', qpak, qpab, r'game\zone_management.qb.psp', 'Zone_SetAppropriateMap', 'SkateZonesStoryOpening', 'SkateZones')
    if GOALS:
        # CAREER_ONETIMEINTRO belongs to THAW's story-select opening, which P8 lacks. While it is set,
        # load_level loads the zone as freeskate2p (THAW's Z_HO_Goals then adds only multiplayer goals)
        # and game_progress_process_status returns at once (no story atom ever runs). The story start
        # sets CAREER_STARTED twice instead: the level loads as career and THAW's progression starts.
        tool('p8qb.py', 'rekey', qpak, qpab, r'menu\skateshop.qb.psp', 'story_options_change_level', 'CAREER_ONETIMEINTRO', 'CAREER_STARTED')
        # P8's career opening clip (c\C_s_int, played once when the Houses slot first loads; script
        # 0x5ea3b6b7) runs out of memory with THAW's goals loaded and crashes the movie player: not played
        tool('p8qb.py', 'rekey', qpak, qpab, r'game\gameflow.qb.psp', '0x5ea3b6b7', '0x287fb55a', 'NullScript')
    # pause-menu map (THAW's pause_menu_map, kept by P8): the Houses slot's level struct gets Hollywood's
    # level_map, map_offset, map_conversion and map_scale in place of fields it can spare. The two pairs
    # need string fields to hold their data (p8qb copyfield): the sky name (unused, see above) and the
    # ambient track (given back below with addfield).
    for dst, src in (('loading_time', 'level_map'), ('no_sky', 'map_offset'), ('ambient_track', 'map_conversion'),
                     ('num_m_legs', 'map_scale')):
        tool('p8qb.py', 'copyfield', qpak, qpab, r'game\levels.qb.psp', '0xdb6cc528', dst, 'Level_Z_HO', src)
    # the pause screen's level name (GetCurrentLevelName; display only)
    tool('p8qb.py', 'setfield', qpak, qpab, r'game\levels.qb.psp', '0xdb6cc528', 'Name', 'str:Hollywood')
    # Free Skate's level select lists the Houses slot as SUBURBS
    tool('p8qb.py', 'setstr', qpak, qpab, r'menu\gamemenu_levelselect.qb.psp', 'SUBURBS', 'HOLLYWOOD')
    # main menu legend: THAW's capitals (its submenus already say ACCEPT)
    tool('p8qb.py', 'setstr', qpak, qpab, r'menu\mainmenu_strings.qb.psp', chr(92) + 'm0 Accept', chr(92) + 'm0 ACCEPT')
    # THAW's Hollywood sky: Level_Z_HO names TestLevel_Sky, which load_level turns into default_sky
    # (P8 has skies\default_sky); Houses' own sky field holds map_offset now, so the field is new
    tool('p8qb.py', 'addfield', qpak, qpab, r'game\levels.qb.psp', '0xdb6cc528', 'level', 'sky', 'str:Default_sky')
    # the ambience the map data displaced (P8's Houses background loop; THAW's z_ho_bg is not on the disc)
    tool('p8qb.py', 'addfield', qpak, qpab, r'game\levels.qb.psp', '0xdb6cc528', 'Name', 'ambient_track',
         'str:music\\vag\\backgrounds\\z_houses_bg')
    # the arrow sprite is turned a quarter counter-clockwise to fit its slot (p8map.py), and a positive
    # rot_angle turns a sprite counter-clockwise (with heading + 90 the spawn arrow pointed left, with
    # heading + 180 down): rot_angle = heading + 90 becomes heading + 0
    tool('p8qb.py', 'rekey', qpak, qpab, r'menu\gamemenu_pause.qb.psp', 'pause_menu_map', '0x5a', '0x0')
if GOALS:  # P8's goal_load_pak takes THAW's mission prefix/suffix (p8goals.py)
    tool('p8goals.py', 'loadpak', qpak, qpab)
    tool('p8goals.py', 'igcskip', qpak, qpab)  # THAW's in-game cutscenes need its character paks
    # the story's save prompt waits for ingame_save_finished, which P8's own No handler (0xe345fc6b)
    # never sends: THAW's ingame_save_return_to_game does; then the progression goes on (saveprompt)
    tool('p8qb.py', 'rekey', qpak, qpab, r'game\career_scripts.qb.psp', 'game_progress_save_prompt_display', '0xe345fc6b',
         'ingame_save_return_to_game')
    # its Yes handler is P8's tab-UI state script (0x9510a3cb, crash at module 0x334b00): THAW's
    # launch_ingame_menu_save_game_sequence (ingame_confirm_save's own default) instead
    tool('p8qb.py', 'rekey', qpak, qpab, r'game\career_scripts.qb.psp', 'game_progress_save_prompt_display', '0x9510a3cb',
         'launch_ingame_menu_save_game_sequence')
    tool('p8goals.py', 'saveprompt', qpak, qpab)
    tool('p8goals.py', 'savecoim', qpak, qpab, *([str(BIG_HEAPS[0])] if BIG else []))  # room for the save's script pools (see p8goals)
    # after an in-game save P8's back_to_pause_menu opens P8's options menu (0x8075d1aa); THAW returns
    # to the game and broadcasts ingame_save_finished (the story's save prompt waits for it)
    tool('p8qb.py', 'rekey', qpak, qpab, r'menu\memcard.qb.psp', 'back_to_pause_menu', '0x8075d1aa', 'ingame_save_return_to_game')
    tool('p8goals.py', 'cutsceneskip', qpak, qpab)
    tool('p8goals.py', 'nodeflags', qpak, qpab)  # P8 creates only its own 4; THAW's must exist to be set
    tool('p8goals.py', 'storyflags', qpak, qpab)  # THAW's initial Hollywood node flags (the dinosaur building)
    # chapter_info's level-event IGCs name their pak's folder THAW's way (<mission>/<mission>_SUCCESS);
    # the mission paks here are flat (missions/worldzones/<part>/), and LoadPak of a missing file is a
    # null read (FUN_0018ce2c: no handle check): the dino head event crashed on winning Highcombo3
    # the stat challenges (sponsor step): stats.qb's spots name Hollywood Z_HO, but the level structure
    # Hollywood runs under is Houses' (level = Z_Houses), so StatsManager_GetGroupNumFromLevel found none
    tool('p8qb.py', 'setdata', qpak, qpab, r'menu\stats.qb.psp', 'Z_HO=Z_Houses')
    if os.environ.get('P8V_STATTEST'):  # test: 'Land a 2,000 point combo' becomes 100 (one air trick)
        tool('p8qb.py', 'setdata', qpak, qpab, r'menu\stats.qb.psp', 'int:2000=100')
    # its poster draws THAW sprites; a sprite whose texture P8 lacks is a null read (CreateScreenElement)
    for tex in ('heart', 'spazzburst', 'new_bg_2'):
        tool('p8qb.py', 'rekeyall', qpak, qpab, r'menu\gamemenu_stats.qb.psp', tex, 'white2')
    tool('p8goals.py', 'igcpaks', qpak, qpab)  # THAW's IGC asset paks are not on P8's disc
    tool('p8goals.py', 'scriptstr', qpak, qpab, r'menu\chapter_info.qb.psp', 'chapter_info_register_structure',
         *[f'missions/worldzones/{m}/{m}_SUCCESS=missions/worldzones/{m}_SUCCESS'
           for m in ('M_ZHOHIGHCOMBO3', 'M_ZHOGAPS13', 'M_ZHOChinese')])
    if os.environ.get('P8V_TESTGOAL'):  # test aid: the story opens with this goal instead of the barber
        tool('p8qb.py', 'rekeyall', qpak, qpab, r'menu\chapter_info.qb.psp', 'z_ho_goal_gaps15', os.environ['P8V_TESTGOAL'])  # THAW's story cutscenes are not on P8's disc
tool('p8qb.py', 'compact', qpak, qpab)  # drop the old copies of moved files
tool('hed.py', 'replace', HED, WAD, r'\pak\qb.pab.psp', qpab, '--sectors')
tool('hed.py', 'replace', HED, WAD, r'\pak\qb.pak.psp', qpak, '--sectors')
for f in ('z_houses.pak.psp', 'z_houses.psp_level'):
    tool('hed.py', 'replace', HED, WAD, rf'\worlds\worldzones\z_houses\{f}', os.path.join(zone, f), '--sectors')

# THAW's Hollywood mission paks (node arrays and scripts), flat as P8 names them: p8goals.py missions
if GOALS:
    mo = os.path.join(W, 'missions_out')
    ms = [m for m in os.listdir(os.path.join(R, 'extracted', 'thaw_ps2_data', 'missions', 'worldzones')) if m.lower().startswith('m_zho')]
    if not os.path.isdir(mo):
        tool('hed.py', 'extract', os.path.join(W, 'datap.hed.orig'), os.path.join(W, 'datap.wad.orig'), os.path.join(W, 'missions'),
             '--sectors', '--match', 'm_alc_classic_tier0.psp_level')
        tool('p8goals.py', 'missions', os.path.join(R, 'extracted', 'thaw_ps2_data'), mo,
             os.path.join(W, 'missions', 'missions', 'worldzones', 'm_alc_classic_tier0', 'm_alc_classic_tier0.psp_level'), *ms)
    # the dino level event's state change sits in its IGC's shot script (M_ZHOHIGHCOMBO3_SUCCESS_Shot2:
    # BEFORE 0, AFTER 1, BLDG_AFTER 1) and in the end script of the cutscene after it (cutscenemenu's
    # HO_LevelEvent_Dino_end: AFTER 1, HEAD 1 -- the fallen head on the street --, BLDG_AFTER 1); both are
    # skipped, so the success pak's startup (which only loaded the scene's anims) sets the net state
    tool('p8goals.py', 'zonescript', os.path.join(mo, 'missions', 'worldzones', 'm_zhohighcombo3_success',
                                                  'm_zhohighcombo3_success.pak.psp'), 'M_ZHOHIGHCOMBO3_Success_startup',
         DINO_EVENT_FLAGS)
    for root, _, files in os.walk(os.path.join(mo, 'missions')):
        for f in files:
            tool('hed.py', 'add', HED, WAD, B + os.path.relpath(os.path.join(root, f), mo), os.path.join(root, f), '--sectors')

# Main menu, as in the Remix build: P8's own menu logic, THAW's look. P8's z_mainmenu level is one card
# behind the menu; it gets the alley render (work/backdrops/mainmenu.png, casbackdrop.py from THAW's menu
# camera), and the menu bar's title art gets THAW's default logo (p8menubg.py). Loading THAW's whole
# z_mainmenu zone instead fails: its scripts load Z_StorySelect, which P8 does not have (docs/LOG.md).
mm = os.path.join(W, 'mm_alley')
os.makedirs(mm, exist_ok=True)
mm0 = os.path.join(W, r'mm\worlds\worldzones\z_mainmenu')
tool('hed.py', 'extract', os.path.join(W, 'datap.hed.orig'), os.path.join(W, 'datap.wad.orig'), os.path.join(W, 'mm'),
     '--sectors', '--match', r'worldzones\z_mainmenu\z_mainmenu.')
tool('p8menubg.py', os.path.join(mm0, 'z_mainmenu.psp_level'), os.environ.get('P8V_MMBG', os.path.join(R, 'work', 'backdrops', 'mainmenu.png')),
     os.path.join(mm, 'z_mainmenu.psp_level'), '4')
tool('p8menubg.py', '--pak', os.path.join(mm0, 'z_mainmenu.pak.psp'), os.path.join(mm, 'z_mainmenu.pak.psp'),
     os.path.join(R, r'work\THAW_logo_default.png'))
if not os.environ.get('P8V_P8UI'):  # THAW's own main menu items (create_base_main_menu from THAW PS2)
    tool('p8menubg.py', '--scripts', os.path.join(mm, 'z_mainmenu.pak.psp'), os.path.join(mm, 'z_mainmenu.pak.psp'),
         os.path.join(R, r'extracted\thaw_ps2_data\worlds\worldzones\z_mainmenu\z_mainmenu.pak.ps2'),
         os.environ.get('P8V_THAWMM', 'create_base_main_menu'))
    # Classic's first start asks for initials (while they are still the default, 0x3bfd8eb7) on THAW's
    # keyboard, which takes no input on P8: the default never matches, the keyboard is skipped
    tool('p8goals.py', 'zonerekey', os.path.join(mm, 'z_mainmenu.pak.psp'), 'gamemode_options_menu_exit', '0x3bfd8eb7', 'thx_never')
if not os.environ.get('P8V_NOINTRO') and not os.environ.get('P8V_EBOOTINTRO'):
    # the intro (startup_loading_screen's PSP list) once, when the main menu first loads after boot: P8's
    # in-game movie script 0x287fb55a, which plays movies on the PSP from a loaded zone (ISOs H-J)
    tool('p8goals.py', 'zoneappend', os.path.join(mm, 'z_mainmenu.pak.psp'), 'z_mainmenu_setup',
         r'if not IsTrue thx_intro_done\nchange thx_intro_done = 1\n' +
         # THAW's own order: Activision, then its intro (which opens with the Neversoft logo) as one movie
         # (split in two, P8's ns_logo / g_intro, it hitched between them); P8's Page 44 and Shaba left out
         ''.join(r'0x287fb55a Name = "start\\%s"\n' % m for m in ('atvilogo', 'g_intro')) +
         'endif')
for f in ('z_mainmenu.pak.psp', 'z_mainmenu.psp_level'):
    tool('hed.py', 'replace', HED, WAD, rf'\worlds\worldzones\z_mainmenu\{f}', os.path.join(mm, f), '--sectors')

# THAW HUD: P8 already has THAW's banner, special bar and colours; the balance meter and arrow are swapped
hud = os.path.join(W, 'hud')
tool('hed.py', 'extract', os.path.join(W, 'datap.hed.orig'), os.path.join(W, 'datap.wad.orig'), os.path.join(hud, 'orig'),
     '--sectors', '--match', r'worlds\global\global.pa')
g = os.path.join(hud, 'orig', 'worlds', 'global')
tool('p8hud.py', os.path.join(R, 'THAW CLEAN', 'Game'), os.path.join(g, 'global.pak.psp'), os.path.join(g, 'global.pab.psp'),
     os.path.join(hud, 'out'))
# pause-menu map sprites: ho_level_map and Bike_arrow in two unused global.pak slots, as in Remix
tool('p8map.py', os.path.join(R, 'THAW CLEAN', 'Game'), os.path.join(g, 'global.pak.psp'), os.path.join(hud, 'out', 'global.pab.psp'),
     os.path.join(hud, 'out'))
if not os.environ.get('P8V_NOHUD'):
    for f in ('global.pab.psp', 'global.pak.psp'):
        tool('hed.py', 'replace', HED, WAD, rf'\worlds\global\{f}', os.path.join(hud, 'out', f), '--sectors')

# Free Skate's level select: THAW's Hollywood poster for the Houses slot (p8lsel.py)
lsel = os.path.join(W, 'lsel')
tool('hed.py', 'extract', os.path.join(W, 'datap.hed.orig'), os.path.join(W, 'datap.wad.orig'), lsel,
     '--sectors', '--match', r'pak\levelselect\levelselect.pak')
tool('p8lsel.py', os.path.join(R, 'THAW CLEAN', 'Game'), os.path.join(lsel, 'pak', 'levelselect', 'levelselect.pak.psp'),
     os.path.join(lsel, 'levelselect.pak.psp'))
tool('hed.py', 'replace', HED, WAD, r'\pak\levelselect\levelselect.pak.psp', os.path.join(lsel, 'levelselect.pak.psp'), '--sectors')

# THAW Remix look: loading screens, boot title and save/XMB icons (p8screens.py --vanilla --logo)
scr = os.path.join(W, 'screens')
tool('p8screens.py', os.path.join(R, 'THAW CLEAN', 'Game'), scr, '--vanilla', '--logo',
     os.path.join(R, 'work', 'THAW_American_Wasteland_Remix.png'))
for root, _, files in os.walk(os.path.join(scr, 'images')):
    for f in files:
        rel = os.path.relpath(os.path.join(root, f), scr)
        tool('hed.py', 'replace', HED, WAD, B + rel, os.path.join(root, f), '--sectors')
for f in ('ICON0.PNG', 'PIC1.PNG'):
    pristine(os.path.join(T, f), os.path.join(W, f + '.orig'))
    shutil.copyfile(os.path.join(scr, 'PSP_GAME', f), os.path.join(T, f))
# P8's XMB music would play behind the THAW Remix icon; kept aside, as in the Remix build
snd = os.path.join(T, 'SND0.AT3')
if os.path.exists(snd):
    shutil.move(snd, os.path.join(W, 'SND0.AT3.orig'))

# THAW intro movies over P8's (pmfmux.py --template <P8 atvilogo.pmf> --crop 640:360:0:60 -> work/p8mod/movies/start);
# g_intro is THAW's whole intro.bik (the menu script plays only atvilogo and g_intro); ns_logo (its first
# 11.5 s) only matters to the old P8V_EBOOTINTRO path
mov = os.path.join(U, 'movies', 'start')
for f in ('atvilogo.pmf', 'ns_logo.pmf', 'g_intro.pmf'):
    pristine(os.path.join(mov, f), os.path.join(W, f + '.orig'))
    shutil.copyfile(os.path.join(R, r'work\p8mod\movies\start', f), os.path.join(mov, f))
print('done')
