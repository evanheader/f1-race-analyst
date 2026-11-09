import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getLaps, getPitStops, getRace, getRaces, getResults, getSprintResults } from './api'

const raceQuery = (id: number) => ({ queryKey: ['race', id], queryFn: () => getRace(id) })
const resultsQuery = (id: number) => ({ queryKey: ['results', id], queryFn: () => getResults(id) })

export const useRaces = () => useQuery({ queryKey: ['races'], queryFn: () => getRaces() })
export const useRace = (id: number) => useQuery(raceQuery(id))
export const useResults = (id: number) => useQuery(resultsQuery(id))
export const useSprintResults = (id: number, enabled: boolean) =>
  useQuery({ queryKey: ['sprint-results', id], queryFn: () => getSprintResults(id), enabled })
export const useLaps = (id: number, enabled: boolean) =>
  useQuery({ queryKey: ['laps', id], queryFn: () => getLaps(id), enabled })
export const usePitStops = (id: number, enabled: boolean) =>
  useQuery({ queryKey: ['pit-stops', id], queryFn: () => getPitStops(id), enabled })

/** The race page's code, loaded on demand. Shared with App so both use the same chunk. */
export const loadRacePage = () => import('./pages/RaceDetailPage')

/**
 * Starts loading a race before it is opened: its page code, the race and its results. Called on
 * hover and focus, so the page usually has its data by the time the click lands.
 */
export function usePrefetchRace(id: number) {
  const client = useQueryClient()
  return () => {
    void loadRacePage()
    void client.prefetchQuery({ ...raceQuery(id), staleTime: 60_000 })
    void client.prefetchQuery({ ...resultsQuery(id), staleTime: 60_000 })
  }
}
