# Lucca Traffic Twin

A 3D, hour-by-hour **microsimulation of road traffic in Lucca (Italy)** and the surrounding plain, built with
[Eclipse SUMO](https://eclipse.dev/sumo/) on the real OpenStreetMap network. It simulates a typical school weekday and a
Saturday, 24 hours each, and ranks the junctions where traffic loses the most time.

**▶ Live viewer: https://mastro993.github.io/lucca-traffic-twin/**

![Weekday 08:00, morning peak](docs/assets/weekday.jpg)

The goal is a calibrated **baseline** for testing how traffic in Lucca could be improved: junction redesigns, new links,
signal timing, school-time staggering, parking policy. Every vehicle (about 340,000 trips on a weekday) is simulated
individually.

> This is a model, not a live traffic feed. The demand is synthetic and calibrated to the few public traffic counts
> available (see [Calibration](#calibration) and [Limits](#limits)). Rely on the ranking of critical points more than on the absolute delays.

---

## What the viewer shows

| | |
|---|---|
| **Roads** | Coloured for the selected hour by speed (simulated speed ÷ speed limit), volume (vehicles/h per lane) or delay (vehicle-minutes lost per km). |
| **Vehicles** | A replay of the actual SUMO trajectories: a 90-second slice recorded at HH:29 of every hour. Dark (light theme) or white (dark theme) = cars, orange = vans and lorries, blue = ZTL permit holders, red = stopped. |
| **Critical points** | The 12 junction clusters with the most daily delay. Column height = delay in the selected hour; click one to fly to it at its peak hour. |
| **24-hour strip** | Network-wide delay per hour (bars = selected day, dashed = the other day). Drag to change the hour; **Play** runs through the day. |
| **Panel** | Vehicles on the network, average speed, delay and km of congested road for the hour, plus the method, the calibration table and the sources. |

Deep links: `?h=8` opens 08:00, `?d=sat` opens Saturday, `?z=16` zooms in. For example, [`?d=sat&h=11`](https://mastro993.github.io/lucca-traffic-twin/?d=sat&h=11) opens the Saturday 11:00 peak.

| Saturday 11:00 | Weekday 17:00, close-up (dark mode) |
|---|---|
| ![Saturday](docs/assets/saturday.jpg) | ![Close-up](docs/assets/closeup.jpg) |

---

## Key findings (baseline)

**Weekday.**
- The network peaks at **08:00–10:00**: about 3,900 vehicle-hours are lost per hour, there are about 9,000 vehicles on the road at once, the average speed is 30 km/h, and about 110 km of road run below half the speed limit.
- The evening peak (17:00–19:00) is milder, at about 2,500 vehicle-hours per hour.
- Over the whole day: 22,000 vehicle-hours lost and 3.0 million vehicle-km.

| # | Critical point | Control | Peak | Delay (veh-h/day) |
|---|---|---|---|---|
| 1 | Viale Carducci / Viale Europa roundabout | roundabout | 17h | 487 |
| 2 | A11 at the Lucca Est exit | motorway diverge | 09h | 377 |
| 3 | Viale Nieri / Via delle Tagliate (Porta Sant'Anna) | priority | 18h | 344 |
| 4 | Porta Sant'Anna roundabout (Luporini / Papi / Carducci) | roundabout | 18h | 255 |
| 5 | Viale Europa south (San Concordio) | priority | 08h | 252 |
| 6 | Monte San Quirico bridge, south end (Via di Sant'Alessio) | priority | 09h | 239 |
| 7 | Via delle Tagliate | priority | 17h | 231 |
| 8 | Viale San Concordio roundabout | roundabout | 18h | 230 |
| 9 | Viale Luporini / Via San Donato roundabout | roundabout | 17h | 223 |
| 10 | Viale Europa / Via Teresa Bandettini | roundabout | 17h | 218 |

Also high on the list: the north end of the Monte San Quirico bridge, Ponte a Moriano (SS12 at Galleria Colletto), and Via Sarzanese at Ponte San Pietro.

**Saturday.** The peak is at **11:00–12:00** (about 2,000 vehicle-hours per hour). Delay concentrates on the west and south-west of the ring road around the Walls (the Viali), driven by traffic to the car parks: Carducci / Europa roundabout (392 veh-h/day), Porta Sant'Anna side streets (307), Porta Sant'Anna roundabout (222), Viale Europa / Bandettini (205), A11 Lucca Est exit (171).

**The pattern.** The bottlenecks cluster in three places:
1. **The south-west corner of the Viali.** Here Viale Europa, carrying traffic from the A11 Lucca Est exit, meets the ring road and the big car parks (Carducci, Palatucci, Tagliate). A 2005 University of Pisa count had already found Viale Carducci to be the most saturated approach.
2. **The Serchio crossings.** Monte San Quirico, Ponte San Pietro (SR439) and Ponte a Moriano (SS12) are the only river crossings in the area, and they meter the morning inbound flow.
3. **The A11 exits.** Lucca Est and Capannori.

---

## How it works

```
OpenStreetMap ──► netconvert ──► SUMO network ──┐
OpenMapTiles buildings + land use ──► zones ─────┼──► tour-based demand ──► SUMO 24 h microsimulation ──► edge data ──► critical points ──► web viewer
ISTAT population, traffic counts ──► calibration ┘                         (TraCI: vehicle replays)
```

### Network
- **Source:** the OpenStreetMap road graph for the bbox 43.795–43.915 N, 10.420–10.620 E, about 16 × 13 km.
- **Conversion:** SUMO `netconvert` with guessed ramps, roundabouts and signals, OSM turn restrictions and lane counts. The result has about 1,700 km of road, 10,332 directed links and 4,721 junctions.
- **ZTL:** inside the Walls the network is closed to general traffic; only permit holders (`custom1`), taxis, buses and deliveries can enter.
- **Speed limits:** derived from building density, as OSM rarely tags them. 50 km/h in built-up areas, 60–90 km/h outside, 30 km/h in the ZTL, 130 km/h on the A11.
- **Junction fix:** right-before-left junctions are turned into priority junctions. In SUMO they otherwise block main roads, for example just after toll plazas.

### Demand
A tour-based synthetic population, `05_generate_demand.py`:
- **Residents:** about 115,000 in the study area (ISTAT, 1 Jan 2025: Lucca 89,002; part of Capannori, 46,644; part of Porcari, 8,845).
- **Homes and activities:** taken from 50,000 building volumes (footprint × height) and land use. Attraction to the walled centre is assigned to the car parks around the Walls.
- **Purposes** with Italian timing:
  - work, with 18% returning home for lunch;
  - school escort: drop-off 7:30–8:30, pick-ups around 13:00 and 16:15;
  - shopping, leisure and other trips, plus non-home-based trips.
- **Destination choice:** gravity models (exp(−β·t) on free-flow travel times between 403 zones of 700 m).
- **62 boundary gateways** with daily volumes from counts or road class:
  - commuters and visitors entering the area;
  - residents leaving it;
  - through traffic, mostly on the A11.
- **Other traffic:** vans and lorries (6% on weekdays) and ZTL permit traffic (about 5,000 transits a day, as reported by the Comune di Lucca).
- **Totals:**
  - Weekday: **339,525 trips**.
  - Saturday: **299,048 trips**, 0.88 × the weekday, which is the ratio measured at the SR439 station. Saturday has later and flatter peaks and more shopping and leisure trips.

### Simulation
- **Simulator:** Eclipse SUMO 1.28 microscopic, 1 s steps, Krauss car-following, LC2013 lane changing.
- **Route choice:** dynamic. Vehicles route on current travel times when they depart and reroute every 5 minutes, with a small penalty for low-priority roads to avoid unrealistic rat-runs. This approximates a dynamic user equilibrium without iterating.
- **Recording:** the run is driven through TraCI (`07_run_simulation.py`). It writes hourly edge statistics and records the vehicle replays.
- **Teleports:** vehicles stuck for more than 3 minutes are teleported, standard SUMO practice. This affected 1.7% of trips on the weekday and 1.3% on Saturday.
- **Trip averages:** 9.6 km and 14 min on a weekday (4.5 min lost); 9.5 km and 12 min on Saturday.

### Critical points
- **Clusters:** junctions are grouped into clusters, either roundabouts or nodes joined by links shorter than 45 m.
- **Score:** each cluster gets the vehicle-hours lost on its approach links (SUMO `timeLoss`, measured against free-flow speed).
- **Excluded:** insertion queues on boundary roads, and lane-end deadlock artefacts (near-zero speed with almost no throughput). One junction at the Lucca Ovest toll is left out of the ranking for this reason.

### Calibration
Weekday daily traffic, both directions:

| Section | Observed | Simulated | Ratio | Source |
|---|---:|---:|---:|---|
| SR439 Via Sarzanese at Ponte San Pietro | 14,500 | 16,485 | 1.14 | Regione Toscana station P058, 2019/2021 |
| SS12 Brennero, north of Lucca | 19,068 | 19,086 | 1.00 | NEPA / ANAS, 2017 |
| SR435 Via Pesciatina at Antraccoli | 15,272 | 11,620 | 0.76 | NEPA / ANAS, 2017 |
| Viale Europa, Capannori (busiest section) | 21,062 | 15,443 | 0.73 | NEPA / ANAS, 2017 |
| Via Romana, east (busiest section) | 24,140 | 22,756 | 0.94 | NEPA / ANAS, 2017 |

- The simulated peak-hour shares are 8–10% of daily traffic; the stations measured 8.2–9.5%.
- The eastern corridors (Capannori) are underestimated by about 25%.
- All counts are in [`data/counts/counts.json`](data/counts/counts.json).

---

## Repository layout

```
data/
  osm/lucca_roads.osm.gz      OSM roads, rail, walls, parking (Overpass, 11 Oct 2026)
  osm/lucca_omt_z14.bin       OpenMapTiles z14 tiles: buildings with heights, land cover, water (OpenFreeMap)
  counts/counts.json          observed traffic counts and population used for calibration
network/
  lucca.net.xml.gz            final SUMO network
  patches/                    ZTL, speed-limit and junction patches applied by netconvert
demand/
  weekday.trips.xml.gz        339,525 trips (exactly the demand used for the results)
  saturday.trips.xml.gz       299,048 trips
results/
  weekday/, saturday/         hourly edgeData (SUMO meandata) and run statistics
  *_results.json              hourly KPIs and ranked critical points
  calibration.json, run_stats.json
scripts/                      the pipeline (01–11), shared helpers and diagnostics
docs/                         the web viewer (GitHub Pages): index.html + packed data
run_pipeline.sh               runs everything end to end
```

## Reproduce

```bash
pip install -r requirements.txt            # includes the SUMO binaries (eclipse-sumo)
SIMULATE=0 ./run_pipeline.sh               # rebuild network, demand, viewer data from the committed inputs (~5 min)
./run_pipeline.sh                          # ... and re-run both 24 h simulations (~70-90 min each, 2 cores)
DOWNLOAD=1 ./run_pipeline.sh               # also re-download OSM and building tiles first
python3 -m http.server -d docs 8000        # open http://localhost:8000
```

The pipeline is deterministic. With fixed random seeds, the committed network and trip files are reproduced exactly from `data/osm/`.

| Step | Script | Output |
|---|---|---|
| 1 | `01_download_osm.py` | OSM roads from Overpass, in 12 tiles (one big query times out) |
| 2 | `02_download_tiles.py` | OpenFreeMap z14 vector tiles |
| 3 | `03_build_network.py` | `network/lucca.net.xml.gz` + patches |
| 4 | `04_build_zones.py` | zones, trip-end weights, gateways, travel-time matrix |
| 5 | `05_generate_demand.py <day> [scale]` | `demand/<day>.trips.xml.gz` |
| 6 | `06_export_static.py` | viewer scene: buildings, land cover, walls, roads |
| 7 | `07_run_simulation.py <day> [trips]` | `results/<day>/` + vehicle replays |
| 8 | `08_export_results.py <day>` | per-edge hourly metrics, KPIs, critical points |
| 9 | `09_check_counts.py` | `results/calibration.json` |
| 10 | `10_build_summary.py` | `docs/data/summary.json` |
| 11 | `11_pack_web.py` | `docs/data/*.b64.txt` |

**Test a scenario** without touching the baseline. Edit the network (add a netconvert patch) or the demand, then run:

```bash
RUN_NAME=carducci_signals python3 scripts/07_run_simulation.py weekday demand/my_scenario.trips.xml.gz
```

Before a full run, use `scripts/tools/route_volumes.py weekday` for a 3-minute free-flow check against the counts.

### Viewer data format
The viewer is one HTML file using [deck.gl](https://deck.gl) 8.9, with no build step.

**Binary files.** They are stored as gzip + base64 text so the same page also works on hosts that only serve text:
- `static`: typed arrays for buildings, ground, roads and walls, indexed in `static.json`.
- `<day>_edges`: uint8 speed ratio, uint16 flow, delay and density per edge and hour.
- `veh/<day>_HH`: the `LVF2` vehicle replay. A 20-byte header, a per-vehicle table, then delta-coded int16 positions at 0.5 m resolution, plus heading and speed every 2 s.

**Coordinates** are local metres in the SUMO/UTM frame, relative to Piazza San Michele.

---

## Limits

- **Sparse, dated counts.** There are five calibration sections, from 2017–2021; the eastern corridors run about 25% low. More counts (Comune / Provincia, A11 toll data) would improve the model.
- **Signal plans** are not public. SUMO-generated actuated plans are used, and there are only 19 signalised junctions in OSM.
- **Not modelled:** buses, bicycles, pedestrians, parking search, roadworks, incidents and events (Lucca Comics & Games, Summer Festival).
- **Fixed departure times.** Without departure-time choice, peaks are probably sharper than in reality, so the 08–10 congestion is on the strong side.
- **Model artefacts.** Some delay at the A11 boundaries comes from vehicles waiting to enter the study area, and a few short multi-lane links deadlock until teleported. Both are excluded from the KPIs and the ranking.

## Roadmap: improvement scenarios

- [ ] **Ring road, south-west:** Carducci / Europa roundabout redesign, signal coordination on the Viali, access management for the Carducci / Palatucci / Tagliate car parks.
- [ ] **Park-and-ride at Lucca Est** with a shuttle to the Walls.
- [ ] **The planned "Assi viari" / Viabilità Est** (Ponte a Moriano – A11 Frizzone / Lucca Est) and a new Serchio bridge.
- [ ] **Ramp metering or toll-plaza layout** at Lucca Est and Capannori.
- [ ] **Demand-side measures:** staggered school starts (8:00 / 8:30), modal shift for school trips, Saturday parking guidance.
- [ ] **Comparison mode** in the viewer: scenario vs baseline difference maps.

## Data access notes
- Overpass rejected the single large query (HTTP 504), so the extract was downloaded in 12 tiles and merged (`merge_osm.py`).
- Building footprints with heights come from OpenFreeMap's OpenMapTiles z14 tiles rather than raw OSM. They are lighter, and their `render_height` values give consistent 3D heights.

## Credits

- Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) (ODbL).
- Buildings and land cover from [OpenFreeMap](https://openfreemap.org) / [OpenMapTiles](https://openmaptiles.org).
- Traffic counts:
  - [Regione Toscana](https://dati.toscana.it/dataset/sr439) (CC BY-SA);
  - [NEPA / ANAS, Viabilità Est di Lucca](https://va.mite.gov.it/File/Documento/341806);
  - [University of Pisa, Porta Sant'Anna study](https://docenti.ing.unipi.it/~dic/ingegneria_civile/bacheca/doc_pubblici/atti_lucca_21_2210208/10_pratelli_etc.pdf);
  - [Comune di Lucca, PUMS monitoring 2024](https://comune.lucca.it/app/uploads/2025/02/Documento-di-Monitoraggio2024.pdf).
- Population from ISTAT.
- Simulation by [Eclipse SUMO](https://eclipse.dev/sumo/) (EPL-2.0). Rendering by [deck.gl](https://deck.gl) (MIT).

## Licence

Code: [MIT](LICENSE). Data derived from OpenStreetMap stays under the ODbL; see [DATA_LICENSE.md](DATA_LICENSE.md).
