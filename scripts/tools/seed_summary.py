"""Sum up a scenario's comparison over several random seeds: the change in time lost, distance driven and mean speed for
the whole network and for each area of the scenario's areas.json, per seed and on average. One seed cannot settle a
difference of a few per cent (see the README, Scenarios); the spread across seeds shows how much of it is noise.
usage: python3 scripts/tools/seed_summary.py <name> <weekday|saturday> [base]
       after python3 scripts/12_scenario.py <name> <day> with SEED unset, SEED=2, SEED=3, ... (and BASE=<base>)"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import RESULTS, run_stats

name, day = sys.argv[1], sys.argv[2]
base = sys.argv[3] if len(sys.argv) > 3 else 'baseline'
runs = sorted(RESULTS.glob(f"scenarios/{name}/{day}*/{'comparison.json' if base == 'baseline' else f'comparison_vs_{base}.json'}"))
if not runs: sys.exit(f'no comparison of {name} with {base} for {day}: run scripts/12_scenario.py first')
comps = [json.load(open(f)) for f in runs]
stale = [f.parent.name for f, c in zip(runs, comps)   # a run redone since it was compared
         if 'runs' in c and c['runs'] != {'baseline': run_stats(RESULTS / c['baseline'] / 'stats.xml'), 'scenario': run_stats(f.parent / 'stats.xml')}]
if stale or len({tuple(c['hours']) for c in comps}) > 1:
    sys.exit(f"comparisons {'older than their runs (' + ', '.join(stale) + ')' if stale else 'over different hours'}: compare again with COMPARE=1")
rows = {}   # area -> per seed {metric: (reference, scenario)} summed over the compared hours
for c in comps:
    for label, d in {'Whole network': c['per_hour'], **c.get('areas', {})}.items():
        rows.setdefault(label, []).append({k: (sum(v['baseline']), sum(v['scenario'])) for k, v in d.items()})
pct = lambda a, b: (b - a) / a * 100 if a else 0.0
mean = lambda xs: sum(xs) / len(xs)
print(f"{name} vs {base}, {day}, hours {c['hours'][0]:02d}-{c['hours'][1]:02d}, {len(runs)} seeds: {', '.join(f.parent.name for f in runs)}")
print(f"{'':22s}{base[:11]:>12s}{name[:11]:>12s}   change: mean (each seed)")
for label, seeds in rows.items():
    print(label)
    for key, unit in (('time_lost_vh', 'time lost, veh-h'), ('veh_km', 'veh-km')):
        ch = [pct(*s[key]) for s in seeds]
        print(f'  {unit:20s}{mean([s[key][0] for s in seeds]):12.0f}{mean([s[key][1] for s in seeds]):12.0f}   '
              f"{mean(ch):+6.1f}% ({' '.join(f'{x:+.1f}' for x in ch)})")
    kmh = [[s['veh_km'][i] / s['vehicles_on_road'][i] if s['vehicles_on_road'][i] else 0 for s in seeds] for i in (0, 1)]
    print(f"  {'mean speed, km/h':20s}{mean(kmh[0]):12.1f}{mean(kmh[1]):12.1f}   {mean(kmh[1]) - mean(kmh[0]):+6.1f}")
