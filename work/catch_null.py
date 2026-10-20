"""Story run with a breakpoint on FUN_0000f480 (virtual call on a0 + 0x3c) when a0 == 0: prints ra and a stack dump."""
import sys, time, struct, base64
sys.path.insert(0, 'tools')
import ppsspp_ws as p
print(p.start('work/p8v/tree'))
ws = p.WS()
time.sleep(95)
print(ws.call({'event': 'cpu.breakpoint.add', 'address': 0x08813480, 'condition': 'a0 == 0', 'enabled': True}))
t0 = time.time()
while time.time() - t0 < 520:
    st = ws.call({'event': 'cpu.status'})
    if st.get('stepping'):
        regs = ws.call({'event': 'cpu.getAllRegs'})
        r = {n: v for c in regs['categories'] for n, v in zip(c['registerNames'], c['uintValues'])}
        print('pc %08x ra %08x sp %08x a0 %08x a1 %08x s0 %08x s1 %08x' % (r['pc'], r['ra'], r['sp'], r['a0'], r['a1'], r['s0'], r['s1']))
        m = ws.call({'event': 'memory.read', 'address': r['sp'], 'size': 256})
        d = base64.b64decode(m['base64'])
        print(' '.join('%08x' % w for w in struct.unpack('<64I', d) if 0x08804000 <= w < 0x08c00000))
        p.shot(ws, 'work/shots/null_at.png')
        break
    p.press(ws, ['cross'])
    time.sleep(12)
