"""Assemble docs/data/summary.json for the viewer: hourly KPIs, labelled critical points with notes,
calibration table, run statistics and the method / data / limits text.
usage: python3 scripts/10_build_summary.py"""
import json, math, re
from common import RESULTS, WEBDATA
meta = json.load(open(WEBDATA / 'static.json'))
places = meta['places']

LANDMARKS = [  # lat, lon, label, note  (manual names for well-known nodes; matched within 250 m)
    (43.8304, 10.4925, 'A11 at the Lucca Est exit',
     'Exit and entry flows at Lucca Est mix with traffic on Viale Europa heading for San Concordio and the Walls. In the morning the exit queue backs up toward the motorway.'),
    (43.8317, 10.4905, 'Lucca Est junction ramps',
     'The ramps that connect the A11 to Viale Europa and San Concordio. Ramp traffic merges with the urban flow inbound to the city.'),
    (43.8342, 10.4744, 'A11 Lucca Ovest exit / Via delle Città Gemelle', 'Short multi-lane links after the Lucca Ovest toll; part of the delay here is lane-change blocking in the model.'),
    (43.8379, 10.4691, 'A11 Lucca Ovest junction ramps', 'Ramps of the Lucca Ovest / Viareggio junction feeding Sant\'Anna and the western ring.'),
    (43.8242, 10.5972, 'A11 Capannori exit', 'Toll exit serving the Capannori industrial area and the eastern plain. It queues as morning shifts arrive.'),
    (43.8234, 10.5890, 'A11 approaching Capannori', 'Motorway traffic slowed by the queue for the Capannori exit.'),
    (43.9052, 10.5288, 'Ponte a Moriano: SS12 at Galleria Colletto',
     'All traffic from the Serchio valley and Garfagnana funnels onto the SS12 here, on single-lane approaches. The Ponte a Moriano junction meters the inbound morning flow.'),
    (43.8652, 10.5087, 'Monte San Quirico bridgehead (north)',
     'North end of the SP1 bridge over the Serchio, one of only three river crossings in the area. Flows from the Camaiore road, Via di Moriano and Monte San Quirico converge on it.'),
    (43.8628, 10.5094, 'Monte San Quirico roundabout', 'Roundabout on the north bank, just before the Serchio bridge toward the city.'),
    (43.8575, 10.5045, 'Monte San Quirico bridge (south): Via di Sant\'Alessio',
     'South end of the Serchio bridge, where it meets Via di Sant\'Alessio and Via delle Piagge. The inbound queue from the bridge builds up here before reaching the north side of the ring.'),
    (43.8398, 10.4953, 'Viale Carducci / Viale Europa roundabout',
     'Where the ring boulevards meet Viale Europa, the main axis from the A11 Lucca Est exit. A 2005 University of Pisa count already found Viale Carducci to be the most saturated approach, with 1,660 pcu/h in the morning.'),
    (43.8420, 10.4944, 'Porta Sant\'Anna roundabout (Luporini / Papi / Carducci)',
     'North-west corner of the ring, where Viale Luporini and Viale Papi meet Viale Carducci. It takes inbound traffic from Sant\'Anna and the Lucca Ovest exit.'),
    (43.8404, 10.4931, 'Viale Nieri / Via delle Tagliate (Porta Sant\'Anna)', 'Side streets feeding the Porta Sant\'Anna roundabouts. They queue when the ring is saturated.'),
    (43.8407, 10.4898, 'Viale Luporini / Via San Donato roundabout', 'Sant\'Anna gateway roundabout on the approach from the Lucca Ovest exit.'),
    (43.8571, 10.4299, 'Via Sarzanese west of Ponte San Pietro', 'SR439 from Massarosa and the Versilia approaching the Serchio crossing at Ponte San Pietro.'),
    (43.8573, 10.4356, 'Via Sarzanese at Ponte San Pietro',
     'SR439 crosses the Serchio here. The regional counting station records about 15,000 vehicles a day, with a sharp peak at 8:00.'),
    (43.8566, 10.4402, 'Via Sarzanese / Via di Mezzo (Ponte San Pietro)', 'SR439 east of the bridge, where local roads join the queue toward the city.'),
    (43.8314, 10.4942, 'Viale Europa south (San Concordio)', 'Four-lane axis between Lucca Est and the Walls, carrying motorway traffic into the city.'),
    (43.8308, 10.4976, 'Viale San Concordio roundabout', 'San Concordio roundabout on the southern approach to the station and the Walls.'),
]
def dist_m(a, b):  # (lat, lon)
    return math.hypot((a[0] - b[0]) * 111200, (a[1] - b[1]) * 80300)

def landmark(h):
    lat, lon = h['lonlat'][1], h['lonlat'][0]
    best = min(LANDMARKS, key=lambda L: dist_m((lat, lon), (L[0], L[1])))
    return best if dist_m((lat, lon), (best[0], best[1])) < 250 else None

def label(h):
    lm = landmark(h)
    if lm: return lm[2]
    st = [s for s in h['streets'] if s and not s.startswith('Traversa')]
    near = min(places, key=lambda p: math.hypot(p['p'][0] - h['x'], p['p'][1] - h['y']))
    dn = math.hypot(near['p'][0] - h['x'], near['p'][1] - h['y'])
    if not st: return f"Junction near {near['n']}"
    base = ' / '.join(st[:2])
    return base

def area(h):
    near = min(places, key=lambda p: math.hypot(p['p'][0] - h['x'], p['p'][1] - h['y']))
    return near['n']

out = {'subtitle': 'Eclipse SUMO microsimulation · OpenStreetMap network · weekday and Saturday, 24 h'}
for key, day in (('wd', 'weekday'), ('sat', 'saturday')):
    r = json.load(open(RESULTS / f'{day}_results.json'))
    r['hotspots'] = [h for h in r['hotspots'] if not (landmark(h) and 'Città Gemelle' in landmark(h)[2])]
    for h in r['hotspots']:
        h['label'] = label(h); h['area'] = area(h); lm = landmark(h)
        if lm: h['note'] = lm[3]
    out[key] = r
try:
    out['calibration'] = json.load(open(RESULTS / 'calibration.json'))
except FileNotFoundError:
    out['calibration'] = []
stats = {}
for key, day in (('wd', 'weekday'), ('sat', 'saturday')):
    x = open(RESULTS / day / 'stats.xml').read()
    g = lambda tag, att: re.search(rf'<{tag}[^>]*\b{att}="([^"]+)"', x)
    stats[f'{key}_trips'] = int(g('vehicles', 'loaded').group(1)); stats[f'{key}_inserted'] = int(g('vehicles', 'inserted').group(1))
    stats[f'{key}_teleports'] = int(g('teleports', 'total').group(1)); stats[f'{key}_teleports_jam'] = int(g('teleports', 'jam').group(1))
    for att in ('duration', 'routeLength', 'timeLoss'):
        m = g('vehicleTripStatistics', att); stats[f'{key}_mean_{att}'] = float(m.group(1)) if m else None
json.dump(stats, open(RESULTS / 'run_stats.json', 'w'), indent=1)
out['stats'] = stats
st = out['stats']
out['about'] = {
    'intro': ('A 24-hour digital twin of road traffic in Lucca and the surrounding plain (about 16 × 13 km, from Ponte a Moriano to the A11). '
              'Every vehicle is simulated individually. The moving vehicles replay every simulated trip from departure to arrival, along the route and at the '
              'times SUMO recorded for each road; road colours blend the hourly averages as the clock runs. It is a model calibrated to published counts, '
              'not a live traffic feed.'),
    'network': ('OpenStreetMap road graph converted with SUMO netconvert: about 1,700 km of road, 10,332 directed links, signalised and priority junctions, '
                'roundabouts, OSM turn restrictions and lane counts. Inside the Walls the ZTL is closed to general traffic and open only to permit holders, '
                'taxis, buses and deliveries. Speed limits are 50 km/h in built-up areas, 70–90 km/h outside, and 130 km/h on the A11.'),
    'demand': ('Tour-based synthetic demand for about 115,000 residents in the study area (ISTAT 1 Jan 2025: Lucca 89,002; part of Capannori, 46,644; part of Porcari, 8,845). '
               'Homes and destinations come from 50,000 building volumes and land use. Trip timing follows Italian patterns: school runs at 7:30–8:15, '
               'pick-ups around 13:00 and 16:15, a lunch return home for part of the workforce, and an evening peak. Destinations follow a gravity model. '
               'On top of that: commuters and visitors entering through 62 boundary roads, through traffic on the A11, vans and lorries, and ZTL permit traffic. '
               f"Weekday: {st.get('wd_trips', 355808):,} vehicle trips. Saturday: {st.get('sat_trips', 311988):,} (0.88 × weekday, the ratio measured on SR439)."),
    'sim': ('Eclipse SUMO 1.28 microscopic simulation: Krauss car-following, LC2013 lane changing, 1-second steps. Route choice is dynamic: every vehicle routes on current travel times '
            'when it departs and reroutes every 5 minutes, an approximation of dynamic user equilibrium. Vehicles stuck for more than 3 minutes are teleported, as is standard in SUMO. '
            + (f"Teleports: {st.get('wd_teleports', 0):,} on the weekday and {st.get('sat_teleports', 0):,} on Saturday." if st else '')),
    'hotspots': ('Junctions are grouped into clusters: roundabouts, and nodes linked by edges shorter than 45 m. Each cluster is scored by the vehicle-hours lost on its approach links, '
                 'measured as SUMO time loss against free-flow speed. Insertion queues on the boundary roads are excluded. The ranking uses daily totals; the 3D columns show the selected hour.'),
    'limits': ('Counts are sparse and dated (2017–2021). The model is about 10–15% high on SR439 and SS12 and 25–35% low on the eastern Pesciatina and Viale Europa corridors. '
               'Signal plans are not public, so SUMO-generated actuated plans are used. About 1% of vehicles get teleported out of local deadlocks. One junction at the Lucca Ovest toll is left out of the ranking because its delay comes from lane-change blocking on very short links, a known SUMO artefact. Parking search, buses, bicycles, roadworks, incidents and events '
               '(such as Lucca Comics & Games) are not modelled. Treat absolute delays as indicative and the ranking of critical points as the main result.'),
    'sources': [
        {'t': 'OpenStreetMap (ODbL)', 'url': 'https://www.openstreetmap.org/copyright'},
        {'t': 'OpenFreeMap / OpenMapTiles buildings', 'url': 'https://openfreemap.org'},
        {'t': 'Regione Toscana traffic stations SR439 P058/P066', 'url': 'https://dati.toscana.it/dataset/sr439'},
        {'t': 'NEPA / ANAS traffic report, Viabilità Est di Lucca (2018)', 'url': 'https://va.mite.gov.it/File/Documento/341806'},
        {'t': 'Univ. Pisa study, Porta Sant’Anna counts', 'url': 'https://docenti.ing.unipi.it/~dic/ingegneria_civile/bacheca/doc_pubblici/atti_lucca_21_2210208/10_pratelli_etc.pdf'},
        {'t': 'Comune di Lucca PUMS monitoring 2024', 'url': 'https://comune.lucca.it/app/uploads/2025/02/Documento-di-Monitoraggio2024.pdf'},
        {'t': 'ISTAT population 2025 (tuttitalia)', 'url': 'https://www.tuttitalia.it/toscana/53-lucca/92-comuni-limitrofi/'},
        {'t': 'Eclipse SUMO', 'url': 'https://eclipse.dev/sumo/'},
        {'t': 'Source code and data (GitHub)', 'url': 'https://github.com/mastro993/lucca-traffic-twin'},
    ],
    'credits': 'Map data © OpenStreetMap contributors. Building heights via OpenMapTiles/OpenFreeMap. Simulation by Eclipse SUMO (EPL-2.0). Rendering with deck.gl.',
}
json.dump(out, open(WEBDATA / 'summary.json', 'w'), ensure_ascii=False, separators=(',', ':'))
for key in ('wd', 'sat'):
    print(key)
    for k, h in enumerate(out[key]['hotspots'][:12]): print(f"  {k+1:2d} {h['daily_delay_vh']:7.1f} peak {h['peak_hour']:02d} {h['label']}  [{h['area']}]")
