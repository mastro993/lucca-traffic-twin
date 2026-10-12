#!/usr/bin/env bash
# Full pipeline, from raw data to the web viewer. Steps 1-2 need internet access; the downloaded data is already in data/osm.
# A full 24 h run (step 7) takes about an hour per day type on one CPU core; the two day types run in parallel.
set -euo pipefail
cd "$(dirname "$0")"
S=scripts
[ "${DOWNLOAD:-0}" = "1" ] && python3 $S/01_download_osm.py && python3 $S/02_download_tiles.py
python3 $S/03_build_network.py              # OSM -> network/lucca.net.xml.gz (+ build/omt_geo.pkl)
python3 $S/04_build_zones.py                # zones, gateways, travel-time matrix -> build/zones.pkl
python3 $S/05_generate_demand.py weekday    # -> demand/weekday.trips.xml.gz
python3 $S/05_generate_demand.py saturday   # -> demand/saturday.trips.xml.gz
python3 $S/06_export_static.py              # scene geometry for the viewer
if [ "${SIMULATE:-1}" = "1" ]; then
  python3 $S/07_run_simulation.py weekday & python3 $S/07_run_simulation.py saturday & wait
fi
python3 $S/08_export_results.py weekday
python3 $S/08_export_results.py saturday
# the viewer's scenarios (VIEWER_SCENARIOS in scripts/common.py), when their runs from 12_scenario.py are here
for s in $(cd $S && python3 -c 'from common import VIEWER_SCENARIOS as v; print(*v)'); do
  for d in weekday saturday; do
    if [ -f results/scenarios/$s/$d/edgedata_hourly.xml.gz ]; then python3 $S/08_export_results.py $d $s; fi
  done
done
python3 $S/09_check_counts.py weekday
python3 $S/10_build_summary.py
python3 $S/11_pack_web.py
echo "Done. Run the viewer with: pnpm install && pnpm dev"
