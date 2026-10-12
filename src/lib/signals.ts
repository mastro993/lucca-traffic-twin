// Traffic signals: the fixed-time programs SUMO ran, replayed on the clock. Every head shows the state of the links
// of its lane; a lane with several movements (straight and turning) shows green if any of them may go.
export interface Program { o: number; p: [dur: number, state: string][] }
export interface Head { t: number; l: number[]; p: [number, number]; a: number }   // a: heading, degrees clockwise from north
export interface Pole { t: number; p: [number, number]; a: number; r: number }    // r: arm reach to the far head, metres
export interface Signals { prog: Program[]; heads: Head[]; poles: Pole[] }

export const RED = 0, AMBER = 1, GREEN = 2
export const LIGHT_NAME = ['red', 'amber', 'green']

const light = (state: string, links: number[]) => {
  let v = RED
  for (const i of links) { const c = state[i]; if (c === 'G' || c === 'g') return GREEN; if (c === 'y' || c === 'Y') v = AMBER }
  return v
}
export const cycleOf = (p: Program) => p.p.reduce((s, ph) => s + ph[0], 0)

/** The head's light at clock time t (s), and the seconds until it changes. */
export function signalAt(s: Signals, h: Head, t: number): { light: number; left: number } {
  const pr = s.prog[h.t], n = pr.p.length, C = cycleOf(pr)
  let x = (((t - pr.o) % C) + C) % C, k = 0
  while (x >= pr.p[k][0]) x -= pr.p[k++][0]
  const now = light(pr.p[k][1], h.l)
  let left = pr.p[k][0] - x
  for (let j = 1; j < n && light(pr.p[(k + j) % n][1], h.l) === now; j++) left += pr.p[(k + j) % n][0]
  return { light: now, left }
}
