"""24 h microscopic SUMO run driven through TraCI.
Writes hourly edgeData, tripinfo and statistics to results/<day>/, and records a 90 s vehicle window
(every 2 s) at HH:29:00 of every hour for the 3D replay (build/web/veh/<key>_HH.bin).
usage: python3 scripts/07_run_simulation.py <weekday|saturday> [trips file]
       END=3600 python3 scripts/07_run_simulation.py weekday   # quick test: first hour only
       RUN_NAME=my_scenario python3 scripts/07_run_simulation.py weekday demand/my.trips.xml.gz   # keep baseline results"""
import os, sys, struct, json
import numpy as np
from common import NET, DEMAND, RESULTS, WEBRAW, ORIGIN, sumo_home, read_net
SUMO_HOME = sumo_home()
sys.path.insert(0, f'{SUMO_HOME}/tools')
import traci
import traci.constants as tc

day = sys.argv[1]; key = {'weekday': 'wd', 'saturday': 'sat'}[day]
trips = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else str(DEMAND / f'{day}.trips.xml.gz')
out = RESULTS / os.environ.get('RUN_NAME', day); out.mkdir(parents=True, exist_ok=True); os.chdir(out)  # RUN_NAME=<scenario> keeps the baseline
open('edgedata_h.add.xml', 'w').write('<additional>\n  <edgeData id="hourly" period="3600" file="edgedata_hourly.xml.gz" excludeEmpty="true" withInternal="false"/>\n</additional>\n')
WEB = WEBRAW / 'veh'; WEB.mkdir(parents=True, exist_ok=True)
net = read_net(NET)
X0, Y0 = net.convertLonLat2XY(*ORIGIN)
TYPES = {'car': 0, 'van': 1, 'truck': 2, 'ztl': 3}
WIN_START, WIN_LEN, WIN_DT = 29 * 60, 90, 2

cmd = [f'{SUMO_HOME}/bin/sumo', '-n', str(NET), '-r', trips, '-a', 'edgedata_h.add.xml',
       '--ignore-junction-blocker', '30', '--collision.action', 'warn', '--time-to-impatience', '60', '--lanechange.duration', '0',
       '--device.rerouting.probability', '1', '--device.rerouting.period', '300', '--device.rerouting.adaptation-interval', '10',
       '--device.rerouting.adaptation-steps', '30', '--routing-algorithm', 'astar', '--weights.priority-factor', '0.5', '--threads', '2', '--ignore-route-errors',
       '--max-depart-delay', '1800', '--time-to-teleport', '180', '--begin', '0', '--end', os.environ.get('END', '90000'),
       '--no-step-log', '--duration-log.statistics', '--tripinfo-output', 'tripinfo.xml.gz', '--statistic-output', 'stats.xml', '-W']
traci.start(cmd, label=key)
VARS = [tc.VAR_POSITION, tc.VAR_ANGLE, tc.VAR_SPEED, tc.VAR_TYPE]
log = open('progress.log', 'w')
t = 0
rec = None
END = int(os.environ.get('END', '90000'))
while t < END:
    traci.simulationStep()
    t = int(round(traci.simulation.getTime()))
    h, s = divmod(t, 3600)
    if s == WIN_START and h < 24:
        rec = {'h': h, 'frames': [], 'subs': set(), 'init': False}
        log.write(f'{t} hour {h} vehicles {traci.vehicle.getIDCount()} pending {traci.simulation.getMinExpectedNumber() - traci.vehicle.getIDCount()}\n'); log.flush()
    if rec is not None:
        for v in traci.simulation.getDepartedIDList(): traci.vehicle.subscribe(v, VARS); rec['subs'].add(v)
        if not rec['init']:
            for v in traci.vehicle.getIDList(): traci.vehicle.subscribe(v, VARS); rec['subs'].add(v)
            rec['init'] = True
            traci.simulationStep(); t = int(round(traci.simulation.getTime()))
            for v in traci.simulation.getDepartedIDList(): traci.vehicle.subscribe(v, VARS); rec['subs'].add(v)
        if (t - (rec['h'] * 3600 + WIN_START)) % WIN_DT == 0:
            res = traci.vehicle.getAllSubscriptionResults()
            rec['frames'].append({v: (r[tc.VAR_POSITION][0], r[tc.VAR_POSITION][1], r[tc.VAR_ANGLE], r[tc.VAR_SPEED], r[tc.VAR_TYPE]) for v, r in res.items()})
        if t >= rec['h'] * 3600 + WIN_START + WIN_LEN:
            # write the window
            frames = rec['frames']; nF = len(frames)
            vids = {}
            for fi, fr in enumerate(frames):
                for v in fr: vids.setdefault(v, []).append(fi)
            table, xy, ang, spd = [], [], [], []
            for v, fis in vids.items():
                # keep contiguous runs only (vehicles do not reappear)
                f0, n = fis[0], len(fis)
                if fis[-1] - f0 + 1 != n: n = next((k for k in range(1, len(fis)) if fis[k] != fis[k - 1] + 1), len(fis))
                if n < 2: continue
                ty = TYPES.get(frames[f0][v][4], 0)
                table.append((f0, n, ty))
                if any(abs(frames[fi][v][0]) > 1e6 or abs(frames[fi][v][1]) > 1e6 for fi in range(f0, f0 + n)): table.pop(); continue
                for fi in range(f0, f0 + n):
                    x, y, a, sp, _ = frames[fi][v]
                    sp = max(0.0, sp) if sp > -1e6 else 0.0; a = a if abs(a) < 1e6 else 0.0
                    xy += [int(round((x - X0) * 2)), int(round((y - Y0) * 2))]
                    ang.append(int(round(a / 360 * 256)) % 256); spd.append(min(255, int(round(sp * 3.6))))
            with open(f'{WEB}/{key}_{rec["h"]:02d}.bin', 'wb') as f:
                f.write(b'LVF1'); f.write(struct.pack('<IIff', len(table), nF, WIN_DT, rec['h'] * 3600 + WIN_START))
                f.write(np.array([[a, b] for a, b, c in table], np.uint16).tobytes())
                f.write(np.array([c for a, b, c in table], np.uint8).tobytes())
                pad = (20 + 5 * len(table)) % 2
                f.write(b'\0' * pad)
                f.write(np.clip(np.array(xy), -32767, 32767).astype(np.int16).tobytes())
                f.write(np.array(ang, np.uint8).tobytes()); f.write(np.array(spd, np.uint8).tobytes())
            log.write(f'  wrote hour {rec["h"]}: {len(table)} vehicles, {len(ang)} points\n'); log.flush()
            alive = set(traci.vehicle.getIDList())
            for v in rec['subs']:
                if v in alive:
                    try: traci.vehicle.unsubscribe(v)
                    except traci.TraCIException: pass
            rec = None
    if traci.simulation.getMinExpectedNumber() == 0 and t > 86400: break
traci.close()
log.write('DONE\n'); log.close()
