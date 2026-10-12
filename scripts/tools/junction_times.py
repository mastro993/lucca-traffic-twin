"""Travel times through one junction, from the vehicle routes of two scenarios (vehroutes.xml.gz, with exit times):
for each arm, the vehicles that came in by it and their mean time from entering the first road of the approach to
leaving the first road past the junction. Unlike the edge data, this counts the time spent inside the junction, which
for a roundabout is most of its ring. Mean of the seed runs the two scenarios share.
The arms are in scenarios/<name>/junction.json: {"arm": ["first road of the approach", "first road past the junction,
leaving by this arm"]}, with roads both networks have.
usage: python3 scripts/tools/junction_times.py <name> <weekday|saturday> <other>   # <name> against <other>
       HOURS=8,17 python3 scripts/tools/junction_times.py ...                         # and in these hours (reaching the approach)"""
import sys, os, json, gzip
from lxml import etree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import ROOT, RESULTS

name, day, other = sys.argv[1:4]
arms = json.load(open(ROOT / 'scenarios' / name / 'junction.json'))
up, down = {u: a for a, (u, _) in arms.items()}, {d for _, d in arms.values()}
hours = [int(h) for h in os.environ.get('HOURS', '').split(',') if h]

def through(run):
    """(arm, hour the vehicle reached the approach, seconds to past the junction) for each vehicle through it."""
    out = []
    for _, v in etree.iterparse(gzip.open(run / 'vehroutes.xml.gz'), tag='vehicle'):
        r = v.find('route')
        if r is not None and r.get('exitTimes'):
            edges, ex = r.get('edges').split(), [float(t) for t in r.get('exitTimes').split()]
            for i, e in enumerate(edges[1:], 1):   # entering the approach = leaving the road before it
                j = next((j for j in range(i + 1, min(len(edges), i + 30)) if edges[j] in down), None) if e in up else None
                if j: out.append((up[e], int(ex[i - 1] // 3600), ex[j] - ex[i - 1]))
        v.clear()
    return out

seeds = sorted(p.name for p in (RESULTS / 'scenarios' / name).glob(f'{day}*')
               if (p / 'vehroutes.xml.gz').exists() and (RESULTS / 'scenarios' / other / p.name / 'vehroutes.xml.gz').exists())
if not seeds: sys.exit(f'no {day} runs of both {name} and {other} with vehicle routes')
R = {s: {n: through(RESULTS / 'scenarios' / n / s) for n in (other, name)} for s in seeds}
mean = lambda xs: sum(xs) / len(xs) if xs else 0
print(f'{name} against {other}, {day}, {len(seeds)} seeds ({", ".join(seeds)}): vehicles, mean seconds through the junction')
for a in arms:
    cells = []
    for h in (None, *hours):
        (vo, to), (vn, tn) = ((mean([len(x) for x in xs]), mean([mean(x) for x in xs if x])) for xs in
                              [[[t for arm, hh, t in R[s][n] if arm == a and (h is None or hh == h)] for s in seeds] for n in (other, name)])
        cells.append(f"{'day' if h is None else f'{h:02d}h'} {vo:5.0f} -> {vn:5.0f} veh, {to:4.0f} -> {tn:4.0f} s")
    print(f'  {a:32s} ' + ' | '.join(cells))
tot = {n: [sum(t for *_, t in R[s][n]) / 3600 for s in seeds] for n in (other, name)}
print(f"  all arms, veh-h a day {mean(tot[other]):7.0f} -> {mean(tot[name]):7.0f}   "
      f"{(mean(tot[name]) - mean(tot[other])) / mean(tot[other]) * 100:+.1f}% (seeds {' '.join(f'{(b - a) / a * 100:+.1f}' for a, b in zip(tot[other], tot[name]))})")
