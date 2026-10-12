import { getRouteApi } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { Engine } from '../lib/engine'
import { startTime } from '../lib/search'
import { FollowCard, Tooltip } from './Overlays'
import { Layers, Panel } from './Panel'
import { Strip } from './Strip'

const route = getRouteApi('/')

// Layout: full-bleed 3D scene; a floating control column on the left (bottom sheet on phones);
// layer switches in a box on the right; a 24-hour strip docked at the bottom that doubles as the clock.
export function Viewer() {
  const { scene, summary, run } = route.useLoaderData()
  const { queryClient } = route.useRouteContext()
  const search = route.useSearch()
  const sceneEl = useRef<HTMLDivElement>(null)
  const [engine, setEngine] = useState<Engine | null>(null)
  const open = useRef({ ...search, run })   // deep links only set the opening state

  useEffect(() => {
    const s = open.current
    const e = new Engine(sceneEl.current!, scene, summary, queryClient, { day: s.d ?? 'wd', run: s.run, t: startTime(s), z: s.z, still: !!s.still })
    setEngine(e)
    return () => { e.destroy(); setEngine(null) }
  }, [scene, summary, queryClient])

  return <>
    <div id="scene" ref={sceneEl} aria-label="3D view of Lucca with simulated traffic" />
    <div className="brand">
      <h1>Lucca <span>Traffic</span> Twin</h1>
      <p>{summary.subtitle}</p>
    </div>
    {engine && <>
      <Panel engine={engine} />
      <Layers engine={engine} />
      <Strip engine={engine} />
      <FollowCard engine={engine} />
      <Tooltip />
    </>}
    <div id="loading" className={engine ? 'done' : undefined}><div>Loading Lucca…</div></div>
  </>
}
