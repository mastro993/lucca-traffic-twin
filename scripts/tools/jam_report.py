"""List the edges with the largest time loss in one hour of a run (diagnostics).
usage: python3 scripts/tools/jam_report.py <weekday|saturday> <hour>"""
import sys, os
from lxml import etree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common import RESULTS, zopen, read_net
day, hour = sys.argv[1], int(sys.argv[2])
net = read_net()
rows = []
for ev, el in etree.iterparse(zopen(RESULTS / day / 'edgedata_hourly.xml.gz', 'rb'), tag='interval'):
    if int(float(el.get('begin')) // 3600) == hour:
        for e in el:
            tl = float(e.get('timeLoss') or 0)
            if tl > 3600:
                ed = net.getEdge(e.get('id')); x, y = ed.getShape()[-1]; lon, lat = net.convertXY2LonLat(x, y)
                rows.append((round(tl / 3600, 1), e.get('id'), ed.getName(), ed.getType()[8:], e.get('speedRelative'), e.get('entered'), f'{lat:.4f},{lon:.4f}'))
    el.clear()
for r in sorted(rows, reverse=True)[:30]: print(r)
