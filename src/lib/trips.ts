// Trip replay files: every simulated trip, with the time it left each road of its route (motion in replay.ts).
// One LTR1 file per hour holds every vehicle on the road during that hour, so any clock time needs exactly one file.
import { getBin, runKey, type Day, type Run } from './data'
import { pad2 } from './format'
import type { Routes } from './replay'

export const VNAME = ['car', 'van', 'lorry', 'ZTL permit car']

export interface Trips extends Routes {
  n: number
  ready: boolean                                                              // vf set from the road speeds
  key: Float64Array; act: Uint32Array                                         // scratch for queue()
  pos: Float32Array; ori: Float32Array; col: Uint8Array; scl: Float32Array   // per-frame instance buffers for deck.gl
}

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
  return { n, dep, arr, offs, edge, exit, type, dpos, apos, cur: new Uint16Array(n), vf: new Float32Array(n).fill(1), cap: new Float32Array(n), adv: new Float32Array(n),
    lk: new Uint16Array(n), ln: new Uint8Array(n), tau: new Float32Array(n), wait: new Uint8Array(n),
    ready: false, key: new Float64Array(n), act: new Uint32Array(n),
    pos: new Float32Array(n * 3), ori: new Float32Array(n * 3), col: new Uint8Array(n * 4), scl: new Float32Array(n * 3) }
}

// hour files: undefined while loading, null if missing
const cache: Record<string, { v: Trips | null | undefined; p: Promise<Trips | null> }> = {}
const key = (day: Day, run: Run, h: number) => `${runKey(day, run)}_${pad2(h)}`
function entry(day: Day, run: Run, h: number) {
  const k = key(day, run, h)
  let c = cache[k]
  if (!c) { const e = { v: undefined } as (typeof cache)[string]; e.p = getBin(`trips/${k}.bin`).then(parseTrips).catch(() => null).then(v => (e.v = v)); c = cache[k] = e }
  return c
}
/** The hour's trips, starting the download if needed. */
export const trips = (day: Day, run: Run, h: number) => entry(day, run, h).v
export const loadTrips = (day: Day, run: Run, h: number) => entry(day, run, h).p
/** Drop hour files away from the clock. */
export function keepTrips(day: Day, run: Run, hour: number) {
  const keep = [hour, (hour + 1) % 24, (hour + 23) % 24].map(h => key(day, run, h))
  for (const k in cache) if (!keep.includes(k)) delete cache[k]
}
