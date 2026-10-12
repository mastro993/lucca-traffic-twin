import { shallow, useSelector } from '@tanstack/react-store'
import { useLayoutEffect, useRef, useState, type PointerEvent } from 'react'
import { blendOf, css, hourBlend, sevColor } from '../lib/color'
import { dayData, DAYS, otherDay } from '../lib/data'
import type { Engine } from '../lib/engine'
import { fmt, hhmm, pad2 } from '../lib/format'
import { viewer } from '../lib/store'

const SPEEDS = [1, 10, 60, 360]

export function Strip({ engine }: { engine: Engine }) {
  const { playing, mult } = useSelector(viewer, s => ({ playing: s.playing, mult: s.mult }), { compare: shallow })
  return <div id="strip">
    <div className="transport">
      <button className="play" onClick={() => engine.setPlaying(!playing)} aria-label={playing ? 'Pause the day' : 'Play the day'}>
        <svg viewBox="0 0 24 24"><path d={playing ? 'M6 4h4v16H6zM14 4h4v16h-4z' : 'M7 4l13 8-13 8z'} /></svg>
      </button>
      <div className="speed" role="group" aria-label="Replay speed">
        {SPEEDS.map(s => <button key={s} aria-pressed={mult === s} onClick={() => engine.setMult(s)}>{s}×</button>)}
      </div>
    </div>
    <Chart engine={engine} />
  </div>
}

// 24-hour strip: network delay per hour (bars = this day and run; dashed = the run it is compared with, or else the other
// day) with the clock's playhead; drag to scrub
function Chart({ engine }: { engine: Engine }) {
  const { day, run, hour, t } = useSelector(viewer, s => ({ day: s.day, run: s.run, hour: s.hour, t: s.t, rev: s.themeRev }), { compare: shallow })
  const ref = useRef<SVGSVGElement>(null), dragging = useRef(false)
  const [{ W, H }, setSize] = useState({ W: 200, H: 60 })
  useLayoutEffect(() => {
    const el = ref.current!
    const ro = new ResizeObserver(() => { const r = el.getBoundingClientRect(); setSize({ W: Math.max(200, r.width), H: Math.max(60, r.height) }) })
    ro.observe(el); return () => ro.disconnect()
  }, [])
  const timeAt = (e: PointerEvent) => { const r = ref.current!.getBoundingClientRect(); return Math.max(0, Math.min(86399, Math.round((e.clientX - r.left - 4) / (r.width - 8) * 1440) * 60)) }

  const pad = { l: 4, r: 4, t: 14, b: 16 }, cw = (W - pad.l - pad.r) / 24, ih = H - pad.t - pad.b
  const runs = engine.summary.runs, me = runs.find(r => r.id === run), vs = runs.find(r => r.id === me?.vs)
  const cur = dayData(engine.summary, day, run).kpi.map(k => k.delay_vh)
  const oth = (vs ? dayData(engine.summary, day, vs.id) : dayData(engine.summary, otherDay(day), run)).kpi.map(k => k.delay_vh)
  const names = vs && me ? [me.label, vs.label] : [DAYS[day], DAYS[otherDay(day)]]
  const mx = Math.max(...cur, ...oth) * 1.05
  const line = oth.map((v, h) => `${(pad.l + h * cw + cw / 2).toFixed(1)},${(pad.t + ih - v / mx * ih).toFixed(1)}`).join(' ')
  const xh = pad.l + t / 3600 * cw, legLeft = xh > W / 2
  return <svg id="chart" ref={ref} viewBox={`0 0 ${W} ${H}`} role="slider" aria-label="Time of day" aria-valuemin={0} aria-valuemax={23} aria-valuenow={hour}
    aria-valuetext={hhmm(t)} tabIndex={0}
    onPointerDown={e => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); engine.scrub(timeAt(e)) }}
    onPointerMove={e => { if (dragging.current) engine.scrub(timeAt(e)) }}
    onPointerUp={() => { dragging.current = false }}
    onKeyDown={e => {
      const d = ({ ArrowRight: 3600, ArrowUp: 3600, ArrowLeft: -3600, ArrowDown: -3600 } as Record<string, number>)[e.key]
      if (d) { engine.scrub((engine.t + d + 86400) % 86400); e.preventDefault() }
    }}>
    {cur.map((v, h) => {
      const bh = Math.max(1.5, v / mx * ih), x = pad.l + h * cw, now = h === hour
      return <rect key={h} x={(x + cw * .14).toFixed(1)} y={(pad.t + ih - bh).toFixed(1)} width={(cw * .72).toFixed(1)} height={bh.toFixed(1)} rx="2"
        style={{ fill: now ? 'var(--ink)' : css(sevColor(v / 12)) }} fillOpacity={now ? 1 : .85} />
    })}
    <polyline points={line} fill="none" style={{ stroke: 'var(--ink-3)' }} strokeWidth="1.2" strokeDasharray="3 3" />
    {Array.from({ length: 24 }, (_, h) => h).filter(h => h % (W < 500 ? 6 : 3) === 0).map(h =>
      <text key={h} x={(pad.l + h * cw + cw / 2).toFixed(1)} y={H - 3} textAnchor="middle">{pad2(h)}</text>)}
    <line x1={xh.toFixed(1)} x2={xh.toFixed(1)} y1={pad.t - 2} y2={pad.t + ih} style={{ stroke: 'var(--ink)' }} strokeWidth="1.5" />
    <g className="hl"><text x={Math.min(W - 40, Math.max(40, xh)).toFixed(1)} y="10" textAnchor="middle">{hhmm(t)} · {fmt(blendOf(cur, hourBlend(t)))} vh/h</text></g>
    {W > 560 && <text x={legLeft ? 4 : W - 4} y="10" textAnchor={legLeft ? 'start' : 'end'}>
      network delay per hour · bars {names[0].toLowerCase()} · dashed {names[1].toLowerCase()}
    </text>}
  </svg>
}
