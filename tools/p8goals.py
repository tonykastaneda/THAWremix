"""THAW's story goals on vanilla Project 8 PSP.

  p8goals.py loadpak <qb.pak.psp> <qb.pab.psp>
      P8's goal_load_pak takes THAW's prefix/suffix (see patch_goal_load_pak)
  p8goals.py igcskip <qb.pak.psp> <qb.pab.psp>
      in-game cutscenes skipped (see skip_igc)
  p8goals.py nodeflags <qb.pak.psp> <qb.pab.psp>
      THAW's node flags created at boot (see node_flags)
  p8goals.py storyflags <qb.pak.psp> <qb.pab.psp>
      the story's initial node flags applied on a menu-started story too (see story_flags)
  p8goals.py heaps <qb.pak.psp> <qb.pab.psp> <COIM> <PedParts> <AnimHeap>
      bigger ped heaps for the PSP-2000/3000 build (see heaps)
  p8goals.py missions <THAW PS2 data dir> <outdir> <empty .psp_level> <prefix> [<prefix> ...]
      THAW's mission paks (missions\\worldzones\\<m>\\<m>_<part>\\<m>_<part>.pak.ps2) as P8 mission paks,
      each with an empty scene: on PSP, P8's goal_load_pak also loads <name>.psp_level (a missing
      one stops the game in the level loader, module 0x97b94); P8's classic missions carry a
      72-byte empty one (e.g. m_alc_classic_tier0.psp_level)

P8 kept THAW's goal machinery (AddGoal_Gaps and the other templates, goal_utilities), but its own
goals load one flat mission pak, missions\\worldzones\\<name>\\<name>.pak, named by pak_short_name.
THAW's goals pass pak_info { prefix = "M_ZHOGAPS31" start gameplay } and goal_utilities still hands
goal_load_pak prefix and suffix (start, gameplay, success, fail); P8's goal_load_pak then builds a
path from a missing pak_short_name and LoadPak gets no name (a null file, module 0xf480).
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import p8qb  # noqa: E402
import p8zone  # noqa: E402
import pak  # noqa: E402
import qb  # noqa: E402

NAME, EQ, NL, STRING, IF, NOT, ENDIF, ARG = 0x16, 0x07, 0x01, 0x1B, 0x47, 0x39, 0x28, 0x2D


def name(n):
    return bytes([NAME]) + struct.pack('<I', pak.qbkey(n))


def guard_pak_short_name():
    """if not GotParam pak_short_name / FormatText TextName = pak_short_name "%p_%s" p = <> prefix
    s = <> suffix / endif  (THAW's own goal_load_pak names the pak that way; an if's u16 is the
    distance to its endif)."""
    fmt = b'%p_%s\0'
    body = (bytes([NOT]) + name('GotParam') + name('pak_short_name') + bytes([NL]) +
            name('FormatText') + name('TextName') + bytes([EQ]) + name('pak_short_name') +
            bytes([STRING]) + struct.pack('<I', len(fmt)) + fmt +
            name('p') + bytes([EQ, ARG]) + name('prefix') + name('s') + bytes([EQ, ARG]) + name('suffix') + bytes([NL]))
    return bytes([IF]) + struct.pack('<H', 3 + len(body)) + body + bytes([ENDIF, NL])


def patch_goal_load_pak(pakp, pabp):
    """The guard goes first in goal_load_pak, so prefix/suffix callers get pak_short_name
    <prefix>_<suffix>: their paks are missions\\worldzones\\<prefix>_<suffix>\\<prefix>_<suffix>.pak."""
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(bytes(p))
    e = next(e for e in ents if e['name'].lower().endswith('goal_utilities.qb.psp'))
    start = e['offset'] - len(p)
    d = bytes(b[start:start + e['size']])
    k = pak.qbkey('goal_load_pak')
    _, items = p8qb.pointer_sites(d)
    _, _, _, v = next(i for i in items if i[2] == k and i[1] == 7)
    usz, csz = struct.unpack_from('<2I', d, v + 4)
    code = p8qb.body(d, v + 12, usz, csz)
    assert code[0] == NL
    code = code[:1] + guard_pak_short_name() + code[1:]
    new_d = p8qb.swap_script(d, k, d[v:v + 4] + struct.pack('<2I', len(code), len(code)) + code)
    b += bytes(-len(b) % 16)
    pos = len(p) + len(b)
    b += new_d
    struct.pack_into('<II', p, e['entry_pos'] + 4, pos - e['entry_pos'], len(new_d))
    open(pakp, 'wb').write(p)
    open(pabp, 'wb').write(b)
    print(f'goal_load_pak: pak_short_name from prefix/suffix when not given ({len(code)} bytes)')


def script_code(d, key):
    _, items = p8qb.pointer_sites(d)
    _, _, _, v = next(i for i in items if i[2] == key and i[1] == 7)
    usz, csz = struct.unpack_from('<2I', d, v + 4)
    return v, p8qb.body(d, v + 12, usz, csz)


def edit_script(pakp, pabp, fname, script, fn):
    """fn(code) -> new code for one script of the pack; the file moves to the end of the .pab."""
    p, b = bytearray(open(pakp, 'rb').read()), bytearray(open(pabp, 'rb').read())
    ents, _ = pak.read_entries(bytes(p))
    e = next(e for e in ents if e['name'].lower().endswith(fname.lower()))
    start = e['offset'] - len(p)
    d = bytes(b[start:start + e['size']])
    k = pak.qbkey(script)
    v, code = script_code(d, k)
    code = fn(code)
    new_d = p8qb.swap_script(d, k, d[v:v + 4] + struct.pack('<2I', len(code), len(code)) + code)
    b += bytes(-len(b) % 16)
    pos = len(p) + len(b)
    b += new_d
    struct.pack_into('<II', p, e['entry_pos'] + 4, pos - e['entry_pos'], len(new_d))
    open(pakp, 'wb').write(p)
    open(pabp, 'wb').write(b)
    return code


def skip_igc(code):
    """igc_player_run without the scene: its parameter defaults, then start_script and end_script
    (goals hang setup on them), igc_playing = 0 and the igc_scene_finished broadcast, as at its end.
    THAW's in-game cutscenes need THAW's character paks (Pak/IGC/IGC_Mindy, ...), which P8 lacks."""
    import qb2
    toks = list(qb2.tokens(code))
    end_if = next(o for o, t, pl in toks if t == NAME and pl == struct.pack('<I', pak.qbkey('end_script')))
    if_at = max(o for o, t, pl in toks if t == IF and o < end_if)
    endif_at = if_at + struct.unpack_from('<H', code, if_at + 1)[0]
    end_block = code[if_at:endif_at + 2]  # if ... endif, newline
    start_block = end_block.replace(struct.pack('<I', pak.qbkey('end_script')), struct.pack('<I', pak.qbkey('start_script'))).replace(
        struct.pack('<I', pak.qbkey('end_script_params')), struct.pack('<I', pak.qbkey('start_script_params')))
    tail = code[next(o for o, t, pl in toks if t == NAME and pl == struct.pack('<I', pak.qbkey('change'))
                     and o > endif_at and code[o + 6:o + 10] == struct.pack('<I', pak.qbkey('igc_playing'))):]
    head = code[:code.index(bytes([0x04])) + 2]  # the { defaults } block and its newline
    return head + start_block + end_block + tail


def skip_cutscene(code):
    """game_progress_process_cutscene up to its PlayCutscene call (unpausegame, music, the intro
    restart node), then SpawnScriptLater game_progress_process_status params = { wait_time = 1 } in
    place of the scene: PlayCutscene's exitScript does that once the scene ends (the atom counts as
    done when no cutscene plays; its next UpdateAtoms must come after the atom has started, and
    while the game is paused spawned scripts wait). THAW's story cutscenes (cutscenes/HO_2.cut, ...)
    are not on P8's disc."""
    import qb2
    at = next(o for o, t, pl in qb2.tokens(code) if t == NAME and pl == struct.pack('<I', pak.qbkey('PlayCutscene')))
    body = (name('SpawnScriptLater') + name('game_progress_process_status') + name('params') + bytes([EQ, 0x03]) +
            name('wait_time') + bytes([EQ, 0x17]) + struct.pack('<i', 1) + bytes([0x04, NL, 0x24]))
    return code[:at] + body


def spawn_progress(code):
    """The script, then SpawnScriptLater game_progress_process_status params = { wait_time = 1 } at
    its end: game_progress_save_prompt ends its atom, and without another UpdateAtoms the next one
    (the caveman lesson) never starts."""
    assert code[-1] == 0x24
    return code[:-1] + (name('SpawnScriptLater') + name('game_progress_process_status') + name('params') +
                        bytes([EQ, 0x03]) + name('wait_time') + bytes([EQ, 0x17]) + struct.pack('<i', 1) +
                        bytes([0x04, NL, 0x24]))


def insert_code(code, at, new):
    """Bytecode with new inserted at offset at: every if (0x47), else (0x48) or case jump (0x49) that
    starts before at and jumps past it grows by len(new) (their u16 is the distance to the target).
    new is padded to a multiple of 4 with newlines: inline structs (0x4A) further on are aligned."""
    import qb2
    new = new + bytes([NL]) * (-len(new) % 4)
    code = bytearray(code)
    for o, t, pl in qb2.tokens(bytes(code)):
        if t in (IF, 0x48, 0x49) and o < at < o + struct.unpack('<H', pl)[0] + 1:
            struct.pack_into('<H', code, o + 1, struct.unpack('<H', pl)[0] + len(new))
    return bytes(code[:at]) + new + bytes(code[at:])


def call_line(func, **params):
    """<func> name = <int> ... newline"""
    out = name(func)
    for k, v in params.items():
        out += name(k) + bytes([EQ, 0x17]) + struct.pack('<i', v)
    return out + bytes([NL])


COIM_SIZE = 652288  # Hollywood's COIM heap, measured at the pause menu (all of it free there)


def int_once(old, new):
    """edit_script fn: the one integer literal old -> new."""
    def edit(code):
        o, n = bytes([0x17]) + struct.pack('<i', old), bytes([0x17]) + struct.pack('<i', new)
        if code.count(o) != 1:
            raise SystemExit(f'{old}: {code.count(o)} integer literals, not 1')
        return code.replace(o, n)
    return edit


def heaps(pakp, pabp, coim, pedparts, anim):
    """Bigger ped heaps for the PSP-2000/3000 build (MEMSIZE = 1 in PARAM.SFO: P8 sizes its main
    region from sceKernelMaxFreeMemSize, so it grows by itself; these three are script numbers):
    the COIM heap (coim.qb's global 0xcfae4518), Houses' PedParts heap (load_level) and the animation
    heap (load_permanent_assets' InitAnimSystem AnimHeapSize)."""
    p8qb.setglobal(pakp, pabp, 'game' + chr(92) + 'coim.qb.psp', '0xcfae4518', str(coim))
    edit_script(pakp, pabp, 'game' + chr(92) + 'levels.qb.psp', 'load_level', int_once(401472, pedparts))
    edit_script(pakp, pabp, 'game' + chr(92) + 'startup.qb.psp', 'load_permanent_assets', int_once(131072, anim))
    print(f'heaps: COIM {coim}, PedParts (Houses) {pedparts}, AnimHeap {anim}')


def node_flags(pakp, pabp):
    """P8's create_node_flags (nodeflags.qb) creates only its own 4 node flags; THAW's (291 in
    game_progress_set_initial_story_mode_nodeflags, among them the 30 Hollywood's nodes are gated on:
    DINO_BEFORE, TOWERWIRES, DT_EVENT, ...) never existed, so ChangeNodeFlag on them did nothing and
    every piece and rail on one stayed hidden (the dinosaur building). They are created there too."""
    import qb2
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'p8v', 'qbdump',
                            'scripts_game_menu_chapter_info.qb.psp.txt'), encoding='latin-1').read()
    flags = re.findall(r'\{ (NODEFLAG_\w+) \d \}', src.split('=== game_progress_set_non_story_mode_nodeflags')[0])
    lines = b''.join(name('CreateNodeFlag') + name(f) + bytes([NL]) for f in dict.fromkeys(flags))

    def edit(code):
        at = next(o for o, t, pl in qb2.tokens(code) if t == NAME and pl == struct.pack('<I', pak.qbkey('CreateNodeFlag')))
        return insert_code(code, at, lines)
    edit_script(pakp, pabp, 'nodeflags.qb.psp', 'create_node_flags', edit)
    print(f'create_node_flags: {len(dict.fromkeys(flags))} THAW node flags created')


def story_flags(pakp, pabp):
    """chapter_1_startup applies the story's node flags (CareerFunc SetAppropriateNodeFlags) only
    when the game was autolaunched; a story started from the menu never got THAW's initial Hollywood
    flags (game_progress_set_initial_story_mode_nodeflags: DINO_BEFORE 1, TOWERWIRES 1, ...), so the
    pieces on them stayed hidden (the dinosaur building). The call now runs first, always."""
    import qb2
    line = name('CareerFunc') + name('func') + bytes([EQ]) + name('SetAppropriateNodeFlags') + bytes([NL])

    def edit(code):
        at = next(o for o, t, pl in qb2.tokens(code) if t == NAME and pl == struct.pack('<I', pak.qbkey('ChangeNodeFlag')))
        return insert_code(code, at, line)
    edit_script(pakp, pabp, 'menu' + chr(92) + 'chapter_info.qb.psp', 'chapter_1_startup', edit)
    print('chapter_1_startup: SetAppropriateNodeFlags always')


def coim_around_save(pakp, pabp, coim=COIM_SIZE):
    """Saving pushes temporary script pools (20000 CComponent, 9000 CStruct, 3000 CVector, ~440 KB)
    onto the main heap, which has 422 KB free with THAW's Hollywood and its goals loaded: the last
    pool comes back null and the engine's pool report crashes reading it. The COIM heap (652 KB,
    empty at the pause menu) goes for the save: UnloadAnimsAndCreateMemCardPools calls
    ResizeCOIMHeap newsize = 0 before its in-game PushTemporaryMemCardPools, and
    RemoveMemCardPoolsAndLoadAnims makes it again after its in-game PopTemporaryMemCardPools."""
    import qb2

    def before_first(func, line):
        def edit(code):
            at = next(o for o, t, pl in qb2.tokens(code) if t == NAME and pl == struct.pack('<I', pak.qbkey(func)))
            return insert_code(code, at, line)
        return edit

    def after_first(func, line):
        def edit(code):
            toks = list(qb2.tokens(code))
            i = next(i for i, (o, t, pl) in enumerate(toks) if t == NAME and pl == struct.pack('<I', pak.qbkey(func)))
            at = next(o for o, t, pl in toks[i + 1:] if t == NL) + 1
            return insert_code(code, at, line)
        return edit
    edit_script(pakp, pabp, 'menu' + chr(92) + 'memcard.qb.psp', 'UnloadAnimsAndCreateMemCardPools',
                before_first('PushTemporaryMemCardPools', call_line('ResizeCOIMHeap', newsize=0)))
    edit_script(pakp, pabp, 'menu' + chr(92) + 'memcard.qb.psp', 'RemoveMemCardPoolsAndLoadAnims',
                after_first('PopTemporaryMemCardPools', call_line('ResizeCOIMHeap', newsize=coim)))
    print(f'memcard pools: COIM heap dropped for the save, made again at {coim} bytes after')


def zone_script(pak_path, script, source):
    """One script of a zone pak's <zone>_scripts.qb replaced by compiled source (qbc syntax, the body
    lines only): qbc's 0x23 <name> .. 0x24 less the leading 0x23 and name, stored unpacked."""
    import qbc
    compiled = qbc.compile_source('script ' + script + chr(10) + source + chr(10) + 'endscript' + chr(10))
    kind, body = compiled[pak.qbkey(script)]
    assert body[0] == 0x23 and body[1] == 0x16, 'unexpected qbc script header'
    code = body[6:]
    ents, blob = p8zone.load_pak(pak_path)
    zone = os.path.basename(pak_path).lower().split('.')[0]
    i, e = next((i, e) for i, e in enumerate(ents) if (e['name'] or '').lower().endswith(chr(92) + zone + '_scripts.qb.psp'))
    d = blob[e['offset']:e['offset'] + e['size']]
    k = pak.qbkey(script)
    v, _ = script_code(d, k)
    d = p8qb.swap_script(d, k, d[v:v + 4] + struct.pack('<2I', len(code), len(code)) + code)
    out = p8zone.write_pak(pak_path, {i: d})  # read the pak before opening it for writing
    open(pak_path, 'wb').write(out)
    print(f'{os.path.basename(pak_path)} {script}: replaced ({len(code)} bytes)')


SHOP_DOOR_RADIUS = 160


def shop_sources():
    """The barber and clothing store steps, in THAW's own scripts (their door triggers live in mission
    collision P8 cannot load, and THAW's shop UI is not in P8): the goal's start script spawns a poll on
    the skater; within SHOP_DOOR_RADIUS of the shop door (THAW's *_Ext restart node) it shows a prompt,
    and Circle there (the \m5 glyph) wins the goal. P8 has no in-level Create-A-Skater (no load_cas level:
    pause_launch_level load_cas freezes the screen in change_level), so the look change itself is still
    to do (P8's CAS is a front-end screen)."""
    shops = (('Z_HO_ChangeYourLookWin', 'Z_HO_EnterBarberShop', 'z_ho_goal_gaps15', (-2505.9, 96.2, -2682.9)),
             ('Z_HO_ChangeYourLookWin2', 'Z_HO_EnterClothingShop', 'z_ho_goal_gaps30', (-2565.2, 95.9, -2030.7)))
    out = {}
    for start, poll, goal, door in shops:
        out[start] = f'skater : Obj_SpawnScript {poll}'
        out[poll] = f'''<hw_near> = 0
while
if not GoalManager_GoalIsActive Name = {goal}
kill_panel_message_if_it_exists id = hw_shop_hint
break
endif
Obj_GetPosition
<hw_d> = (<Pos> - ({door[0]}, {door[1]}, {door[2]}))
if ((<hw_d> . <hw_d>) < {SHOP_DOOR_RADIUS ** 2})
if (<hw_near> = 0)
create_panel_message id = hw_shop_hint text = 'Press \\m5 to go in' time = 100000
endif
<hw_near> = 1
if Held Circle
kill_panel_message_if_it_exists id = hw_shop_hint
GoalManager_WinGoal Name = {goal}
break
endif
else
if (<hw_near> = 1)
kill_panel_message_if_it_exists id = hw_shop_hint
endif
<hw_near> = 0
endif
wait 1 gameframe
repeat'''
    return out


def zone_rekey(pak_path, script, old, new):
    """One checksum swapped for another in one script of a zone pak's <zone>_scripts.qb (in place)."""
    ents, blob = p8zone.load_pak(pak_path)
    zone = os.path.basename(pak_path).lower().split('.')[0]
    i, e = next((i, e) for i, e in enumerate(ents) if (e['name'] or '').lower().endswith(chr(92) + zone + '_scripts.qb.psp'))
    d = blob[e['offset']:e['offset'] + e['size']]
    k = pak.qbkey(script)
    v, code = script_code(d, k)
    o, n = struct.pack('<I', p8qb.key(old)), struct.pack('<I', p8qb.key(new))
    if not code.count(o):
        raise SystemExit(f'{old} not in {script}')
    code = code.replace(o, n)
    d = p8qb.swap_script(d, k, d[v:v + 4] + struct.pack('<2I', len(code), len(code)) + code)
    out = p8zone.write_pak(pak_path, {i: d})
    open(pak_path, 'wb').write(out)
    print(f'{os.path.basename(pak_path)} {script}: {old} -> {new}')


# THAW mission pak entries kept: node array, scripts and peds (THAW's QB, which P8 reads as is).
# Its collision (trigger boxes) crashes without scene geometry behind it (module 0x18e330).
# Models, textures and animations are PS2 formats (not converted yet). Their peds' profiles
# (mission-local M_Ped_* and the like, built from THAW parts) become Ped_HippieF01 (Mindy) or Ped_DVGuy,
# which this zone can draw; otherwise ped creation fails ('Ped has no skeleton!', a crash).
KEEP = {'.qb', '.nqb', '.sqb'}


MISSION_NO_SPAWN = ('Vehicle', 'GameObject')


def missions(thaw_data, out, empty_level, prefixes):
    level = open(empty_level, 'rb').read()
    if not qb.NAMES:  # key names, to find 'profile' fields (extracted/dbg, as qb.py's own main)
        qb.load_names(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'extracted', 'dbg'))
    root = os.path.join(thaw_data, 'missions', 'worldzones')
    made = []
    for m in prefixes:
        m = m.lower()
        for part in sorted(os.listdir(os.path.join(root, m))):
            src = os.path.join(root, m, part, f'{part}.pak.ps2')
            if not os.path.exists(src):
                continue
            ents, blob = p8zone.load_pak(src)
            drop = {i for i, e in enumerate(ents) if pak.EXT.get(e['type']) not in KEEP}
            payloads = {}
            for i, e in enumerate(ents):  # peds: profiles P8 can draw here (see p8zone.PROFILES)
                if i in drop or not (e['name'] or '').lower().endswith('.qb.ps2'):
                    continue
                d0 = blob[e['offset']:e['offset'] + e['size']]
                profs = set(re.findall(r"'profile', '\$([^']+)'", repr(qb.QB(d0).items())))
                known = {k.lower(): v for k, v in p8zone.PROFILES.items()}
                for pr in profs:
                    to = known.get(pr.lower()) or ('Ped_HippieF_FullBody04' if 'mindy' in pr.lower() else 'Ped_DVGuy')
                    d0 = d0.replace(struct.pack('<I', p8qb.key(pr)), struct.pack('<I', pak.qbkey(to)))
                if pak.EXT.get(e['type']) == '.nqb':
                    # THAW vehicles and GameObjects name models P8 does not have (the dropped .mdl
                    # entries): created, they crash scene setup (Whofleck's limo, module 0xae670)
                    try:
                        d1, n_off = p8zone.unspawn(d0, part, MISSION_NO_SPAWN)
                    except KeyError:
                        d1, n_off = d0, 0
                    if n_off:
                        d0, profs = d1, profs or {'unspawned'}
                        print(f'{part}: {n_off} vehicle/GameObject CreatedAtStart flags off')
                if profs:
                    payloads[i] = d0
            d = bytearray(p8zone.write_pak(src, payloads, drop))
            for e in pak.read_entries(bytes(d))[0]:
                if e['flags'] & 0x20:  # name: .ps2 -> .psp (keys stay THAW's)
                    at = e['entry_pos'] + 0x20
                    n = d[at:at + 160].split(b'\0', 1)[0].decode('latin-1')
                    if n.lower().endswith('.ps2'):
                        n = n[:-4] + '.psp'
                        d[at:at + 160] = n.encode('latin-1').ljust(160, b'\0')
            rel = os.path.join('missions', 'worldzones', part, f'{part}.pak.psp')
            os.makedirs(os.path.dirname(os.path.join(out, rel)), exist_ok=True)
            open(os.path.join(out, rel), 'wb').write(d)
            open(os.path.join(out, rel[:-len('.pak.psp')] + '.psp_level'), 'wb').write(level)
            made.append(rel)
            print(f'{rel}: {len(ents) - len(drop)} of {len(ents)} entries')
    return made


def main():
    if sys.argv[1] == 'loadpak':
        patch_goal_load_pak(*sys.argv[2:4])
    elif sys.argv[1] == 'igcskip':
        c = edit_script(sys.argv[2], sys.argv[3], 'igc_player.qb.psp', 'igc_player_run', skip_igc)
        print(f'igc_player_run: scene skipped ({len(c)} bytes)')
    elif sys.argv[1] == 'cutsceneskip':
        c = edit_script(sys.argv[2], sys.argv[3], 'career_scripts.qb.psp', 'game_progress_process_cutscene', skip_cutscene)
        print(f'game_progress_process_cutscene: cutscene skipped ({len(c)} bytes)')
    elif sys.argv[1] == 'saveprompt':
        c = edit_script(sys.argv[2], sys.argv[3], 'career_scripts.qb.psp', 'game_progress_save_prompt', spawn_progress)
        print(f'game_progress_save_prompt: progression goes on after it ({len(c)} bytes)')
    elif sys.argv[1] == 'rekeynth':  # <qb.pak> <qb.pab> <file> <script> <old> <new> <n (0-based)>
        pk, pb, f, sc, old, new, nth = sys.argv[2:9]

        def nth_only(code):
            o, n_ = struct.pack('<I', p8qb.key(old)), struct.pack('<I', p8qb.key(new))
            at = -1
            for _ in range(int(nth) + 1):
                at = code.index(o, at + 1)
            return code[:at] + n_ + code[at + 4:]
        edit_script(pk, pb, f, sc, nth_only)
        print(f'{f} {sc}: occurrence {nth} of {old} -> {new}')
    elif sys.argv[1] == 'savecoim':  # <qb.pak> <qb.pab> [COIM size]
        coim_around_save(*sys.argv[2:4], *map(int, sys.argv[4:5]))
    elif sys.argv[1] == 'nodeflags':
        node_flags(*sys.argv[2:4])
    elif sys.argv[1] == 'storyflags':
        story_flags(*sys.argv[2:4])
    elif sys.argv[1] == 'pedparts':  # <qb.pak> <qb.pab> <size>: Houses' PedParts heap only
        edit_script(*sys.argv[2:4], 'game' + chr(92) + 'levels.qb.psp', 'load_level', int_once(401472, int(sys.argv[4])))
        print(f'PedParts (Houses) {sys.argv[4]}')
    elif sys.argv[1] == 'heaps':  # <qb.pak> <qb.pab> <COIM> <PedParts> <AnimHeap>
        heaps(*sys.argv[2:4], *map(int, sys.argv[4:7]))
    elif sys.argv[1] == 'shops':  # <zone .pak.psp>
        for name, src in shop_sources().items():
            zone_script(sys.argv[2], name, src)
    elif sys.argv[1] == 'zonerekey':  # <zone .pak.psp> <script> <old> <new>
        zone_rekey(*sys.argv[2:6])
    elif sys.argv[1] == 'missions':
        missions(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])


if __name__ == '__main__':
    main()
