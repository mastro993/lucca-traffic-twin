"""Decode the viewer's LTR1 trip-replay files and check them: layout, edge indices, every vehicle on the road during its
file's hour, and per-hour vehicle counts against the edgeData KPIs.
usage: python3 scripts/tools/check_trips.py [wd|sat]"""
import sys, json, struct
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import WEBRAW, RESULTS, EDGE_IDS, DAYS

def read(path):
    b = path.read_bytes(); assert b[:4] == b'LTR1', path
    n, m, t0 = struct.unpack('<III', b[4:16]); o = 16
    def take(dt, k):
        nonlocal o; a = np.frombuffer(b, dt, k, o); o += a.nbytes; return a
    dep, cnt, edge, dt = take(np.uint32, n), take(np.uint16, n), take(np.uint16, m), take(np.uint16, m)
    typ, dpos, apos = take(np.uint8, n), take(np.uint8, n), take(np.uint8, n)
    assert o == len(b) and int(cnt.sum(dtype=np.int64)) == m and (cnt > 0).all(), path
    arr = dep.astype(np.int64) + np.add.reduceat(dt.astype(np.int64), np.r_[0, np.cumsum(cnt, dtype=np.int64)[:-1]]) if n else dep
    return dict(n=n, t0=t0, dep=dep, arr=arr, edge=edge, typ=typ)

key = sys.argv[1] if len(sys.argv) > 1 else 'wd'
NE = json.load(open(EDGE_IDS))['roads']
kpi = json.load(open(RESULTS / f'{DAYS[key]}_results.json'))['kpi']
for h in range(24):
    T = read(WEBRAW / 'trips' / f'{key}_{h:02d}.bin')
    assert T['t0'] == h * 3600 and (T['edge'] < NE).all() and (T['typ'] <= 3).all()
    assert ((T['dep'] < (h + 1) * 3600) & (T['arr'] >= h * 3600)).all(), f'vehicle outside hour {h}'
    # mean vehicles on the road over the hour, from the replay, vs SUMO's sampled seconds / 3600
    on = (np.minimum(T['arr'], (h + 1) * 3600) - np.maximum(T['dep'], h * 3600)).clip(0).sum() / 3600
    print(f'{key} {h:02d}  {T["n"]:6d} vehicles  mean on road {on:7.0f}  edgeData {kpi[h]["veh_in_net"]:7.0f}')
print('ok')
