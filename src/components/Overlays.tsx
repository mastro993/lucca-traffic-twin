import { useSelector } from '@tanstack/react-store'
import type { Engine } from '../lib/engine'
import { viewer } from '../lib/store'

export function FollowCard({ engine }: { engine: Engine }) {
  const f = useSelector(viewer, s => s.follow)
  if (!f) return null
  return <div id="follow">
    <div className="head"><span className="label">{f.label}</span><button onClick={() => engine.stopFollow()} aria-label="Stop following">×</button></div>
    <div className="when">{f.when}</div>
    <div className="bar"><i style={{ width: `${f.progress.toFixed(1)}%` }} /></div>
    <div className="m">{f.meta}</div>
  </div>
}

export function Tooltip() {
  const tip = useSelector(viewer, s => s.tip)
  if (!tip) return null
  return <div id="tip" style={{ left: tip.x, top: tip.y }}>
    <b>{tip.title}</b>{tip.ztl && <> <span className="chip">ZTL</span></>}
    <div className="m">{tip.lines.map((l, k) => <span key={k}>{k > 0 && <br />}{l}</span>)}</div>
    {tip.note && <div style={{ marginTop: 4 }}>{tip.note}</div>}
  </div>
}
