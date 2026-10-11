"""Export static 3D scene geometry (roads, buildings, land cover, water, walls, rail, place labels) for the viewer.
All coordinates are local metres relative to ORIGIN (Piazza San Michele) in the SUMO/UTM frame.
Output: public/data/static.json + build/web/static.bin (packed later by 11_pack_web.py), build/edge_ids.json.
usage: python3 scripts/06_export_static.py"""
import sys, json, pickle, struct, collections, math
import numpy as np, sumolib
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, box
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from osm_extract import load
from common import NET, OMT_GEO, OSM_ROADS, WEBRAW, WEBDATA, EDGE_IDS, BBOX, ORIGIN, read_net

import os
WEBDATA.mkdir(parents=True, exist_ok=True)
net = read_net(NET)
LON0, LAT0 = ORIGIN
X0, Y0 = net.convertLonLat2XY(LON0, LAT0)
bx0, by0 = net.convertLonLat2XY(BBOX[1], BBOX[0]); bx1, by1 = net.convertLonLat2XY(BBOX[3], BBOX[2])
CLIP = box(bx0, by0, bx1, by1)

def loc(pts):
    return [(round(x - X0, 1), round(y - Y0, 1)) for x, y in pts]

class Bin:
    """Accumulates typed arrays into one binary blob with a JSON index."""
    def __init__(self): self.parts = []; self.index = {}; self.off = 0
    def add(self, name, arr):
        arr = np.ascontiguousarray(arr); b = arr.tobytes()
        pad = (-self.off) % 8
        if pad: self.parts.append(b'\0' * pad); self.off += pad
        self.index[name] = {'offset': self.off, 'length': int(arr.size), 'dtype': str(arr.dtype)}
        self.parts.append(b); self.off += len(b)
    def write(self, path):
        open(path, 'wb').write(b''.join(self.parts)); return self.index

B = Bin(); meta = {'origin': [LON0, LAT0], 'bbox_local': [bx0 - X0, by0 - Y0, bx1 - X0, by1 - Y0]}

def polys_to_arrays(polys, extra=None):
    pos, starts, ext = [], [], []
    for k, p in enumerate(polys):
        ring = list(orient(p, 1.0).exterior.coords)
        starts.append(len(pos) // 2)
        for x, y in ring: pos += [x - X0, y - Y0]
        if extra is not None: ext += [extra[k]] * len(ring)
    starts.append(len(pos) // 2)
    return np.array(pos, np.float32), np.array(starts, np.uint32), (np.array(ext, np.float32) if extra is not None else None)

def explode(g):
    if g.is_empty: return []
    if g.geom_type == 'Polygon': return [g]
    if hasattr(g, 'geoms'): return [x for gg in g.geoms for x in explode(gg)]
    return []

geo = pickle.load(open(OMT_GEO, 'rb'))

# ---------------- buildings
bpolys, bh = [], []
for g, p in geo['building']:
    h = float(p.get('render_height') or 6); hmin = float(p.get('render_min_height') or 0)
    for part in explode(g):
        if part.area < 12: continue
        part = part.simplify(0.4, preserve_topology=True)
        if part.is_empty or part.geom_type != 'Polygon': continue
        bpolys.append(part); bh.append(max(3.0, h))
pos, st, he = polys_to_arrays(bpolys, bh)
B.add('bld_pos', pos); B.add('bld_start', st); B.add('bld_h', he)
meta['buildings'] = len(bpolys)
print('buildings', len(bpolys), 'vertices', len(pos) // 2)

# ---------------- ground: land cover / land use / water / parks
GCLASS = {('landcover', 'farmland'): 1, ('landcover', 'grass'): 2, ('landcover', 'wood'): 3, ('landcover', 'wetland'): 2,
          ('landuse', 'residential'): 4, ('landuse', 'industrial'): 5, ('landuse', 'commercial'): 5, ('landuse', 'retail'): 5,
          ('landuse', 'school'): 6, ('landuse', 'hospital'): 6, ('landuse', 'university'): 6, ('landuse', 'cemetery'): 2,
          ('landuse', 'pitch'): 2, ('landuse', 'playground'): 2, ('landuse', 'railway'): 5, ('landuse', 'quarry'): 5,
          ('park', None): 2, ('water', 'river'): 9, ('water', 'lake'): 9, ('water', 'pond'): 9, ('water', 'dock'): 9, ('water', 'ocean'): 9}
gpolys, gcls = [], []
for L in ('landcover', 'landuse', 'park', 'water'):
    for g, p in geo.get(L, []):
        c = GCLASS.get((L, p.get('class'))) or GCLASS.get((L, None))
        if not c: continue
        for part in explode(g.intersection(CLIP)):
            if part.area < (60 if c != 9 else 20): continue
            part = part.simplify(1.0, preserve_topology=True)
            if part.is_empty or part.geom_type != 'Polygon': continue
            gpolys.append(part); gcls.append(c)
order = np.argsort([0 if c in (1, 3, 2) else (1 if c != 9 else 2) for c in gcls], kind='stable')
gpolys = [gpolys[i] for i in order]; gcls = [gcls[i] for i in order]
pos, st, cc = polys_to_arrays(gpolys, gcls)
B.add('gnd_pos', pos); B.add('gnd_start', st); B.add('gnd_cls', cc.astype(np.uint8))
print('ground polys', len(gpolys))

# waterways (canals, streams) as paths
wpos, wst, ww = [], [], []
for g, p in geo.get('waterway', []):
    c = p.get('class')
    if c not in ('river', 'canal', 'stream'): continue
    for ln in (g.geoms if hasattr(g, 'geoms') else [g]):
        if ln.geom_type != 'LineString' or ln.length < 40: continue
        ln = ln.simplify(1.5)
        wst.append(len(wpos) // 2)
        for x, y in ln.coords: wpos += [x - X0, y - Y0]
        ww.append({'river': 14, 'canal': 5, 'stream': 2.5}[c])
wst.append(len(wpos) // 2)
B.add('ww_pos', np.array(wpos, np.float32)); B.add('ww_start', np.array(wst, np.uint32)); B.add('ww_w', np.array(ww, np.float32))

# ---------------- walls, rail, place labels from OSM
nodes, ways, rels = load([OSM_ROADS])
wall_lines, rail_lines = [], []
for wid, (nds, tags) in ways.items():
    pts = [net.convertLonLat2XY(nodes[n][0], nodes[n][1]) for n in nds if n in nodes]
    if len(pts) < 2: continue
    if tags.get('barrier') == 'city_wall' or (tags.get('historic') == 'citywalls' and tags.get('barrier') != 'retaining_wall'):
        wall_lines.append(LineString(pts))
    if tags.get('railway') == 'rail' and tags.get('service') not in ('yard', 'siding', 'spur'):
        rail_lines.append(LineString(pts))
walls = unary_union([l.buffer(9, cap_style=2, join_style=2) for l in wall_lines]).simplify(0.8)
wpolys = explode(walls)
pos, st, _ = polys_to_arrays(wpolys)
B.add('wall_pos', pos); B.add('wall_start', st)
rpos, rst = [], []
for l in rail_lines:
    l = l.intersection(CLIP)
    for s in (l.geoms if hasattr(l, 'geoms') else [l]):
        if s.geom_type != 'LineString' or s.length < 20: continue
        rst.append(len(rpos) // 2)
        for x, y in s.simplify(1.0).coords: rpos += [x - X0, y - Y0]
rst.append(len(rpos) // 2)
B.add('rail_pos', np.array(rpos, np.float32)); B.add('rail_start', np.array(rst, np.uint32))
labels = []
for nid, (lon, lat, tags) in nodes.items():
    pl = tags.get('place')
    if pl in ('city', 'town', 'suburb', 'village', 'quarter') and tags.get('name'):
        x, y = net.convertLonLat2XY(lon, lat)
        if CLIP.contains(LineString([(x, y), (x + 1, y)]).centroid):
            labels.append({'n': tags['name'], 'p': [round(x - X0), round(y - Y0)], 'k': pl})
meta['places'] = labels
print('walls polys', len(wpolys), 'rail', len(rst) - 1, 'labels', len(labels))

# ---------------- roads = simulated edges
ROADCLS = {'highway.motorway': 0, 'highway.motorway_link': 1, 'highway.trunk': 1, 'highway.primary': 2, 'highway.primary_link': 2,
           'highway.secondary': 3, 'highway.secondary_link': 3, 'highway.tertiary': 4, 'highway.tertiary_link': 4,
           'highway.unclassified': 5, 'highway.residential': 6}
edges = [e for e in net.getEdges() if e.getFunction() != 'internal']
names = sorted(set(e.getName().replace('&apos;', "'") for e in edges))
nidx = {n: i for i, n in enumerate(names)}
epos, est, elanes, ecls, ename, elen, espeed, eztl = [], [], [], [], [], [], [], []
edge_ids = []
for e in edges:
    shp = e.getShape()
    # offset the centreline to the right-hand side so the two directions render side by side
    has_rev = any(o.getToNode() == e.getFromNode() for o in e.getToNode().getOutgoing())
    if has_rev and len(shp) >= 2:
        try:
            oc = LineString(shp).offset_curve(-(e.getLaneNumber() * 3.2 / 2 + 0.4), join_style=2, mitre_limit=3)
            if oc.geom_type == 'LineString' and len(oc.coords) >= 2: shp = list(oc.coords)
        except Exception: pass
    est.append(len(epos) // 2)
    for x, y in shp: epos += [x - X0, y - Y0]
    elanes.append(e.getLaneNumber()); ecls.append(ROADCLS.get(e.getType(), 7)); ename.append(nidx[e.getName().replace('&apos;', "'")])
    elen.append(e.getLength()); espeed.append(e.getSpeed()); eztl.append(0 if e.allows('passenger') else 1)
    edge_ids.append(e.getID())
est.append(len(epos) // 2)
B.add('road_pos', np.array(epos, np.float32)); B.add('road_start', np.array(est, np.uint32))
B.add('road_lanes', np.array(elanes, np.uint8)); B.add('road_cls', np.array(ecls, np.uint8)); B.add('road_name', np.array(ename, np.uint16))
B.add('road_len', np.array(elen, np.float32)); B.add('road_speed', np.array(espeed, np.float32)); B.add('road_ztl', np.array(eztl, np.uint8))
meta['road_names'] = names; meta['roads'] = len(edges)

# ---------------- traffic signals: each fixed-time program, one head over every controlled lane at its stop line, and
# one pole per approach at the right kerb with an arm reaching over its lanes. Headings are degrees clockwise from north.
tnet = sumolib.net.readNet(str(NET), withPrograms=True)
prog, heads, poles = [], [], []
for k, tl in enumerate(tnet.getTrafficLights()):
    p = next(iter(tl.getPrograms().values()))
    prog.append({'o': int(float(p._offset)), 'p': [[int(ph.duration), ph.state] for ph in p.getPhases()]})
    links = collections.defaultdict(list)
    for lane, _, li in tl.getConnections(): links[lane].append(li)
    approaches = collections.defaultdict(list)
    for lane in links: approaches[lane.getEdge()].append(lane)
    for lanes in approaches.values():
        lanes.sort(key=lambda l: l.getIndex())   # index 0 = rightmost lane
        for lane in lanes:
            (x0, y0), (x1, y1) = lane.getShape()[-2:]
            ang = math.degrees(math.atan2(x1 - x0, y1 - y0))
            heads.append({'t': k, 'l': sorted(links[lane]), 'p': [round(x1 - X0, 2), round(y1 - Y0, 2)], 'a': round(ang, 1)})
        right, left = heads[-len(lanes)], heads[-1]
        a = math.radians(right['a']); rx, ry = math.cos(a), -math.sin(a)   # unit vector to the right of the heading
        off = lanes[0].getWidth() / 2 + 0.8
        px, py = right['p'][0] + rx * off, right['p'][1] + ry * off
        reach = math.hypot(left['p'][0] - px, left['p'][1] - py)
        poles.append({'p': [round(px, 2), round(py, 2)], 'a': right['a'], 'r': round(reach, 2)})
meta['tls'] = {'prog': prog, 'heads': heads, 'poles': poles}
print('traffic signals', len(prog), 'heads', len(heads), 'poles', len(poles))
idx = B.write(WEBRAW / 'static.bin'); meta['index'] = idx
json.dump(meta, open(WEBDATA / 'static.json', 'w'), separators=(',', ':'), ensure_ascii=False)
json.dump(edge_ids, open(EDGE_IDS, 'w'))
print('roads', len(edges), 'static.bin MB', os.path.getsize(WEBRAW / 'static.bin') / 1e6)
