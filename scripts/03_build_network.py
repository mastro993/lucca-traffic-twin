"""Build the SUMO network from OpenStreetMap: convert, clip to the study area, close the ZTL inside the Walls,
set urban/rural speed limits from building density, and turn right-before-left junctions into priority junctions.
Output: network/lucca.net.xml.gz (+ the patch files in network/patches/).
usage: python3 scripts/03_build_network.py"""
import json, subprocess, pickle, sys, hashlib
import sumolib
import numpy as np
from shapely.geometry import MultiPoint, LineString
from scipy.spatial import cKDTree
from common import BUILD, NETDIR, NET, OSM_ROADS, BBOX, sumo_bin, sumo_home, read_net
from osm_extract import load
import tiles_to_geo

P = NETDIR / 'patches'; P.mkdir(parents=True, exist_ok=True)
S, W, N, E = BBOX
KEEP = ['--output.street-names', '--output.original-names']
# Fixed-time signal plans with Italian standard timings (real plans are not public): 4 s amber, the usual urban value
# (MIT note 67906/2007: never under 3 s; 3/4/5 s for 50/60/70 km/h approaches), 2 s all-red clearance, 70 s cycle.
# Fixed-time plans are deterministic, so the viewer can show each light's state from the program alone.
TLS = ['--tls.default-type', 'static', '--tls.cycle.time', '70', '--tls.yellow.time', '4', '--tls.allred.time', '2']

def nc(*args):
    print('netconvert', ' '.join(map(str, args))[:160], '...')
    subprocess.run([sumo_bin('netconvert'), *map(str, args), '--no-warnings'], check=True)

# 1. OSM -> SUMO. Signalised pedestrian crossings keep their own signals: joined into one, netconvert gives every
# movement of the group its own phase (three crossings on Viale Marti got a 222 s cycle)
nodes, ways, rels = load([OSM_ROADS])
crossings = sorted(str(i) for i, (_, _, tags) in nodes.items() if tags.get('highway') == 'crossing' and tags.get('crossing') == 'traffic_signals')
raw, clip = BUILD / 'lucca_raw.net.xml', BUILD / 'lucca_clip.net.xml'
nc('--osm-files', OSM_ROADS, '-o', raw, '--type-files', f'{sumo_home()}/data/typemap/osmNetconvert.typ.xml',
   '--keep-edges.by-vclass', 'passenger',
   '--remove-edges.by-type', 'highway.track,highway.service,highway.services,highway.path,highway.bridleway,highway.unsurfaced,highway.living_street',
   '--geometry.remove', '--ramps.guess', '--junctions.join', '--junctions.join-dist', '12', '--roundabouts.guess', '--edges.join',
   '--tls.guess-signals', '--tls.discard-simple', '--tls.join', '--tls.join-exclude', ','.join(crossings), *TLS, '--junctions.corner-detail', '5',
   '--osm.turn-lanes', '--no-turnarounds.except-deadend', '--keep-edges.components', '1', '--remove-edges.isolated', '--proj.utm', *KEEP)
# 2. clip to the study area
nc('-s', raw, '--keep-edges.in-geo-boundary', f'{W},{S},{E},{N}', '--keep-edges.components', '1', '-o', clip, *KEEP)

# 3. ZTL: links inside the Walls (convex hull of the OSM wall ways) only for permit holders, taxis, buses, deliveries
net = read_net(clip)
pts = [net.convertLonLat2XY(nodes[n][0], nodes[n][1]) for wid, (nds, tags) in ways.items()
       if tags.get('historic') == 'citywalls' or tags.get('barrier') == 'city_wall' for n in nds if n in nodes]
hull = MultiPoint(pts).convex_hull; inner = hull.buffer(-5)
ztl = [e.getID() for e in net.getEdges() if inner.contains(LineString(e.getShape()))
       and not e.getName().lower().startswith(('viale', 'rotatoria'))]
with open(P / 'ztl.edg.xml', 'w') as f:
    f.write('<edges>\n' + ''.join(f'  <edge id="{i}" allow="custom1 delivery taxi bus emergency authority bicycle pedestrian"/>\n' for i in ztl) + '</edges>\n')
json.dump({'hull': list(hull.exterior.coords), 'ztl_edges': ztl}, open(P / 'ztl.json', 'w'))
ztlnet = BUILD / 'lucca_ztl.net.xml'
nc('-s', clip, '-e', P / 'ztl.edg.xml', '-o', ztlnet, *KEEP)
print('ZTL links', len(ztl))

# 4. decode building / land-use tiles into the network frame (needed for speeds, zones and the viewer)
tiles_to_geo.main(ztlnet)

# 5. speed limits: 50 km/h where building density is urban, 60-90 km/h outside, 30 km/h in the ZTL, 130/60 on the motorway
net = read_net(ztlnet)
geo = pickle.load(open(BUILD / 'omt_geo.pkl', 'rb'))
polys = [part for g, p in geo['building'] for part in (g.geoms if hasattr(g, 'geoms') else [g]) if part.geom_type == 'Polygon' and part.area > 15]
cent = np.array([[q.centroid.x, q.centroid.y] for q in polys]); area = np.array([q.area for q in polys]); kd = cKDTree(cent)
out = []
for e in net.getEdges():
    t, v = e.getType(), e.getSpeed()
    if 'motorway' in t:
        nv = min(v, 130 / 3.6) if t == 'highway.motorway' else min(v, 60 / 3.6)
    else:
        shp = e.getShape(); idx = kd.query_ball_point(shp[len(shp) // 2], 120)
        dens = area[idx].sum() / (np.pi * 120 * 120) if idx else 0
        if not e.allows('passenger'): nv = min(v, 30 / 3.6)
        elif dens > 0.06: nv = min(v, 50 / 3.6)
        else: nv = min(v, {'highway.primary': 90, 'highway.secondary': 90, 'highway.tertiary': 70, 'highway.unclassified': 60, 'highway.residential': 50}.get(t, 70) / 3.6)
    if abs(nv - v) > 0.1: out.append((e.getID(), nv))
with open(P / 'speed.edg.xml', 'w') as f:
    f.write('<edges>\n' + ''.join(f'  <edge id="{i}" speed="{v:.2f}"/>\n' for i, v in out) + '</edges>\n')
spdnet = BUILD / 'lucca_speed.net.xml'
nc('-s', ztlnet, '-e', P / 'speed.edg.xml', '-o', spdnet, *KEEP)

# 6. right-before-left junctions block main roads in SUMO (e.g. after toll plazas): make them priority junctions
net = read_net(spdnet)
rbl = [n.getID() for n in net.getNodes() if n.getType() in ('right_before_left', 'left_before_right')]
with open(P / 'rbl.nod.xml', 'w') as f:
    f.write('<nodes>\n' + ''.join(f'  <node id="{i}" type="priority"/>\n' for i in rbl) + '</nodes>\n')
# 7. uncoordinated signals: each plan starts at its own fixed offset (from a hash of its id) instead of all switching together
tnet = sumolib.net.readNet(str(spdnet), withPrograms=True)
with open(P / 'offsets.tll.xml', 'w') as f:
    f.write('<tlLogics>\n')
    for tl in tnet.getTrafficLights():
        p = next(iter(tl.getPrograms().values())); phases = p.getPhases()
        off = int(hashlib.md5(tl.getID().encode()).hexdigest(), 16) % sum(ph.duration for ph in phases)
        f.write(f'  <tlLogic id="{tl.getID()}" type="static" programID="{p._id}" offset="{off}">\n'
                + ''.join(f'    <phase duration="{ph.duration}" state="{ph.state}"/>\n' for ph in phases) + '  </tlLogic>\n')
    f.write('</tlLogics>\n')
nc('-s', spdnet, '-n', P / 'rbl.nod.xml', '--tllogic-files', P / 'offsets.tll.xml', '-o', NET, *KEEP)
net = read_net(NET)
print('final network', NET, 'edges', len(net.getEdges()), 'nodes', len(net.getNodes()), 'signals', len(net.getTrafficLights()))
