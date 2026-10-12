"""Boot a game on the hidden PPSSPP test copy and take pictures while pressing a button sequence.

  p8boot.py <iso or tree> <tag> "<seq>"

seq as ppsspp_ws.run_seq: wait:<ms>, <button>[+<button>][:<ms>], stick:<x>:<y>:<ms>, and 'shot'
(numbered automatically: work/shots/<tag>_NN.png). The emulator keeps running afterwards (for
p8heaps.py); ppsspp_ws.kill() stops it. Example, story start to the pause menu (default build):
  "wait:5000,start,wait:3000,start,wait:7000,cross,wait:3000,cross,wait:3000,cross,wait:45000,cross,
   wait:10000,start,wait:3000,shot"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import ppsspp_ws as p  # noqa: E402

SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'shots')


def main():
    iso, tag, seq = sys.argv[1:4]
    p.start(iso)
    ws = p.WS()
    n, steps = 0, []
    for s in seq.split(','):
        if s == 'shot':
            n += 1
            s = 'dshot:' + os.path.join(SHOTS, f'{tag}_{n:02d}.png')
        steps.append(s)
    p.run_seq(ws, ','.join(steps))
    st = ws.call({'event': 'cpu.status'})
    print('stepping' if st.get('stepping') else 'running', 'pc %08x' % st.get('pc', 0))


if __name__ == '__main__':
    main()
