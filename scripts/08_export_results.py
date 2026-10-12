"""Turn SUMO edgeData into per-edge hourly metrics (for the viewer), hourly KPIs and ranked critical points,
and the vehicle routes (vehroutes.xml.gz, when the run wrote it) into the viewer's trip replay.
With a scenario, its run in results/scenarios/<scenario>/<day>/ (as 12_scenario.py made it), for the viewer's run switch.
Output: build/web/<key>_edges.bin, build/web/trips/<key>_HH.bin, results/<day>_results.json; key = wd, sat, wd-<scenario>, ...
(the scenario's results.json in its run folder)
usage: python3 scripts/08_export_results.py <weekday|saturday> [scenario]   # after 06_export_static.py, whose road list it uses"""
import sys, json, math, collections, gzip, struct
import numpy as np, sumolib
from lxml import etree
from common import NET, EDGE_IDS, ZONES, RESULTS, WEBRAW, ORIGIN, zopen, read_net, scenario_net
day, scen = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
key = {'weekday': 'wd', 'saturday': 'sat'}[day] + (f'-{scen}' if scen else '')
run = RESULTS / 'scenarios' / scen / day if scen else RESULTS / day
net = read_net(scenario_net(scen) if scen else NET)
edge_ids = json.load(open(EDGE_IDS))
eidx = {e: i for i, e in enumerate(edge_ids)}
NE, NH = len(edge_ids), 24
LON0, LAT0 = ORIGIN; X0, Y0 = net.convertLonLat2XY(LON0, LAT0)

F = {k: np.zeros((NH, NE), np.float32) for k in ('flow', 'speedRel', 'timeLoss', 'waiting', 'sampled', 'distance', 'departed', 'density')}
has = np.zeros((NH, NE), bool)
def _iter():
    try:
        for ev, el in etree.iterparse(zopen(run / 'edgedata_hourly.xml.gz', 'rb'), tag='interval'): yield ev, el
    except etree.XMLSyntaxError: return
for ev, el in _iter():
    h = int(float(el.get('begin')) // 3600)
    if h >= NH: el.clear(); continue
    for e in el:
        i = eidx.get(e.get('id'))
        if i is None: continue
        g = lambda a: float(e.get(a) or 0)
        F['flow'][h, i] = g('entered') + g('departed')
        F['speedRel'][h, i] = g('speedRelative') if e.get('speedRelative') else 1
        F['timeLoss'][h, i] = g('timeLoss'); F['waiting'][h, i] = g('waitingTime')
        F['sampled'][h, i] = g('sampledSeconds'); F['distance'][h, i] = g('distance'); F['departed'][h, i] = g('departed')
        F['density'][h, i] = g('density')
        has[h, i] = g('sampledSeconds') > 0
    el.clear()

# gateway in-edges: exclude insertion queues from hotspot scoring
import pickle
Zd = pickle.load(open(ZONES, 'rb'))
gw_in = set(sum([g['in'] for g in Zd['gateways']], []))

# deadlock signature (lane-end blocking on short multi-lane links, resolved by teleports): near-zero speed, almost no throughput
dead = has & (F['speedRel'] < 0.03) & (F['flow'] < 60) & (F['timeLoss'] > 1800)
gw_mask = np.array([e in gw_in for e in edge_ids])
loss_net = np.where(dead | gw_mask[None, :], 0, F['timeLoss'])
print('deadlock edge-hours', int(dead.sum()), 'veh-h excluded', round(float(F['timeLoss'][dead].sum() / 3600)), 'gateway veh-h excluded', round(float(F['timeLoss'][:, gw_mask].sum() / 3600)))

# ---------------- per-edge hourly binary
spd = np.where(has, np.clip(F['speedRel'] * 200, 0, 254), 255).astype(np.uint8)
flow = np.clip(F['flow'], 0, 65535).astype(np.uint16)
delay = np.clip(F['timeLoss'] / 60, 0, 65535).astype(np.uint16)          # veh-min lost per hour on the edge
dens = np.clip(F['density'] * 10, 0, 65535).astype(np.uint16)             # veh/km * 10
with open(WEBRAW / f'{key}_edges.bin', 'wb') as f:
    for arr in (spd, flow, delay, dens): f.write(arr.tobytes())

# ---------------- KPIs per hour
lens = np.array([net.getEdge(e).getLength() if net.hasEdge(e) else 0 for e in edge_ids])   # roads of other runs: no data
kpi = []
for h in range(NH):
    vh = F['sampled'][h].sum() / 3600; vkm = F['distance'][h].sum() / 1000
    act = has[h] & (F['flow'][h] >= 30)
    cong = act & (F['speedRel'][h] < 0.5)
    kpi.append({'h': h, 'veh_in_net': round(vh, 1), 'veh_km': round(vkm), 'avg_kmh': round(vkm / vh, 1) if vh > 0 else 0,
                'delay_vh': round(float(loss_net[h].sum()) / 3600, 1), 'departed': int(F['departed'][h].sum()),
                'cong_km': round(lens[cong].sum() / 1000, 1), 'act_km': round(lens[act].sum() / 1000, 1)})

# ---------------- critical points: cluster junctions, score by delay on approaches
round_nodes = []
for r in net.getRoundabouts(): round_nodes.append(set(r.getNodes()))
parent = {}
def find(a):
    while parent.get(a, a) != a: a = parent[a]
    return a
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb
for rs in round_nodes:
    rs = list(rs)
    for n in rs[1:]: union(rs[0], n)
for e in net.getEdges():
    if e.getLength() < 45 and e.getFunction() != 'internal':
        union(e.getFromNode().getID(), e.getToNode().getID())
cl_delay = collections.defaultdict(lambda: np.zeros(NH)); cl_edges = collections.defaultdict(collections.Counter)
cl_wait = collections.defaultdict(lambda: np.zeros(NH)); cl_flow = collections.defaultdict(lambda: np.zeros(NH))
cl_minspd = collections.defaultdict(lambda: np.ones(NH))
for i, eid in enumerate(edge_ids):
    if eid in gw_in or not net.hasEdge(eid): continue
    e = net.getEdge(eid)
    c = find(e.getToNode().getID())
    # count only delay incurred on the approach (edges that end at the cluster and are not inside it)
    if find(e.getFromNode().getID()) == c: continue
    cl_delay[c] += loss_net[:, i] / 3600; cl_wait[c] += F['waiting'][:, i] / 3600; cl_flow[c] += F['flow'][:, i]
    cl_edges[c][e.getName().replace('&apos;', "'")] += loss_net[:, i].sum()
    sr = np.where(has[:, i] & (F['flow'][:, i] > 60), F['speedRel'][:, i], 1); cl_minspd[c] = np.minimum(cl_minspd[c], sr)
nodes_of = collections.defaultdict(list)
for n in net.getNodes(): nodes_of[find(n.getID())].append(n)
spots = []
for c, d in cl_delay.items():
    if d.sum() < 5: continue
    ns = nodes_of[c]; x = np.mean([n.getCoord()[0] for n in ns]); y = np.mean([n.getCoord()[1] for n in ns])
    names = [n for n, v in cl_edges[c].most_common(4) if n][:3]
    tls = any(n.getType() == 'traffic_light' for n in ns); rnd = any(c == find(next(iter(r))) for r in round_nodes)
    spots.append({'id': c, 'x': round(x - X0, 1), 'y': round(y - Y0, 1), 'lonlat': [round(v, 6) for v in net.convertXY2LonLat(x, y)],
                  'streets': names, 'control': 'signals' if tls else ('roundabout' if rnd else 'priority'),
                  'delay_h': np.round(d, 2).tolist(), 'flow_h': np.round(cl_flow[c]).astype(int).tolist(),
                  'min_speed_rel': np.round(cl_minspd[c], 2).tolist(),
                  'daily_delay_vh': round(float(d.sum()), 1), 'peak_hour': int(np.argmax(d)), 'peak_delay_vh': round(float(d.max()), 1)})
spots.sort(key=lambda s: -s['daily_delay_vh'])
# merge clusters closer than 150 m (keep the stronger)
kept = []
for s in spots:
    if any(math.hypot(s['x'] - k['x'], s['y'] - k['y']) < 150 for k in kept): continue
    kept.append(s)
top = kept[:40]
json.dump({'kpi': kpi, 'hotspots': top}, open(run / 'results.json' if scen else RESULTS / f'{day}_results.json', 'w'), indent=1, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, 'item') else str(o))
print(key, 'daily delay veh-h', round(sum(k['delay_vh'] for k in kpi)), 'veh-km', sum(k['veh_km'] for k in kpi))
for s in top[:15]:
    print(f"{s['daily_delay_vh']:7.1f} vh  peak {s['peak_hour']:02d}h {s['peak_delay_vh']:6.1f}  {s['control']:10s} {' / '.join(s['streets'])}  @{s['lonlat'][1]:.4f},{s['lonlat'][0]:.4f}")

# ---------------- trip replay: every vehicle's route with its edge exit times (LTR1), one file per hour holding
# every vehicle on the road during that hour, so the viewer needs a single file for any clock time
vr = run / 'vehroutes.xml.gz'
if not vr.exists(): print('no vehroutes.xml.gz, trip replay not exported'); sys.exit()
TYPES = {'car': 0, 'van': 1, 'truck': 2, 'ztl': 3}
frac = lambda d, e: min(255, max(0, round(d / max(lens[e], 0.1) * 255)))   # position along the edge, 0-255
apos = {}
for _, el in etree.iterparse(zopen(run / 'tripinfo.xml.gz', 'rb'), tag='tripinfo'):
    apos[el.get('id')] = float(el.get('arrivalPos')); el.clear()
trips = []   # (depart, id, type, depart pos, arrival pos, edges, exit-time deltas, arrival)
for _, el in etree.iterparse(zopen(vr, 'rb'), tag='vehicle'):
    r = el.find('route'); vid = el.get('id'); dep = round(float(el.get('depart')))
    E = [eidx.get(e) for e in r.get('edges').split()]; X = [round(float(x)) for x in r.get('exitTimes').split()]
    if len(E) == len(X) and None not in E and vid in apos:
        trips.append((dep, vid, TYPES.get(el.get('type'), 0), frac(float(el.get('departPos')), E[0]), frac(apos[vid], E[-1]),
                      np.array(E, np.uint16), np.diff([dep] + X).clip(0, 65535).astype(np.uint16), X[-1]))
    el.clear()
trips.sort(key=lambda t: (t[0], t[1]))
(WEBRAW / 'trips').mkdir(exist_ok=True)
for h in range(NH):
    sel = [t for t in trips if t[0] < (h + 1) * 3600 and t[7] >= h * 3600]
    with open(WEBRAW / 'trips' / f'{key}_{h:02d}.bin', 'wb') as f:
        f.write(b'LTR1' + struct.pack('<III', len(sel), sum(len(t[5]) for t in sel), h * 3600))
        f.write(np.array([t[0] for t in sel], np.uint32).tobytes()); f.write(np.array([len(t[5]) for t in sel], np.uint16).tobytes())
        for col in (5, 6): f.write(np.concatenate([t[col] for t in sel] or [np.zeros(0, np.uint16)]).tobytes())
        for col in (2, 3, 4): f.write(np.array([t[col] for t in sel], np.uint8).tobytes())
print(key, 'trip replay', len(trips), 'vehicles, max trip', max(t[7] - t[0] for t in trips) // 60, 'min')
