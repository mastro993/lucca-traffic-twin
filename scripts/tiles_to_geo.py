"""Decode the OpenMapTiles z14 tiles into shapely geometries in the SUMO network frame (build/omt_geo.pkl).
usage: python3 scripts/tiles_to_geo.py [net file]"""
import sys, struct, gzip, math, pickle, collections
import mapbox_vector_tile as mvt
from shapely.geometry import shape, box
from shapely.ops import transform
from shapely import make_valid
from common import OMT_TILES, OMT_GEO, NET, read_net

def tile2lonlat(z, x, y, px, py, ext=4096):
    n = 2 ** z; lon = (x + px / ext) / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / ext) / n)))); return lon, lat

def main(net_path=NET):
    net = read_net(net_path)
    data = open(OMT_TILES, 'rb').read(); p = 0
    out = collections.defaultdict(list)
    while p < len(data):
        z, x, y, n = struct.unpack('<4I', data[p:p + 16]); p += 16; b = data[p:p + n]; p += n
        if b[:2] == b'\x1f\x8b': b = gzip.decompress(b)
        d = mvt.decode(b, default_options={'y_coord_down': True})
        tb = box(0, 0, 4096, 4096)
        def conv(xx, yy, zz=None):
            res = [net.convertLonLat2XY(*tile2lonlat(z, x, y, a, c)) for a, c in zip(xx, yy)]
            return [r[0] for r in res], [r[1] for r in res]
        for L in ('building', 'landcover', 'landuse', 'water', 'park', 'waterway'):
            for f in d.get(L, {}).get('features', []):
                g = shape(f['geometry'])
                if not g.is_valid: g = make_valid(g)
                g = g.intersection(tb)          # clip the tile buffer so pieces abut exactly
                if g.is_empty: continue
                out[L].append((transform(conv, g), f['properties']))
    pickle.dump(dict(out), open(OMT_GEO, 'wb'))
    print({k: len(v) for k, v in out.items()})

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else NET)
