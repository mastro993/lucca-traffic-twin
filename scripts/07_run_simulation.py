"""24 h microscopic SUMO run.
Writes hourly edgeData, tripinfo, statistics and every vehicle's final route with its edge exit times (vehroutes.xml.gz,
turned into the viewer's trip replay by 08_export_results.py) to results/<day>/.
usage: python3 scripts/07_run_simulation.py <weekday|saturday> [trips file]
       END=3600 python3 scripts/07_run_simulation.py weekday   # quick test: first hour only
       RUN_NAME=my_scenario python3 scripts/07_run_simulation.py weekday demand/my.trips.xml.gz   # keep baseline results"""
import os, sys, subprocess
from common import NET, DEMAND, RESULTS, sumo_bin

day = sys.argv[1]
trips = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else str(DEMAND / f'{day}.trips.xml.gz')
out = RESULTS / os.environ.get('RUN_NAME', day); out.mkdir(parents=True, exist_ok=True); os.chdir(out)  # RUN_NAME=<scenario> keeps the baseline
open('edgedata_h.add.xml', 'w').write('<additional>\n  <edgeData id="hourly" period="3600" file="edgedata_hourly.xml.gz" excludeEmpty="true" withInternal="false"/>\n</additional>\n')

cmd = [sumo_bin('sumo'), '-n', str(NET), '-r', trips, '-a', 'edgedata_h.add.xml',
       '--ignore-junction-blocker', '30', '--collision.action', 'warn', '--time-to-impatience', '60', '--lanechange.duration', '0',
       '--device.rerouting.probability', '1', '--device.rerouting.period', '300', '--device.rerouting.adaptation-interval', '10',
       '--device.rerouting.adaptation-steps', '30', '--routing-algorithm', 'astar', '--weights.priority-factor', '0.5', '--threads', '2', '--ignore-route-errors',
       '--max-depart-delay', '1800', '--time-to-teleport', '180', '--begin', '0', '--end', os.environ.get('END', '90000'),
       '--no-step-log', '--duration-log.statistics', '--tripinfo-output', 'tripinfo.xml.gz', '--statistic-output', 'stats.xml',
       '--vehroute-output', 'vehroutes.xml.gz', '--vehroute-output.exit-times', '--vehroute-output.last-route', '-W']
with open('progress.log', 'w') as log:
    subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)
