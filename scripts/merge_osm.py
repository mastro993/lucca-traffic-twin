"""Merge tiled Overpass extracts into one de-duplicated OSM file. usage: merge_osm.py <out.osm[.gz]> <tile.osm>..."""
import sys, glob, gzip
from lxml import etree
out = sys.argv[1]; files = sys.argv[2:]
nodes, ways, rels = {}, {}, {}
for f in files:
    for ev, el in etree.iterparse(f, events=('end',), tag=('node','way','relation')):
        i = int(el.get('id'))
        d = {'node':nodes,'way':ways,'relation':rels}[el.tag]
        if i not in d: d[i] = etree.tostring(el)
        el.clear()
with (gzip.open(out, 'wb') if out.endswith('.gz') else open(out, 'wb')) as fo:
    fo.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="merge">\n')
    fo.write(b'<bounds minlat="43.795" minlon="10.420" maxlat="43.915" maxlon="10.620"/>\n')
    for d in (nodes, ways, rels):
        for k in sorted(d): fo.write(d[k].strip()+b'\n')
    fo.write(b'</osm>\n')
print(len(nodes), len(ways), len(rels))
