// Trip replay: every simulated trip, driven along its route between the edge exit times SUMO recorded.
// One LTR1 file per hour holds every vehicle on the road during that hour, so any clock time needs exactly one file.
import { getBin, type Day, type Roads } from './data'
import { pad2 } from './format'

export const VSCALE = [[1.8, 4.4, 1.45], [2.0, 5.6, 2.1], [2.5, 11, 3.4], [1.8, 4.3, 1.45]]
export const VNAME = ['car', 'van', 'lorry', 'ZTL permit car']

/** What locate() needs: n routes, route k of trip i is edge[offs[i]..offs[i+1]) with exit times in exit[]. */
export interface Routes { dep: Uint32Array; arr: Uint32Array; offs: Uint32Array; edge: Uint16Array; exit: Uint32Array; dpos: Uint8Array; apos: Uint8Array; cur: Uint16Array }
export interface Trips extends Routes {
  n: number; type: Uint8Array
  pos: Float32Array; ori: Float32Array; col: Uint8Array; scl: Float32Array   // per-frame instance buffers for deck.gl
}
export interface Spot { x: number; y: number; ang: number; kmh: number; k: number; e: number; f: number }

export function parseTrips(buf: ArrayBuffer): Trips {
  const dv = new DataView(buf); if (dv.getUint32(0, true) !== 0x3152544c) throw new Error('not LTR1')
  const n = dv.getUint32(4, true), m = dv.getUint32(8, true); let o = 16
  const take = <A extends Uint32Array | Uint16Array | Uint8Array>(A: new (b: ArrayBuffer, o: number, k: number) => A, k: number) => { const a = new A(buf, o, k); o += a.byteLength; return a }
  const dep = take(Uint32Array, n), cnt = take(Uint16Array, n), edge = take(Uint16Array, m), dt = take(Uint16Array, m)
  const type = take(Uint8Array, n), dpos = take(Uint8Array, n), apos = take(Uint8Array, n)
  const offs = new Uint32Array(n + 1), exit = new Uint32Array(m), arr = new Uint32Array(n)
  for (let i = 0; i < n; i++) {
    const a = offs[i], b = offs[i + 1] = a + cnt[i]; let x = dep[i]
    for (let k = a; k < b; k++) exit[k] = x += dt[k]
    arr[i] = x
  }
  return { n, dep, arr, offs, edge, exit, type, dpos, apos, cur: new Uint16Array(n),
    pos: new Float32Array(n * 3), ori: new Float32Array(n * 3), col: new Uint8Array(n * 4), scl: new Float32Array(n * 3) }
}

// point at distance d along road e, with its heading in degrees
export function roadPoint(roads: Roads, e: number, d: number, out: Partial<Spot> = {}) {
  const P = roads.pos, cum = roads.cum, b = roads.start[e + 1] - 1; let v = roads.start[e] + 1
  while (v < b && cum[v] < d) v++
  const u = cum[v] > cum[v - 1] ? Math.min(1, (d - cum[v - 1]) / (cum[v] - cum[v - 1])) : 0
  const x0 = P[2 * v - 2], y0 = P[2 * v - 1], dx = P[2 * v] - x0, dy = P[2 * v + 1] - y0
  out.x = x0 + dx * u; out.y = y0 + dy * u; out.ang = Math.atan2(dx, dy) * 180 / Math.PI
  return out as Spot
}

// where trip i is at time t: it moves at constant speed along each edge, from entry to exit time
export function locate(roads: Roads, c: Routes, i: number, t: number, out: Partial<Spot> = {}): Spot {
  const o = c.offs[i], n = c.offs[i + 1] - o; let k = c.cur[i]
  if (k && c.exit[o + k - 1] > t) k = 0
  while (k < n - 1 && c.exit[o + k] < t) k++
  c.cur[i] = k
  const t0 = k ? c.exit[o + k - 1] : c.dep[i], t1 = c.exit[o + k], e = c.edge[o + k]
  const f0 = k ? 0 : c.dpos[i] / 255, f1 = k < n - 1 ? 1 : c.apos[i] / 255
  const u = t1 > t0 ? Math.min(1, Math.max(0, (t - t0) / (t1 - t0))) : 1
  roadPoint(roads, e, (f0 + (f1 - f0) * u) * roads.plen[e], out)
  out.kmh = t1 > t0 ? Math.min(150, Math.abs(f1 - f0) * roads.len[e] / (t1 - t0) * 3.6) : 0
  out.k = k; out.e = e; out.f = f0 + (f1 - f0) * u
  return out as Spot
}

// hour files: undefined while loading, null if missing
const cache: Record<string, { v: Trips | null | undefined; p: Promise<Trips | null> }> = {}
const key = (day: Day, h: number) => `${day}_${pad2(h)}`
function entry(day: Day, h: number) {
  const k = key(day, h)
  let c = cache[k]
  if (!c) { const e = { v: undefined } as (typeof cache)[string]; e.p = getBin(`trips/${k}.bin`).then(parseTrips).catch(() => null).then(v => (e.v = v)); c = cache[k] = e }
  return c
}
/** The hour's trips, starting the download if needed. */
export const trips = (day: Day, h: number) => entry(day, h).v
export const loadTrips = (day: Day, h: number) => entry(day, h).p
/** Drop hour files away from the clock. */
export function keepTrips(day: Day, hour: number) {
  const keep = [hour, (hour + 1) % 24, (hour + 23) % 24].map(h => key(day, h))
  for (const k in cache) if (!keep.includes(k)) delete cache[k]
}
