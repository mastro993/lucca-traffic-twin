"""Pack the viewer's binary data as gzip + base64 text files in docs/data (the claude.ai artifact host serves text,
not raw binaries; GitHub Pages serves both, so the same viewer works on either).
Vehicle replays are re-encoded as LVF2: per-vehicle delta-coded positions in planar layout, which gzip compresses ~2x better.
usage: python3 scripts/11_pack_web.py"""
import gzip, base64, struct
import numpy as np
from common import WEBRAW, WEBDATA

def pack(raw: bytes, out):
    out.write_bytes(base64.b64encode(gzip.compress(raw, 9, mtime=0)))

def lvf2(b: bytes) -> bytes:
    n, nF, dt, t0 = struct.unpack('<IIff', b[4:20])
    tab = np.frombuffer(b[20:20 + 4 * n], np.uint16).reshape(-1, 2).astype(np.int64)
    off = 20 + 5 * n; off += off % 2; P = int(tab[:, 1].sum())
    xy = np.frombuffer(b[off:off + 4 * P], np.int16).reshape(-1, 2).astype(np.int32)
    d = xy.copy(); o = 0
    for k in range(n):
        c = int(tab[k, 1]); seg = xy[o:o + c]; d[o + 1:o + c] = seg[1:] - seg[:-1]; o += c
    return (b'LVF2' + b[4:off] + np.ascontiguousarray(d[:, 0]).astype(np.int16).tobytes()
            + np.ascontiguousarray(d[:, 1]).astype(np.int16).tobytes() + b[off + 4 * P:])

(WEBDATA / 'veh').mkdir(parents=True, exist_ok=True)
for name in ('static', 'wd_edges', 'sat_edges'):
    pack((WEBRAW / f'{name}.bin').read_bytes(), WEBDATA / f'{name}.b64.txt')
for f in sorted((WEBRAW / 'veh').glob('*.bin')):
    pack(lvf2(f.read_bytes()), WEBDATA / 'veh' / (f.stem + '.b64.txt'))
print('packed into', WEBDATA)
