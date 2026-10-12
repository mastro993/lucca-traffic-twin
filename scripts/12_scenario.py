"""Simulate a road-network scenario and compare it with a reference run of the unchanged network.
A scenario is a folder scenarios/<name>/ of netconvert patch files, applied on top of network/lucca.net.xml.gz:
  *.nod.xml  junctions (control type, e.g. traffic_light / priority / roundabout nodes)
  *.edg.xml  roads (lanes, speed, allow / disallow, or <delete id=.../>)
  *.con.xml  turning movements (<connection .../>, <delete .../>)
  *.tll.xml  signal plans (<tlLogic id=... type="static" programID="0" offset=...> with phases)
and optionally <day>.trips.xml.gz to replace the demand, and areas.json to report the comparison for parts of the network
too: {"label": {criteria}}, where a road belongs to the area when it meets all the criteria given:
  "near": [lat, lon, metres]                 comes within that distance of the point
  "bbox": [south, west, north, east]         its midpoint is inside the box
  "name" / "type" / "ref": "regex"           its street name, SUMO type (highway.primary, ...) or an OSM way's ref (^SS12$)
Trips are routed when they depart, so traffic finds its own way through the changed network.
The reference is the scenario `baseline` (no changes), run the same way, so both runs differ only in the scenario.
Output: build/scenarios/<name>.net.xml.gz, results/scenarios/<name>/<day>/ (as step 7) with comparison.json
(comparison_vs_<other>.json with BASE=<other>); scripts/tools/seed_summary.py sums up the comparisons of several seeds.
usage: python3 scripts/12_scenario.py baseline <weekday|saturday>   # the reference, once per day type and seed
       python3 scripts/12_scenario.py <name> <weekday|saturday>
       END=36000 python3 scripts/12_scenario.py <name> weekday   # until 10:00 only, compared over the same hours
       SEED=2 python3 scripts/12_scenario.py <name> weekday      # another random seed, in <day>_seed2/ (run baseline too)
       COMPARE=1 python3 scripts/12_scenario.py <name> weekday   # compare an existing run again
       BASE=<other> python3 scripts/12_scenario.py <name> weekday   # compare with another scenario"""
import os, re, sys, json, subprocess, collections
from lxml import etree
from sumolib.geomhelper import distancePointToPolygon, positionAtShapeOffset, polyLength
from common import ROOT, NET, RESULTS, BUILD, OSM_ROADS, zopen, read_net, run_stats, build_scenario_net

name, day = sys.argv[1], sys.argv[2]
src = ROOT / 'scenarios' / name
if not src.is_dir(): sys.exit(f'no scenario folder {src}')
net = BUILD / 'scenarios' / f'{name}.net.xml.gz'
out_dir = day + (f"_seed{os.environ['SEED']}" if os.environ.get('SEED') else '')
base_name = os.environ.get('BASE', 'baseline')
run, base = RESULTS / 'scenarios' / name / out_dir, RESULTS / 'scenarios' / base_name / out_dir

if os.environ.get('COMPARE') != '1':
    build_scenario_net(name)
    trips = src / f'{day}.trips.xml.gz'
    subprocess.run([sys.executable, str(ROOT / 'scripts' / '07_run_simulation.py'), day, *([str(trips)] if trips.exists() else [])],
                   check=True, env={**os.environ, 'NET': str(net), 'RUN_NAME': f'scenarios/{name}/{out_dir}'})

def edgedata(path):
    """Per hour and road: time lost (s), distance driven (m), vehicle-seconds on the road."""
    out = collections.defaultdict(dict)
    try:
        for _, el in etree.iterparse(zopen(path, 'rb'), tag='interval'):
            h = int(float(el.get('begin')) // 3600)
            for e in el: out[h][e.get('id')] = [float(e.get(a) or 0) for a in ('timeLoss', 'distance', 'sampledSeconds')]
            el.clear()
    except (etree.XMLSyntaxError, EOFError): pass   # a run still in progress
    return out

def in_area(e, n, a):
    shape = e.getShape()
    if 'near' in a and distancePointToPolygon(n.convertLonLat2XY(a['near'][1], a['near'][0]), shape) > a['near'][2]: return False
    if 'bbox' in a:
        lon, lat = n.convertXY2LonLat(*positionAtShapeOffset(shape, polyLength(shape) / 2))
        if not (a['bbox'][0] <= lat <= a['bbox'][2] and a['bbox'][1] <= lon <= a['bbox'][3]): return False
    for k, values in (('name', lambda: [e.getName().replace('&apos;', "'")]), ('type', lambda: [e.getType()]), ('ref', lambda: osm_refs(e))):
        if k in a and not any(re.search(a[k], v) for v in values()): return False
    return True

_refs = {}
def osm_refs(e):
    """OSM ref tags of the ways a road was built from (origId), one per way."""
    if not _refs:
        from osm_extract import load
        _refs.update((i, tags.get('ref', '')) for i, (_, tags) in load([OSM_ROADS])[1].items())
    return [_refs.get(int(i), '') for i in (e.getLanes()[0].getParam('origId') or '').split() if i.isdigit()]

if name == base_name: sys.exit(f'reference run written to {run}')
if not (base / 'stats.xml').exists():
    sys.exit(f"no reference run in {base}: run {'SEED=' + os.environ['SEED'] + ' ' if os.environ.get('SEED') else ''}python3 scripts/12_scenario.py {base_name} {day} first")
S, B = run_stats(run / 'stats.xml'), run_stats(base / 'stats.xml')
hours = range(min(24, int(S['end_s'] // 3600), int(B['end_s'] // 3600)))   # whole hours both runs cover
ES, EB = edgedata(run / 'edgedata_hourly.xml.gz'), edgedata(base / 'edgedata_hourly.xml.gz')
def totals(ids=None):
    """Per-hour sums over the given roads (all if None) of both runs."""
    tot = lambda E, h, k: sum(v[k] for e, v in E[h].items() if ids is None or e in ids)
    return {key: {'baseline': [round(tot(EB, h, k) / div, 1) for h in hours], 'scenario': [round(tot(ES, h, k) / div, 1) for h in hours]}
            for key, k, div in (('time_lost_vh', 0, 3600), ('veh_km', 1, 1000), ('vehicles_on_road', 2, 3600))}
per_hour = totals()
loss = collections.Counter()   # change in time lost per road over the compared hours, veh-h
for h in hours:
    for e, v in ES[h].items(): loss[e] += v[0] / 3600
    for e, v in EB[h].items(): loss[e] -= v[0] / 3600
base_net = BUILD / 'scenarios' / f'{base_name}.net.xml.gz'
edges = {e.getID(): (e, n) for n in (read_net(base_net if base_net.exists() else NET), read_net(net)) for e in n.getEdges()}
names = {i: e.getName().replace('&apos;', "'") for i, (e, _) in edges.items()}
roads = [{'edge': e, 'name': names.get(e, ''), 'time_lost_change_vh': round(d, 1)} for e, d in sorted(loss.items(), key=lambda kv: -abs(kv[1]))[:15]]
areas = json.load(open(src / 'areas.json')) if (src / 'areas.json').exists() else {}
areas = {label: totals({i for i, (e, n) in edges.items() if in_area(e, n, a)}) for label, a in areas.items()}
full = S['end_s'] >= B['end_s']   # trip statistics only compare over the same simulated period
out = {'scenario': name, 'day': day, 'baseline': str(base.relative_to(RESULTS)), 'hours': [hours.start, hours.stop], 'per_hour': per_hour, 'roads': roads,
       'areas': areas, 'trips': {'baseline': B, 'scenario': S} if full else None, 'runs': {'baseline': B, 'scenario': S}}   # runs: to spot stale comparisons
out_file = run / ('comparison.json' if base_name == 'baseline' else f'comparison_vs_{base_name}.json')
json.dump(out, open(out_file, 'w'), indent=1, ensure_ascii=False)

pct = lambda a, b: f'{(b - a) / a * 100:+.1f}%' if a else ''
print(f'\n{name} vs {base_name}, {day}, {hours.start:02d}:00-{hours.stop:02d}:00    baseline   scenario   change')
for key, label in (('time_lost_vh', 'time lost, veh-h'), ('veh_km', 'veh-km'), ('vehicles_on_road', 'vehicles on the road (mean)')):
    a, b = sum(per_hour[key]['baseline']), sum(per_hour[key]['scenario'])
    if key == 'vehicles_on_road': a, b = a / len(hours), b / len(hours)
    print(f'  {label:30s} {a:10.0f} {b:10.0f}   {pct(a, b)}')
if full:
    for k in ('arrived', 'teleports', 'mean_duration_s', 'mean_time_lost_s', 'mean_route_km'):
        print(f'  {k:30s} {B[k]:10.1f} {S[k]:10.1f}   {pct(B[k], S[k])}')
for label, A in areas.items():   # mean speed = veh-km / veh-h on the road
    (lb, ls), (kb, ks), (vb, vs) = ((sum(A[k]['baseline']), sum(A[k]['scenario'])) for k in ('time_lost_vh', 'veh_km', 'vehicles_on_road'))
    print(f'  {label}\n    time lost, veh-h {lb:7.0f} {ls:7.0f} {pct(lb, ls):>7s}    veh-km {kb:7.0f} {ks:7.0f} {pct(kb, ks):>7s}'
          f'    km/h {kb / vb if vb else 0:5.1f} {ks / vs if vs else 0:5.1f}')
print('  roads with the biggest change in time lost, veh-h:')
for r in roads[:10]: print(f"    {r['time_lost_change_vh']:+8.1f}  {r['name'] or '(unnamed)'}  [{r['edge']}]")
print('written', out_file)
