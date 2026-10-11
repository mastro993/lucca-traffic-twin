"""Fast calibration helper: route the trips at free flow with duarouter, then count daily/hourly edge volumes into a
pseudo edgeData file that 09_check_counts.py can read. Takes ~3 minutes instead of a 90-minute microsimulation.
usage: python3 scripts/tools/route_volumes.py <weekday|saturday>
then:  python3 scripts/09_check_counts.py freeflow_<day>"""
import sys, os, collections, subprocess, gzip
import numpy as np
from lxml import etree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import NET, DEMAND, BUILD, RESULTS, sumo_bin

day = sys.argv[1]
rou = BUILD / f'{day}.ff.rou.xml'
subprocess.run([sumo_bin('duarouter'), '-n', str(NET), '-r', str(DEMAND / f'{day}.trips.xml.gz'), '-o', str(rou),
                '--routing-algorithm', 'astar', '--ignore-errors', '--repair', '--no-warnings', '--no-step-log', '--routing-threads', '2'], check=True)
hourly = collections.defaultdict(lambda: np.zeros(25, np.float32))
for ev, el in etree.iterparse(str(rou), tag='vehicle'):
    h = min(24, int(float(el.get('depart')) // 3600)); r = el.find('route')
    if r is not None:
        for e in r.get('edges').split(): hourly[e][h] += 1
    el.clear()
out = RESULTS / f'freeflow_{day}'; out.mkdir(exist_ok=True)
with gzip.open(out / 'edgedata_hourly.xml.gz', 'wt') as fo:
    fo.write('<meandata>\n')
    for h in range(24):
        fo.write(f'<interval begin="{h*3600}" end="{(h+1)*3600}" id="ff">\n')
        fo.write(''.join(f'<edge id="{e}" entered="{a[h]:.0f}"/>\n' for e, a in hourly.items() if a[h] > 0))
        fo.write('</interval>\n')
    fo.write('</meandata>\n')
print('wrote', out)
