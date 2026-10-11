"""Hollywood story goals on THUG2 Remix's training level (story phase 1).

  hostory.py <THAW install> <work/out dir from thaw2psp build> <Remix data dir> <outdir>

THAW's Hollywood story chain (chapter_info) up to Beverly Hills unlocking, rebuilt on Remix's own
goal templates in the training level's scripts:

  0a Change your look      gaps        the barber: Triangle at the barber shop door opens Remix's
                                       Create-A-Skater; coming back from it wins the goal
  0b Change your clothes   gaps        the same at the clothing store
  1 Learn caveman          counter     reuses training's caveman goal logic (tr_goal_counter7)
  2 Sponsor challenge      high combo  THAW's sponsor challenge is its own system; a combo here
  3 Kickflip over Ben      gaps        any flip trick while near Ben Whofleck
  4 Learn revert           counter     SkaterEnterRevert
  5 Beat the punk's score  high combo  THAW's score battle has an AI opponent; a combo target here
  6-8 Stop the wool protest  high combos of 2,000, 5,000 and 10,000 in 60 s (THAW's values)

Each goal is the child of the one before. Goal peds are the training level's own goal ped nodes
(Remix pros stand in for THAW's characters) moved, with their restart nodes, to THAW's goal
positions. Cutscenes are not converted.

Remix has no shop interiors, so the two shop steps go through the pause menu's own Edit Appearance
path (pause_launch_level level = load_cas): the level is remembered, CAS loads, and its Done or Back
reloads the level. A global set before leaving (hw_shop_pending, defined in chapter_info.qb, which
stays loaded) tells the level's startup that the shop step is done.

Writes tr.qb (node moves on top of the build's), tr_scripts.qb and tr_scripts.pre.
"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import qb2  # noqa: E402
import psplevel  # noqa: E402
import qbscripts  # noqa: E402
import thawscene  # noqa: E402
from pak import open_pak, qbkey  # noqa: E402

AT = np.array([-3020.952880859375, -765.405029296875, -3511.32470703125])  # training P1 restart

# training goal scripts the story master calls; the caveman one is kept, the next seven are reused
CAVEMAN_SLOT = 0x0e0c6119
SLOTS = [0x60bc5cc4, 0xb66ca5a7, 0xde875313, 0xb0ff23f9, 0x9ea0dcb7, 0xa8d92f93, 0x0f3ad4f1]
ALL_SLOTS = [0x60bc5cc4, 0xb66ca5a7, 0xde875313, 0xb0ff23f9, 0x9ea0dcb7, 0xa8d92f93, 0x0f3ad4f1, 0x6e85fb27,
             0xa6fc3e20, 0xe032c22f, 0x5a1a2d92, 0xc558e600, 0x79684830, 0xde171598, 0xf297b3d0, 0x1cdae682,
             0x96e99a4c, 0x08337c2d, 0x7fd73171, 0x98ff6997, 0x19eb529c, 0x5d0d82cd, 0x4a745797, 0x0e0c6119,
             0x558be0b6, 0x1b9efa5c, 0x910aa746, 0xcc2ac5ab, 0x544939d5, 0x84797adf, 0xdc8dd46e, 0xae3ec476,
             0x8fd5f048, 0xfacfd4b3, 0x0b626032, 0x66e63e6a, 0xa8f99fe1]

# Remix ped node (stand-in) -> THAW node it moves to; restart nodes likewise
PLACES = [
    ('TRG_G_COUNTER7_Pro', 'Z_HO_TRG_G_COUNTER_PRO'),
    ('TRG_G_COUNTER7_RestartNode', 'Z_HO_TRG_G_COUNTER_RESTARTNode'),
    ('TRG_G_GAP7_RestartNode', 'Z_HO_TRG_G_GAPS4_RESTARTNode'),  # red ropes lesson, facing the rope
    ('TRG_G_GAP16_Pro', ('Z_HO_TRG_G_Gaps31_RestartNode', (60, 0, 60))),  # Mindy at the skateshop
    ('TRG_G_GAP16_RestartNode', 'Z_HO_TRG_G_Gaps31_RestartNode'),
    # Ben Whofleck: THAW puts him in a limo near the goal's own start node (Mindy gives the goal at
    # the skateshop); his stand-in stands 300 in ahead of that start node (which faces +X), facing the skater
    ('TRG_G_GAP17_Pro', ('Z_HO_TRG_G_Gap2_RestartNode', (300, 0, 0), 1.5708)),
    ('TRG_G_GAP17_RestartNode', 'Z_HO_TRG_G_Gap2_RestartNode'),  # THAW's start, facing +X toward Ben
    ('TRG_G_COUNTER4_Pro', 'Z_HO_TRG_G_COUNTER4_PRO'),  # Duane, Dog and Cello
    ('TRG_G_COUNTER4_RestartNode', 'Z_HO_TRG_G_COUNTER4_RESTARTNode'),
    ('TRG_G_GAP5_Pro', ('Z_HO_TRG_G_Gaps5_RestartNode', (60, 0, 60))),  # the punk
    ('TRG_G_GAP5_RestartNode', 'Z_HO_TRG_G_Gaps5_RestartNode'),
    ('TRG_G_GAP20_Pro', 'Z_HO_TRG_G_HIGHCOMBO_PRO'),  # Mindy at the wool protest
    ('TRG_G_GAP20_RestartNode', ('Z_HO_TRG_G_HIGHCOMBO_RestartNode', (0, 0, 0), -1.5708)),  # THAW's start, rolling
    # the barber and the clothing store clerk stand beside their shop doors, facing the street; the
    # restart nodes are THAW's own spots outside the doors, facing them (-X)
    ('TRG_G_GAP18_Pro', ('Z_HO_TRG_Restart_BarberShop_Ext', (-40, 0, 110), -1.5708)),
    ('TRG_G_GAP18_RestartNode', 'Z_HO_TRG_Restart_BarberShop_Ext'),
    ('TRG_G_GAP19_Pro', ('Z_HO_TRG_Restart_CASShop_Ext', (-40, 0, 110), -1.5708)),
    ('TRG_G_GAP19_RestartNode', 'Z_HO_TRG_Restart_CASShop_Ext'),
]
SHOP_DOOR_RADIUS = int(os.environ.get('HW_SHOP_RADIUS', 160))  # testing aid override;  # inches from a point 50 in ahead of the shop's restart node, toward the door


# ---------------------------------------------------------------- tiny script assembler

def tok_name(n):
    return bytes([qb2.NAME]) + struct.pack('<I', n if isinstance(n, int) else qbkey(n))


def assemble_line(words):
    """One statement. Words: 'name', 'k=v' handled as separate words k, '=', v; ints; 'str' quoted
    with a leading ' ; ':' object call; '<x>' parameter; 'not'."""
    out = bytearray()
    for w in words:
        if isinstance(w, bytes):
            out += w
        elif isinstance(w, int):
            out += bytes([qb2.INT]) + struct.pack('<i', w)
        elif w == '=':
            out.append(qb2.EQ)
        elif w == ':':
            out.append(0x42)
        elif w == 'not':
            out.append(0x39)
        elif w.startswith("'"):
            b = w[1:].encode('latin-1') + b'\0'
            out += bytes([qb2.STRING]) + struct.pack('<I', len(b)) + b
        elif w.startswith('<') and w.endswith('>'):
            out += bytes([0x2D]) + tok_name(w[1:-1])
        else:
            out += tok_name(w)
    return bytes(out) + bytes([qb2.NEWLINE])


def event_counter(prefix, event, goal):
    """<prefix>_start/_listen/_got/_stop: each broadcast `event` (SkaterExitWalking, SkaterEnterRevert,
    ...) counts one for counter goal `goal`. These are events, not exceptions: a spawned script sets
    an event handler and blocks, the way events.qb listens, run on the skater."""
    dbg = (lambda t: [['create_panel_message', 'id', '=', 'hw_dbg2', 'text', '=', "'" + t]]) if os.environ.get('HW_DEBUG') else (lambda t: [])
    return b''.join([
        script(f'{prefix}_start', dbg(prefix + ' start') + [['skater', ':', 'Obj_SpawnScript', f'{prefix}_listen']]),
        script(f'{prefix}_listen', [['SetEventHandler', 'ex', '=', event, 'scr', '=', f'{prefix}_got'], ['block']]),
        script(f'{prefix}_got', dbg(prefix + ' got') + [['GoalManager_GotCounterObject', 'Name', '=', tok_name(goal)]]),
        script(f'{prefix}_stop', [['skater', ':', 'Obj_KillSpawnedScript', 'Name', '=', f'{prefix}_listen']]),
    ])


def combo_watcher(prefix, goal, score):
    """<prefix>_start/_poll/_stop: on the skater, wait for each combo to end and set the goal's
    got_1 flag if the score it landed is at least `score` (a bail lands nothing)."""
    in_combo = ['SkaterCurrentScorePotGreaterThan', 0]
    dbg = (lambda t: [['create_panel_message', 'id', '=', 'hw_dbg7', 'text', '=', "'" + t]]) if os.environ.get('HW_DEBUG') else (lambda t: [])
    return b''.join([
        script(f'{prefix}_start', [['skater', ':', 'Obj_SpawnScript', f'{prefix}_poll']]
                + ([['spawnscript', 'hw_debug_teleport']] if os.environ.get('HW_DEBUG') and os.environ.get('HW_TP_ON_START') else [])),
        script(f'{prefix}_poll', [['<hw_in_combo>', '=', 0],
                                  ['while'],
                                  ['if'] + in_combo,
                                  ['<hw_in_combo>', '=', 1],
                                  ['else'],
                                  ['if', bytes([0x0E]), '<hw_in_combo>', '=', 1, bytes([0x0F])],
                                  ['<hw_in_combo>', '=', 0],
                                  ['wait', 2, 'gameframes'],
                                  ] + dbg('combo landed') + [
                                  ['if', 'SkaterLastScoreLandedGreaterThan', score - 1],
                                  ] + dbg('combo target reached: flag set') + [
                                  ['GoalManager_SetGoalFlag', 'Name', '=', tok_name(goal), 'got_1', 1],
                                  ['endif'],
                                  ['endif'],
                                  ['endif'],
                                  ['wait', 2, 'gameframes'],
                                  ['repeat']]),
        script(f'{prefix}_stop', [['skater', ':', 'Obj_KillSpawnedScript', 'Name', '=', f'{prefix}_poll']]),
    ])


def dot(param, axis):
    """Expression ( <param> . (x, y, z) ) as raw tokens."""
    return (bytes([0x0E, 0x2D]) + tok_name(param) + bytes([0x08, qb2.VEC]) + struct.pack('<3f', *axis)
            + bytes([0x0F]))


def script(name, lines):
    """Lines are statements (see assemble_line) or the control lines ['if', ...condition words],
    ['else'], ['endif'], ['while'], ['repeat']. An if jumps to just past its else or endif; the
    16-bit offset counts from the offset field itself (as compiled scripts do)."""
    body = bytearray([0x23]) + tok_name(name) + bytes([qb2.NEWLINE])
    stack = []
    for l in lines:
        head = l[0] if l and isinstance(l[0], str) else None
        if head == 'if':
            body.append(0x47)
            stack.append(['if', len(body)])
            body += bytes(2) + assemble_line(l[1:])
        elif head == 'else':
            kind, at = stack.pop()
            body.append(0x48)
            else_at = len(body)
            body += bytes(2)
            struct.pack_into('<H', body, at, len(body) - at)
            body.append(qb2.NEWLINE)
            stack.append(['else', else_at])
        elif head == 'endif':
            kind, at = stack.pop()
            body.append(0x28)
            struct.pack_into('<H', body, at, len(body) - at)
            body.append(qb2.NEWLINE)
        elif head == 'while':
            body += bytes([0x20, qb2.NEWLINE])
        elif head == 'repeat':
            # ['repeat'] loops forever; ['repeat', n] n times
            body += bytes([0x21]) + (assemble_line(l[1:]) if len(l) > 1 else bytes([qb2.NEWLINE]))
        else:
            body += assemble_line(l)
    assert not stack, 'unclosed if'
    body.append(0x24)
    return bytes(body) + bytes([qb2.NEWLINE])


def goal_call(func, fields):
    st = ('struct', [(qbkey(k) if k else None, v) for k, v in fields])
    return bytes([qb2.NEWLINE]) + tok_name(func) + qb2.encode_value(st) + bytes([qb2.NEWLINE])


S, I, N = (lambda s: ('str', s)), (lambda i: ('int', i)), (lambda n: ('name', qbkey(n) if isinstance(n, str) else n))
FLAG = lambda n: (None, N(n))  # noqa: E731


def cam_to(pos, yaw):
    """Intro camera: a few yards in front of the ped, looking at it."""
    fwd = np.array([-np.sin(yaw), 0, -np.cos(yaw)])
    cam = pos + fwd * 220 + np.array([0, 70, 0])
    look = pos + np.array([0, 40, 0])
    return ('array', [('struct', [(None, N('virtual_cam')), (qbkey('targetid'), N('world')),
                                  (qbkey('targetOffset'), ('vec', tuple(map(float, look)))),
                                  (qbkey('positionOffset'), ('vec', tuple(map(float, cam)))),
                                  (qbkey('frames'), I(120)), (qbkey('cam_anim_text'), S('')),
                                  (qbkey('skippable'), I(1)), (qbkey('play_hold'), I(1))])])


# Remix's CAS camera (cas_setup_rotating_camera, full body): position and target offsets from the
# skater, turned with the skater's facing
CAS_CAM, CAS_LOOK = np.array([-60.0, 60, 80]), np.array([-40.0, 45, 0])


def rot_y(v, th):
    c, s = np.cos(th), np.sin(th)
    return np.array([v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c])


def cas_view(spot, th):
    return spot + rot_y(CAS_CAM, th), spot + rot_y(CAS_LOOK, th)


def shot_yaws(yaw):
    """Facings tried for each shop: env HW_SHOT_YAWS (offsets from the node's yaw, in degrees)."""
    offs = os.environ.get('HW_SHOT_YAWS', '0 180 90 270').split()
    return [yaw + np.radians(float(o)) for o in offs]


# ---------------------------------------------------------------- main

def main():
    install, outdir_build, data, out = sys.argv[1:5]
    os.makedirs(out, exist_ok=True)

    # THAW node positions, shifted the way the level was
    entries, blob = open_pak(os.path.join(install, 'data', 'worlds', 'worldzones', 'z_ho', 'z_ho.pak.wpc'))
    qbe = next(e for e in entries if (e['name'] or '').lower().endswith('\\z_ho.qb.wpc'))
    tmp = os.path.join(os.environ.get('TEMP', '.'), 'z_ho_nodes.qb')
    open(tmp, 'wb').write(blob[qbe['offset']:qbe['offset'] + qbe['size']])
    thawscene.qb.load_names(os.path.join(os.path.dirname(__file__), '..', 'extracted', 'dbg'))
    tnodes = {thawscene._key(d['Name']): d for d in thawscene.expanded_nodes(tmp, 'z_ho') if isinstance(d.get('Name'), str)}
    p1 = next(d for d in tnodes.values() if d.get('RestartName') == 'P1: Restart')
    delta = np.round((AT - np.array(p1['Pos'])) * 16) / 16

    def thaw_place(src):
        """A THAW node's shifted position and yaw; (node, offset) or (node, offset, yaw) override."""
        name, off, yaw = (src, (0, 0, 0), None) if isinstance(src, str) else (tuple(src) + (None,))[:3]
        d = tnodes[qbkey(name)]
        return (np.array(d['Pos']) + delta + np.array(off),
                float(d.get('Angles', [0, 0, 0])[1]) if yaw is None else yaw)

    places = {k: thaw_place(v) for k, v in PLACES}

    # node moves
    d = open(os.path.join(outdir_build, 'tr.qb'), 'rb').read()
    start = qb2.find_item(d, struct.unpack_from('<I', d, 1)[0])
    arr, end = qb2.parse_value(d, start)
    want = {qbkey(k): k for k in places}
    moved = 0
    # the red velvet ropes along the Walk of Fame (THAW's caveman lessons grind these)
    rope_keys = {qbkey(n['Name'][1:]) for n in tnodes.values()
                 if n.get('Class') == '$RailNode' and 'VelvetRope' in str(n.get('Name'))
                 and abs(n['Pos'][2] + 88) < 6 and -1330 < n['Pos'][0] < -150}
    ropes_set = 0
    for n in arr[1]:
        nm = qb2.get(n, qbkey('Name'))
        if nm and nm[1] in want:
            pos, yaw = places[want[nm[1]]]
            # goal peds other than the caveman's are not spawned for these goals; create them at start
            if want[nm[1]].endswith('_Pro') and (None, ('name', qbkey('CreatedAtStart'))) not in n[1]:
                n[1].append((None, ('name', qbkey('CreatedAtStart'))))
            for i, (k, v) in enumerate(n[1]):
                if k == qbkey('Pos'):
                    n[1][i] = (k, ('vec', tuple(map(float, pos))))
                elif k == qbkey('Angles'):
                    n[1][i] = (k, ('vec', (0.0, yaw, 0.0)))
            moved += 1
        # the red rope rail THAW checks for caveman lesson part 2
        if nm and nm[1] in rope_keys and qb2.get(n, qbkey('TriggerScript')) is None:
            n[1].append((qbkey('TriggerScript'), ('name', qbkey('hw_rope_trigger'))))
            ropes_set += 1
    # testing aid: HW_SPAWN="x y z yaw" puts the level's other restarts at one spot
    if os.environ.get('HW_SPAWN'):
        x, y, z, yaw = map(float, os.environ['HW_SPAWN'].split())
        bases = {}
        for n in arr[1]:
            nm = qb2.get(n, qbkey('Name'))
            if nm and nm[1] in want:
                continue
            cls = qb2.get(n, qbkey('Class'))
            if not cls:
                for k, v in n[1]:
                    if k is None and v[0] == 'name':
                        if v[1] not in bases:
                            p = qb2.find_item(d, v[1])
                            bases[v[1]] = qb2.parse_value(d, p)[0] if p else None
                        cls = bases[v[1]] and qb2.get(bases[v[1]], qbkey('Class'))
                        if cls:
                            break
            if cls and cls[1] == qbkey('Restart'):
                for i, (k, v) in enumerate(n[1]):
                    if k == qbkey('Pos'):
                        n[1][i] = (k, ('vec', (x, y, z)))
                    elif k == qbkey('Angles'):
                        n[1][i] = (k, ('vec', (0.0, yaw, 0.0)))
        print('test spawn at', x, y, z)
    # the training level's trick objects (TrickObject with a Cluster: its graffiti pieces) name
    # sectors Hollywood does not have. The trick object manager looks each cluster up at level
    # start and uses the result unchecked: a null read that PPSSPP ignores and a real PSP crashes
    # on. Nodes whose cluster is not a piece of this level lose both.
    lvl = psplevel.Level(os.path.join(outdir_build, 'tr.psp_level'))
    sectors = set(struct.unpack_from(f'<{lvl.n_boxes}I', lvl.data, lvl.boxnames))
    col = open(os.path.join(outdir_build, 'tr.col.ps2'), 'rb').read()
    sectors |= {struct.unpack_from('<I', col, 0x20 + 0x40 * i)[0] for i in range(struct.unpack_from('<i', col, 4)[0])}
    # Most of Remix's nodes take these from a shared template (a bare name naming a global struct),
    # so the template's fields are merged in first. Level pieces created at start whose sector is
    # not here (the training level's own geometry) stop being created at start for the same reason.
    templates = {}

    def template(k):
        if k not in templates:
            p = qb2.find_item(d, k)
            v = qb2.parse_value(d, p)[0] if p else None
            templates[k] = v if v and v[0] == 'struct' else None
        return templates[k]
    trick, start_flag, cluster = ('name', qbkey('TrickObject')), ('name', qbkey('CreatedAtStart')), qbkey('Cluster')
    pieces = {qbkey('LevelGeometry'), qbkey('LevelObject')}
    stripped = unstarted = 0
    for n in arr[1]:
        tmpl = [v[1] for k, v in n[1] if k is None and v[0] == 'name' and template(v[1])]
        merged = [f for t in tmpl for f in template(t)[1]] + [f for f in n[1] if not (f[0] is None and f[1][0] == 'name' and f[1][1] in tmpl)]
        own = dict((k, v) for k, v in merged if k)
        bare = {v for k, v in merged if k is None and v[0] == 'name'}
        cl = own.get(cluster)
        dead_trick = cl is not None and cl[1] not in sectors and trick in bare
        cls, nm = own.get(qbkey('Class')), own.get(qbkey('Name'))
        dead_piece = cls is not None and cls[1] in pieces and start_flag in bare and nm and nm[1] not in sectors
        if dead_trick or dead_piece:
            drop = ({trick} if dead_trick else set()) | ({start_flag} if dead_piece else set())
            n[1][:] = [(k, v) for k, v in merged
                       if not (k is None and v in drop) and not (dead_trick and k == cluster)]
            stripped += dead_trick
            unstarted += dead_piece
    print(f'trick objects without a piece in this level: {stripped} (TrickObject and Cluster removed); '
          f'level pieces not here, no longer created at start: {unstarted}')
    trqb = d[:start] + qb2.encode_value(arr) + d[end:]
    open(os.path.join(out, 'tr.qb'), 'wb').write(trqb)
    print(f'nodes moved: {moved} of {len(places)}; red rope trigger on {ropes_set} rail nodes')

    # goals
    ped = lambda v: places[v]  # noqa: E731
    G = {k: qbkey(f'tr_goal_{k}') for k in ('gaps48', 'gaps49', 'counter7', 'gaps41', 'gaps42', 'gaps43', 'gaps40', 'counter40', 'gaps44',
                                           'gaps45', 'gaps46', 'gaps47')}

    def common(text, view, who, pro_node, restart_node, child=None, first=False, stage=False):
        pos, yaw = ped(pro_node)
        f = [('goal_text', S(text)), ('view_goals_text', S(view)), ('goal_description', S(text)),
             ('skater', N('Custom')), ('Pro', S(who)), ('full_name', S(who)),
             ('Trigger_Obj_ID', N(pro_node)), ('restart_node', N(restart_node)),
             ('start_cam_anims', cam_to(pos, yaw))]
        # stages (started by the engine when the goal before wins) must not be locked, or the
        # engine's ActivateGoal on them does nothing; Remix's own staged goals leave the flag off
        if not first and not stage and not os.environ.get('HW_UNLOCK_ALL'):  # testing aid: every goal open at once
            f.append(FLAG('Unlocked_By_Another'))
        if child:
            # the caveman lesson's parts and the wool protest's three combos are stages of one goal
            # (THAW chains them with child too):
            # winning a stage starts the next at once. Every other link is a reward_goal: a real
            # win (only a goal without a child is ever marked won) that unlocks the next goal,
            # whose giver you then go and talk to.
            f.append(('child' if child in ('gaps41', 'gaps42', 'gaps46', 'gaps47') else 'reward_goal', N(G[child])))
        return f

    goals = []
    combo_watchers = []
    # testing aid: HW_COMBO_SCORE=100 lowers every combo target so automated play can reach them
    test_score = int(os.environ.get('HW_COMBO_SCORE', 0))

    def combo_goal(version, score, text, view, who, pro, restart, child, post=None):
        """A landed combo of at least `score` wins (Remix's own high-combo goals are silent area
        challenges that deactivate when a combo lands, so they cannot be given by a ped)."""
        key = f'gaps{version}'
        target = test_score or score
        combo_watchers.append(combo_watcher(f'hw_combo{version}', G[key], target))
        return goal_call('AddGoal_Gaps', [('version', I(version)), ('time', I(60)),
                                          ('goal_flags', ('array', [N('got_1')])),
                                          ('goal_start_script', N(f'hw_combo{version}_start')),
                                          ('goal_success_Script', N(f'hw_combo{version}_stop')),
                                          ('goal_deactivate_script', N(f'hw_combo{version}_stop'))]
                         # goal_success runs goal_outro_script once the goal is won
                         + ([('goal_outro_script', N(post))] if post else [])
                         + ([('goal_success_Script', N('hw_dbg_won')), ('goal_deactivate_script', N('hw_dbg_deact'))] if os.environ.get('HW_DEBUG') else [])
                         + common(text, view, who, pro, restart, child, stage=version in (46, 47)))

    # 0 the two shops: the barber, then the clothing store
    shop_scripts, shop_goals = [], []
    for v, text, view, who, child in (
            (48, 'Change your look: go to the barber shop door and press \\b0', 'Change your look', 'Barber', 'gaps49'),
            (49, 'Change your clothes: go to the clothing store door and press \\b0', 'Change your clothes',
             'Store Clerk', 'counter7')):
        shop_goals.append(goal_call('AddGoal_Gaps', [('version', I(v)), ('time', I(120)),
                                                ('goal_flags', ('array', [N('got_1')])),
                                                ('goal_start_script', N(f'hw_shop{v}_start')),
                                                ('goal_success_Script', N(f'hw_shop{v}_stop')),
                                                ('goal_deactivate_script', N(f'hw_shop{v}_stop'))] + common(
            text, view, who, f'TRG_G_GAP{v - 30}_Pro', f'TRG_G_GAP{v - 30}_RestartNode', child, first=(v == 48))))
        rpos, ryaw = places[f'TRG_G_GAP{v - 30}_RestartNode']
        door = rpos + np.array([-np.sin(ryaw), 0, -np.cos(ryaw)]) * 50
        shop_scripts += [
            script(f'hw_shop{v}_start', [['skater', ':', 'Obj_SpawnScript', f'hw_shop{v}_poll']]),
            # on the skater: near the door, show the prompt; Triangle there sets the pending step
            # and leaves for CAS (spawned globally: changing level kills the skater's scripts)
            script(f'hw_shop{v}_poll', [['<hw_near>', '=', 0],
                                        ['while'],
                                        ['Obj_GetPosition'],
                                        ['<hw_d>', '=', bytes([0x0E, 0x2D]) + tok_name('Pos') + bytes([0x0A, qb2.VEC])
                                         + struct.pack('<3f', *map(float, door)) + bytes([0x0F])],
                                        ['if', bytes([0x0E, 0x0E, 0x2D]) + tok_name('hw_d') + bytes([0x08, 0x2D]) + tok_name('hw_d')
                                         + bytes([0x0F, 0x12, qb2.INT]) + struct.pack('<i', SHOP_DOOR_RADIUS ** 2) + bytes([0x0F])],
                                        ['if', bytes([0x0E]), '<hw_near>', '=', 0, bytes([0x0F])],
                                        ['create_panel_message', 'id', '=', 'hw_shop_hint', 'text', '=',
                                         "'Press \\b0 to go in", 'time', '=', 100000],
                                        ['endif'],
                                        ['<hw_near>', '=', 1],
                                        ['if', 'Held', 'Triangle'],
                                        ['kill_panel_message_if_it_exists', 'id', '=', 'hw_shop_hint'],
                                        ['change', 'hw_shop_pending', '=', v],
                                        ['spawnscript', 'hw_shop_go'],
                                        [bytes([0x22])],
                                        ['endif'],
                                        ['else'],
                                        ['if', bytes([0x0E]), '<hw_near>', '=', 1, bytes([0x0F])],
                                        ['kill_panel_message_if_it_exists', 'id', '=', 'hw_shop_hint'],
                                        ['endif'],
                                        ['<hw_near>', '=', 0],
                                        ['endif'],
                                        ['wait', 1, 'gameframe'],
                                        ['repeat']]),
            script(f'hw_shop{v}_stop', [['skater', ':', 'Obj_KillSpawnedScript', 'Name', '=', f'hw_shop{v}_poll'],
                                        ['kill_panel_message_if_it_exists', 'id', '=', 'hw_shop_hint']]),
        ]
    shop_scripts += [
        # the pause menu's Edit Appearance: remembers this level, deactivates goals, loads CAS
        script('hw_shop_go', [['wait', 2, 'gameframes'], ['pause_launch_level', 'level', '=', 'load_cas']]),
        # back from CAS (the level reloads): the pending shop step is won
        script('hw_shop_return', sum(([['if', bytes([0x0E]), 'hw_shop_pending', '=', v, bytes([0x0F])],
                                       ['change', 'hw_shop_pending', '=', 0],
                                       # a goal need not be active to be won (CGoal::Win); activating it
                                       # would bring up the giver's intro box again
                                       ['wait', 90, 'gameframes'],
                                       ['GoalManager_WinGoal', 'Name', '=', tok_name(G[f'gaps{v}'])],
                                       ['endif']] for v in (48, 49)), [])),
    ]
    # capture aid (HW_SHOT): the shop interiors seen the way Remix's CAS camera sees its skater,
    # for the CAS backdrops (tools/casbackdrop.py); HUD and skater hidden, one view every 4 s
    shot_lines = [['wait', 240, 'gameframes'], ['hide_everything'], ['skater', ':', 'hide']]
    for node in ('Z_HO_TRG_Restart_BarberShop_Edit', 'Z_HO_TRG_Restart_CASShop_Edit'):
        spot, yaw = thaw_place(node)
        for th in shot_yaws(yaw):
            cam, look = cas_view(spot, th)
            shot_lines += [['PlaySkaterCamAnim', 'skater', '=', 0, 'targetid', '=', 'world',
                            'targetOffset', '=', bytes([qb2.VEC]) + struct.pack('<3f', *map(float, look)),
                            'positionOffset', '=', bytes([qb2.VEC]) + struct.pack('<3f', *map(float, cam)),
                            'play_hold', 'frames', '=', 1, 'virtual_cam'],
                           ['wait', 240, 'gameframes']]
    shop_scripts.append(script('hw_shot_cams', shot_lines))
    # 4 sponsor challenge
    goals.append(combo_goal(43, 1500, 'Sponsor challenge: land a 1,500 point combo',
                            'Go to the skateshop, win a sponsor challenge', 'Mindy',
                            'TRG_G_GAP16_Pro', 'TRG_G_GAP16_RestartNode', 'gaps40'))
    # 5 kickflip over Ben Whofleck
    goals.append(goal_call('AddGoal_Gaps', [('version', I(40)), ('time', I(60)),
                                            ('goal_flags', ('array', [N('got_1')])),
                                            ('goal_start_script', N('hw_ben_start')),
                                            ('goal_success_Script', N('hw_ben_stop')),
                                            ('goal_deactivate_script', N('hw_ben_stop'))] + common(
        'Do a Kickflip over Ben Whofleck', 'Kickflip Ben Whofleck', 'Ben Whofleck',
        'TRG_G_GAP17_Pro', 'TRG_G_GAP17_RestartNode', 'counter40')))
    # 6 revert
    goals.append(goal_call('AddGoal_Counter', [('version', I(40)), ('number', I(1)), ('time', I(120)),
                                               FLAG('use_hud_counter'), ('hud_counter_caption', S('Revert')),
                                               ('goal_start_script', N('hw_revert_start')),
                                               ('goal_success_Script', N('hw_revert_stop')),
                                               ('goal_deactivate_script', N('hw_revert_stop'))] + common(
        'Do a Revert: go up a quarter pipe and revert as you land back down', 'Meet Duane at the Dog and Cello',
        'Duane', 'TRG_G_COUNTER4_Pro', 'TRG_G_COUNTER4_RestartNode', 'gaps44')))
    # 7 get your stuff back (the punk)
    goals.append(combo_goal(44, 3000, 'Beat my score: land a 3,000 point combo', 'Get your stuff back',
                            'Joe Skater', 'TRG_G_GAP5_Pro', 'TRG_G_GAP5_RestartNode', 'gaps45'))
    # 8 stop the wool protest (three stages; the third knocks down the dino head in THAW)
    for v, score, child in ((45, 2000, 'gaps46'), (46, 5000, 'gaps47'), (47, 10000, None)):
        goals.append(combo_goal(v, score, f'Land a {score:,} point combo', 'Stop the wool protest!', 'Mindy',
                                'TRG_G_GAP20_Pro', 'TRG_G_GAP20_RestartNode', child,
                                post=('hw_dino_fall' if v == 47 else None)))

    goto = [script('hw_goto_level', [['wait', 120, 'gameframes'], ['change_level', 'level', '=', os.environ['HW_GOTO_LEVEL']]])]         if os.environ.get('HW_GOTO_LEVEL') else []
    helpers = b''.join(shop_scripts + combo_watchers + goto + [
        # Ben: polled on the skater (event handlers for skater events never fired): while in a combo
        # that has a Kickflip in it, being within 180 inches of Ben wins. Ben's position is fixed.
        script('hw_ben_start', [['skater', ':', 'Obj_SpawnScript', 'hw_ben_poll']]),
        script('hw_ben_poll', [['while'],
                               ['if', 'SkaterCurrentScorePotGreaterThan', 0],
                               ['GetNumberOfTrickOccurrences', 'TrickText', '=', "'Kickflip"],
                               ['if', bytes([0x0E]), '<Number_Of_Occurrences>', bytes([0x14]), 0, bytes([0x0F])],
                               ['Obj_GetPosition'],
                               ['<hw_d>', '=', bytes([0x0E, 0x2D]) + tok_name('Pos') + bytes([0x0A, qb2.VEC])
                                + struct.pack('<3f', *map(float, places['TRG_G_GAP17_Pro'][0])) + bytes([0x0F])],
                               ['if', bytes([0x0E, 0x0E, 0x2D]) + tok_name('hw_d') + bytes([0x08, 0x2D]) + tok_name('hw_d')
                                + bytes([0x0F, 0x12, qb2.INT]) + struct.pack('<i', 180 * 180) + bytes([0x0F])],
                               ] + ([['create_panel_message', 'id', '=', 'hw_dbg7', 'text', '=', "'kickflip over Ben"]] if os.environ.get('HW_DEBUG') else []) + [
                               ['GoalManager_SetGoalFlag', 'Name', '=', tok_name(G['gaps40']), 'got_1', 1],
                               ['endif'],
                               ['endif'],
                               ['endif'],
                               ['wait', 2, 'gameframes'],
                               ['repeat']]),
        script('hw_ben_stop', [['skater', ':', 'Obj_KillSpawnedScript', 'Name', '=', 'hw_ben_poll']]),
        # revert: polled on the skater; a combo with a Revert in it counts once
        script('hw_revert_start', [['skater', ':', 'Obj_SpawnScript', 'hw_revert_poll']]
                + ([['spawnscript', 'hw_debug_teleport']] if os.environ.get('HW_DEBUG') and os.environ.get('HW_TP_ON_START') else [])),
        script('hw_revert_poll', [['while'],
                                  ['if', 'SkaterCurrentScorePotGreaterThan', 0],
                                  # Remix names the trick 'FS Revert' or 'BS Revert'
                                  ['GetNumberOfTrickOccurrences', 'TrickText', '=', "'FS Revert"],
                                  ['<hw_rv>', '=', '<Number_Of_Occurrences>'],
                                  ['GetNumberOfTrickOccurrences', 'TrickText', '=', "'BS Revert"],
                                  ['if', bytes([0x0E, 0x0E, 0x2D]) + tok_name('hw_rv') + bytes([0x0B, 0x2D]) + tok_name('Number_Of_Occurrences')
                                   + bytes([0x0F, 0x14, qb2.INT]) + struct.pack('<i', 0) + bytes([0x0F])],
                                  ] + ([['create_panel_message', 'id', '=', 'hw_dbg7', 'text', '=', "'revert seen"]] if os.environ.get('HW_DEBUG') else []) + [
                                  ['GoalManager_GotCounterObject', 'Name', '=', tok_name(G['counter40'])],
                                  ['while'],
                                  ['wait', 2, 'gameframes'],
                                  ['if', 'not', 'SkaterCurrentScorePotGreaterThan', 0],
                                  [bytes([0x22])],
                                  ['endif'],
                                  ['repeat'],
                                  ['endif'],
                                  ['endif'],
                                  ['wait', 2, 'gameframes'],
                                  ['repeat']]),
        script('hw_revert_stop', [['skater', ':', 'Obj_KillSpawnedScript', 'Name', '=', 'hw_revert_poll']]),
        script('hw_dbg_watch', [['while'],
                                ['<hw_st>', '=', "'goal: inactive"],
                                ['if', 'GoalManager_GoalIsActive', 'Name', '=', tok_name(qbkey('tr_goal_' + os.environ.get('HW_START_GOAL', 'none')))],
                                ['<hw_st>', '=', "'goal: ACTIVE"],
                                ['endif'],
                                ['if', 'GoalManager_HasWonGoal', 'Name', '=', tok_name(qbkey('tr_goal_' + os.environ.get('HW_START_GOAL', 'none')))],
                                ['<hw_st>', '=', "'goal: WON"],
                                ['endif'],
                                ['create_panel_message', 'id', '=', 'hw_dbg4', 'text', '=', '<hw_st>'],
                                ['wait', 30, 'gameframes'],
                                ['repeat']]),
        script('hw_dbg_deact', [['create_panel_message', 'id', '=', 'hw_dbg5', 'text', '=', "'DEACTIVATED"]]),
        script('hw_dbg_fail', [['create_panel_message', 'id', '=', 'hw_dbg6', 'text', '=', "'FAILED"]]),
        script('hw_dbg_won', [['create_panel_message', 'id', '=', 'hw_dbg3', 'text', '=', "'GOAL WON"]]),
        script('hw_debug_start_goal', [['wait', 120, 'gameframes'],
                                       ['if', 'GoalManager_HasWonGoal', 'Name', '=', tok_name(qbkey('tr_goal_' + os.environ.get('HW_START_GOAL', 'none')))],
                                       [bytes([0x29])],
                                       ['endif'],
                                       ['GoalManager_UnlockGoal', 'Name', '=', tok_name(qbkey('tr_goal_' + os.environ.get('HW_START_GOAL', 'none')))],
                                       ['GoalManager_ActivateGoal', 'Name', '=', tok_name(qbkey('tr_goal_' + os.environ.get('HW_START_GOAL', 'none')))]]),
        # red rope rail trigger, in the pattern of training's grind goal
        script('hw_rope_trigger', [['GetTriggerArray', 'grind', 'off'],
                                   ['if', 'Triggertype', '<trigger_array>'],
                                   ['if', 'GoalManager_GoalIsActive', 'Name', '=', tok_name(G['gaps41'])],
                                   ['GoalManager_SetGoalFlag', 'Name', '=', tok_name(G['gaps41']), 'got_1', 1],
                                   ['endif'],
                                   # follow my line: the grind must come in a combo that has a Caveman in it
                                   ['if', 'GoalManager_GoalIsActive', 'Name', '=', tok_name(G['gaps42'])],
                                   ['GetNumberOfTrickOccurrences', 'TrickText', '=', "'CaveMan"],
                                   ['if', bytes([0x0E]), '<Number_Of_Occurrences>', bytes([0x14]), 0, bytes([0x0F])],
                                   ['GoalManager_SetGoalFlag', 'Name', '=', tok_name(G['gaps42']), 'got_1', 1],
                                   ['endif'],
                                   ['endif'],
                                   ['endif']]),
        # THAW's caveman lesson counts switching from walking back to skating; polled, because the
        # skater's own walking scripts clear event handlers at exactly that moment
        script('hw_cave_start', [['skater', ':', 'Obj_SpawnScript', 'hw_cave_poll']]),
        script('hw_cave_poll', ([['create_panel_message', 'id', '=', 'hw_dbg3', 'text', '=', "'cave poll running"]] if os.environ.get('HW_DEBUG') else []) + [
                                ['<hw_was_walking>', '=', 0],
                                ['while'],
                                ['if', 'skater', ':', 'walking'],
                                ['<hw_was_walking>', '=', 1],
                                ] + ([['create_panel_message', 'id', '=', 'hw_dbg2', 'text', '=', "'walking seen"]] if os.environ.get('HW_DEBUG') else []) + [
                                ['else'],
                                ['if', bytes([0x0E]), '<hw_was_walking>', '=', 1, bytes([0x0F])],
                                ['<hw_was_walking>', '=', 0],
                                ] + ([['create_panel_message', 'id', '=', 'hw_dbg2', 'text', '=', "'caveman counted"]] if os.environ.get('HW_DEBUG') else []) + [
                                ['GoalManager_GotCounterObject', 'Name', '=', tok_name(G['counter7'])],
                                ['endif'],
                                ['endif'],
                                ['wait', 2, 'gameframes'],
                                ['repeat']]),
        script('hw_cave_stop', [['skater', ':', 'Obj_KillSpawnedScript', 'Name', '=', 'hw_cave_poll']]
                + ([['spawnscript', 'hw_debug_teleport']] if os.environ.get('HW_DEBUG') and os.environ.get('HW_SPAWN') else [])),
        # the protest won: the dinosaur head comes down (THAW swaps these pieces by node flag)
        script('hw_dbg_chain', [['while'],
                                ['<hw_s45>', '=', "'-"],
                                ['if', 'GoalManager_GoalIsActive', 'Name', '=', tok_name(G['gaps45'])],
                                ['<hw_s45>', '=', "'A"],
                                ['endif'],
                                ['if', 'GoalManager_HasWonGoal', 'Name', '=', tok_name(G['gaps45'])],
                                ['<hw_s45>', '=', "'W"],
                                ['endif'],
                                ['<hw_s46>', '=', "'-"],
                                ['if', 'GoalManager_GoalIsActive', 'Name', '=', tok_name(G['gaps46'])],
                                ['<hw_s46>', '=', "'A"],
                                ['endif'],
                                ['if', 'GoalManager_HasWonGoal', 'Name', '=', tok_name(G['gaps46'])],
                                ['<hw_s46>', '=', "'W"],
                                ['endif'],
                                ['<hw_s47>', '=', "'-"],
                                ['if', 'GoalManager_GoalIsActive', 'Name', '=', tok_name(G['gaps47'])],
                                ['<hw_s47>', '=', "'A"],
                                ['endif'],
                                ['if', 'GoalManager_HasWonGoal', 'Name', '=', tok_name(G['gaps47'])],
                                ['<hw_s47>', '=', "'W"],
                                ['endif'],
                                ['<hw_dn>', '=', "'gone"], ['if', 'IsAlive', 'Name', '=', 'Z_HO_HO_Before_Dino01'], ['<hw_dn>', '=', "'standing"], ['endif'],
                                ['<hw_dh>', '=', "'-"], ['if', 'IsAlive', 'Name', '=', 'Z_HO_HO_After_DinoHead'], ['<hw_dh>', '=', "'head down"], ['endif'],
                                ['FormatText', 'TextName', '=', 'hw_ct', "'protest %a %b %c dino %d %e", 'a', '=', '<hw_s45>', 'b', '=', '<hw_s46>', 'c', '=', '<hw_s47>', 'd', '=', '<hw_dn>', 'e', '=', '<hw_dh>'],
                                ['create_panel_message', 'id', '=', 'hw_dbg9', 'text', '=', '<hw_ct>'],
                                ['wait', 20, 'gameframes'], ['repeat']]),
        script('hw_dino_fall', [['Kill', 'Name', '=', n] for n in ('Z_HO_HO_Before_dino_sign', 'Z_HO_HO_Before_Dino01',
                                                                   'Z_HO_NightOn_03_HO_Before_Dino01_eyes',
                                                                   'Z_HO_HO_Before_dino_bldg', 'Z_HO_HO_Before_dino_roof_pool')]
                + [['create', 'Name', '=', n] for n in ('Z_HO_HO_After_dino_bldg', 'Z_HO_HO_After_dino_sign',
                                                        'Z_HO_HO_After_Dino01', 'Z_HO_HO_After_DinoHead')]
                + ([['create_panel_message', 'id', '=', 'hw_dbg8', 'text', '=', "'DINO HEAD FELL"]] if os.environ.get('HW_DEBUG') else [])
                + ([['spawnscript', 'hw_debug_teleport']] if os.environ.get('HW_DEBUG') and os.environ.get('HW_TP_ON_DINO') else [])),
        # testing aid: the skater's position on screen twice a second
        script('hw_debug_teleport', [['wait', int(os.environ.get('HW_TP_WAIT', 90)), 'gameframes'],
                                     ['skater', ':', 'Obj_SetPosition', 'position', '=', bytes([qb2.VEC]) + struct.pack('<3f', *map(float, os.environ.get('HW_SPAWN', '0 0 0 0').split()[:3]))],
                                     ['skater', ':', 'Obj_SetOrientation', 'y', '=', bytes([qb2.FLOAT]) + struct.pack('<f', float(os.environ.get('HW_SPAWN', '0 0 0 0').split()[3]) * 57.29578)],
                                     
                                     ['while'],
                                     ['skater', ':', 'SetSpeed', 0],
                                     ['wait', 1, 'gameframes'],
                                     ['repeat', int(os.environ.get('HW_TP_HOLD', 120))]]),
        script('hw_debug_peds', [['wait', 150, 'gameframes'], ['<hw_peds>', '=', "'peds:"],
                                 ['if', 'ObjectExists', 'id', '=', 'TRG_G_COUNTER7_Pro'], ['FormatText', 'TextName', '=', 'hw_peds', "'%a 0", 'a', '=', '<hw_peds>'], ['endif'],
                                 ['if', 'ObjectExists', 'id', '=', 'TRG_G_GAP16_Pro'], ['FormatText', 'TextName', '=', 'hw_peds', "'%a 1", 'a', '=', '<hw_peds>'], ['endif'],
                                 ['if', 'ObjectExists', 'id', '=', 'TRG_G_GAP17_Pro'], ['FormatText', 'TextName', '=', 'hw_peds', "'%a 2", 'a', '=', '<hw_peds>'], ['endif'],
                                 ['if', 'ObjectExists', 'id', '=', 'TRG_G_COUNTER4_Pro'], ['FormatText', 'TextName', '=', 'hw_peds', "'%a 3", 'a', '=', '<hw_peds>'], ['endif'],
                                 ['if', 'ObjectExists', 'id', '=', 'TRG_G_GAP5_Pro'], ['FormatText', 'TextName', '=', 'hw_peds', "'%a 4", 'a', '=', '<hw_peds>'], ['endif'],
                                 ['if', 'ObjectExists', 'id', '=', 'TRG_G_GAP20_Pro'], ['FormatText', 'TextName', '=', 'hw_peds', "'%a 5", 'a', '=', '<hw_peds>'], ['endif'],
                                 ['create_panel_message', 'id', '=', 'hw_dbg3', 'text', '=', '<hw_peds>'],
                                 ['wait', 60, 'gameframes'],
                                 ['TRG_G_GAP17_Pro', ':', 'Obj_GetPosition'],
                                 ['FormatText', 'TextName', '=', 'hw_pos_text', "'ben %a %b %c",
                                  'a', '=', dot('Pos', (1, 0, 0)), 'b', '=', dot('Pos', (0, 1, 0)), 'c', '=', dot('Pos', (0, 0, 1))],
                                 ['create_panel_message', 'id', '=', 'hw_dbg3', 'text', '=', '<hw_pos_text>']]),
        script('hw_debug_pos', [['while'],
                                ['skater', ':', 'Obj_GetPosition'],
                                ['FormatText', 'TextName', '=', 'hw_pos_text', "'%a %b %c",
                                 'a', '=', dot('Pos', (1, 0, 0)), 'b', '=', dot('Pos', (0, 1, 0)), 'c', '=', dot('Pos', (0, 0, 1))],
                                ['create_panel_message', 'id', '=', 'hw_debug', 'text', '=', '<hw_pos_text>'],
                                ['wait', 30, 'gameframes'],
                                ['repeat']]),
    ])

    # scripts file
    d = open(os.path.join(data, 'levels', 'tr', 'tr_scripts.qb'), 'rb').read()
    sc = qbscripts.scripts(d)
    edits = []  # (start, end, new bytes)
    # caveman: training's goal, retexted and moved to the start of the chain
    s, e = sc[CAVEMAN_SLOT]
    toks = list(qb2.tokens(d, s, e))
    call_at = next(p for p, t, pl in toks if t == qb2.NAME and struct.unpack_from('<I', pl)[0] == qbkey('AddGoal_Counter'))
    st, st_end = qb2.parse_value(d, call_at + 5)
    keep = {qbkey(k) for k in ('version', 'number', 'goal_intro_script', 'use_hud_counter', 'hud_counter_caption')} | {0x11116ea1}
    fields = [(k, v) for k, v in st[1] if k in keep or (k is None and v[1] == qbkey('use_hud_counter'))]
    fields += [(qbkey('goal_start_script'), N('hw_cave_start')), (qbkey('goal_success_Script'), N('hw_cave_stop')),
               (qbkey('goal_deactivate_script'), N('hw_cave_stop'))]
    fields += [(qbkey(k) if k else None, v) for k, v in common(
        'Switch to walk and back to skating 3 times: get off your board (\\be), then Caveman (\\be) back on',
        'Learn from the Hollywood skaters', 'Hollywood Skater', 'TRG_G_COUNTER7_Pro', 'TRG_G_COUNTER7_RestartNode',
        'gaps41')]
    edits.append((call_at + 5, st_end, qb2.encode_value(('struct', fields))))
    for slot, body in zip(SLOTS, goals):
        s, e = sc[slot]
        edits.append((s, e, script(slot, []).replace(bytes([qb2.NEWLINE, 0x24]), body + bytes([0x24]), 1)))
    spare = [x for x in ALL_SLOTS if x != CAVEMAN_SLOT and x not in SLOTS]
    for slot in spare:
        s, e = sc[slot]
        lines = []
        if slot == spare[1]:
            lines = [['spawnscript', 'hw_shop_return']]
        if slot == spare[3] and os.environ.get('HW_GOTO_LEVEL'):
            # testing aid: from story mode straight into another level (a stock one, for comparison)
            lines = [['spawnscript', 'hw_goto_level']]
        if slot == spare[2] and os.environ.get('HW_SHOT'):
            lines = [['spawnscript', 'hw_shot_cams']]
        if os.environ.get('HW_DEBUG') and slot == spare[0]:
            lines = [] if os.environ.get('HW_NOPOS') else [['spawnscript', 'hw_debug_pos']]
            if os.environ.get('HW_SPAWN'):
                lines.append(['spawnscript', 'hw_debug_teleport'])
            lines.append(['spawnscript', 'hw_debug_peds'])
            if os.environ.get('HW_START_GOAL'):
                lines.append(['spawnscript', 'hw_dbg_chain' if os.environ.get('HW_CHAIN') else 'hw_dbg_watch'])
            if os.environ.get('HW_START_GOAL'):  # testing aid: start one goal directly after load
                lines.append(['spawnscript', 'hw_debug_start_goal'])
        body = script(slot, lines)[:-1]
        if slot == spare[-1]:
            # caveman lesson part 2 (THAW's z_ho_goal_gaps40): grind the red ropes, same skater
            red_ropes = goal_call('AddGoal_Gaps', [('version', I(41)), ('time', I(120)),
                                                   ('goal_flags', ('array', [N('got_1')]))] + common(
                'Grind (\\b0) the red ropes', 'Learn from the Hollywood skaters', 'Hollywood Skater',
                'TRG_G_COUNTER7_Pro', 'TRG_G_GAP7_RestartNode', 'gaps42', stage=True))
            body = body.replace(bytes([qb2.NEWLINE, 0x24]), red_ropes + bytes([0x24]), 1)
        if slot in spare[-4:-2]:  # the two shop goals
            body = body.replace(bytes([qb2.NEWLINE, 0x24]), shop_goals[spare.index(slot) - len(spare) + 4] + bytes([0x24]), 1)
        if slot == spare[-2]:
            # caveman lesson part 3 (THAW's z_ho_goal_gaps4): off the board, Caveman back on, jump and
            # grind the red ropes, all in one combo; winning it is THAW's "learned Caveman" moment
            line = goal_call('AddGoal_Gaps', [('version', I(42)), ('time', I(120)),
                                              ('goal_flags', ('array', [N('got_1')]))] + common(
                'Follow my line: get off your board (\\be), Caveman (\\be) back on, then jump and grind (\\b0) the red ropes in one combo',
                'Learn from the Hollywood skaters', 'Hollywood Skater',
                'TRG_G_COUNTER7_Pro', 'TRG_G_GAP7_RestartNode', 'gaps43', stage=True))
            body = body.replace(bytes([qb2.NEWLINE, 0x24]), line + bytes([0x24]), 1)
        edits.append((s, e, body))
    new = bytearray()
    pos = 0
    for s, e, b in sorted(edits):
        new += d[pos:s] + b
        pos = e
    new += d[pos:]
    # helper scripts go before the end-of-file token
    end_tok = new.rfind(b'\x00')
    while end_tok > 0 and new[end_tok - 1] != qb2.NEWLINE and new[end_tok - 1] != 0x24:
        end_tok = new.rfind(b'\x00', 0, end_tok)
    toks = list(qb2.tokens(bytes(new)))
    end_tok = toks[-1][0]
    new = new[:end_tok] + bytes([qb2.NEWLINE]) + helpers + new[end_tok:]
    list(qb2.tokens(bytes(new)))  # must tokenise end to end
    open(os.path.join(out, 'tr_scripts.qb'), 'wb').write(new)
    print(f'tr_scripts.qb {len(d)} -> {len(new)} bytes')

    # chapter 1 starts with Remix's training intro cutscenes (TR_1A-1C), played in the training
    # level; with Hollywood in that slot the first one hangs, and they are not Hollywood's story
    ch = open(os.path.join(data, 'scripts', 'game', 'menu', 'chapter_info.qb'), 'rb').read()
    p = qb2.find_item(ch, 0x1887ba3d)  # the chapter array
    chapters, cend = qb2.parse_value(ch, p)
    while ch[p] in (qb2.NEWLINE, 0x02):
        p += 1
    ch1 = chapters[1][0][1]
    ch1[:] = [(k, v) for k, v in ch1 if k != 0x84546ab7]  # chapter 1's cutscene list
    ch = ch[:p] + qb2.encode_value(chapters) + ch[cend:]
    # the shop step pending across the trip to CAS (this file stays loaded when the level unloads)
    end_tok = next(p for p, t, pl in qb2.tokens(ch) if t in (0x2B, 0x00))  # before the name table
    ch = ch[:end_tok] + assemble_line(['hw_shop_pending', '=', 0]) + ch[end_tok:]
    list(qb2.tokens(ch))
    open(os.path.join(out, 'chapter_info.qb'), 'wb').write(ch)
    # build on the HUD port's qb_scripts.pre when there is one, so both changes survive
    base = os.environ.get('HW_QB_BASE') or os.path.join(data, 'pre', 'qb_scripts.pre')
    qb2.replace_in_pre(base, os.path.join(out, 'qb_scripts.pre'),
                       r'scripts\game\menu\chapter_info.qb', ch)
    print(f'chapter_info.qb: chapter 1 intro cutscenes removed')

    pre = os.path.join(out, 'tr_scripts.pre')
    qb2.replace_in_pre(os.path.join(data, 'pre', 'tr_scripts.pre'), pre, r'levels\TR\TR_scripts.qb', bytes(new))
    qb2.replace_in_pre(pre, pre, r'levels\TR\TR.qb', trqb)
    print(f'tr_scripts.pre {os.path.getsize(pre)} bytes')


if __name__ == '__main__':
    main()
