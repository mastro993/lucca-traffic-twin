"""Tour-based demand generator for Lucca (weekday / saturday). Output: demand/<day>.trips.xml.gz
usage: python3 scripts/05_generate_demand.py <weekday|saturday> [scale=1.0] [gateway_scale=1.0]

Residents' home-based tours with purpose-specific timing and gravity destination choice,
external visitors from gateway counts, through traffic, trucks, non-home-based trips and ZTL permit traffic."""
import sys, pickle, math, json, collections
import numpy as np, gzip
from common import ZONES, DEMAND
day = sys.argv[1]            # 'weekday' | 'saturday'
SCALE = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
GWSCALE = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
seed = 42 if day == 'weekday' else 7
rng = np.random.default_rng(seed)
D = pickle.load(open(ZONES, 'rb'))
W, Z, zones, GW = D['W'], D['Z'], D['zones'], D['gateways']
T_zz, T_gz, T_zg = D['T_zz'], D['T_gz'], D['T_zg']
NZ = len(zones)
POP = 115000
SAT = day == 'saturday'

def mix(spec, n):
    """spec: list of (mean_h, sd_h, weight) -> n samples (hours, clipped to [0, 26))"""
    w = np.array([s[2] for s in spec]); w = w / w.sum()
    k = rng.choice(len(spec), size=n, p=w)
    m = np.array([s[0] for s in spec])[k]; sd = np.array([s[1] for s in spec])[k]
    return np.clip(rng.normal(m, sd), 0.0, 25.9)

def zone_w(key):
    if key == 'res': return np.array([Z[z]['res'] for z in zones])
    if key == 'work': return np.array([Z[z]['work'] for z in zones])
    if key == 'school': return np.array([Z[z]['school'] + 0.02 * Z[z]['res'] for z in zones])
    if key == 'shop': return np.array([Z[z]['shop'] + 0.08 * Z[z]['res'] for z in zones])
    if key == 'leisure': return np.array([0.6 * Z[z]['shop'] + 0.25 * Z[z]['res'] + 0.2 * Z[z]['work'] for z in zones])
    if key == 'other': return np.array([0.5 * Z[z]['work'] + 0.5 * Z[z]['shop'] + 0.1 * Z[z]['res'] for z in zones])
    if key == 'truck': return np.array([Z[z]['truck'] + 0.03 * Z[z]['work'] for z in zones])

def edge_in_zone(zi, key):
    es = Z[zones[zi]]['edges']
    kk = {'school': 'school', 'res': 'res', 'work': 'work', 'shop': 'shop', 'truck': 'truck'}.get(key, None)
    if kk is None:
        w = np.array([W[e].get('shop', 0) + W[e].get('work', 0) + 0.2 * W[e].get('res', 0) for e in es])
    else:
        w = np.array([W[e].get(kk, 0) for e in es])
        if kk == 'school': w = w + 0.02 * np.array([W[e].get('res', 0) for e in es])
        if kk == 'truck': w = w + 0.03 * np.array([W[e].get('work', 0) for e in es])
    if w.sum() <= 0: w = np.ones(len(es))
    return es[rng.choice(len(es), p=w / w.sum())]

T = np.where(np.isfinite(T_zz), T_zz, 999)
gw_in_ok = [k for k, g in enumerate(GW) if g['in']]
gw_out_ok = [k for k, g in enumerate(GW) if g['out']]
gw_vol = np.array([g['vol'] * GWSCALE for g in GW], float)
TZG = np.full((NZ, len(GW)), 999.0)
for k, v in T_zg.items(): TZG[:, k] = np.where(np.isfinite(v), v, 999)
TGZ = np.full((len(GW), NZ), 999.0)
for k, v in T_gz.items(): TGZ[k, :] = np.where(np.isfinite(v), v, 999)

trips = []   # (depart_s, from_edge, to_edge, vtype, tag)
def add(t_h, fe, te, vt, tag):
    if fe == te: return
    trips.append((float(t_h) * 3600.0, fe, te, vt, tag))

# ------------------------------------------------------------- resident home-based tours
if not SAT:
    P = {  # share, departure mixture, dwell (median h, sigma log), beta, p_external
        'work':    (0.36, [(7.3, .8, .25), (8.3, .7, .25), (6.4, .6, .12), (9.4, .9, .18), (13.8, .6, .09), (5.6, .6, .06), (22.0, .8, .05)], (9.0, .18), 0.055, 0.22),
        'school':  (0.14, [(7.6, .3, .35), (8.05, .25, .35), (8.4, .25, .30)], (0.1, .4), 0.20, 0.03),
        'shop':    (0.32, [(10.2, 1.3, .5), (17.2, 1.2, .4), (19.0, .7, .1)], (0.8, .5), 0.10, 0.07),
        'leisure': (0.13, [(18.2, 1.5, .5), (20.6, 1.0, .3), (15.0, 1.5, .2)], (2.0, .5), 0.07, 0.15),
        'other':   (0.05, [(9.5, 1.5, .6), (15.5, 1.5, .4)], (1.0, .5), 0.09, 0.10)}
    TOURS = 0.55 * POP * SCALE
else:
    P = {
        'work':    (0.14, [(8.0, .8, .7), (14.5, 1.0, .3)], (6.0, .25), 0.06, 0.15),
        'school':  (0.03, [(7.8, .25, 1.0)], (0.1, .4), 0.20, 0.02),
        'shop':    (0.45, [(10.4, 1.3, .6), (16.6, 1.3, .4)], (1.2, .5), 0.085, 0.10),
        'leisure': (0.30, [(16.0, 2.0, .3), (19.6, 1.5, .5), (21.6, 1.0, .2)], (2.5, .5), 0.06, 0.18),
        'other':   (0.08, [(10.0, 1.5, .6), (16.0, 1.5, .4)], (1.0, .5), 0.09, 0.10)}
    TOURS = 0.60 * POP * SCALE
res_w = zone_w('res'); res_p = res_w / res_w.sum()
ext_use = np.zeros(len(GW))
for purp, (share, dep, dwell, beta, pext) in P.items():
    n = int(round(TOURS * share))
    o = rng.choice(NZ, size=n, p=res_p)
    t0 = mix(dep, n)
    dw = np.exp(rng.normal(np.log(dwell[0]), dwell[1], n))
    ext = rng.random(n) < pext
    A = zone_w('school' if purp == 'school' else purp)
    for zi in np.unique(o):
        idx = np.where(o == zi)[0]
        home_edges = [edge_in_zone(zi, 'res') for _ in idx]
        # internal destinations
        pr = A * np.exp(-beta * T[zi]); pr[T[zi] >= 999] = 0
        if pr.sum() <= 0: continue
        pr = pr / pr.sum()
        # external gateway choice
        pg = gw_vol * np.exp(-0.04 * TZG[zi]); pg[[k for k in range(len(GW)) if k not in gw_out_ok or k not in gw_in_ok]] = 0
        pg = pg / pg.sum()
        for j, i in enumerate(idx):
            he = home_edges[j]
            if ext[i]:
                k = rng.choice(len(GW), p=pg); ext_use[k] += 1
                out_e = GW[k]['out'][0]; in_e = GW[k]['in'][0]
                add(t0[i], he, out_e, 'car', purp + '_ext')
                add(t0[i] + dw[i] + 0.3, in_e, he, 'car', purp + '_ext')
                continue
            dz = rng.choice(NZ, p=pr); de = edge_in_zone(dz, purp if purp != 'leisure' else 'shop')
            if purp == 'school':
                add(t0[i], he, de, 'car', 'school'); add(t0[i] + 0.12 + 0.05 * rng.random(), de, he, 'car', 'school')
                # afternoon pickup tour (60% at ~13:10, 40% at ~16:20 on weekdays)
                tp = rng.normal(13.0, 0.4) if (SAT or rng.random() < 0.55) else rng.normal(16.3, 0.3)
                add(tp, he, de, 'car', 'school'); add(tp + 0.25 + 0.1 * rng.random(), de, he, 'car', 'school')
                continue
            add(t0[i], he, de, 'car', purp)
            if purp == 'work' and not SAT and rng.random() < 0.18:      # lunch return home (Italian pattern)
                tl = rng.normal(12.9, 0.35); add(tl, de, he, 'car', 'work_lunch'); add(tl + 1.3 + 0.3 * rng.random(), he, de, 'car', 'work_lunch')
            add(t0[i] + dw[i] + 0.25, de, he, 'car', purp)

# ------------------------------------------------------------- non-home-based trips
nhb = int(round(TOURS * (0.12 if not SAT else 0.08)))
Aw = zone_w('other'); pw = Aw / Aw.sum()
o = rng.choice(NZ, size=nhb, p=pw); t0 = mix([(10.6, 1.3, .5), (15.6, 1.3, .4), (12.5, 1.0, .1)], nhb)
for zi in np.unique(o):
    idx = np.where(o == zi)[0]
    pr = Aw * np.exp(-0.09 * T[zi]); pr[T[zi] >= 999] = 0; pr /= pr.sum()
    for i in idx:
        dz = rng.choice(NZ, p=pr); add(t0[i], edge_in_zone(zi, 'work'), edge_in_zone(dz, 'other'), 'car', 'nhb')

# ------------------------------------------------------------- external visitors (gateway -> zone -> gateway)
dayf = 1.0 if not SAT else 0.92
vis_mix = ({'work': .55, 'shop': .2, 'other': .15, 'leisure': .1} if not SAT else {'work': .18, 'shop': .45, 'other': .12, 'leisure': .25})
for k, g in enumerate(GW):
    if not (g['in'] and g['out']): continue
    v_local = g['vol'] * GWSCALE * dayf * (1 - g['through'])
    n_vis = int(max(0, (v_local - 2 * ext_use[k]) / 2))
    for purp, sh in vis_mix.items():
        n = int(round(n_vis * sh));
        if n == 0: continue
        _, dep, dwell, beta, _ = P[purp]
        t0 = mix(dep, n) - 0.1; dw = np.exp(rng.normal(np.log(dwell[0] if purp != 'school' else 1), dwell[1], n))
        A = zone_w(purp)
        pr = A * np.exp(-beta * 0.7 * TGZ[k]); pr[TGZ[k] >= 999] = 0
        if pr.sum() <= 0: continue
        pr /= pr.sum()
        dz = rng.choice(NZ, size=n, p=pr)
        for i in range(n):
            de = edge_in_zone(dz[i], purp if purp != 'leisure' else 'shop')
            add(t0[i], g['in'][0], de, 'car', 'visitor')
            add(t0[i] + dw[i] + 0.3, de, g['out'][0], 'car', 'visitor')

# ------------------------------------------------------------- through traffic (gateway -> gateway)
thr_prof = ([(8.0, 1.5, .22), (12.5, 2.6, .33), (17.6, 1.5, .27), (21.0, 2.0, .11), (3.0, 2.0, .07)] if not SAT else
            [(10.5, 2.0, .35), (14.5, 2.5, .3), (18.0, 2.0, .25), (22.0, 2.0, .1)])
thr = np.array([g['vol'] * GWSCALE * dayf * g['through'] / 2 for g in GW])   # one-directional starts per gateway
mot = [k for k, g in enumerate(GW) if g['type'] == 'highway.motorway']
for k, g in enumerate(GW):
    n = int(round(thr[k]))
    if n == 0 or not g['in']: continue
    if g['type'] == 'highway.motorway':
        dest = [m for m in mot if m != k and GW[m]['out']]
    else:
        dest = [m for m in range(len(GW)) if m != k and GW[m]['out'] and GW[m]['vol'] >= 3000 and math.dist(GW[m]['lonlat'], g['lonlat']) > 0.05]
    w = np.array([thr[m] for m in dest]); w /= w.sum()
    dd = rng.choice(dest, size=n, p=w); t0 = mix(thr_prof, n)
    for i in range(n):
        vt = 'truck' if rng.random() < (0.14 if g['type'] == 'highway.motorway' else 0.05) * (0.4 if SAT else 1) else 'car'
        add(t0[i], g['in'][0], GW[dd[i]]['out'][0], vt, 'through')

# ------------------------------------------------------------- trucks / vans (local + external)
ntr = int(len(trips) * (0.06 if not SAT else 0.025))
At = zone_w('truck'); pt = At / At.sum()
t0 = mix([(9.0, 2.0, .55), (14.5, 2.0, .4), (5.5, 1.0, .05)], ntr)
gwp = np.array([g['vol'] if g['type'] in ('highway.motorway', 'highway.primary') and g['in'] and g['out'] else 0 for g in GW], float); gwp /= gwp.sum()
for i in range(ntr):
    vt = 'truck' if rng.random() < 0.45 else 'van'
    zi = rng.choice(NZ, p=pt)
    if rng.random() < 0.55:
        k = rng.choice(len(GW), p=gwp)
        if rng.random() < 0.5: add(t0[i], GW[k]['in'][0], edge_in_zone(zi, 'truck'), vt, 'freight')
        else: add(t0[i], edge_in_zone(zi, 'truck'), GW[k]['out'][0], vt, 'freight')
    else:
        pr = At * np.exp(-0.06 * T[zi]); pr[T[zi] >= 999] = 0; pr /= pr.sum()
        add(t0[i], edge_in_zone(zi, 'truck'), edge_in_zone(rng.choice(NZ, p=pr), 'truck'), vt, 'freight')

# ------------------------------------------------------------- ZTL permit traffic (residents inside walls, taxis, deliveries)
zt = D['ztl_edges']
n_ztl = int((2500 if not SAT else 2200) * SCALE)
Ao = zone_w('other'); po = Ao / Ao.sum()
t0 = mix([(8.0, 1.2, .35), (11.0, 1.5, .25), (16.5, 1.5, .3), (19.5, 1.2, .1)], n_ztl)
for i in range(n_ztl):
    ze = zt[rng.integers(len(zt))]; oz = edge_in_zone(rng.choice(NZ, p=po), 'other')
    dw = np.exp(rng.normal(np.log(1.5), 0.6))
    if rng.random() < 0.6: add(t0[i], ze, oz, 'ztl', 'ztl'); add(t0[i] + dw, oz, ze, 'ztl', 'ztl')
    else: add(t0[i], oz, ze, 'ztl', 'ztl'); add(t0[i] + 0.3 * dw, ze, oz, 'ztl', 'ztl')

# ------------------------------------------------------------- write
trips = [t for t in trips if t[0] < 86400 + 1800]
trips.sort(key=lambda t: t[0])
tags = collections.Counter(t[4] for t in trips)
with gzip.open(DEMAND / f'{day}.trips.xml.gz', 'wt') as f:
    f.write('<routes>\n')
    f.write('  <vType id="car" vClass="passenger" length="4.4" minGap="2.0" speedFactor="normc(1,0.1,0.75,1.25)" sigma="0.3" impatience="0.5" color="0.85,0.85,0.9"/>\n')
    f.write('  <vType id="van" vClass="delivery" length="5.6" minGap="2.5" speedFactor="normc(0.95,0.08,0.75,1.2)" color="0.95,0.75,0.3"/>\n')
    f.write('  <vType id="truck" vClass="truck" length="11.0" minGap="3.0" maxSpeed="25" accel="1.1" speedFactor="normc(0.92,0.05,0.8,1.05)" color="0.9,0.45,0.2"/>\n')
    f.write('  <vType id="ztl" vClass="custom1" guiShape="passenger" length="4.3" minGap="2.0" sigma="0.3" speedFactor="normc(1,0.1,0.75,1.2)" color="0.4,0.8,1"/>\n')
    for i, (t, fe, te, vt, tag) in enumerate(trips):
        f.write(f'  <trip id="{tag}{i}" type="{vt}" depart="{t:.0f}" from="{fe}" to="{te}" departLane="best" departSpeed="max" departPos="random_free" arrivalPos="random"/>\n')
    f.write('</routes>\n')
hist = np.histogram([t[0] / 3600 for t in trips], bins=24, range=(0, 24))[0]
print(day, 'trips', len(trips), dict(tags))
print('hourly %', np.round(hist / hist.sum() * 100, 1).tolist())
