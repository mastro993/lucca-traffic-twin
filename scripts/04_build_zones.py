"""Build trip-end weights per edge (from building volume and land use), 700 m zones, the 62 boundary gateways
with their daily volumes, and the zone travel-time matrix. Output: build/zones.pkl.
usage: python3 scripts/04_build_zones.py"""
import sys, pickle, json, math, collections
import numpy as np, sumolib
from shapely.geometry import Point, LineString, Polygon, shape
from shapely.strtree import STRtree
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from osm_extract import load
from common import NET, OMT_GEO, OSM_ROADS, NETDIR, ZONES, BBOX, read_net

net = read_net(NET)
geo = pickle.load(open(OMT_GEO, 'rb'))
ztl = json.load(open(NETDIR / 'patches' / 'ztl.json'))
hull = Polygon(ztl['hull'])

# ---------- candidate trip-end edges
round_edges = set()
for r in net.getRoundabouts(): round_edges.update(r.getEdges())
cand = [e for e in net.getEdges() if e.allows('passenger') and 'motorway' not in e.getType() and '_link' not in e.getType()
        and e.getLength() >= 15 and e.getID() not in round_edges]
ztl_edges = [net.getEdge(i) for i in ztl['ztl_edges'] if net.getEdge(i).getLength() >= 10]
print('candidate edges', len(cand), 'ztl edges', len(ztl_edges))
lines = [LineString(e.getShape()) for e in cand]
tree = STRtree(lines)

# ---------- landuse classes
lu_polys, lu_cls = [], []
for g, p in geo['landuse']:
    c = p.get('class')
    if c in ('industrial', 'commercial', 'retail', 'school', 'hospital', 'university', 'college', 'kindergarten', 'residential', 'railway', 'cemetery'):
        for part in (g.geoms if hasattr(g, 'geoms') else [g]):
            if part.geom_type == 'Polygon': lu_polys.append(part); lu_cls.append(c)
lu_tree = STRtree(lu_polys)

# ---------- buildings -> edges
W = collections.defaultdict(lambda: collections.Counter())  # edge id -> {res, work, shop, school, centre}
centre_attr = collections.Counter()
nb = 0
for g, p in geo['building']:
    h = p.get('render_height') or 6
    floors = max(1, round(h / 3.2))
    for part in (g.geoms if hasattr(g, 'geoms') else [g]):
        if part.geom_type != 'Polygon' or part.area < 25: continue
        nb += 1
        c = part.centroid
        vol = part.area * floors
        cls = 'residential'
        for k in lu_tree.query(c, predicate='within'):
            cls = lu_cls[k]
            if cls != 'residential': break
        if hull.contains(c):
            # walled centre: mixed use -> residents (ZTL permits) + strong attraction (shops, offices, tourism)
            centre_attr['res'] += vol * 0.5; centre_attr['attr'] += vol * 0.5
            continue
        i = tree.query_nearest(c, max_distance=250)
        if len(i) == 0: continue
        eid = cand[int(i[0])].getID()
        if cls == 'residential':
            W[eid]['res'] += vol * (0.85 if part.area < 800 else 0.6)
            W[eid]['work'] += vol * (0.15 if part.area < 800 else 0.4)   # ground-floor shops / large mixed buildings
            W[eid]['shop'] += vol * 0.05
        elif cls in ('industrial',):
            W[eid]['work'] += vol * 0.6;  W[eid]['truck'] += vol
        elif cls in ('commercial', 'retail'):
            W[eid]['work'] += vol * 1.0; W[eid]['shop'] += vol * 1.5; W[eid]['truck'] += vol * 0.3
        elif cls in ('school', 'university', 'college', 'kindergarten'):
            W[eid]['school'] += vol; W[eid]['work'] += vol * 0.3
        elif cls == 'hospital':
            W[eid]['work'] += vol * 1.5; W[eid]['shop'] += vol * 0.8
        else:
            W[eid]['res'] += vol * 0.3
print('buildings used', nb, 'centre', centre_attr)

# ---------- car parks around the walls receive the centre attraction
nodes, ways, rels = load([OSM_ROADS])
parks = []
for wid, (nds, tags) in ways.items():
    if tags.get('amenity') == 'parking' and len(nds) > 3 and nds[0] == nds[-1]:
        pts = [net.convertLonLat2XY(nodes[n][0], nodes[n][1]) for n in nds if n in nodes]
        if len(pts) < 4: continue
        pg = Polygon(pts)
        if not pg.is_valid or pg.area < 600: continue
        d = hull.exterior.distance(pg.centroid)
        if d < 650 and not hull.contains(pg.centroid):
            parks.append((pg, tags.get('name', ''), tags.get('capacity')))
print('car parks near walls', len(parks), sorted([(round(p.area), n) for p, n, c in parks], reverse=True)[:15])
tot_area = sum(p.area for p, n, c in parks)
park_list = []
for pg, name, cap in parks:
    i = tree.query_nearest(pg.centroid, max_distance=300)
    if len(i) == 0: continue
    eid = cand[int(i[0])].getID()
    share = pg.area / tot_area
    W[eid]['work'] += centre_attr['attr'] * 0.55 * share
    W[eid]['shop'] += centre_attr['attr'] * 1.6 * share
    W[eid]['park'] += share
    park_list.append((eid, name, share))

# ---------- zones (700 m grid)
x0, y0 = net.convertLonLat2XY(BBOX[1], BBOX[0]); x1, y1 = net.convertLonLat2XY(BBOX[3], BBOX[2])
G = 700.0
zone_of = {}
Z = collections.defaultdict(lambda: {'edges': [], 'res': 0, 'work': 0, 'shop': 0, 'school': 0, 'truck': 0})
for e in cand:
    w = W.get(e.getID())
    if not w: continue
    x, y = e.getShape()[len(e.getShape()) // 2]
    zid = f'z{int((x - x0) // G)}_{int((y - y0) // G)}'
    zone_of[e.getID()] = zid
    Z[zid]['edges'].append(e.getID())
    for k in ('res', 'work', 'shop', 'school', 'truck'): Z[zid][k] += w[k]
zones = sorted(Z)
print('zones', len(zones))

# ---------- gateways
GW_SPEC = {  # node-adjacent edge ids: (in_edge, out_edge, weekday 2-way daily volume, label, through_share, kind)
}
gateways = []
for n in net.getNodes():
    x, y = n.getCoord()
    d = min(x - x0, x1 - x, y - y0, y1 - y)
    inc = [e for e in n.getIncoming() if e.allows('passenger')]; out = [e for e in n.getOutgoing() if e.allows('passenger')]
    nbs = set([e.getFromNode().getID() for e in inc] + [e.getToNode().getID() for e in out])
    if d < 250 and len(nbs) == 1:
        e0 = (out or inc)[0]; t = e0.getType()
        if t == 'highway.residential': continue
        gateways.append({'node': n.getID(), 'type': t, 'name': e0.getName(), 'in': [e.getID() for e in out], 'out': [e.getID() for e in inc],
                         'lonlat': net.convertXY2LonLat(x, y)})
# merge motorway carriageways (one-way in/out nodes) and known pairs by name+proximity
merged = []
used = set()
for i, g in enumerate(gateways):
    if i in used: continue
    grp = [g]; used.add(i)
    for j, h in enumerate(gateways):
        if j in used: continue
        if h['name'] == g['name'] and math.dist(g['lonlat'], h['lonlat']) < 0.004:
            grp.append(h); used.add(j)
    merged.append({'name': g['name'], 'type': g['type'], 'in': sum([x['in'] for x in grp], []), 'out': sum([x['out'] for x in grp], []),
                   'lonlat': g['lonlat']})
# volumes (weekday, both directions) -- from counts where available, by class otherwise
def vol(g):
    n, t, (lon, lat) = g['name'], g['type'], g['lonlat']
    if t == 'highway.motorway':
        if 'Viareggio' in n: return 34000, 'A11 branch Viareggio', 0.70
        if lon < 10.45: return 26000, 'A11 to Pisa', 0.67
        return 60000, 'A11 to Firenze', 0.66
    if n == 'Via Sarzanese': return 10500, 'SR439 Sarzanese (Massarosa)', 0.10
    if n in ('Galleria Sesto',): return 11000, 'SS12 Brennero north (Serchio valley)', 0.15
    if n == 'Via Nazionale': return 5000, 'SS12 old road north', 0.10
    if n == 'Via Pesciatina': return 15000, 'SR435 Pesciatina (Porcari / Pescia)', 0.10
    if n == 'Via Nuova per Pisa': return 9000, 'Via Nuova per Pisa (San Giuliano)', 0.10
    if n == 'Via di Poggio II': return 3800, 'SR12 to Pisa via Ripafratta', 0.10
    if n == 'Strada Provinciale Lucca-Camaiore': return 7500, 'SP1 Lucca-Camaiore', 0.10
    if n == 'Via Ludovica': return 5000, 'Via Ludovica (Serchio valley)', 0.10
    if n == 'Via Roma': return 7000, 'Via Roma (Porcari)', 0.05
    if n == "Via di Sant'Andrea": return 4000, "Via di Sant'Andrea (Altopascio)", 0.05
    if t == 'highway.primary': return 8000, n, 0.05
    if t == 'highway.secondary': return 5000, n, 0.05
    if t == 'highway.tertiary': return 2000, n, 0.03
    return 400, n, 0.0
for g in merged:
    g['vol'], g['label'], g['through'] = vol(g)
merged = [g for g in merged if g['in'] or g['out']]
print('gateways', len(merged), 'total 2-way', sum(g['vol'] for g in merged))

# ---------- zone travel-time matrix (free-flow minutes)
nid = {n.getID(): k for k, n in enumerate(net.getNodes())}
rows, cols, data = [], [], []
for e in net.getEdges():
    if not e.allows('passenger') and not e.allows('custom1'): continue
    a, b = nid[e.getFromNode().getID()], nid[e.getToNode().getID()]
    rows.append(a); cols.append(b); data.append(e.getLength() / max(e.getSpeed() * 0.75, 3) + 6)  # +6 s junction penalty
M = csr_matrix((data, (rows, cols)), shape=(len(nid), len(nid)))
def zone_node(z):
    es = Z[z]['edges']; best = max(es, key=lambda i: W[i]['res'] + W[i]['work'])
    return nid[net.getEdge(best).getToNode().getID()]
zn = [zone_node(z) for z in zones]
gw_in_nodes = [nid[net.getEdge(g['in'][0]).getToNode().getID()] if g['in'] else None for g in merged]
gw_out_nodes = [nid[net.getEdge(g['out'][0]).getFromNode().getID()] if g['out'] else None for g in merged]
src = zn + [x for x in gw_in_nodes if x is not None]
D = dijkstra(M, directed=True, indices=src)
T_zz = D[:len(zn)][:, zn] / 60
# zone -> gateway out, gateway in -> zone
gin_idx = [k for k, x in enumerate(gw_in_nodes) if x is not None]
T_gz = {}
for r, k in enumerate(gin_idx): T_gz[k] = D[len(zn) + r][zn] / 60
T_zg = {k: D[:len(zn)][:, gw_out_nodes[k]] / 60 for k, x in enumerate(gw_out_nodes) if x is not None}
print('median zone tt', np.nanmedian(T_zz[np.isfinite(T_zz)]))
pickle.dump({'W': {k: dict(v) for k, v in W.items()}, 'Z': {k: dict(v) for k, v in Z.items()}, 'zones': zones, 'gateways': merged,
             'T_zz': T_zz, 'T_gz': T_gz, 'T_zg': T_zg, 'parks': park_list, 'centre': dict(centre_attr),
             'ztl_edges': [e.getID() for e in ztl_edges]}, open(ZONES, 'wb'))
for g in sorted(merged, key=lambda g: -g['vol'])[:16]: print(g['vol'], g['label'], g['in'], g['out'])
