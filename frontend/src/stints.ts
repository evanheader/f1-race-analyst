import type { Lap, PitStop } from './api'

export interface Stint {
  driverId: number
  stintNumber: number
  compound: string
  firstLap: number
  lastLap: number
  /** How many laps the driver has recorded in this stint. */
  laps: number
}

interface Group extends Stint {
  /** Tire age on the first and last lap, or null when the API did not know it. */
  firstAge: number | null
  lastAge: number | null
}

/**
 * Groups laps into tire stints, ordered by driver and then stint. Laps without a stint number are ignored.
 *
 * OpenF1 starts a new stint every time a driver drives through the pit lane. Under a safety car
 * many drivers do that without changing tires, so the "new" stint has the same compound and a tire
 * age that keeps counting. Those are merged into the stint before, because no tire changed.
 */
export function deriveStints(laps: Lap[]): Stint[] {
  const groups = new Map<string, Group>()
  for (const lap of [...laps].sort((a, b) => a.lap_number - b.lap_number)) {
    if (lap.stint_number === null) continue
    const key = `${lap.driver_id}:${lap.stint_number}`
    const group = groups.get(key)
    if (!group) {
      groups.set(key, {
        driverId: lap.driver_id,
        stintNumber: lap.stint_number,
        compound: lap.tire_type ?? 'UNKNOWN',
        firstLap: lap.lap_number,
        lastLap: lap.lap_number,
        laps: 1,
        firstAge: lap.tire_age,
        lastAge: lap.tire_age,
      })
      continue
    }
    group.lastLap = lap.lap_number
    group.lastAge = lap.tire_age
    group.laps += 1
    // The first lap with a known tire decides the compound.
    if (group.compound === 'UNKNOWN' && lap.tire_type !== null) group.compound = lap.tire_type
  }

  const ordered = [...groups.values()].sort(
    (a, b) => a.driverId - b.driverId || a.stintNumber - b.stintNumber,
  )
  const merged: Group[] = []
  for (const group of ordered) {
    const previous = merged.at(-1)
    const sameTire =
      previous !== undefined &&
      previous.driverId === group.driverId &&
      previous.compound === group.compound &&
      previous.lastAge !== null &&
      group.firstAge !== null &&
      group.firstAge >= previous.lastAge
    if (sameTire) {
      previous.lastLap = group.lastLap
      previous.lastAge = group.lastAge
      previous.laps += group.laps
    } else {
      merged.push({ ...group })
    }
  }
  return merged.map(({ firstAge: _firstAge, lastAge: _lastAge, ...stint }) => stint)
}

export interface ClassifiedPitStop extends PitStop {
  /** True when the driver drove through the pit lane but kept the same tires. */
  pass: boolean
  /** The stint the driver left on, for a tire stop. */
  nextStint: Stint | null
}

/**
 * A pit stop is a tire stop when a stint starts on its lap (or the next one). Otherwise the stop fell
 * inside a merged stint, so the driver only passed through the pit lane.
 */
export function classifyPitStops(pitStops: PitStop[], stints: Stint[]): ClassifiedPitStop[] {
  return pitStops.map((stop) => {
    const nextStint =
      stints.find(
        (s) =>
          s.driverId === stop.driver_id &&
          s.stintNumber > 1 &&
          (s.firstLap === stop.lap_number || s.firstLap === stop.lap_number + 1),
      ) ?? null
    return { ...stop, pass: nextStint === null, nextStint }
  })
}

export const COMPOUND_COLORS: Record<string, string> = {
  SOFT: '#DA291C',
  MEDIUM: '#FFD12E',
  HARD: '#F0F0EC',
  INTERMEDIATE: '#43B02A',
  WET: '#0067AD',
  UNKNOWN: '#6B7280',
}

export const COMPOUND_LETTERS: Record<string, string> = {
  SOFT: 'S',
  MEDIUM: 'M',
  HARD: 'H',
  INTERMEDIATE: 'I',
  WET: 'W',
  UNKNOWN: '?',
}

export function compoundColor(compound: string): string {
  return COMPOUND_COLORS[compound] ?? COMPOUND_COLORS.UNKNOWN
}

export function compoundLetter(compound: string): string {
  return COMPOUND_LETTERS[compound] ?? '?'
}
