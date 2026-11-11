import type { Lap } from './api'

/**
 * Clean: racing laps only, so the lines show pace. Raw: every timed lap as recorded.
 */
export type LapChartMode = 'clean' | 'raw'

export interface ChartData {
  /**
   * One row per lap number, with a `d<driverId>` key for each driver's lap time. In the clean view a
   * short gap is bridged with straight-line values, flagged with an `i<driverId>` key so the tooltip
   * can skip them. A missing key is a break in the line.
   */
  rows: Record<string, number | boolean>[]
  /** The race's first and last lap, so both views share an x axis. */
  firstLap: number
  lastLap: number
  yMin: number
  yMax: number
  /** Runs of laps where the whole field was slow, as [first lap, last lap]. */
  slowRanges: [number, number][]
  /** Laps left out of the clean view, over all chosen drivers. Zero in the raw view. */
  hidden: number
}

/** A lap is slow for the field when its median time is above this share of the race's median lap. */
const SLOW_LAP_FACTOR = 1.1
/**
 * The clean view drops laps slower than this share of the driver's own median racing lap, after the
 * 107% rule. There is no lower limit: in a race that turns from wet to dry, the fast dry laps are real.
 */
const CLEAN_MAX_FACTOR = 1.07
/** The clean view bridges a gap of up to this many hidden laps, such as a pit stop. Longer gaps stay broken. */
const MAX_BRIDGED_LAPS = 3

export function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

/**
 * Runs of consecutive laps where the median time of the whole field is above 110% of the race's median lap.
 * Pit out laps count here: under a safety car the whole field can be sent through the pit lane.
 */
export function slowLapRanges(laps: Lap[]): [number, number][] {
  const times = new Map<number, number[]>()
  for (const lap of laps) {
    if (lap.lap_time_seconds === null) continue
    times.set(lap.lap_number, [...(times.get(lap.lap_number) ?? []), lap.lap_time_seconds])
  }
  if (times.size === 0) return []
  const limit = median([...times.values()].flat()) * SLOW_LAP_FACTOR
  const slow = [...times.entries()]
    .filter(([, values]) => median(values) > limit)
    .map(([lapNumber]) => lapNumber)
    .sort((a, b) => a - b)
  const ranges: [number, number][] = []
  for (const lapNumber of slow) {
    const last = ranges.at(-1)
    if (last && last[1] === lapNumber - 1) last[1] = lapNumber
    else ranges.push([lapNumber, lapNumber])
  }
  return ranges
}

/**
 * One driver's racing laps: timed, not deleted, not a pit out lap or the in lap before it, not in a
 * slow run for the whole field, and within 107% of the driver's median of those.
 */
export function cleanLaps(own: Lap[], slowRanges: [number, number][]): Lap[] {
  const outLaps = new Set(own.filter((l) => l.is_pit_out_lap).map((l) => l.lap_number))
  const candidates = own.filter(
    (l) =>
      l.lap_time_seconds !== null &&
      !l.is_deleted &&
      !l.is_pit_out_lap &&
      !outLaps.has(l.lap_number + 1) &&
      !slowRanges.some(([first, last]) => l.lap_number >= first && l.lap_number <= last),
  )
  if (candidates.length === 0) return []
  const med = median(candidates.map((l) => l.lap_time_seconds as number))
  return candidates.filter((l) => (l.lap_time_seconds as number) <= med * CLEAN_MAX_FACTOR)
}

/** Returns null when there is nothing to plot. */
export function buildChartData(laps: Lap[], driverIds: number[], mode: LapChartMode = 'clean'): ChartData | null {
  const slowRanges = slowLapRanges(laps)
  const chosen = laps.filter((l) => driverIds.includes(l.driver_id) && l.lap_time_seconds !== null)
  const plotted =
    mode === 'raw'
      ? chosen
      : driverIds.flatMap((id) => cleanLaps(chosen.filter((l) => l.driver_id === id), slowRanges))
  if (plotted.length === 0) return null

  const byLap = new Map<number, Record<string, number | boolean>>()
  const put = (lapNumber: number, key: string, value: number | boolean) => {
    const row = byLap.get(lapNumber) ?? { lap: lapNumber }
    row[key] = value
    byLap.set(lapNumber, row)
  }
  for (const lap of plotted) put(lap.lap_number, `d${lap.driver_id}`, lap.lap_time_seconds as number)
  if (mode === 'clean') {
    for (const id of driverIds) {
      const own = plotted.filter((l) => l.driver_id === id).sort((a, b) => a.lap_number - b.lap_number)
      for (let k = 1; k < own.length; k++) {
        const [a, b] = [own[k - 1], own[k]]
        const missing = b.lap_number - a.lap_number - 1
        if (missing < 1 || missing > MAX_BRIDGED_LAPS) continue
        const [ta, tb] = [a.lap_time_seconds as number, b.lap_time_seconds as number]
        for (let n = a.lap_number + 1; n < b.lap_number; n++) {
          put(n, `d${id}`, ta + ((tb - ta) * (n - a.lap_number)) / (b.lap_number - a.lap_number))
          put(n, `i${id}`, true)
        }
      }
    }
  }
  const allLaps = laps.filter((l) => l.lap_time_seconds !== null).map((l) => l.lap_number)
  // Every lap gets a row, even an empty one: a lap missing from the rows would let the line jump straight over it.
  for (let n = Math.min(...allLaps); n <= Math.max(...allLaps); n++) if (!byLap.has(n)) byLap.set(n, { lap: n })
  const times = plotted.map((l) => l.lap_time_seconds as number)
  // Half a second of room above and below, on whole half seconds, so the lines never touch the edges.
  return {
    rows: [...byLap.values()].sort((a, b) => (a.lap as number) - (b.lap as number)),
    firstLap: Math.min(...allLaps),
    lastLap: Math.max(...allLaps),
    yMin: Math.floor(Math.min(...times) * 2) / 2 - 0.5,
    yMax: Math.ceil(Math.max(...times) * 2) / 2 + 0.5,
    slowRanges,
    hidden: mode === 'raw' ? 0 : chosen.length - plotted.length,
  }
}
