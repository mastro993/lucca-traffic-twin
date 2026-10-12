"""Simulate a road-network scenario and compare it with a reference run of the unchanged network.
A scenario is a folder scenarios/<name>/ of netconvert patch files, applied on top of network/lucca.net.xml.gz:
  *.nod.xml  junctions (control type, e.g. traffic_light / priority / roundabout nodes)
  *.edg.xml  roads (lanes, speed, allow / disallow, or <delete id=.../>)
  *.con.xml  turning movements (<connection .../>, <delete .../>)
  *.tll.xml  signal plans (<tlLogic id=... type="static" programID="0" offset=...> with phases)
and optionally <day>.trips.xml.gz to replace the demand. Trips are routed when they depart, so traffic finds its own way
through the changed network.
The reference is the scenario `baseline` (no changes), run the same way, so both runs differ only in the scenario.
Output: build/scenarios/<name>.net.xml.gz, results/scenarios/<name>/<day>/ (as step 7) with comparison.json.
usage: python3 scripts/12_scenario.py baseline <weekday|saturday>   # the reference, once per day type and seed
       python3 scripts/12_scenario.py <name> <weekday|saturday>
       END=36000 python3 scripts/12_scenario.py <name> weekday   # until 10:00 only, compared over the same hours
       SEED=2 python3 scripts/12_scenario.py <name> weekday      # another random seed, in <day>_seed2/ (run baseline too)
       COMPARE=1 python3 scripts/12_scenario.py <name> weekday   # compare an existing run again
       BASE=<other> python3 scripts/12_scenario.py <name> weekday   # compare with another scenario"""
import os, sys, json, subprocess, collections
from lxml import etree
from common import ROOT, NET, RESULTS, BUILD, sumo_bin, zopen, read_net

name, day = sys.argv[1], sys.argv[2]
src = ROOT / 'scenarios' / name
if not src.is_dir(): sys.exit(f'no scenario folder {src}')
net = BUILD / 'scenarios' / f'{name}.net.xml.gz'
out_dir = day + (f"_seed{os.environ['SEED']}" if os.environ.get('SEED') else '')
run, base = RESULTS / 'scenarios' / name / out_dir, RESULTS / 'scenarios' / os.environ.get('BASE', 'baseline') / out_dir

if os.environ.get('COMPARE') != '1':
    net.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sumo_bin('netconvert'), '-s', str(NET), '-o', str(net), '--output.street-names', '--output.original-names', '--no-warnings']
    for ext, opt in (('nod', '-n'), ('edg', '-e'), ('con', '-x'), ('tll', '-i')):
        files = sorted(str(p) for p in src.glob(f'*.{ext}.xml'))
        if files: cmd += [opt, ','.join(files)]
    subprocess.run(cmd, check=True)
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
    except etree.XMLSyntaxError: pass   # a run still in progress
    return out

def stats(path):
    r = etree.parse(str(path)).getroot()
    v, tp, ts, pf = (r.find(k).attrib for k in ('vehicles', 'teleports', 'vehicleTripStatistics', 'performance'))
    return {'end_s': float(pf['end']), 'trips': int(v['loaded']), 'arrived': int(ts['count']), 'teleports': int(tp['total']),
            'mean_duration_s': float(ts['duration']), 'mean_time_lost_s': float(ts['timeLoss']), 'mean_route_km': float(ts['routeLength']) / 1000}

if name == os.environ.get('BASE', 'baseline'): sys.exit(f'reference run written to {run}')
if not (base / 'stats.xml').exists(): sys.exit(f'no reference run in {base}: run python3 scripts/12_scenario.py baseline {day} first')
S, B = stats(run / 'stats.xml'), stats(base / 'stats.xml')
hours = range(min(24, int(S['end_s'] // 3600), int(B['end_s'] // 3600)))   # whole hours both runs cover
ES, EB = edgedata(run / 'edgedata_hourly.xml.gz'), edgedata(base / 'edgedata_hourly.xml.gz')
tot = lambda E, h, k: sum(v[k] for v in E[h].values())
per_hour = {key: {'baseline': [round(tot(EB, h, k) / div, 1) for h in hours], 'scenario': [round(tot(ES, h, k) / div, 1) for h in hours]}
            for key, k, div in (('time_lost_vh', 0, 3600), ('veh_km', 1, 1000), ('vehicles_on_road', 2, 3600))}
loss = collections.Counter()   # change in time lost per road over the compared hours, veh-h
for h in hours:
    for e, v in ES[h].items(): loss[e] += v[0] / 3600
    for e, v in EB[h].items(): loss[e] -= v[0] / 3600
names = {e.getID(): e.getName().replace('&apos;', "'") for e in read_net(net).getEdges()} | {e.getID(): e.getName().replace('&apos;', "'") for e in read_net(NET).getEdges()}
roads = [{'edge': e, 'name': names.get(e, ''), 'time_lost_change_vh': round(d, 1)} for e, d in sorted(loss.items(), key=lambda kv: -abs(kv[1]))[:15]]
full = S['end_s'] >= B['end_s']   # trip statistics only compare over the same simulated period
out = {'scenario': name, 'day': day, 'baseline': str(base.relative_to(RESULTS)), 'hours': [hours.start, hours.stop], 'per_hour': per_hour, 'roads': roads,
       'trips': {'baseline': B, 'scenario': S} if full else None}
json.dump(out, open(run / 'comparison.json', 'w'), indent=1, ensure_ascii=False)

pct = lambda a, b: f'{(b - a) / a * 100:+.1f}%' if a else ''
print(f'\n{name}, {day}, {hours.start:02d}:00-{hours.stop:02d}:00    baseline   scenario   change')
for key, label in (('time_lost_vh', 'time lost, veh-h'), ('veh_km', 'veh-km'), ('vehicles_on_road', 'vehicles on the road (mean)')):
    a, b = sum(per_hour[key]['baseline']), sum(per_hour[key]['scenario'])
    if key == 'vehicles_on_road': a, b = a / len(hours), b / len(hours)
    print(f'  {label:30s} {a:10.0f} {b:10.0f}   {pct(a, b)}')
if full:
    for k in ('arrived', 'teleports', 'mean_duration_s', 'mean_time_lost_s', 'mean_route_km'):
        print(f'  {k:30s} {B[k]:10.1f} {S[k]:10.1f}   {pct(B[k], S[k])}')
print('  roads with the biggest change in time lost, veh-h:')
for r in roads[:10]: print(f"    {r['time_lost_change_vh']:+8.1f}  {r['name'] or '(unnamed)'}  [{r['edge']}]")
print('written', run / 'comparison.json')
