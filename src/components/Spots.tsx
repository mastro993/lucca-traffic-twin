import { shallow, useSelector } from '@tanstack/react-store'
import { css, sevColor } from '../lib/color'
import type { Engine } from '../lib/engine'
import { controlName, fmt, pad2, spotName } from '../lib/format'
import { viewer } from '../lib/store'

function Spark({ arr, h, col }: { arr: number[]; h: number; col: string }) {
  const w = 72, H = 18, mx = Math.max(1, ...arr)
  const pts = arr.map((v, i) => `${(i / 23 * w).toFixed(1)},${(H - 1 - v / mx * (H - 3)).toFixed(1)}`).join(' ')
  const x = (h / 23 * w).toFixed(1)
  return <svg className="spark" viewBox={`0 0 ${w} ${H}`} aria-hidden="true">
    <polygon points={`0,${H} ${pts} ${w},${H}`} fill={col} fillOpacity=".18" />
    <polyline points={pts} fill="none" stroke={col} strokeWidth="1.3" />
    <line x1={x} x2={x} y1="0" y2={H} stroke="currentColor" strokeOpacity=".5" strokeWidth="1" />
  </svg>
}

export function Spots({ engine }: { engine: Engine }) {
  const { day, hour, sel } = useSelector(viewer, s => ({ day: s.day, hour: s.hour, sel: s.sel, rev: s.themeRev }), { compare: shallow })
  return <ol className="spots">
    {engine.summary[day].hotspots.map(h => {
      const col = css(sevColor(h.peak_delay_vh)), now = h.delay_h[hour], go = () => engine.selectSpot(h.id, true)
      return <li key={h.id} className="spot" role="option" tabIndex={0} aria-selected={sel === h.id} onClick={go}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go() } }}>
        <span className="rk" style={{ background: col }}>{h.rank}</span>
        <span className="nm">{spotName(h)}</span>
        <span className="val" title="Delay in the selected hour">{fmt(now, now < 10 ? 1 : 0)} vh</span>
        <span className="meta"><span>{controlName(h.control)} · peak {pad2(h.peak_hour)}h · {fmt(h.daily_delay_vh)} vh/day</span></span>
        <span className="sp"><Spark arr={h.delay_h} h={hour} col={col} /></span>
        {sel === h.id && h.note && <span className="note">{h.note}</span>}
      </li>
    })}
  </ol>
}
