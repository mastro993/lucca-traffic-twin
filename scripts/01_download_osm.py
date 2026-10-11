"""Download the OpenStreetMap road network for the study area from Overpass, in 12 tiles
(one big query times out), and merge it into data/osm/lucca_roads.osm.gz.
usage: python3 scripts/01_download_osm.py [--endpoint URL]"""
import sys, time, urllib.parse, urllib.request
from common import BUILD, OSM_ROADS, BBOX
import subprocess

EP = sys.argv[sys.argv.index('--endpoint') + 1] if '--endpoint' in sys.argv else 'https://overpass-api.de/api/interpreter'
S, W, N, E = BBOX
ROWS, COLS = 3, 4
BODY = ('(way[highway];way[railway];relation[type=restriction];node[highway~"traffic_signals|stop|give_way|crossing"];'
        'node[place];way[historic=citywalls];way[barrier=city_wall];way[amenity=parking];);(._;>;);out body;')
tiles = []
for r in range(ROWS):
    for c in range(COLS):
        s = S + (N - S) * r / ROWS; n = S + (N - S) * (r + 1) / ROWS
        w = W + (E - W) * c / COLS; e = W + (E - W) * (c + 1) / COLS
        out = BUILD / f'osm_roads_r{r}c{c}.osm'
        tiles.append(out)
        if out.exists() and out.stat().st_size > 1000:
            continue
        q = f'[out:xml][timeout:180][maxsize:268435456][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];' + BODY
        for attempt in range(6):
            try:
                req = urllib.request.Request(EP, data=urllib.parse.urlencode({'data': q}).encode(), headers={'User-Agent': 'lucca-traffic-twin'})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    out.write_bytes(resp.read())
                print('ok', out.name, out.stat().st_size // 1024, 'KB'); break
            except Exception as ex:
                print('retry', out.name, ex); time.sleep(15 * (attempt + 1))
        time.sleep(3)
subprocess.run([sys.executable, str(BUILD.parent / 'scripts' / 'merge_osm.py'), str(OSM_ROADS)] + [str(t) for t in tiles], check=True)
print('wrote', OSM_ROADS)
