import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, createRoute, createRouter, type ErrorComponentProps } from '@tanstack/react-router'
import { Viewer } from './components/Viewer'
import { BASE, edgesQuery, sceneQuery, summaryQuery } from './lib/data'
import { startTime, validateSearch } from './lib/search'
import { loadTrips } from './lib/trips'

const Loading = ({ children = 'Loading Lucca…' }: { children?: React.ReactNode }) => <div id="loading"><div>{children}</div></div>
const LoadError = ({ error }: ErrorComponentProps) => (
  <Loading><span className="err">Could not load the simulation data ({error instanceof Error ? error.message : String(error)}). Reload the page to try again.</span></Loading>
)

const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()()
const viewerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  validateSearch,
  loaderDeps: ({ search }) => ({ d: search.d ?? 'wd', s: search.s ?? BASE, hour: Math.floor(startTime(search) / 3600) }),
  // the map, the summary, the run's road data and the opening hour's trips; the map labels' font weights must be loaded
  // before the first draw, since deck.gl rasterises the glyphs once. The summary lists the runs a deep link may open, so
  // the run's files wait for it; the map and the fonts do not.
  loader: async ({ context: { queryClient: qc }, deps: { d, s, hour } }) => {
    const sceneP = Promise.all([qc.ensureQueryData(sceneQuery), document.fonts.load('600 15px "Barlow Condensed"'), document.fonts.load('700 15px "Barlow Condensed"')])
    const summary = await qc.ensureQueryData(summaryQuery), run = summary.runs.some(r => r.id === s) ? s : BASE
    const [[scene]] = await Promise.all([sceneP, qc.ensureQueryData(edgesQuery(d, run)), loadTrips(d, run, hour)])
    return { scene, summary, run }
  },
  component: Viewer,
  pendingComponent: Loading,
  errorComponent: LoadError,
})

export const createAppRouter = (queryClient: QueryClient) => createRouter({
  routeTree: rootRoute.addChildren([viewerRoute]),
  context: { queryClient },
  basepath: import.meta.env.BASE_URL,
  defaultPendingMs: 0,
  defaultPendingMinMs: 0,
})
