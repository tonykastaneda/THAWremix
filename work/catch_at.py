"""catch_at.py <addr hex> <arm after s> "<steps>": breakpoint at addr when a0 == 0; prints regs + stack code pointers."""
import sys, time, struct, base64
sys.path.insert(0, 'tools')
import ppsspp_ws as p
addr, arm, steps = int(sys.argv[1], 16), float(sys.argv[2]), sys.argv[3]
p.kill()
print(p.start('work/p8v/tree'))
ws = p.WS()
t0 = time.time()
armed = False
for step in steps.split(','):
    if not armed and time.time() - t0 >= arm:
        ws.call({'event': 'cpu.breakpoint.add', 'address': addr, 'condition': 'a0 == 0', 'enabled': True})
        armed = True
    k, _, v = step.partition(':')
    if k == 'wait':
        end = time.time() + int(v) / 1000
        while time.time() < end:
            time.sleep(0.5)
            if not armed and time.time() - t0 >= arm:
                ws.call({'event': 'cpu.breakpoint.add', 'address': addr, 'condition': 'a0 == 0', 'enabled': True})
                armed = True
    elif k == 'stick':
        x, y, ms = v.split(':')
        ws.call({'event': 'input.analog.send', 'stick': 'left', 'x': float(x), 'y': float(y)})
        time.sleep(int(ms) / 1000)
        ws.call({'event': 'input.analog.send', 'stick': 'left', 'x': 0, 'y': 0})
    else:
        p.press(ws, k.split('+'), int(v) if v else 120)
for _ in range(20):
    st = ws.call({'event': 'cpu.status'})
    if st.get('stepping'):
        regs = ws.call({'event': 'cpu.getAllRegs'})
        r = {n: v for c in regs['categories'] for n, v in zip(c['registerNames'], c['uintValues'])}
        print('pc %08x ra %08x sp %08x a0 %08x a1 %08x s0 %08x s1 %08x s2 %08x' % (r['pc'], r['ra'], r['sp'], r['a0'], r['a1'], r['s0'], r['s1'], r['s2']))
        d = base64.b64decode(ws.call({'event': 'memory.read', 'address': r['sp'], 'size': 512})['base64'])
        print(' '.join('%08x' % w for w in struct.unpack('<128I', d) if 0x08804000 <= w < 0x08c00000))
        break
    time.sleep(1)
else:
    print('no hit')
