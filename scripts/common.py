"""Shared paths and helpers. Every script resolves files relative to the repository root."""
import os, sys, gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OSM = DATA / 'osm'
NETDIR = ROOT / 'network'
DEMAND = ROOT / 'demand'
RESULTS = ROOT / 'results'
DOCS = ROOT / 'docs'
WEBDATA = DOCS / 'data'
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
