import type { Day } from './data'

// deep links: ?h=8 (or 8.5) opens that time, ?d=sat opens Saturday, ?s=<scenario> opens a scenario of the run switch,
// ?z=16 zooms in, ?ll=43.8305,10.5197 centres the close-up there (latitude, longitude), ?still renders one frame without
// the clock running
export interface ViewerSearch { d?: Day; s?: string; h?: number; z?: number; ll?: string; still?: boolean }
export function validateSearch(s: Record<string, unknown>): ViewerSearch {
  const num = (v: unknown) => (v === undefined || v === '' || !Number.isFinite(+(v as number)) ? undefined : +(v as number))
  return { d: s.d === 'sat' ? 'sat' : undefined, s: typeof s.s === 'string' && s.s ? s.s : undefined, h: num(s.h), z: num(s.z),
    ll: typeof s.ll === 'string' && /^-?\d+(\.\d+)?,-?\d+(\.\d+)?$/.test(s.ll) ? s.ll : undefined,
    still: s.still !== undefined && s.still !== false ? true : undefined }
}
/** Clock seconds the page opens at. */
export const startTime = (s: ViewerSearch) => (s.h !== undefined ? Math.min(23.99, Math.max(0, s.h)) : 8) * 3600
