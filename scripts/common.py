"""Shared paths and helpers. Every script resolves files relative to the repository root."""
import os, sys, gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OSM = DATA / 'osm'
NETDIR = ROOT / 'network'
DEMAND = ROOT / 'demand'
RESULTS = ROOT / 'results'
WEBDATA = ROOT / 'public' / 'data'   # data the viewer fetches at runtime
BUILD = ROOT / 'build'            # intermediate files, git-ignored
BUILD.mkdir(exist_ok=True)

NET = NETDIR / 'lucca.net.xml.gz'  # final SUMO network
OSM_ROADS = OSM / 'lucca_roads.osm.gz'
OMT_TILES = OSM / 'lucca_omt_z14.bin'
OMT_GEO = BUILD / 'omt_geo.pkl'
ZONES = BUILD / 'zones.pkl'
EDGE_IDS = BUILD / 'edge_ids.json'
WEBRAW = BUILD / 'web'             # raw binaries before packing for the viewer
WEBRAW.mkdir(exist_ok=True)

BBOX = (43.795, 10.420, 43.915, 10.620)   # south, west, north, east
ORIGIN = (10.50300, 43.84300)             # lon, lat of the viewer's local frame (Piazza San Michele)
DAYS = {'wd': 'weekday', 'sat': 'saturday'}
# Fixed-time signal plans with Italian standard timings (real plans are not public): 4 s amber, the usual urban value
# (MIT note 67906/2007: never under 3 s; 3/4/5 s for 50/60/70 km/h approaches), 2 s all-red clearance, 70 s cycle.
# Fixed-time plans are deterministic, so the viewer can show each light's state from the program alone.
TLS = ['--tls.default-type', 'static', '--tls.cycle.time', '70', '--tls.yellow.time', '4', '--tls.allred.time', '2']


def sumo_home():
    if os.environ.get('SUMO_HOME'):
        return os.environ['SUMO_HOME']
    import sumo  # pip install eclipse-sumo
    os.environ['SUMO_HOME'] = sumo.SUMO_HOME
    return sumo.SUMO_HOME


def sumo_bin(name):
    return str(Path(sumo_home()) / 'bin' / name)


def zopen(path, mode='rt'):
    path = str(path)
    return gzip.open(path, mode) if path.endswith('.gz') else open(path, mode)


def read_net(path=NET):
    import sumolib
    return sumolib.net.readNet(str(path), withInternal=False)


def run_stats(path):
    """The trip statistics of a run's stats.xml (SUMO --statistic-output)."""
    from lxml import etree
    r = etree.parse(str(path)).getroot()
    v, tp, ts, pf = (r.find(k).attrib for k in ('vehicles', 'teleports', 'vehicleTripStatistics', 'performance'))
    return {'end_s': float(pf['end']), 'trips': int(v['loaded']), 'arrived': int(ts['count']), 'teleports': int(tp['total']),
            'mean_duration_s': float(ts['duration']), 'mean_time_lost_s': float(ts['timeLoss']), 'mean_route_km': float(ts['routeLength']) / 1000}
