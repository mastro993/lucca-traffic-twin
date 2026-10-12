import { shallow, useSelector } from '@tanstack/react-store'
import { useState } from 'react'
import { delayStops, speedStops, volStops, type Mode } from '../lib/color'
import type { Day, PoiCat } from '../lib/data'
import type { Engine } from '../lib/engine'
import { ctxText, fmt, hhmm } from '../lib/format'
import { viewer, type LayerKey } from '../lib/store'
import { Spots } from './Spots'

const DAY_BUTTONS: [Day, string][] = [['wd', 'Weekday'], ['sat', 'Saturday']]
const MODE_BUTTONS: [Mode, string][] = [['speed', 'Speed'], ['vol', 'Volume'], ['delay', 'Delay']]
const POI_CATS: [PoiCat, string][] = [['edu', 'Schools'], ['health', 'Hospitals, clinics'], ['shop', 'Big stores, markets'], ['sport', 'Sports grounds'],
  ['work', 'Factories, industry'], ['civic', 'Stations, civic, culture']]
const LAYER_TOGGLES: [LayerKey, string][] = [['veh', 'Vehicles'], ['tls', 'Traffic lights'], ['bld', 'Buildings'], ['hot', 'Critical points'], ['lbl', 'Place names'], ['poi', 'Points of interest']]

export function Panel({ engine }: { engine: Engine }) {
  const [collapsed, setCollapsed] = useState(() => window.innerWidth < 760)
  const { day, run, mode } = useSelector(viewer, s => ({ day: s.day, run: s.run, mode: s.mode }), { compare: shallow })
  const runs = engine.summary.runs
  return <aside id="panel" className={collapsed ? 'collapsed' : undefined} aria-label="Simulation controls">
    <button className="sheet-handle" onClick={() => setCollapsed(c => !c)} aria-label="Expand or collapse panel" />
    <div className="scroll">
      <div className="seg" role="group" aria-label="Day type">
        {DAY_BUTTONS.map(([d, label]) => <button key={d} aria-pressed={day === d} onClick={() => void engine.setDay(d)}>{label}</button>)}
      </div>
      {runs.length > 1 && <div>
        <div className="seg" role="group" aria-label="Scenario">
          {runs.map(r => <button key={r.id} aria-pressed={run === r.id} onClick={() => void engine.setRun(r.id)}>{r.label}</button>)}
        </div>
        <p className="hint">{runs.find(r => r.id === run)?.note}</p>
      </div>}
      <Clock />
      <Kpis />
      <div className="legend">
        <div className="label">Colour roads by</div>
        <div className="seg" role="group" aria-label="Road colour metric">
          {MODE_BUTTONS.map(([m, label]) => <button key={m} aria-pressed={mode === m} onClick={() => engine.setMode(m)}>{label}</button>)}
        </div>
        <Legend mode={mode} />
      </div>
      <div>
        <div className="label" style={{ marginBottom: 6, display: 'flex', justifyContent: 'space-between' }}><span>Critical points by daily delay</span><span>this hour</span></div>
        <Spots engine={engine} />
      </div>
      <p className="hint">Click a vehicle to follow its trip from departure to arrival.</p>
      <About engine={engine} />
    </div>
  </aside>
}

// Layer switches float in a drawer on the right: a pin button that pulls the box out from the edge and pushes it
// back. Closed at first on phones, where the panel is a bottom sheet.
export function Layers({ engine }: { engine: Engine }) {
  const layers = useSelector(viewer, s => s.layers)
  const [open, setOpen] = useState(() => window.innerWidth >= 760)
  return <div id="layers" className={open ? 'open' : undefined}>
    <button className="handle" aria-expanded={open} aria-controls="layers-box" aria-label="Layers" onClick={() => setOpen(o => !o)}>
      <svg viewBox="0 0 24 24"><path d="M12 2a7 7 0 0 0-7 7c0 5.25 7 13 7 13s7-7.75 7-13a7 7 0 0 0-7-7zm0 9.5a2.5 2.5 0 1 1 0-5 2.5 2.5 0 0 1 0 5z" /></svg>
    </button>
    <aside id="layers-box" aria-label="Layers">
      <div className="label">Layers</div>
      <div className="toggles" role="group" aria-label="Layers">
        {LAYER_TOGGLES.map(([k, label]) => <label key={k}>
          <input type="checkbox" checked={layers[k]} onChange={e => engine.setLayer(k, e.target.checked)} /> {label}
        </label>)}
      </div>
      {layers.poi && <ul className="poi-key" aria-label="Points of interest">
        {POI_CATS.map(([c, label]) => <li key={c}><i style={{ background: `var(--poi-${c})` }} />{label}</li>)}
      </ul>}
    </aside>
  </div>
}

function Clock() {
  const { day, hour, t } = useSelector(viewer, s => ({ day: s.day, hour: s.hour, t: s.t }), { compare: shallow })
  return <div className="clock">
    <div className="time">{hhmm(t)}</div>
    <div className="ctx">{ctxText(day, hour)}</div>
  </div>
}

function Kpis() {
  const k = useSelector(viewer, s => s.kpi)
  return <div className="kpis">
    <div className="kpi"><b>{fmt(k.veh)}</b><span>vehicles on the road now</span></div>
    <div className="kpi"><b>{fmt(k.kmh, 1)}</b><span>average speed now, km/h</span></div>
    <div className="kpi"><b>{fmt(k.delay)}</b><span>delay, vehicle-hours per hour</span></div>
    <div className="kpi"><b>{fmt(k.cong, 1)}</b><span>km of road below half speed</span></div>
  </div>
}

const LEGENDS = {
  speed: [speedStops, ['stopped', '25%', '45%', '62%', '80%', 'free flow']],
  vol: [volStops, ['0', '300', '800', '1600+ veh/h/lane']],
  delay: [delayStops, ['0', '20', '80', '250', '700+ veh-min/km']],
} as const
function Legend({ mode }: { mode: Mode }) {
  useSelector(viewer, s => s.themeRev)
  const [getStops, ticks] = LEGENDS[mode], stops = getStops()
  const lo = stops[0][0], hi = stops[stops.length - 1][0]
  const g = stops.map(([v, c]) => `rgb(${c[0]},${c[1]},${c[2]}) ${((v - lo) / (hi - lo) * 100).toFixed(0)}%`).join(',')
  return <>
    <div className="bar" style={{ background: `linear-gradient(90deg, ${g})` }} />
    <div className="ticks">{ticks.map(t => <span key={t}>{t}</span>)}</div>
  </>
}

function About({ engine }: { engine: Engine }) {
  const { about: a, calibration = [] } = engine.summary
  return <details>
    <summary>Method, data and limits</summary>
    <div className="body">
      <p>{a.intro}</p>
      <p><b>Network.</b> {a.network}</p><p><b>Demand.</b> {a.demand}</p><p><b>Simulation.</b> {a.sim}</p>
      <p><b>Validation against counts</b> (weekday, both directions):</p>
      <table>
        <thead><tr><th>Section</th><th className="n">Observed</th><th className="n">Simulated</th></tr></thead>
        <tbody>{calibration.map(c => <tr key={c.label}>
          <td>{c.label}<br /><span style={{ color: 'var(--ink-3)' }}>{c.src}</span></td><td className="n">{fmt(c.obs)}</td><td className="n">{fmt(c.sim)}</td>
        </tr>)}</tbody>
      </table>
      <p><b>Critical points.</b> {a.hotspots}</p>
      <p><b>Limits.</b> {a.limits}</p>
      <p><b>Sources.</b> {a.sources.map((s, k) => <span key={s.url}>{k > 0 && ' · '}<a href={s.url} target="_blank" rel="noopener">{s.t}</a></span>)}</p>
      <p style={{ color: 'var(--ink-3)' }}>{a.credits}</p>
    </div>
  </details>
}
