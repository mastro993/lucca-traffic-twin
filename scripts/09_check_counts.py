"""Compare simulated weekday daily 2-way volumes with observed counts. Output: results/calibration.json
usage: python3 scripts/09_check_counts.py [weekday]"""
import sys, collections, math
import numpy as np, sumolib
from lxml import etree
sys.path.insert(0, __import__('os').path.dirname(__file__))
from common import NET, RESULTS, zopen, read_net
day = sys.argv[1] if len(sys.argv) > 1 else 'weekday'
net = read_net(NET)
flows = collections.Counter(); hourly = collections.defaultdict(lambda: np.zeros(25))
for ev, el in etree.iterparse(zopen(RESULTS / day / 'edgedata_hourly.xml.gz', 'rb'), tag='interval'):
    h = int(float(el.get('begin')) // 3600)
    for e in el:
        n = float(e.get('entered', e.get('left', 0)) or 0)
        flows[e.get('id')] += n; hourly[e.get('id')][h] += n
    el.clear()

def reverse(e):
    for o in e.getToNode().getOutgoing():
        if o.getToNode() == e.getFromNode(): return o
    return None

def section(lon, lat, name=None, r=200):
    x, y = net.convertLonLat2XY(lon, lat)
    best = None
    for e, d in net.getNeighboringEdges(x, y, r):
        if name and name.lower() not in e.getName().lower(): continue
        if not e.allows('passenger'): continue
        if best is None or d < best[1]: best = (e, d)
    if best is None: return None
    e = best[0]; rv = reverse(e)
    ids = [e.getID()] + ([rv.getID()] if rv else [])
    return ids, e.getName()

def at_name(name, frac=0.5, near=None):
    es = [e for e in net.getEdges() if e.getName() == name and e.allows('passenger')]
    if near:
        x, y = net.convertLonLat2XY(*near)
        es.sort(key=lambda e: math.dist(e.getShape()[len(e.getShape()) // 2], (x, y)))
        e = es[0]
    else:
        e = sorted(es, key=lambda e: -flows[e.getID()])[int(len(es) * frac)]
    rv = reverse(e)
    return [e.getID()] + ([rv.getID()] if rv else []), name

def xsec(lon, lat, name=None, r=45, corridor=False, east_of=None):
    """2-way flow at a cross-section: edges passing within r m of the point, max per direction, summed.
    corridor=True: max 2-way flow over all sections of the named road (east_of: lon threshold)."""
    if corridor:
        best = (0, None)
        es = [e for e in net.getEdges() if e.getName() == name and e.allows('passenger')]
        for e in es:
            x, y = e.getShape()[len(e.getShape()) // 2]
            lo, la = net.convertXY2LonLat(x, y)
            if east_of and lo < east_of: continue
            v = xsec(lo, la, name, r)
            if v and v[0] > best[0]: best = (v[0], v[1], (round(lo, 4), round(la, 4)))
        return best
    x, y = net.convertLonLat2XY(lon, lat)
    cands = [(e, d) for e, d in net.getNeighboringEdges(x, y, r) if e.allows('passenger') and (name is None or e.getName() == name)]
    if not cands: return None
    e0 = min(cands, key=lambda c: c[1])[0]
    def heading(e):
        s = e.getShape(); return math.atan2(s[-1][1] - s[0][1], s[-1][0] - s[0][0])
    h0 = heading(e0); fw, bw = [], []
    for e, d in cands:
        if e.getName() != e0.getName(): continue
        (fw if math.cos(heading(e) - h0) > 0 else bw).append(e)
    f = max([flows[e.getID()] for e in fw] or [0]); b = max([flows[e.getID()] for e in bw] or [0])
    ids = [max(fw, key=lambda e: flows[e.getID()]).getID()] + ([max(bw, key=lambda e: flows[e.getID()]).getID()] if bw else [])
    return f + b, ids

COUNTS = [  # label, locator, observed weekday 2-way, source
    ('SR439 Via Sarzanese, Ponte S. Pietro (P058)', lambda: xsec(10.4387, 43.8568, 'Via Sarzanese', 80), 14500, 'Regione Toscana P058 2019/2021'),
    ('SS12 Brennero north of Lucca', lambda: xsec(10.5259, 43.8714, 'Strada Statale 12 dell&apos;Abetone e del Brennero', 60), 19068, 'NEPA/ANAS 2017'),
    ('SR435 Via Pesciatina (Antraccoli)', lambda: xsec(10.5426, 43.8528, 'Via Pesciatina', 60), 15272, 'NEPA/ANAS 2017'),
    ('Viale Europa (Capannori, corridor max)', lambda: xsec(0, 0, 'Viale Europa', 45, True, 10.52), 21062, 'NEPA/ANAS 2017'),
    ('Via Romana (east, corridor max)', lambda: xsec(0, 0, 'Via Romana', 45, True, 10.52), 24140, 'NEPA/ANAS 2017'),
]
print(f'{"section":48s} {"sim":>8s} {"obs":>8s} {"ratio":>6s}')
res = []
for label, loc, obs, src in COUNTS:
    s = loc()
    if not s or not s[0]: print(label, 'NOT FOUND'); continue
    sim, ids = s[0], s[1]; nm = s[2] if len(s) > 2 else ''
    res.append((label, sim, obs, src))
    pk = sum(hourly[i] for i in ids)
    print(f'{label:48s} {sim:8.0f} {obs:8d} {sim/obs:6.2f}  [{nm}] peak h={int(np.argmax(pk[:24]))} share={pk.max()/max(sim,1):.3f} ids={ids}')
geh = [math.sqrt(2 * (s / 10 - o / 10) ** 2 / (s / 10 + o / 10)) for _, s, o, _ in res]  # GEH on hourly-average basis
print('mean ratio', np.mean([s / o for _, s, o, _ in res]), 'GEH(avg hourly, /10)', np.round(geh, 2))
# Viale Carducci AM peak (approach to Porta Sant'Anna roundabout)
car = [e for e in net.getEdges() if 'Carducci' in e.getName() and e.allows('passenger')]
print('Viale Carducci edges AM 7-10 avg/h per edge (max):', max(hourly[e.getID()][7:10].mean() for e in car))

NAMES = {'SR439 Via Sarzanese, Ponte S. Pietro (P058)': 'SR439 Via Sarzanese at Ponte San Pietro (station P058)',
         'SS12 Brennero north of Lucca': 'SS12 Brennero, north of Lucca', 'SR435 Via Pesciatina (Antraccoli)': 'SR435 Via Pesciatina at Antraccoli',
         'Viale Europa (Capannori, corridor max)': 'Viale Europa, Capannori (busiest section)', 'Via Romana (east, corridor max)': 'Via Romana, east (busiest section)'}
SRCS = {'Regione Toscana P058 2019/2021': 'Regione Toscana, 2019 and 2021 average', 'NEPA/ANAS 2017': 'NEPA/ANAS counts, 2017'}
import json
json.dump([{'label': NAMES.get(l, l), 'sim': round(s), 'obs': o, 'src': SRCS.get(src, src)} for l, s, o, src in res], open(RESULTS / ('calibration.json' if day == 'weekday' else f'calibration_{day}.json'), 'w'), indent=1)
