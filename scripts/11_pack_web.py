"""Pack the viewer's binary data as gzip + base64 text files in web/public/data (the claude.ai artifact host serves text,
not raw binaries; GitHub Pages serves both, so the same viewer works on either).
usage: python3 scripts/11_pack_web.py"""
import gzip, base64
from common import WEBRAW, WEBDATA

def pack(raw: bytes, out):
    out.write_bytes(base64.b64encode(gzip.compress(raw, 9, mtime=0)))

(WEBDATA / 'trips').mkdir(parents=True, exist_ok=True)
for name in ('static', 'wd_edges', 'sat_edges'):
    pack((WEBRAW / f'{name}.bin').read_bytes(), WEBDATA / f'{name}.b64.txt')
for f in sorted((WEBRAW / 'trips').glob('*.bin')):
    pack(f.read_bytes(), WEBDATA / 'trips' / (f.stem + '.b64.txt'))
print('packed into', WEBDATA)
