import { queryOptions } from '@tanstack/react-query'
import type { Signals } from './signals'

export type Day = 'wd' | 'sat'
export const DAYS: Record<Day, string> = { wd: 'Weekday', sat: 'Saturday' }
export const otherDay = (d: Day): Day => (d === 'wd' ? 'sat' : 'wd')

type TypedArray = Float32Array | Uint32Array | Uint16Array | Uint8Array | Int16Array
const T = { float32: Float32Array, uint32: Uint32Array, uint16: Uint16Array, uint8: Uint8Array, int16: Int16Array }
interface IndexEntry { dtype: keyof typeof T; offset: number; length: number }

export interface Place { n: string; k: string; p: [number, number] }
export interface Meta { origin: [number, number]; index: Record<string, IndexEntry>; road_names: string[]; places: Place[]; tls: Signals }
export interface Kpi { veh_in_net: number; avg_kmh: number; delay_vh: number; cong_km: number }
export interface Hotspot {
  id: string; x: number; y: number; lonlat: [number, number]; streets: string[]; control: string; delay_h: number[]
  daily_delay_vh: number; peak_hour: number; peak_delay_vh: number; label?: string; note?: string
  rank: number   // 1-based, added on load
}
export interface Summary {
  subtitle: string
  wd: { kpi: Kpi[]; hotspots: Hotspot[] }
  sat: { kpi: Kpi[]; hotspots: Hotspot[] }
  calibration?: { label: string; src: string; obs: number; sim: number }[]
  about: { intro: string; network: string; demand: string; sim: string; hotspots: string; limits: string; credits: string; sources: { t: string; url: string }[] }
}

export interface Roads {
  n: number; pos: Float32Array; start: Uint32Array; lanes: TypedArray; cls: TypedArray; name: TypedArray; len: TypedArray; speed: TypedArray; ztl: TypedArray
  minor: number[]; major: number[]   // road indices, drawn in class order
  cum: Float32Array                  // distance along its road at every vertex
  plen: Float32Array                 // drawn length of each road
}
export interface Shapes { length: number; startIndices: TypedArray; pos: TypedArray }
export interface Scene {
  meta: Meta; roads: Roads
  bld: Shapes & { h: TypedArray }; gnd: Shapes & { cls: TypedArray }; ww: Shapes & { w: TypedArray }; wall: Shapes; rail: Shapes
}
export interface Edges { spd: Uint8Array; flow: Uint16Array; delay: Uint16Array; dens: Uint16Array }

const url = (path: string) => `${import.meta.env.BASE_URL}data/${path}`

// binary data ships as gzip + base64 text (the claude.ai artifact host serves text, not raw binaries)
export async function getBin(path: string): Promise<ArrayBuffer> {
  const r = await fetch(url(path.replace(/\.bin$/, '.b64.txt'))); if (!r.ok) throw new Error(`${path} ${r.status}`)
  const bin = atob((await r.text()).trim()), u8 = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i)
  return new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()
}
async function getJSON<J>(path: string): Promise<J> {
  const r = await fetch(url(path)); if (!r.ok) throw new Error(`${path} ${r.status}`)
  return r.json()
}

async function loadScene(): Promise<Scene> {
  const [meta, buf] = await Promise.all([getJSON<Meta>('static.json'), getBin('static.bin')])
  const v = (k: string) => { const e = meta.index[k]; return new T[e.dtype](buf, e.offset, e.length) }
  const pos = v('road_pos') as Float32Array, start = v('road_start') as Uint32Array, lanes = v('road_lanes'), cls = v('road_cls')
  const n = lanes.length
  const order = Array.from({ length: n }, (_, i) => i).sort((a, b) => cls[b] - cls[a])
  const cum = new Float32Array(pos.length / 2), plen = new Float32Array(n)
  for (let e = 0; e < n; e++) {
    let s = 0
    for (let k = start[e] + 1; k < start[e + 1]; k++) { s += Math.hypot(pos[2 * k] - pos[2 * k - 2], pos[2 * k + 1] - pos[2 * k - 1]); cum[k] = s }
    plen[e] = s
  }
  const roads: Roads = { n, pos, start, lanes, cls, name: v('road_name'), len: v('road_len'), speed: v('road_speed'), ztl: v('road_ztl'),
    minor: order.filter(i => cls[i] >= 5), major: order.filter(i => cls[i] < 5), cum, plen }
  // polygon start arrays carry a closing entry deck.gl must not see; path start arrays are passed whole
  const polys = (k: string) => { const s = v(`${k}_start`); return { length: s.length - 1, startIndices: s.subarray(0, s.length - 1), pos: v(`${k}_pos`) } }
  const paths = (k: string) => { const s = v(`${k}_start`); return { length: s.length - 1, startIndices: s, pos: v(`${k}_pos`) } }
  return { meta, roads, bld: { ...polys('bld'), h: v('bld_h') }, gnd: { ...polys('gnd'), cls: v('gnd_cls') }, ww: { ...paths('ww'), w: v('ww_w') },
    wall: polys('wall'), rail: paths('rail') }
}

async function loadSummary(): Promise<Summary> {
  const s = await getJSON<Summary>('summary.json')
  for (const d of ['wd', 'sat'] as const) s[d].hotspots = s[d].hotspots.slice(0, 12).map((h, k) => ({ ...h, rank: k + 1 }))
  return s
}

// <day>_edges: per road and hour, uint8 relative speed, then uint16 flow, delay and density (7 bytes per road-hour)
function decodeEdges(buf: ArrayBuffer): Edges {
  const NH = buf.byteLength / 7
  return { spd: new Uint8Array(buf, 0, NH), flow: new Uint16Array(buf, NH, NH), delay: new Uint16Array(buf, NH * 3, NH), dens: new Uint16Array(buf, NH * 5, NH) }
}

export const sceneQuery = queryOptions({ queryKey: ['scene'], queryFn: loadScene })
export const summaryQuery = queryOptions({ queryKey: ['summary'], queryFn: loadSummary })
export const edgesQuery = (day: Day) => queryOptions({ queryKey: ['edges', day], queryFn: async () => decodeEdges(await getBin(`${day}_edges.bin`)) })
