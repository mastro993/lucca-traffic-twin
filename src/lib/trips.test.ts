import { describe, expect, it } from 'vitest'
import { validateSearch } from './search'
import { parseTrips } from './trips'

// one LTR1 vehicle: departs at 1000 s from the start of road 0, exits it at 1010 s, arrives at 1030 s at the middle of road 1
function ltr1() {
  const b = new ArrayBuffer(16 + 4 + 2 + 2 * 2 + 2 * 2 + 3), dv = new DataView(b)
  dv.setUint32(0, 0x3152544c, true); dv.setUint32(4, 1, true); dv.setUint32(8, 2, true); dv.setUint32(12, 0, true)
  dv.setUint32(16, 1000, true); dv.setUint16(20, 2, true)                // departure, route length
  dv.setUint16(22, 0, true); dv.setUint16(24, 1, true)                    // route edges
  dv.setUint16(26, 10, true); dv.setUint16(28, 20, true)                  // seconds since the previous exit
  dv.setUint8(30, 0); dv.setUint8(31, 0); dv.setUint8(32, 128)            // type, departure and arrival positions
  return b
}

describe('trip replay', () => {
  const c = parseTrips(ltr1())
  it('decodes exit and arrival times', () => {
    expect([...c.exit]).toEqual([1010, 1030])
    expect(c.arr[0]).toBe(1030)
    expect([...c.edge, c.apos[0]]).toEqual([0, 1, 128])
  })
  it('rejects other files', () => expect(() => parseTrips(new ArrayBuffer(16))).toThrow('not LTR1'))
})

describe('deep links', () => {
  it('parses the documented parameters', () => {
    expect(validateSearch({ d: 'sat', h: 8.5, z: 16, still: '' })).toEqual({ d: 'sat', h: 8.5, z: 16, still: true })
  })
  it('stays stable when the router re-validates its own output', () => {
    const once = validateSearch({ h: 8 })
    expect(validateSearch({ ...once })).toEqual(once)
    expect(once.still).toBeUndefined()
  })
})
