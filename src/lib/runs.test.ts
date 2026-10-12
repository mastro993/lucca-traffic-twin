import { describe, expect, it } from 'vitest'
import { BASE, dayData, runKey, type DayData, type Scene, type Summary } from './data'
import { runParts } from './layers'

// two roads only the baseline has (0, 1), one only the scenario has (2); one signal each
const scene = {
  roads: { major: [0, 2], minor: [1] },
  meta: {
    tls: {
      prog: [{ o: 0, p: [[60, 'G']] }, { o: 0, p: [[60, 'r']] }],
      heads: [{ t: 0, l: [0], p: [0, 0], a: 0 }, { t: 1, l: [0], p: [5, 5], a: 90 }],
      poles: [{ t: 0, p: [1, 0], a: 0, r: 3 }, { t: 1, p: [6, 5], a: 90, r: 3 }],
    },
    absent: { base: { roads: [2], tls: [1] }, before: { roads: [0, 1], tls: [0] } },
  },
} as unknown as Pick<Scene, 'roads' | 'meta'>

describe('runParts', () => {
  it('draws only the roads and signals of the run', () => {
    const base = runParts(scene, BASE), before = runParts(scene, 'before')
    expect([base.major, base.minor, before.major, before.minor]).toEqual([[0], [1], [2], []])
    expect(base.heads.map(h => h.i)).toEqual([0])
    expect(before.heads.map(h => h.i)).toEqual([1])   // the head keeps its index in meta.tls.heads, where its light is kept
    expect(before.lamps.map(l => l.h)).toEqual([1, 1, 1])
    expect(before.frame.length).toBe(2)               // its pole and its arm
  })
  it('draws everything when the scene lists no runs', () => {
    const plain = { ...scene, meta: { ...scene.meta, absent: undefined } }
    expect(runParts(plain, BASE).major).toEqual([0, 2])
  })
})

describe('run data', () => {
  const d = (n: number): DayData => ({ kpi: [{ veh_in_net: n, avg_kmh: 0, delay_vh: 0, cong_km: 0 }], hotspots: [] })
  const s = { wd: d(1), sat: d(2), runs: [], scen: { 'wd-before': d(3) } } as unknown as Summary
  it('keeps the baseline files as they were and prefixes the scenarios', () => {
    expect([runKey('wd', BASE), runKey('sat', 'before')]).toEqual(['wd', 'sat-before'])
    expect([dayData(s, 'wd', BASE), dayData(s, 'wd', 'before')].map(x => x.kpi[0].veh_in_net)).toEqual([1, 3])
  })
})
