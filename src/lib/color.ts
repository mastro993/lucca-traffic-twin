// Theme-aware colours read from the CSS tokens in styles.css; readTokens() refreshes them when the theme changes.
export type RGBA = [number, number, number, number]
type Stops = [number, RGBA][]

function hex2rgb(h: string): RGBA {
  h = h.trim()
  if (h.startsWith('rgb')) { const m = h.match(/[\d.]+/g)!.map(Number); return [m[0], m[1], m[2], m[3] !== undefined ? Math.round(m[3] * 255) : 255] }
  h = h.replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join('')
  const n = parseInt(h, 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 255]
}

const tokens = (g: (k: string) => RGBA) => ({
  bg: g('--bg'), ground: g('--scene-ground'), farm: g('--scene-farm'), green: g('--scene-green'), wood: g('--scene-wood'), urban: g('--scene-urban'),
  ind: g('--scene-ind'), civic: g('--scene-civic'), water: g('--scene-water'), bld: g('--scene-bld'), road: g('--scene-road'), rail: g('--scene-rail'),
  wall: g('--scene-wall'), car: g('--scene-car'), bldA: [...g('--scene-bld').slice(0, 3), 240] as RGBA, label: g('--scene-label'), halo: g('--scene-halo'),
  poi: { edu: g('--poi-edu'), health: g('--poi-health'), shop: g('--poi-shop'), sport: g('--poi-sport'), work: g('--poi-work'), civic: g('--poi-civic') },
  accent: g('--accent'), cong: ['--c-free', '--c-ok', '--c-busy', '--c-slow', '--c-jam', '--c-stop'].map(g), vol: ['--v-1', '--v-2', '--v-3', '--v-4'].map(g),
})
export const C = {} as ReturnType<typeof tokens>
export function readTokens() {
  const cs = getComputedStyle(document.documentElement)
  Object.assign(C, tokens(k => hex2rgb(cs.getPropertyValue(k))))
}

export const lerp = (a: number, b: number, t: number) => a + (b - a) * t
export function ramp(stops: Stops, v: number): RGBA { // stops ascending by value
  if (v <= stops[0][0]) return stops[0][1]
  for (let i = 1; i < stops.length; i++) if (v <= stops[i][0]) {
    const t = (v - stops[i - 1][0]) / (stops[i][0] - stops[i - 1][0]), a = stops[i - 1][1], b = stops[i][1]
    return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t), 255]
  }
  return stops[stops.length - 1][1]
}
export const mix = (a: RGBA, b: RGBA, t: number): RGBA => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t), lerp(a[3], b[3], t)]
export const css = (c: RGBA) => `rgb(${c[0]},${c[1]},${c[2]})`

// hourly figures are averages over the hour, so they belong at half past: blend the two hours around time t
export type Blend = [h0: number, h1: number, w: number]
export function hourBlend(t: number): Blend { const x = t / 3600 - 0.5, h0 = Math.floor(x); return [(h0 + 24) % 24, (h0 + 25) % 24, x - h0] }
export const blendOf = (arr: ArrayLike<number>, b: Blend) => lerp(arr[b[0]], arr[b[1]], b[2])

export type Mode = 'speed' | 'vol' | 'delay'
export const speedStops = (): Stops => [[0.08, C.cong[5]], [0.25, C.cong[4]], [0.45, C.cong[3]], [0.62, C.cong[2]], [0.8, C.cong[1]], [0.95, C.cong[0]]]
export const volStops = (): Stops => [[0, C.vol[0]], [300, C.vol[1]], [800, C.vol[2]], [1600, C.vol[3]]]
export const delayStops = (): Stops => [[0, C.cong[0]], [20, C.cong[2]], [80, C.cong[3]], [250, C.cong[4]], [700, C.cong[5]]]
export const sevColor = (vh: number) => ramp([[0, C.cong[1]], [5, C.cong[2]], [15, C.cong[3]], [40, C.cong[4]], [90, C.cong[5]]], vh)
