"""Download the OpenStreetMap road network for the study area from Overpass, in 12 tiles
(one big query times out), and merge it into data/osm/lucca_roads.osm.gz; then the places that draw crowds (schools,
hospitals, big stores, sports grounds, workplaces, stations) with their outlines into data/osm/lucca_poi.json.gz.
usage: python3 scripts/01_download_osm.py [--endpoint URL]"""
import sys, time, gzip, urllib.parse, urllib.request
from common import BUILD, OSM_ROADS, OSM_POI, BBOX
import subprocess

EP = sys.argv[sys.argv.index('--endpoint') + 1] if '--endpoint' in sys.argv else 'https://overpass-api.de/api/interpreter'
S, W, N, E = BBOX
ROWS, COLS = 3, 4
BODY = ('(way[highway];way[railway];relation[type=restriction];node[highway~"traffic_signals|stop|give_way|crossing"];'
        'node[place];way[historic=citywalls];way[barrier=city_wall];way[amenity=parking];);(._;>;);out body;')

def fetch(q, name):
    for attempt in range(6):
        try:
            req = urllib.request.Request(EP, data=urllib.parse.urlencode({'data': q}).encode(), headers={'User-Agent': 'lucca-traffic-twin'})
            with urllib.request.urlopen(req, timeout=300) as resp:
                b = resp.read()
            if b.lstrip()[:1] not in (b'<', b'{') or b'runtime error' in b[:2000]: raise RuntimeError(b[:300])   # Overpass errors come back as 200 + HTML
            print('ok', name, len(b) // 1024, 'KB'); return b
        except Exception as ex:
            print('retry', name, ex); time.sleep(15 * (attempt + 1))
    raise SystemExit(f'Overpass failed for {name}')

tiles = []
for r in range(ROWS):
    for c in range(COLS):
        s = S + (N - S) * r / ROWS; n = S + (N - S) * (r + 1) / ROWS
        w = W + (E - W) * c / COLS; e = W + (E - W) * (c + 1) / COLS
        out = BUILD / f'osm_roads_r{r}c{c}.osm'
        tiles.append(out)
        if out.exists() and out.stat().st_size > 1000:
            continue
        out.write_bytes(fetch(f'[out:xml][timeout:180][maxsize:268435456][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];' + BODY, out.name))
        time.sleep(3)
subprocess.run([sys.executable, str(BUILD.parent / 'scripts' / 'merge_osm.py'), str(OSM_ROADS)] + [str(t) for t in tiles], check=True)
print('wrote', OSM_ROADS)
# 06_export_static.py sorts these into the viewer's points of interest (POI_KINDS) and drops workplaces under 5000 m2
POI = ('(nwr[amenity~"^(school|college|university|hospital|clinic|townhall|courthouse|bus_station|cinema|theatre|marketplace)$"];'
       'nwr[healthcare=hospital];nwr[shop~"^(supermarket|mall|department_store|doityourself|wholesale|electronics|garden_centre)$"];'
       'nwr[landuse=retail][name];nwr[leisure~"^(stadium|sports_centre|sports_hall)$"];nwr[leisure=swimming_pool][name];'
       'nwr[man_made=works];nwr[landuse=industrial][name];nwr[building=industrial][name];nwr[industrial][name];nwr[railway=station];);out geom;')
OSM_POI.write_bytes(gzip.compress(fetch(f'[out:json][timeout:180][bbox:{S},{W},{N},{E}];' + POI, OSM_POI.name)))
print('wrote', OSM_POI)
