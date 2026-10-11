import type { Day, Hotspot } from './data'

export const fmt = (v: number, d = 0) => v.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d })
export const pad2 = (v: number) => String(v).padStart(2, '0')
export const hh = (h: number) => pad2(h) + ':00'
export const hhmm = (t: number) => `${pad2(Math.floor(t / 3600) % 24)}:${pad2(Math.floor(t / 60) % 60)}`
export const spotName = (h: Hotspot) => h.label || h.streets.slice(0, 2).join(' × ') || 'Unnamed junction'
export const controlName = (c: string) => ({ signals: 'Signals', roundabout: 'Roundabout', priority: 'Junction' } as Record<string, string>)[c] || c

export function ctxText(day: Day, h: number) {
  if (day === 'wd') {
    if (h >= 7 && h <= 8) return 'School and work morning peak'
    if (h >= 12 && h <= 14) return 'School exit and lunch return'
    if (h >= 16 && h <= 18) return 'Evening commute'
    if (h <= 5 || h >= 22) return 'Night, network nearly empty'
    return 'Weekday off-peak'
  }
  if (h >= 10 && h <= 12) return 'Saturday shopping peak'
  if (h >= 16 && h <= 19) return 'Saturday afternoon and evening'
  if (h <= 6) return 'Night, network nearly empty'
  return 'Saturday off-peak'
}
