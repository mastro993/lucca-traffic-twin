import { describe, expect, it } from 'vitest'
import { AMBER, GREEN, RED, signalAt, type Signals } from './signals'

// a two-phase netconvert plan: 29 s green, 4 s amber, 2 s all-red for each direction, 70 s cycle
const s: Signals = {
  prog: [{ o: 0, p: [[29, 'rrrGGgGGg'], [4, 'rrryyyyyy'], [2, 'rrrrrrrrr'], [29, 'GGGGrrrrr'], [4, 'yyyyrrrrr'], [2, 'rrrrrrrrr']] }],
  heads: [{ t: 0, l: [6, 7, 8], p: [0, 0], a: 0 }, { t: 0, l: [0, 1, 2], p: [0, 0], a: 180 }, { t: 0, l: [2, 3], p: [0, 0], a: 90 }],
  poles: [],
}
const at = (h: number, t: number) => signalAt(s, s.heads[h], t)

describe('signalAt', () => {
  it('follows the phases through the cycle', () => {
    expect(at(0, 0)).toEqual({ light: GREEN, left: 29 })
    expect(at(0, 30.5)).toEqual({ light: AMBER, left: 2.5 })
    expect(at(0, 33)).toEqual({ light: RED, left: 37 })   // all-red, the other direction's phases, all-red again
    expect(at(1, 33)).toEqual({ light: RED, left: 2 })
    expect(at(1, 40)).toEqual({ light: GREEN, left: 24 })
  })
  it('repeats every cycle at any clock time', () => {
    expect(at(0, 8 * 3600 + 5)).toEqual(at(0, (8 * 3600 + 5) % 70))
    expect(at(1, -65)).toEqual(at(1, 5))
  })
  it('delays the plan by its offset, as SUMO does', () => {
    const late: Signals = { ...s, prog: [{ ...s.prog[0], o: 64 }] }
    expect(signalAt(late, s.heads[0], 0)).toEqual({ light: GREEN, left: 23 })
    expect(signalAt(late, s.heads[0], 64)).toEqual(at(0, 0))
  })
  it('shows green when any movement of the lane may go', () => {
    expect(at(2, 0).light).toBe(GREEN)    // link 3 green, link 2 red
    expect(at(2, 36).light).toBe(GREEN)   // link 2 and 3 green
  })
})
