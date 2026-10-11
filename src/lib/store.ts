// UI state shared by the React panels and the render loop. The loop owns the precise clock and pushes a
// throttled copy here (t, kpi, follow card), so React re-renders a few times a second, not every frame.
import { Store } from '@tanstack/react-store'
import type { Mode } from './color'
import type { Day } from './data'

export type LayerKey = 'veh' | 'bld' | 'hot' | 'lbl'
export interface FollowCard { label: string; when: string; progress: number; meta: string }
export interface Tip { x: number; y: number; title: string; ztl?: boolean; lines: string[]; note?: string }

export interface ViewerState {
  day: Day; hour: number; t: number; mode: Mode; playing: boolean; mult: number; sel: string | null
  layers: Record<LayerKey, boolean>
  kpi: { veh: number; kmh: number; delay: number; cong: number }
  follow: FollowCard | null; tip: Tip | null
  themeRev: number   // bumps when the colour theme changes
}

export const initialState = (day: Day, t: number): ViewerState => ({
  day, hour: Math.floor(t / 3600), t, mode: 'speed', playing: false, mult: 60, sel: null,
  layers: { veh: true, bld: true, hot: true, lbl: true },
  kpi: { veh: 0, kmh: 0, delay: 0, cong: 0 }, follow: null, tip: null, themeRev: 0,
})

export const viewer = new Store<ViewerState>(initialState('wd', 8 * 3600))
export const patch = (p: Partial<ViewerState>) => viewer.setState(s => ({ ...s, ...p }))
