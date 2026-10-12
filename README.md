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
| **Clock** | The simulation runs as a continuous 24-hour clock at 1×, 10×, 60× or 360× real time. Traffic builds up and fades minute by minute; nothing restarts when the hour changes. At midnight the clock wraps to the start of the same simulated day, which begins with an empty network. |
| **Roads** | Coloured by speed (simulated speed ÷ speed limit), volume (vehicles/h per lane) or delay (vehicle-minutes lost per km). The hourly averages are blended as the clock moves, so colours change gradually. |
| **Vehicles** | Every simulated trip, replayed from departure to arrival along the route SUMO chose, at the times each vehicle entered and left every road. On each road a vehicle drives in a lane that leads to its next road, at its own free speed, and waits in the queue at the stop line until the second SUMO let it go, so vehicles stop at red lights and queue behind each other. Dark (light theme) or white (dark theme) = cars, orange = vans and lorries, blue = ZTL permit holders, red = crawling (under 5 km/h). **Click a vehicle to follow it**: the camera tracks it, its route is drawn, and a card shows departure, arrival, distance and speed. |
| **Traffic lights** | The 22 signals in the network, running the fixed-time plans SUMO simulated. Zoomed in, each approach has a pole with an arm over its lanes and a head per lane whose red, amber or green lamp is lit (heads are drawn at twice their real size); zoomed out, each head is a coloured dot. Hover a light for its state, the seconds until it changes and the cycle length. |
| **Critical points** | The 12 junction clusters with the most daily delay. Column height = delay at the current time; click one to fly to it at its peak hour. |
| **24-hour strip** | Network-wide delay per hour (bars = selected day, dashed = the other day) with the clock's playhead. Drag to scrub through the day; **Play** runs the clock. |
| **Panel** | Vehicles on the road and their average speed right now (counted from the replay), delay and km of congested road (blended hourly figures), plus the method, the calibration table and the sources. |

Deep links: `?h=8` opens 08:00 (`?h=8.5` opens 08:30), `?d=sat` opens Saturday, `?z=16` zooms in. For example, [`?d=sat&h=11`](https://mastro993.github.io/lucca-traffic-twin/?d=sat&h=11) opens the Saturday 11:00 peak.

| Saturday 11:00 | Weekday 17:00, close-up (dark mode) |
|---|---|
| ![Saturday](docs/assets/saturday.jpg) | ![Close-up](docs/assets/closeup.jpg) |

---

## Key findings (baseline)

**Weekday.**
- The network peaks at **08:00–10:00**: about 3,200 vehicle-hours are lost per hour, up to about 8,600 vehicles are on the road at once, the average speed is 31–32 km/h, and up to about 105 km of road run below half the speed limit.
- The evening peak (17:00–19:00) is milder, at about 2,000 vehicle-hours per hour.
- Over the whole day: 19,400 vehicle-hours lost and 3.0 million vehicle-km.

| # | Critical point | Control | Peak | Delay (veh-h/day) |
|---|---|---|---|---|
| 1 | Viale Carducci / Viale Europa roundabout | roundabout | 18h | 439 |
| 2 | Viale Nieri / Via delle Tagliate (Porta Sant'Anna) | priority | 19h | 316 |
| 3 | A11 at the Lucca Est exit | motorway diverge | 09h | 286 |
| 4 | Porta Sant'Anna roundabout (Luporini / Papi / Carducci) | roundabout | 08h | 249 |
| 5 | Viale Europa south (San Concordio) | priority | 08h | 244 |
| 6 | Via delle Tagliate | priority | 18h | 210 |
| 7 | Viale Giacomo Puccini / Via Alfredo Catalani | signals | 08h | 205 |
| 8 | Monte San Quirico bridgehead (north) | priority | 09h | 202 |
| 9 | Viale Europa / Via Teresa Bandettini | roundabout | 08h | 198 |
| 10 | Via Carlo Angeloni / Via Castruccio Buonamici | priority | 18h | 190 |

Also high on the list: the A11 approaching the Capannori exit and the Viale Luporini / Via San Donato roundabout.

**Saturday.** The peak is at **11:00–12:00** (about 1,600 vehicle-hours per hour). Delay concentrates on the west and south-west of the ring road around the Walls (the Viali), driven by traffic to the car parks: Carducci / Europa roundabout (368 veh-h/day), Porta Sant'Anna side streets (277), Porta Sant'Anna roundabout (213), Viale Europa / Bandettini (195), the Viale Puccini / Via Catalani signals (170).

**The pattern.** The bottlenecks cluster in three places:
1. **The south-west corner of the Viali.** Here Viale Europa, carrying traffic from the A11 Lucca Est exit, meets the ring road and the big car parks (Carducci, Palatucci, Tagliate). A 2005 University of Pisa count had already found Viale Carducci to be the most saturated approach.
2. **The Serchio crossings.** Monte San Quirico, Ponte San Pietro (SR439) and Ponte a Moriano (SS12) are the only river crossings in the area, and they meter the morning inbound flow.
3. **The A11 exits.** Lucca Est and Capannori.

---

## How it works

```
OpenStreetMap ──► netconvert ──► SUMO network ──┐
OpenMapTiles buildings + land use ──► zones ─────┼──► tour-based demand ──► SUMO 24 h microsimulation ──► edge data ──► critical points ──► web viewer
ISTAT population, traffic counts ──► calibration ┘                         (vehroutes: trip replay)
```

### Network
- **Source:** the OpenStreetMap road graph for the bbox 43.795–43.915 N, 10.420–10.620 E, about 16 × 13 km.
- **Conversion:** SUMO `netconvert` with guessed ramps, roundabouts and signals, OSM turn restrictions and lane counts. The result has about 1,700 km of road, 10,332 directed links and 4,721 junctions.
- **ZTL:** inside the Walls the network is closed to general traffic; only permit holders (`custom1`), taxis, buses and deliveries can enter.
- **Speed limits:** derived from building density, as OSM rarely tags them. 50 km/h in built-up areas, 60–90 km/h outside, 30 km/h in the ZTL, 130 km/h on the A11.
- **Traffic lights:** the 23 junction signals and 18 signalised pedestrian crossings tagged in OSM give 22 signals (netconvert joins the nodes of one junction and drops crossings it treats as plain geometry). Real signal plans are not public, so each runs a fixed-time plan with Italian standard timings:
  - a 70 s cycle (the typical urban junction cycle), split into one green stage per pair of opposite approaches, with a short left-turn stage where netconvert adds one;
  - 4 s amber, the usual urban value (the Ministry of Transport note 67906/2007 sets 3 s as the minimum and refers to 3, 4 and 5 s for approaches at 50, 60 and 70 km/h);
  - 2 s all-red between stages;
  - no coordination: each signal starts its cycle at its own fixed offset, derived from its id, so the city does not switch in step;
  - pedestrian crossings are not joined to nearby signals, otherwise netconvert gives each movement of the group its own stage. As pedestrians are not simulated, a crossing turns red for vehicles only during its amber and all-red time.

  Fixed-time plans are deterministic, so the viewer replays each light from its plan and shows exactly what the simulated vehicles obeyed: in the weekday 08:00 hour, 99.9% of the vehicles leaving a signalised approach do so on green or amber.
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
- **Recording:** `07_run_simulation.py` writes hourly edge statistics and every vehicle's final route with the time it left each road (SUMO vehroute output with exit times), which the viewer replays.
- **Teleports:** vehicles stuck for more than 3 minutes are teleported, standard SUMO practice. This affected 1.4% of trips on the weekday and 1.1% on Saturday.
- **Trip averages:** 9.5 km and 13 min on a weekday (4.0 min lost); 9.5 km and 12 min on Saturday.

### Critical points
- **Clusters:** junctions are grouped into clusters, either roundabouts or nodes joined by links shorter than 45 m.
- **Score:** each cluster gets the vehicle-hours lost on its approach links (SUMO `timeLoss`, measured against free-flow speed).
- **Excluded:** insertion queues on boundary roads, and lane-end deadlock artefacts (near-zero speed with almost no throughput). One junction at the Lucca Ovest toll is left out of the ranking for this reason.

### Calibration
Weekday daily traffic, both directions:

| Section | Observed | Simulated | Ratio | Source |
|---|---:|---:|---:|---|
| SR439 Via Sarzanese at Ponte San Pietro | 14,500 | 16,453 | 1.13 | Regione Toscana station P058, 2019/2021 |
| SS12 Brennero, north of Lucca | 19,068 | 19,150 | 1.00 | NEPA / ANAS, 2017 |
| SR435 Via Pesciatina at Antraccoli | 15,272 | 11,918 | 0.78 | NEPA / ANAS, 2017 |
| Viale Europa, Capannori (busiest section) | 21,062 | 15,236 | 0.72 | NEPA / ANAS, 2017 |
| Via Romana, east (busiest section) | 24,140 | 22,174 | 0.92 | NEPA / ANAS, 2017 |

- The simulated peak-hour shares are 7.5–10% of daily traffic; the stations measured 8.2–9.5%.
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
  weekday/, saturday/         hourly edgeData (SUMO meandata) and run statistics (tripinfo and vehroutes are not committed)
  *_results.json              hourly KPIs and ranked critical points
  calibration.json, run_stats.json
  scenarios/<name>/<day>/     scenario runs and their comparison with the baseline (not committed unless worth keeping)
scenarios/<name>/             network changes to test, as netconvert patch files (see Scenarios)
scripts/                      the pipeline (01–12), shared helpers and diagnostics
src/                          the web viewer (Vite + React + TanStack Router/Query, deployed to GitHub Pages)
public/data/                  packed viewer data written by steps 6, 10 and 11
docs/assets/                  README screenshots
run_pipeline.sh               runs everything end to end
```

## Reproduce

```bash
pip install -r requirements.txt            # includes the SUMO binaries (eclipse-sumo)
SIMULATE=0 ./run_pipeline.sh               # rebuild network, demand, viewer data from the committed inputs (~5 min)
./run_pipeline.sh                          # ... and re-run both 24 h simulations (about an hour each, in parallel)
DOWNLOAD=1 ./run_pipeline.sh               # also re-download OSM and building tiles first
pnpm install && pnpm dev                   # open http://localhost:5173/lucca-traffic-twin/
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
| 7 | `07_run_simulation.py <day> [trips]` | `results/<day>/`: edge data, statistics, tripinfo, vehroutes |
| 8 | `08_export_results.py <day>` | per-edge hourly metrics, KPIs, critical points, trip replay |
| 9 | `09_check_counts.py` | `results/calibration.json` |
| 10 | `10_build_summary.py` | `public/data/summary.json` |
| 11 | `11_pack_web.py` | `public/data/*.b64.txt` |
| 12 | `12_scenario.py <name> <day>` | `results/scenarios/<name>/<day>/`: a scenario run and its comparison with the baseline |

### Scenarios
A scenario changes the road network and is compared with a reference run of the unchanged network. It is a folder
`scenarios/<name>/` of [netconvert patch files](https://sumo.dlr.de/docs/Networks/PlainXML.html), applied on top of
`network/lucca.net.xml.gz`, using the ids in that file:

| File | Changes | Example |
|---|---|---|
| `*.tll.xml` | signal plans | `<tlLogic id="248886555" type="static" programID="0" offset="64">` with its `<phase>`s |
| `*.nod.xml` | junction control | `<node id="…" type="traffic_light"/>`, `type="priority"` |
| `*.edg.xml` | roads | `<edge id="…" numLanes="2" speed="8.33"/>`, `disallow="passenger"`, `<delete id="…"/>` |
| `*.con.xml` | turning movements | `<connection from="…" to="…"/>`, `<delete from="…" to="…"/>` |
| `<day>.trips.xml.gz` | demand (optional) | replaces `demand/<day>.trips.xml.gz` |

Vehicles choose their route when they depart and every 5 minutes, so traffic finds its own way through the changed network.

```bash
python3 scripts/12_scenario.py baseline weekday                   # the reference run, once per day type (~1 h)
python3 scripts/12_scenario.py puccini_signals weekday            # build, simulate 24 h, compare with the reference
END=36000 python3 scripts/12_scenario.py puccini_signals weekday  # until 10:00 only, compared over the same hours
SEED=2 python3 scripts/12_scenario.py puccini_signals weekday     # another random seed (run the baseline with it too)
COMPARE=1 python3 scripts/12_scenario.py puccini_signals weekday  # compare an existing run again
```

The comparison prints and writes to `comparison.json` the time lost, vehicle-km and vehicles on the road per hour, the
trip statistics (full-day runs only) and the roads where time lost changed most. These totals include every road, also
the boundary insertion queues the critical-point ranking leaves out.

**Compare like with like.** The reference is the scenario `baseline` (an empty folder) rather than the committed
`results/<day>/`, and SUMO runs on a single thread. With two threads, as the committed baseline was run, two runs of the
same network differed by 11% in daily time lost, more than most changes are worth; on one thread a run is repeated
exactly. Any change still reshuffles which vehicle gets which random speed, so repeat a promising scenario with a few
`SEED`s (and the baseline with each) before trusting a difference of a few per cent.

`scenarios/puccini_signals` is a worked example: the signals of critical point 7 on a 90 s cycle instead of 70 s. On one
seed it cut the time lost on the junction's four approaches by 3% (188 to 183 veh-h a day), while the network total
moved by +1.9% and single hours by up to ±30% on roads kilometres away: one changed light reshuffles the whole run, which
is why a single seed cannot settle a result.

Before a full run, use `scripts/tools/route_volumes.py weekday` for a 3-minute free-flow check against the counts.

### Viewer
The viewer (`src/`, `index.html`, `package.json` at the repository root) is a [Vite](https://vite.dev) + React + TypeScript app (pnpm), rendering with [deck.gl](https://deck.gl) 8.9.
[TanStack Router](https://tanstack.com/router) parses the deep links and loads the data before the first frame,
[TanStack Query](https://tanstack.com/query) caches the data files, and [TanStack Store](https://tanstack.com/store) shares the UI state
between the panels and the render loop.

- `src/lib/engine.ts`: the deck.gl scene and its animation loop (clock, vehicle replay, follow camera, picking).
- `src/lib/layers.ts`: the deck.gl layers for each frame.
- `src/lib/signals.ts`: the traffic light state at any clock time, from the fixed-time plans.
- `src/lib/data.ts`, `src/lib/trips.ts`: data loading and decoding.
- `src/lib/replay.ts`: where each vehicle is between the exit times SUMO recorded: lanes, queues, junction crossings.
- `src/components/`: the control panel, the 24-hour strip and the overlays.

```bash
pnpm dev        # dev server
pnpm test       # unit tests (Vitest)
pnpm build      # type-check and build to dist/
```

Every push to `main` that touches the viewer builds the site and deploys it to GitHub Pages (`.github/workflows/pages.yml`).

### Viewer data format

**Binary files.** They are stored as gzip + base64 text so the same page also works on hosts that only serve text:
- `static`: typed arrays for buildings, ground, roads and walls, indexed in `static.json`. Roads are drawn along the middle of their lanes; `move_from`, `move_to` and `move_lanes` list, for each pair of consecutive roads, the lanes of the first (a bit mask, bit 0 = rightmost) that lead to the second.
- `<day>_edges`: uint8 speed ratio, uint16 flow, delay and density per edge and hour.
- `trips/<day>_HH`: the `LTR1` trip replay, one file per hour holding every vehicle on the road during that hour, so any clock time needs a single file. A 16-byte header (magic, vehicles, route edges, hour start), then per vehicle the uint32 departure second and the uint16 route length; per route edge a uint16 road index and the uint16 seconds since the previous exit; finally per vehicle the type and the departure and arrival positions on their edges (uint8, 0–255 of the edge length). The viewer rebuilds the motion in between the way [MATSim](https://matsim.org) draws its queue snapshots. On each road a vehicle drives in a lane that leads to its next road, at its free speed (the speed limit times its own speed factor, estimated from its fastest roads), until it reaches the back of the queue of vehicles that entered the lane before it and leave first; it waits there, moving up as they leave (each gives up its place over its last 2 s), until its own exit time, then crosses the junction in a straight line. A vehicle that took at most 3 s, or 25%, longer than its free-flow time on a road (whichever is more) drives it at a steady speed instead. SUMO only lets a vehicle leave a signalised approach on green or amber, so the replayed vehicles stop at red lights.

**Traffic lights** are in `static.json` under `tls`: `prog` holds each signal's plan (offset and `[seconds, state]` phases, one SUMO state letter per controlled link), `heads` one head per controlled lane (signal index, link indices, stop-line position, heading in degrees clockwise from north) and `poles` one pole per approach (position, heading, arm reach in metres). A head shows green if any of its links has `G` or `g`, amber for `y`, red otherwise.

**Coordinates** are local metres in the SUMO/UTM frame, relative to Piazza San Michele.

---

## Limits

- **Sparse, dated counts.** There are five calibration sections, from 2017–2021; the eastern corridors run about 25% low. More counts (Comune / Provincia, A11 toll data) would improve the model.
- **Signal plans** are not public. Fixed-time plans with standard Italian timings are used (see [Network](#network)); real plans may be actuated, coordinated or switch to flashing amber at night. OSM tags only 23 signalised junctions in the area.
- **Not modelled:** buses, bicycles, pedestrians, parking search, roadworks, incidents and events (Lucca Comics & Games, Summer Festival).
- **Fixed departure times.** Without departure-time choice, peaks are probably sharper than in reality, so the 08–10 congestion is on the strong side.
- **Replayed motion.** Only the second each vehicle left each road is recorded, not its lane or its speed along the road, so the viewer reconstructs both (see [Viewer data format](#viewer-data-format)). Delay shows as standing in queues rather than as slow driving, and where SUMO let a vehicle pass another in a lane the replay may briefly draw them overlapping.
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
