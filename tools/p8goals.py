"""THAW's story goals on vanilla Project 8 PSP.

  p8goals.py loadpak <qb.pak.psp> <qb.pab.psp>
      P8's goal_load_pak takes THAW's prefix/suffix (see patch_goal_load_pak)
  p8goals.py igcskip <qb.pak.psp> <qb.pab.psp>
      in-game cutscenes skipped (see skip_igc)
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
                for pr in profs:
                    to = 'Ped_HippieF01' if 'mindy' in pr.lower() else 'Ped_DVGuy'
                    d0 = d0.replace(struct.pack('<I', p8qb.key(pr)), struct.pack('<I', pak.qbkey(to)))
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
    elif sys.argv[1] == 'zonerekey':  # <zone .pak.psp> <script> <old> <new>
        zone_rekey(*sys.argv[2:6])
    elif sys.argv[1] == 'missions':
        missions(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:])


if __name__ == '__main__':
    main()
