// deck.gl layers for one frame. Static geometry is passed as binary attributes; updateTriggers keep
// per-road colours from being recomputed unless the 2-minute colour step, day, mode or theme changed.
import { COORDINATE_SYSTEM } from '@deck.gl/core/typed'
import { ColumnLayer, PathLayer, ScatterplotLayer, SolidPolygonLayer, TextLayer } from '@deck.gl/layers/typed'
import { SimpleMeshLayer } from '@deck.gl/mesh-layers/typed'
import { blendOf, C, delayStops, lerp, mix, ramp, sevColor, speedStops, volStops, type RGBA } from './color'
import type { Edges, Hotspot, Scene } from './data'
import type { Engine } from './engine'

function boxMesh() {
  const P: number[] = [], N: number[] = [], U: number[] = []
  const f = (n: number[], ...q: number[][]) => { for (const p of [q[0], q[1], q[2], q[0], q[2], q[3]]) { P.push(...p); N.push(...n); U.push(0, 0) } }
  const x0 = -.5, x1 = .5, y0 = -.5, y1 = .5, z0 = 0, z1 = 1
  f([0, 0, 1], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]); f([0, 0, -1], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0], [x1, y0, z0])
  f([1, 0, 0], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1]); f([-1, 0, 0], [x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0])
  f([0, 1, 0], [x0, y1, z0], [x0, y1, z1], [x1, y1, z1], [x1, y1, z0]); f([0, -1, 0], [x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1])
  return { positions: new Float32Array(P), normals: new Float32Array(N), texCoords: new Float32Array(U) }
}
const MESH = boxMesh()

function groundColors({ gnd }: Scene) {
  const map: Record<number, RGBA> = { 1: C.farm, 2: C.green, 3: C.wood, 4: C.urban, 5: C.ind, 6: C.civic, 9: C.water }
  const cols = new Uint8Array(gnd.cls.length * 4)
  for (let i = 0; i < gnd.cls.length; i++) { const c = map[gnd.cls[i]] || C.ground; cols.set([c[0], c[1], c[2], 255], i * 4) }
  return cols
}
/** Ground polygons with their colours baked in: rebuild after a theme change. */
export const groundData = (s: Scene) => ({ length: s.gnd.length, startIndices: s.gnd.startIndices,
  attributes: { getPolygon: { value: s.gnd.pos, size: 2 }, getFillColor: { value: groundColors(s), size: 4, normalized: true } } })
/** Binary layer data, built once so deck.gl keeps the uploaded buffers. */
export function sceneData(s: Scene) {
  const { ww, rail, wall, bld } = s
  return {
    ground: groundData(s),
    ww: { length: ww.length, startIndices: ww.startIndices, attributes: { getPath: { value: ww.pos, size: 2 } } },
    rail: { length: rail.length, startIndices: rail.startIndices, attributes: { getPath: { value: rail.pos, size: 2 } } },
    wall: { length: wall.length, startIndices: wall.startIndices, attributes: { getPolygon: { value: wall.pos, size: 2 } } },
    bld: { length: bld.length, startIndices: bld.startIndices, attributes: { getPolygon: { value: bld.pos, size: 2 }, getElevation: { value: bld.h, size: 1 } } },
  }
}

export function buildLayers(g: Engine) {
  const { roads, meta, ww } = g.scene, st = g.state, E = g.edges(st.day), B = g.B, rev = st.themeRev
  const COORD = { coordinateSystem: COORDINATE_SYSTEM.METER_OFFSETS, coordinateOrigin: [meta.origin[0], meta.origin[1], 0] as [number, number, number] }
  const roadColorAt = (E: Edges, h: number, i: number): RGBA => {
    const k = h * roads.n + i, s = E.spd[k]
    if (s === 255) return [C.road[0], C.road[1], C.road[2], 150]
    if (st.mode === 'speed') return ramp(speedStops(), s / 200)
    if (st.mode === 'vol') return ramp(volStops(), E.flow[k] / Math.max(1, roads.lanes[i]))
    return ramp(delayStops(), E.delay[k] / Math.max(0.05, roads.len[i] / 1000))
  }
  const roadWidth = (i: number) => {
    const base = Math.max(1, roads.lanes[i]) * 3.3
    if (st.mode !== 'vol') return base
    const f = E ? lerp(E.flow[B[0] * roads.n + i], E.flow[B[1] * roads.n + i], B[2]) : 0
    return Math.max(base * 0.7, Math.sqrt(f) * 0.9)
  }
  const L: unknown[] = []
  L.push(new SolidPolygonLayer({ id: 'ground', ...COORD, data: g.data.ground as never, positionFormat: 'XY', _normalize: false, pickable: false, updateTriggers: { getFillColor: rev } }))
  L.push(new PathLayer({ id: 'waterways', ...COORD, data: g.data.ww as never, positionFormat: 'XY', _pathType: 'open', getWidth: (_: unknown, { index }: { index: number }) => ww.w[index],
    widthUnits: 'meters', widthMinPixels: 0.5, getColor: C.water, updateTriggers: { getColor: rev } }))
  L.push(new PathLayer({ id: 'rail', ...COORD, data: g.data.rail as never, positionFormat: 'XY', _pathType: 'open', getWidth: 3, widthUnits: 'meters', widthMinPixels: 1,
    getColor: C.rail, updateTriggers: { getColor: rev } }))
  const roadProps = { ...COORD, positionFormat: 'XY' as const, _pathType: 'open' as const,
    getPath: (i: number) => roads.pos.subarray(roads.start[i] * 2, roads.start[i + 1] * 2) as never, getWidth: roadWidth, widthUnits: 'meters' as const, widthMaxPixels: 40,
    getColor: (i: number) => (E ? mix(roadColorAt(E, B[0], i), roadColorAt(E, B[1], i), B[2]) : C.road),
    capRounded: true, jointRounded: true, pickable: true, autoHighlight: true, highlightColor: [255, 255, 255, 90] as RGBA,
    updateTriggers: { getColor: [st.day, g.ct, st.mode, rev, !!E], getWidth: [st.mode, st.mode === 'vol' ? st.day + g.ct : 0] } }
  L.push(new PathLayer<number>({ id: 'roads-minor', data: roads.minor, widthMinPixels: 0.7, opacity: 0.7, ...roadProps }))
  L.push(new PathLayer<number>({ id: 'roads', data: roads.major, widthMinPixels: 1.6, ...roadProps }))
  L.push(new SolidPolygonLayer({ id: 'walls', ...COORD, data: g.data.wall as never, positionFormat: 'XY', _normalize: false, extruded: true, getElevation: 12, getFillColor: C.wall,
    material: { ambient: .55, diffuse: .55 }, updateTriggers: { getFillColor: rev } }))
  if (st.layers.bld) L.push(new SolidPolygonLayer({ id: 'buildings', ...COORD, data: g.data.bld as never, positionFormat: 'XY', _normalize: false, extruded: true, getFillColor: C.bldA,
    material: { ambient: .45, diffuse: .65, shininess: 8, specularColor: [40, 40, 40] }, updateTriggers: { getFillColor: rev } }))
  const f = g.follow
  if (f?.paths) for (const halo of [true, false]) L.push(new PathLayer<{ p: Float32Array; done: boolean }>({ id: halo ? 'route-halo' : 'route', ...COORD, data: f.paths,
    positionFormat: 'XY', _pathType: 'open', getPath: d => d.p as never, getWidth: halo ? 11 : 6, widthUnits: 'meters', widthMinPixels: halo ? 6 : 3, capRounded: true, jointRounded: true,
    getColor: d => (halo ? [...C.halo.slice(0, 3), d.done ? 90 : 220] : [...C.accent.slice(0, 3), d.done ? 90 : 240]) as RGBA, updateTriggers: { getColor: rev } }))
  if (st.layers.veh && g.vehView.length) {
    if (g.zoom >= 17) L.push(new SimpleMeshLayer({ id: 'veh-mesh', ...COORD, data: g.vehView as never, mesh: MESH as never, sizeScale: 1, pickable: true, material: { ambient: .6, diffuse: .6 } }))
    else L.push(new ScatterplotLayer({ id: 'veh-dots', ...COORD, data: g.vehView as never, radiusUnits: 'meters', getRadius: 3.4, radiusMinPixels: g.zoom < 13 ? 1.3 : 2.0, radiusMaxPixels: 7,
      stroked: false, pickable: true }))
  }
  if (f) L.push(new ScatterplotLayer<{ x: number; y: number; end: number }>({ id: 'follow-marks', ...COORD, data: [...f.ends, { x: g.FP.x, y: g.FP.y, end: 2 }],
    getPosition: d => [d.x, d.y, 1], radiusUnits: 'pixels', getRadius: d => (d.end === 2 ? 11 : 6), stroked: true, filled: true, lineWidthUnits: 'pixels', getLineWidth: 2.5,
    getFillColor: d => (d.end === 1 ? C.accent : [0, 0, 0, 0]), getLineColor: C.accent, updateTriggers: { getPosition: g.t, getFillColor: rev, getLineColor: rev } }))
  if (st.layers.hot) {
    const hd = g.summary[st.day].hotspots, dh = (d: Hotspot) => blendOf(d.delay_h, B)
    L.push(new ScatterplotLayer<Hotspot>({ id: 'hot-ring', ...COORD, data: hd, getPosition: d => [d.x, d.y, 1], getRadius: d => 20 + Math.sqrt(dh(d)) * 14, radiusUnits: 'meters',
      stroked: true, filled: true, getFillColor: d => { const c = sevColor(dh(d)); return [c[0], c[1], c[2], 30] }, getLineColor: d => { const c = sevColor(dh(d)); return [c[0], c[1], c[2], 200] },
      lineWidthUnits: 'pixels', getLineWidth: 1.5, updateTriggers: { getRadius: [st.day, g.ct], getFillColor: [st.day, g.ct, rev], getLineColor: [st.day, g.ct, rev] } }))
    const tall = g.zoom < 16.2, es = Math.round(Math.max(0.15, Math.min(1.6, 2 ** (13.3 - g.zoom))) * 20) / 20
    if (tall) L.push(new ColumnLayer<Hotspot>({ id: 'hot', ...COORD, data: hd, diskResolution: 16, radius: 14, extruded: true, pickable: true,
      getPosition: d => [d.x, d.y], getElevation: d => 12 + dh(d) * 10, elevationScale: es,
      getFillColor: d => { const c = sevColor(dh(d)); return [c[0], c[1], c[2], st.sel === d.id ? 255 : 215] },
      getLineColor: [255, 255, 255, 200], material: { ambient: .7, diffuse: .4 }, updateTriggers: { getElevation: [st.day, g.ct], getFillColor: [st.day, g.ct, st.sel, rev] } }))
    L.push(new TextLayer<Hotspot>({ id: 'hot-rank', ...COORD, data: hd, getPosition: d => [d.x, d.y, tall ? (12 + dh(d) * 10) * es + 20 : 6], getText: d => String(d.rank), getSize: 15,
      pickable: !tall, fontFamily: 'Barlow Condensed, Arial Narrow, sans-serif', fontWeight: 700, getColor: C.label, fontSettings: { sdf: true }, outlineWidth: 4,
      outlineColor: [...C.halo.slice(0, 3), 230] as RGBA, billboard: true, updateTriggers: { getPosition: [st.day, g.ct, tall, es], getColor: rev, outlineColor: rev } }))
  }
  if (st.layers.lbl) L.push(new TextLayer<(typeof meta.places)[number]>({ id: 'places', ...COORD, data: meta.places, getPosition: d => [d.p[0], d.p[1], 30], getText: d => d.n,
    getSize: d => (d.k === 'city' || d.k === 'town' ? 15 : 12), sizeUnits: 'pixels', fontFamily: 'Barlow Condensed, Arial Narrow, sans-serif', fontWeight: 600,
    characterSet: 'auto', getColor: [...C.label.slice(0, 3), 210] as RGBA, fontSettings: { sdf: true }, outlineWidth: 4, outlineColor: [...C.halo.slice(0, 3), 220] as RGBA,
    billboard: true, updateTriggers: { getColor: rev, outlineColor: rev } }))
  return L
}
