// The 3D scene and its animation loop. The clock (t, in seconds of the day) runs continuously; the map colours
// follow it in 2-minute steps (ct) and every vehicle is placed from the trip replay on every frame.
import { AmbientLight, Deck, FlyToInterpolator, LightingEffect, WebMercatorViewport, _SunLight, type PickingInfo } from '@deck.gl/core/typed'
import type { QueryClient } from '@tanstack/react-query'
import { C, hourBlend, lerp, readTokens, type Blend, type Mode } from './color'
import { edgesQuery, otherDay, type Day, type Hotspot, type Scene, type Summary } from './data'
import { fmt, hh, hhmm, spotName } from './format'
import { buildLayers, groundData, sceneData } from './layers'
import { cycleOf, LIGHT_NAME, signalAt, type Head } from './signals'
import { initialState, patch, viewer, type LayerKey, type Tip } from './store'
import { keepTrips, locate, roadPoint, trips, VNAME, VSCALE, type Routes, type Spot, type Trips } from './trips'

export interface Init { day: Day; t: number; z?: number; still: boolean }
type ViewState = { longitude: number; latitude: number; zoom: number; pitch: number; bearing: number; [k: string]: unknown }
type VehView = { length: number; attributes?: Record<string, unknown> }
interface Follow extends Routes {
  type: number; km: Float32Array; d0: number; total: number; k: number; since: number; from: [number, number, number] | null
  paths: { p: Float32Array; done: boolean }[] | null; ends: { x: number; y: number; end: number }[]
  card: { label: string; when: string; progress: number; meta: string }
}

export class Engine {
  readonly deck: Deck
  readonly data: ReturnType<typeof sceneData>
  t: number; ct = -1; B: Blend; zoom: number; vs: ViewState
  vehView: VehView = { length: 0 }; vehSet: Trips | null = null; live = { n: 0, kmh: 0 }
  follow: Follow | null = null; FP = {} as Spot
  sig: Uint8Array; sigKey = ''   // light of every signal head now, and a string of them that changes when any light does
  private readonly LP = {} as Spot   // scratch point for placing vehicles
  private raf = 0; private last = performance.now(); private lastLive = -1e9
  private readonly rm = matchMedia('(prefers-reduced-motion: reduce)').matches
  private readonly mvp: WebMercatorViewport
  private readonly cleanup: (() => void)[] = []

  constructor(parent: HTMLDivElement, readonly scene: Scene, readonly summary: Summary, private readonly qc: QueryClient, init: Init) {
    viewer.setState(() => initialState(init.day, init.t))
    readTokens(); this.data = sceneData(scene); this.sig = new Uint8Array(scene.meta.tls.heads.length)
    this.t = init.t; this.B = hourBlend(init.t)
    const o = scene.meta.origin; this.mvp = new WebMercatorViewport({ longitude: o[0], latitude: o[1] })
    const narrow = window.innerWidth < 760, bounds = { maxPitch: 75, minZoom: 11, maxZoom: 19 }
    this.vs = init.z !== undefined ? { longitude: 10.4955, latitude: 43.8396, zoom: init.z, pitch: 60, bearing: -25, ...bounds }
      : { longitude: narrow ? 10.507 : 10.493, latitude: narrow ? 43.838 : 43.846, zoom: narrow ? 12.4 : 13.25, pitch: 52, bearing: -18, ...bounds }
    this.zoom = this.vs.zoom
    const lighting = new LightingEffect({ amb: new AmbientLight({ color: [255, 255, 255], intensity: 1.0 }),
      sun: new _SunLight({ timestamp: Date.UTC(2026, 9, 13, 9, 30), color: [255, 250, 240], intensity: 1.6, _shadow: false }) })
    this.deck = new Deck({ parent, effects: [lighting], initialViewState: this.vs, controller: { inertia: true }, layers: [], pickingRadius: 4,
      onViewStateChange: ({ viewState }) => { this.vs = viewState as ViewState; this.zoom = this.vs.zoom },
      getTooltip: null, onHover: i => this.onHover(i), onClick: i => this.onClick(i),
      getCursor: ({ isHovering, isDragging }) => (isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab') })

    const retheme = () => { readTokens(); this.data.ground = groundData(scene); patch({ themeRev: this.state.themeRev + 1 }) }
    const mq = matchMedia('(prefers-color-scheme: dark)'); mq.addEventListener('change', retheme)
    const mo = new MutationObserver(retheme); mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape' && this.follow) this.stopFollow() }
    document.addEventListener('keydown', esc)
    this.cleanup.push(() => mq.removeEventListener('change', retheme), () => mo.disconnect(), () => document.removeEventListener('keydown', esc))

    this.updateLive()
    patch({ playing: !this.rm && !init.still })
    if (init.still) {   // a still frame (for screenshots): no loop, redraw only when the controls change
      this.tick(performance.now())
      const sub = viewer.subscribe(() => this.render()); this.cleanup.push(() => sub.unsubscribe())
    } else this.raf = requestAnimationFrame(this.frame)
    void this.qc.prefetchQuery(edgesQuery(otherDay(init.day)))   // background-load the other day
  }

  destroy() { cancelAnimationFrame(this.raf); this.cleanup.forEach(f => f()); this.deck.finalize() }

  get state() { return viewer.state }
  edges(day: Day) { return this.qc.getQueryData(edgesQuery(day).queryKey) }

  // ---------- controls
  setTime(t: number) {
    this.t = t; const h = Math.floor(t / 3600)
    if (h !== this.state.hour) { patch({ hour: h }); keepTrips(this.state.day, h) }
  }
  /** Move the clock from the UI, updating the panels at once. */
  scrub(t: number) { this.setTime(t); this.updateLive() }
  async setDay(day: Day) {
    patch({ day, sel: null }); this.stopFollow(); keepTrips(day, this.state.hour)
    await this.qc.ensureQueryData(edgesQuery(day)); this.updateLive()
  }
  setMode(mode: Mode) { patch({ mode }) }
  setPlaying(playing: boolean) { patch({ playing }) }
  setMult(mult: number) { patch({ mult }) }
  setLayer(key: LayerKey, on: boolean) { patch({ layers: { ...this.state.layers, [key]: on } }) }
  selectSpot(id: string, fly: boolean) {
    patch({ sel: this.state.sel === id && !fly ? null : id })
    const h = this.summary[this.state.day].hotspots.find(x => x.id === id)
    if (!h || !fly) return
    this.stopFollow(); this.scrub(h.peak_hour * 3600 + 1800)
    this.deck.setProps({ initialViewState: { ...this.vs, longitude: h.lonlat[0], latitude: h.lonlat[1], zoom: 16.2, pitch: 58, bearing: Math.random() * 60 - 30,
      transitionDuration: this.rm ? 0 : 1600, transitionInterpolator: this.rm ? undefined : new FlyToInterpolator() } })
  }

  // ---------- animation loop
  private frame = (now: number) => {
    const dt = Math.min(0.1, (now - this.last) / 1000); this.last = now
    const { playing, mult, day, hour } = this.state
    if (playing) {
      let t = this.t + dt * mult
      // hold at the hour boundary until the next hour's trips are in (the call also prefetches them)
      if (trips(day, (hour + 1) % 24) === undefined) t = Math.min(t, (hour + 1) * 3600 - 0.001)
      this.setTime(t >= 86400 ? t - 86400 : t)
    }
    this.tick(now)
    this.raf = requestAnimationFrame(this.frame)
  }
  private tick(now: number) {
    const ct = Math.floor(this.t / 120)
    if (ct !== this.ct) { this.ct = ct; this.B = hourBlend(ct * 120 + 60) }
    this.updateVehicles(); this.updateSignals(); this.updateFollow(now)
    if (now - this.lastLive > 200) { this.lastLive = now; this.updateLive() }
    this.render()
  }
  private render() { this.deck.setProps({ layers: buildLayers(this) as never }) }

  // clock and KPIs: vehicles and speed are counted live from the replay, the rest blends the hourly figures
  private updateLive() {
    const k = this.summary[this.state.day].kpi, b = hourBlend(this.t), at = (key: keyof (typeof k)[number]) => lerp(k[b[0]][key], k[b[1]][key], b[2])
    const v = this.vehSet, f = this.follow
    patch({ t: this.t, follow: f && { ...f.card },
      kpi: { veh: v ? this.live.n : at('veh_in_net'), kmh: v && this.live.n ? this.live.kmh : at('avg_kmh'), delay: at('delay_vh'), cong: at('cong_km') } })
  }

  private updateVehicles() {
    const { day, hour, layers } = this.state, c = trips(day, hour) ?? null, roads = this.scene.roads
    this.vehSet = c; this.live.n = 0; this.live.kmh = 0
    if (!c) { this.vehView = { length: 0 }; return }
    const t = this.t, draw = layers.veh, m = c.n, LP = this.LP; let ksum = 0
    const stopCol = C.cong[4], carCol = C.car, trkCol = [214, 122, 52, 255], ztlCol = [70, 150, 230, 255]
    // one slot per trip, so a picked index is the trip index in any frame; trips not on the road are parked far off-screen
    for (let i = 0; i < m; i++) {
      if (t < c.dep[i] || t > c.arr[i]) { if (draw) { c.pos[3 * i] = 1e8; c.pos[3 * i + 1] = 1e8 } continue }
      locate(roads, c, i, t, LP); this.live.n++; ksum += LP.kmh
      if (!draw) continue
      c.pos[3 * i] = LP.x; c.pos[3 * i + 1] = LP.y; c.pos[3 * i + 2] = 0.3
      c.ori[3 * i] = 0; c.ori[3 * i + 1] = -LP.ang; c.ori[3 * i + 2] = 0
      const ty = c.type[i], sc = VSCALE[ty] || VSCALE[0]
      c.scl[3 * i] = sc[0]; c.scl[3 * i + 1] = sc[1]; c.scl[3 * i + 2] = sc[2]
      const col = LP.kmh < 5 ? stopCol : ty === 2 || ty === 1 ? trkCol : ty === 3 ? ztlCol : carCol
      c.col[4 * i] = col[0]; c.col[4 * i + 1] = col[1]; c.col[4 * i + 2] = col[2]; c.col[4 * i + 3] = 255
    }
    this.live.kmh = this.live.n ? ksum / this.live.n : 0
    if (!draw || !this.live.n) { this.vehView = { length: 0 }; return }
    this.vehView = { length: m, attributes: { getPosition: { value: c.pos.subarray(0, 3 * m), size: 3 }, getOrientation: { value: c.ori.subarray(0, 3 * m), size: 3 },
      getScale: { value: c.scl.subarray(0, 3 * m), size: 3 }, getColor: { value: c.col.subarray(0, 4 * m), size: 4, normalized: true },
      getFillColor: { value: c.col.subarray(0, 4 * m), size: 4, normalized: true } } }
  }

  private updateSignals() {
    const s = this.scene.meta.tls; let key = ''
    for (let i = 0; i < s.heads.length; i++) { this.sig[i] = signalAt(s, s.heads[i], this.t).light; key += this.sig[i] }
    this.sigKey = key
  }

  // ---------- follow one vehicle: a self-contained copy of its trip (it outlives hour files), its route drawn on the map
  startFollow(c: Trips, i: number) {
    const roads = this.scene.roads, o = c.offs[i], n = c.offs[i + 1] - o, edge = c.edge.slice(o, o + n)
    const km = new Float32Array(n + 1)   // route km at the start of each edge, counted from the departure point
    for (let k = 0; k < n; k++) km[k + 1] = km[k] + roads.len[edge[k]] / 1000
    const d0 = c.dpos[i] / 255 * roads.len[edge[0]] / 1000, total = km[n - 1] + c.apos[i] / 255 * roads.len[edge[n - 1]] / 1000 - d0
    const vs = this.vs, from = !this.rm ? [vs.longitude, vs.latitude, vs.zoom] as [number, number, number] : null
    const f: Follow = { type: c.type[i], dep: c.dep.slice(i, i + 1), arr: c.arr.slice(i, i + 1), offs: Uint32Array.of(0, n), edge, exit: c.exit.slice(o, o + n),
      dpos: c.dpos.slice(i, i + 1), apos: c.apos.slice(i, i + 1), cur: new Uint16Array(1), km, d0, total, k: -1, paths: null, since: performance.now(), from,
      ends: [{ ...roadPoint(roads, edge[0], c.dpos[i] / 255 * roads.plen[edge[0]]), end: 0 }, { ...roadPoint(roads, edge[n - 1], c.apos[i] / 255 * roads.plen[edge[n - 1]]), end: 1 }],
      card: { label: `Following a ${VNAME[c.type[i]] || 'car'}`, when: `${hhmm(c.dep[i])} → ${hhmm(c.arr[i])}`, progress: 0, meta: '' } }
    this.follow = f
    if (!from) this.vs = { ...vs, zoom: Math.max(vs.zoom, 16) }   // reduced motion: jump instead of easing in
    this.updateFollow(performance.now())
    patch({ sel: null, follow: { ...f.card } })
  }
  stopFollow() { this.follow = null; patch({ follow: null }) }
  private routePath(f: Follow, k0: number, k1: number) { // flat XY path through route edges k0..k1-1
    const { start: st, pos } = this.scene.roads; let len = 0
    for (let k = k0; k < k1; k++) len += st[f.edge[k] + 1] - st[f.edge[k]]
    const out = new Float32Array(len * 2); let o = 0
    for (let k = k0; k < k1; k++) { const e = f.edge[k]; out.set(pos.subarray(st[e] * 2, st[e + 1] * 2), o); o += (st[e + 1] - st[e]) * 2 }
    return out
  }
  private updateFollow(now: number) {
    const f = this.follow; if (!f) return
    const roads = this.scene.roads, FP = this.FP
    const tc = f.arr[0] > 86400 && this.t < f.arr[0] - 86400 ? this.t + 86400 : this.t   // a trip running past midnight goes on after the clock wraps
    locate(roads, f, 0, Math.min(Math.max(tc, f.dep[0]), f.arr[0]), FP)
    if (FP.k !== f.k) { f.k = FP.k; f.paths = [{ p: this.routePath(f, 0, f.k + 1), done: true }, { p: this.routePath(f, f.k, f.offs[1]), done: false }] }
    // ease the camera onto the vehicle over 1.2 s, then stay locked on it; zoom, tilt and rotation stay with the user
    // metres in the scene frame -> lon/lat, with the same projection deck.gl uses for METER_OFFSETS
    const [lon, lat] = this.mvp.addMetersToLngLat(this.scene.meta.origin, [FP.x, FP.y])
    const u = f.from ? Math.min(1, (now - f.since) / 1200) : 1, w = u * u * (3 - 2 * u), fr = f.from || [lon, lat, this.vs.zoom]
    this.vs = { ...this.vs, longitude: lerp(fr[0], lon, w), latitude: lerp(fr[1], lat, w), zoom: u < 1 ? lerp(fr[2], Math.max(fr[2], 16), w) : this.vs.zoom,
      transitionDuration: 0, transitionInterpolator: undefined }
    this.zoom = this.vs.zoom; this.deck.setProps({ initialViewState: this.vs })
    const done = Math.max(0, f.km[FP.k] + FP.f * roads.len[FP.e] / 1000 - f.d0)
    f.card.progress = Math.min(100, done / Math.max(0.01, f.total) * 100)
    f.card.meta = tc < f.dep[0] ? `Departs at ${hhmm(f.dep[0])} · ${fmt(f.total, 1)} km trip`
      : tc >= f.arr[0] ? `Arrived after ${fmt(f.total, 1)} km in ${Math.round((f.arr[0] - f.dep[0]) / 60)} min`
      : `${fmt(done, 1)} of ${fmt(f.total, 1)} km · ${fmt(FP.kmh)} km/h · ${this.scene.meta.road_names[roads.name[FP.e]] || 'unnamed road'}`
  }

  // ---------- picking
  private onHover(info: PickingInfo) {
    const tip = this.tipFor(info)
    patch({ tip: tip && { ...tip, x: Math.min(window.innerWidth - 270, info.x + 14), y: Math.max(8, info.y - 10) } })
  }
  private tipFor(info: PickingInfo): Omit<Tip, 'x' | 'y'> | null {
    const id = info.layer?.id, { day, hour } = this.state, { roads, meta } = this.scene
    if (!id || (!info.object && info.index < 0)) return null
    if (id === 'roads' || id === 'roads-minor') {
      const i = info.object as number, E = this.edges(day); if (!E) return null
      const k = hour * roads.n + i, s = E.spd[k], lim = roads.speed[i] * 3.6
      return { title: meta.road_names[roads.name[i]] || 'Unnamed road', ztl: !!roads.ztl[i], lines: s === 255 ? ['no traffic this hour']
        : [`${fmt(s / 200 * lim)} km/h of ${fmt(lim)} · ${fmt(E.flow[k])} veh/h`, `${fmt(E.delay[k])} veh-min lost · ${roads.lanes[i]} lane${roads.lanes[i] > 1 ? 's' : ''}`] }
    }
    const v = this.vehSet
    if (id.startsWith('veh') && v && info.index < v.n) {
      const p = locate(roads, v, info.index, this.t)
      return { title: VNAME[v.type[info.index]] || 'car', lines: [`${fmt(p.kmh)} km/h · ${meta.road_names[roads.name[p.e]] || 'unnamed road'}`, 'click to follow its trip'] }
    }
    if (id.startsWith('tls')) {
      const h = info.object as Head, s = this.scene.meta.tls, now = signalAt(s, h, this.t)
      return { title: 'Traffic light', lines: [`${LIGHT_NAME[now.light]} · changes in ${Math.ceil(now.left)} s`, `fixed-time plan · ${cycleOf(s.prog[h.t])} s cycle`] }
    }
    if (id === 'hot' || id === 'hot-rank') {
      const h = info.object as Hotspot
      return { title: `#${h.rank} ${spotName(h)}`, note: h.note,
        lines: [`${fmt(h.delay_h[hour], 1)} veh-h lost ${hh(hour)}–${hh((hour + 1) % 24)}`, `${fmt(h.daily_delay_vh)} veh-h per day · peak ${hh(h.peak_hour)}`] }
    }
    return null
  }
  private onClick(info: PickingInfo) {
    const id = info.layer?.id, v = this.vehSet; if (!id) return
    if ((id === 'hot' || id === 'hot-rank') && info.object) this.selectSpot((info.object as Hotspot).id, false)
    else if (id.startsWith('veh') && v && info.index >= 0 && info.index < v.n) this.startFollow(v, info.index)
  }
}
