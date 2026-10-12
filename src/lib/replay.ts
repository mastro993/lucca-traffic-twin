// Where every replayed vehicle is. SUMO recorded only the second each vehicle left each road, so the motion in between
// is rebuilt the way MATSim draws its queue snapshots: a vehicle cruises at its own free speed, then waits in the queue
// at the end of the road (a red light, a give-way line, a jam) until its recorded exit. Vehicles keep to a lane that
// leads to their next road, stop behind the vehicles that entered that lane before them, and cross junctions in a
// straight line. As SUMO only lets a vehicle leave on green or amber, the replay stops at red lights too.
import type { Roads } from './data'

export const VSCALE = [[1.8, 4.4, 1.45], [2.0, 5.6, 2.1], [2.5, 11, 3.4], [1.8, 4.3, 1.45]]   // width, length, height
const GAP = [2.0, 2.5, 3.0, 2.0]        // SUMO minGap of each vehicle type, metres
const VMAX = [55, 55, 25, 55]           // SUMO maxSpeed of each vehicle type, m/s
const LANE_W = 3.2
const CLEAR = 2                         // seconds a leaving vehicle takes to clear its place in the queue

/** What locate() needs: route k of trip i is edge[offs[i]..offs[i+1]) with exit times in exit[]. */
export interface Routes {
  dep: Uint32Array; arr: Uint32Array; offs: Uint32Array; edge: Uint16Array; exit: Uint32Array; dpos: Uint8Array; apos: Uint8Array; type: Uint8Array
  cur: Uint16Array      // route index of the current road, a cache for the next lookup
  vf: Float32Array      // free speed as a share of the speed limit, from the trip's fastest roads
  cap: Float32Array     // furthest point the vehicle can reach on its road: the back of the queue ahead of it
  adv: Float32Array     // speed at which the back of that queue is moving forward, drawn m/s
  lk: Uint16Array; ln: Uint8Array; tau: Float32Array; wait: Uint8Array   // on route road lk - 1: lane, junction crossing seconds, queues
}
export interface Spot { x: number; y: number; ang: number; kmh: number; k: number; e: number; f: number }

/** Point at distance d along road e (extended straight past either end), with its heading in degrees from north. */
export function roadPoint(roads: Roads, e: number, d: number, out: Partial<Spot> = {}) {
  const P = roads.pos, cum = roads.cum, b = roads.start[e + 1] - 1; let v = roads.start[e] + 1
  while (v < b && cum[v] < d) v++
  const u = cum[v] > cum[v - 1] ? Math.min(1, (d - cum[v - 1]) / (cum[v] - cum[v - 1])) : 0
  const x0 = P[2 * v - 2], y0 = P[2 * v - 1], dx = P[2 * v] - x0, dy = P[2 * v + 1] - y0
  out.x = x0 + dx * u; out.y = y0 + dy * u; out.ang = Math.atan2(dx, dy) * 180 / Math.PI
  return out as Spot
}

/** Route index of trip i's road at time t. */
export function edgeAt(c: Routes, i: number, t: number) {
  const o = c.offs[i], n = c.offs[i + 1] - o; let k = c.cur[i]
  if (k && c.exit[o + k - 1] > t) k = 0
  while (k < n - 1 && c.exit[o + k] < t) k++
  return (c.cur[i] = k)
}

/** Lane (0 = rightmost) trip i drives on along route road k: one that leads to its next road, the same on every frame. */
export function laneOf(roads: Roads, c: Routes, i: number, k: number) {
  const o = c.offs[i], e = c.edge[o + k], n = Math.min(8, roads.lanes[e] || 1)
  const mask = (k < c.offs[i + 1] - o - 1 && roads.moves.get(e * 65536 + c.edge[o + k + 1])) || (1 << n) - 1
  let pick = (c.dep[i] + k) % popcount(mask)
  for (let l = 0; l < 8; l++) if (mask & (1 << l) && !pick--) return l
  return 0
}
const popcount = (m: number) => { let s = 0; for (; m; m &= m - 1) s++; return s }

const space = (c: Routes, i: number) => VSCALE[c.type[i]]?.[1] + GAP[c.type[i]] || 6.4
const drawnPerMetre = (roads: Roads, e: number) => roads.plen[e] / Math.max(0.1, roads.len[e])

/** Trip free speeds: the fastest road of each trip (timed over at least 8 s) against its speed limit, 0.7-1.3. */
export function speedFactors(roads: Roads, c: Routes, n: number) {
  const vf = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    const a = c.offs[i], b = c.offs[i + 1], vmax = VMAX[c.type[i]] ?? 55; let best = 0
    for (let k = a + 1; k < b - 1; k++) {   // whole roads only: the first and last are driven in part
      const dt = c.exit[k] - c.exit[k - 1], e = c.edge[k]
      if (dt >= 8) best = Math.max(best, roads.len[e] / dt / Math.min(roads.speed[e], vmax))
    }
    vf[i] = best ? Math.min(1.3, Math.max(0.7, best)) : 1
  }
  return vf
}

// how trip i drives route road k, worked out once per road: its lane, the seconds it takes to cross the junction
// before the road, and whether it waits in a queue or, near free flow, drives at a steady speed to the exit
function enter(roads: Roads, c: Routes, i: number, k: number) {
  if (c.lk[i] === k + 1) return
  const o = c.offs[i], n = c.offs[i + 1] - o, e = c.edge[o + k], lane = laneOf(roads, c, i, k), v = speed(roads, c, i, e)
  const t0 = k ? c.exit[o + k - 1] : c.dep[i], t1 = c.exit[o + k]
  let tau = 0
  if (k) {
    const A = crossing(roads, c, i, k, {}), B = shifted(roads, e, -half(c, i), lat(roads, e, lane), {})
    tau = Math.min(Math.hypot(B.x - A.x, B.y - A.y) / v, (t1 - t0) / 2)
  }
  const drive = ((k < n - 1 ? 1 : c.apos[i] / 255) - (k ? 0 : c.dpos[i] / 255)) * roads.plen[e] / v
  c.lk[i] = k + 1; c.ln[i] = lane; c.tau[i] = tau; c.wait[i] = +(t1 - t0 - tau - drive > Math.max(3, drive / 4))
}
const half = (c: Routes, i: number) => (VSCALE[c.type[i]]?.[1] ?? 4.4) / 2
const lat = (roads: Roads, e: number, lane: number) => ((Math.min(8, roads.lanes[e] || 1) - 1) / 2 - lane) * LANE_W   // metres right of the drawn road
const speed = (roads: Roads, c: Routes, i: number, e: number) => Math.max(1, Math.min(roads.speed[e], VMAX[c.type[i]] ?? 55) * c.vf[i]) * drawnPerMetre(roads, e)
// where trip i left the road before route road k
function crossing(roads: Roads, c: Routes, i: number, k: number, out: Partial<Spot>) {
  const p = c.edge[c.offs[i] + k - 1]
  return shifted(roads, p, roads.plen[p] - half(c, i), lat(roads, p, laneOf(roads, c, i, k - 1)), out)
}

const LANE_KEY = 2 ** 35   // queue() sort key: (road * 8 + lane) * 2^35 + entry second * 2^17 + trip index

/** Queue places at time t for the vehicles act[0..na), whose road edgeAt() has set: fills cap and adv. Reorders act. */
export function queue(roads: Roads, c: Routes, t: number, act: Uint32Array, na: number, key: Float64Array) {
  const K = key.subarray(0, na)
  for (let j = 0; j < na; j++) {
    const i = act[j], o = c.offs[i], k = c.cur[i]
    enter(roads, c, i, k)
    K[j] = (c.edge[o + k] * 8 + c.ln[i]) * LANE_KEY + (k ? c.exit[o + k - 1] : c.dep[i]) * 131072 + i
  }
  K.sort()
  for (let j = 0; j < na; j++) act[j] = K[j] % 131072
  for (let g = 0; g < na;) {
    const lane = Math.floor(K[g] / LANE_KEY); let h = g
    while (h < na && Math.floor(K[h] / LANE_KEY) === lane) h++
    const e = c.edge[c.offs[act[g]] + c.cur[act[g]]], sc = drawnPerMetre(roads, e)
    let ahead = 0, adv = 0   // room taken by every vehicle that entered the lane earlier, and how fast it frees up
    for (let p = g; p < h; p++) {
      const i = act[p], o = c.offs[i], k = c.cur[i], x = c.exit[o + k]
      let a = ahead, v = adv
      // a vehicle SUMO let overtake (it entered earlier but leaves later) makes room only as the overtaker leaves.
      // ponytail: only the 8 vehicles that entered just before are checked; look further back if queues still overlap
      for (let q = p - 1; q >= g && q >= p - 8; q--) {
        const j = act[q], xj = c.exit[c.offs[j] + c.cur[j]]
        if (xj > x) { const sj = space(c, j) * sc; a += (fade(x, t) - fade(xj, t)) * sj; v += (freeing(x, t) - freeing(xj, t)) * sj }
      }
      c.cap[i] = (k < c.offs[i + 1] - o - 1 ? 1 : c.apos[i] / 255) * roads.plen[e] - a; c.adv[i] = v
      const s = space(c, i) * sc
      ahead += fade(x, t) * s; adv += freeing(x, t) * s
    }
    g = h
  }
}
// share of its place in the queue a vehicle leaving at x still holds at time t: it gives it up over its last CLEAR seconds
const fade = (x: number, t: number) => Math.min(1, Math.max(0, (x - t) / CLEAR))
const freeing = (x: number, t: number) => (x > t && x - t < CLEAR ? 1 / CLEAR : 0)   // rate at which it does

/** Where trip i is at time t, from the queue places queue() last set. x, y is the middle of the vehicle. */
export function locate(roads: Roads, c: Routes, i: number, t: number, out: Partial<Spot> = {}): Spot {
  const k = edgeAt(c, i, t), o = c.offs[i], n = c.offs[i + 1] - o, e = c.edge[o + k], L = roads.plen[e], sc = drawnPerMetre(roads, e)
  enter(roads, c, i, k)
  const t0 = k ? c.exit[o + k - 1] : c.dep[i], t1 = c.exit[o + k], ts = t0 + c.tau[i]
  const d0 = (k ? 0 : c.dpos[i] / 255) * L, d1 = (k < n - 1 ? 1 : c.apos[i] / 255) * L, v = speed(roads, c, i, e), h = half(c, i), y = lat(roads, e, c.ln[i])
  out.k = k; out.e = e
  if (t < ts) {   // across the junction, in a straight line from the end of the previous road
    const A = crossing(roads, c, i, k, {}), B = shifted(roads, e, d0 - h, y, out), dx = B.x - A.x, dy = B.y - A.y, u = (t - t0) / c.tau[i]
    out.x = A.x + dx * u; out.y = A.y + dy * u; out.ang = Math.atan2(dx, dy) * 180 / Math.PI
    out.kmh = Math.hypot(dx, dy) / c.tau[i] / sc * 3.6; out.f = d0 / L
    return out as Spot
  }
  let d: number
  if (t >= t1) { d = d1; out.kmh = 0 }
  else if (!c.wait[i]) {                                // about free flow, or a little slower: steady speed to the exit
    d = Math.min(d0 + (d1 - d0) * (t - ts) / (t1 - ts), Math.max(0, c.cap[i])); out.kmh = (d1 - d0) / sc / (t1 - ts) * 3.6
  } else {                                              // cruise, then queue until the exit time
    const free = d0 + v * (t - ts), cap = Math.min(d1, Math.max(0, c.cap[i]))   // a departing vehicle joins the back of the queue
    if (free < cap) { d = free; out.kmh = v / sc * 3.6 } else { d = cap; out.kmh = cap < d1 ? c.adv[i] / sc * 3.6 : 0 }
  }
  shifted(roads, e, d - h, y, out); out.f = d / L
  return out as Spot
}

// point at distance d along road e, moved lat metres to the right of the road
function shifted(roads: Roads, e: number, d: number, lat: number, out: Partial<Spot>) {
  roadPoint(roads, e, d, out)
  const a = out.ang! * Math.PI / 180
  out.x! += Math.cos(a) * lat; out.y! -= Math.sin(a) * lat
  return out as Spot
}
