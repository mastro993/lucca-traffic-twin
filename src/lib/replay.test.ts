import { describe, expect, it } from 'vitest'
import type { Roads } from './data'
import { edgeAt, laneOf, locate, queue, VSCALE, type Routes } from './replay'

// road 0: 100 m east from (0,0), one lane; road 1: 200 m north from (110,10), two lanes, only the left one (1) turning
// into road 2: 80 m north from (110,220). All have a 10 m/s limit.
const roads = {
  pos: Float32Array.of(0, 0, 100, 0, 110, 10, 110, 210, 110, 220, 110, 300), start: Uint32Array.of(0, 2, 4, 6),
  cum: Float32Array.of(0, 100, 0, 200, 0, 80), plen: Float32Array.of(100, 200, 80), len: Float32Array.of(100, 200, 80),
  speed: Float32Array.of(10, 10, 10), lanes: Uint8Array.of(1, 2, 1), moves: new Map([[0 * 65536 + 1, 1], [1 * 65536 + 2, 2]]),
} as unknown as Roads

// cars on route 0 -> 1 -> 2 that leave each road at the given times
function cars(...trips: { dep: number; exits: [number, number, number] }[]): Routes & { n: number } {
  const n = trips.length
  return { n, dep: Uint32Array.from(trips, t => t.dep), arr: Uint32Array.from(trips, t => t.exits[2]), offs: Uint32Array.from({ length: n + 1 }, (_, i) => 3 * i),
    edge: Uint16Array.from(trips.flatMap(() => [0, 1, 2])), exit: Uint32Array.from(trips.flatMap(t => t.exits)), dpos: new Uint8Array(n), apos: new Uint8Array(n).fill(255),
    type: new Uint8Array(n), cur: new Uint16Array(n), vf: new Float32Array(n).fill(1), cap: new Float32Array(n), adv: new Float32Array(n),
    lk: new Uint16Array(n), ln: new Uint8Array(n), tau: new Float32Array(n), wait: new Uint8Array(n) }
}
const at = (c: Routes & { n: number }, i: number, t: number) => {
  const act = new Uint32Array(c.n); let na = 0
  for (let j = 0; j < c.n; j++) if (t >= c.dep[j] && t <= c.arr[j]) { edgeAt(c, j, t); act[na++] = j }
  queue(roads, c, t, act, na, new Float64Array(c.n))
  return locate(roads, c, i, t)
}
const HALF = VSCALE[0][1] / 2, SLOT = VSCALE[0][1] + 2

describe('trip replay', () => {
  it('drives at a steady speed when the road took about the free-flow time', () => {
    const c = cars({ dep: 1000, exits: [1011, 1033, 1042] })
    const a = at(c, 0, 1005.5)
    expect(a.e).toBe(0); expect(a.x).toBeCloseTo(50 - HALF); expect(a.y).toBeCloseTo(0)
    expect(a.kmh).toBeCloseTo(100 / 11 * 3.6)
  })
  it('stops at the stop line until its recorded exit, as at a red light', () => {
    const c = cars({ dep: 1000, exits: [1060, 1082, 1091] })
    expect(at(c, 0, 1005).x).toBeCloseTo(50 - HALF)                 // cruising at the limit
    const w = at(c, 0, 1040)
    expect(w.x).toBeCloseTo(100 - HALF); expect(w.kmh).toBe(0)     // waiting, front bumper on the stop line
    expect(at(c, 0, 1059.9).x).toBeCloseTo(100 - HALF)
  })
  it('queues behind the vehicles ahead and moves up as they leave', () => {
    const c = cars({ dep: 1000, exits: [1060, 1082, 1091] }, { dep: 1005, exits: [1062, 1084, 1093] })
    expect(at(c, 1, 1040).x).toBeCloseTo(100 - SLOT - HALF)        // one place behind the first car
    expect(at(c, 1, 1059).x).toBeCloseTo(100 - SLOT / 2 - HALF)    // the first car is half-way out of its place
    expect(at(c, 1, 1060).x).toBeCloseTo(100 - HALF)
  })
  it('lets a vehicle SUMO had overtake reach the stop line at its own exit time', () => {
    const c = cars({ dep: 1000, exits: [1070, 1092, 1101] }, { dep: 1005, exits: [1060, 1082, 1091] })
    expect(at(c, 1, 1040).x).toBeCloseTo(100 - SLOT - HALF)        // behind the first car
    expect(at(c, 1, 1059).x).toBeCloseTo(100 - SLOT / 2 - HALF)    // squeezing past in its last 2 s
    expect(at(c, 1, 1060).x).toBeCloseTo(100 - HALF)
    expect(at(c, 0, 1065).x).toBeCloseTo(100 - HALF)
  })
  it('keeps to a lane that leads to the next road', () => {
    const c = cars({ dep: 1000, exits: [1011, 1033, 1042] }, { dep: 1001, exits: [1012, 1034, 1043] })
    expect(laneOf(roads, c, 0, 1)).toBe(1); expect(laneOf(roads, c, 1, 1)).toBe(1)
    expect(at(c, 0, 1025).x).toBeCloseTo(110 - 1.6)                // left lane of a two-lane road heading north
  })
  it('crosses the junction from the end of one road to the start of the next', () => {
    const c = cars({ dep: 1000, exits: [1011, 1033, 1042] })
    const end = at(c, 0, 1011), start = at(c, 0, 1011.001)
    expect(Math.hypot(start.x - end.x, start.y - end.y)).toBeLessThan(0.1)
    const mid = at(c, 0, 1011.7)
    expect(mid.e).toBe(1); expect(mid.x).toBeGreaterThan(end.x); expect(mid.x).toBeLessThan(110)
  })
})
