"""Download OpenMapTiles vector tiles (z14) from OpenFreeMap for the study area: buildings with heights,
land cover, land use and water. They are stored in one file: repeated [uint32 z, x, y, length][pbf bytes].
usage: python3 scripts/02_download_tiles.py"""
import json, math, struct, urllib.request
from common import OMT_TILES, BBOX

def tile(lon, lat, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)

S, W, N, E = BBOX
x0, y0 = tile(W, N, 14); x1, y1 = tile(E, S, 14)
tj = json.load(urllib.request.urlopen('https://tiles.openfreemap.org/planet'))
url = tj['tiles'][0]
with open(OMT_TILES, 'wb') as f:
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            b = urllib.request.urlopen(url.replace('{z}', '14').replace('{x}', str(x)).replace('{y}', str(y))).read()
            f.write(struct.pack('<4I', 14, x, y, len(b))); f.write(b)
print('wrote', OMT_TILES, (x1 - x0 + 1) * (y1 - y0 + 1), 'tiles')
