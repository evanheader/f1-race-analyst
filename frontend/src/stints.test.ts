import { describe, expect, it } from 'vitest'
import type { Lap } from './api'
import { classifyPitStops, compoundColor, compoundLetter, deriveStints } from './stints'

function lap(
  driver_id: number,
  lap_number: number,
  stint_number: number | null,
  tire_type: string | null,
  tire_age: number | null = 0,
): Lap {
  return {
    driver_id,
    lap_number,
    lap_time_seconds: 90,
    tire_type,
    tire_age,
    stint_number,
    position: 1,
    is_pit_out_lap: false,
    is_deleted: false,
  }
}

describe('deriveStints', () => {
  it('groups laps into stints with their lap range and count', () => {
    const laps = [
      lap(1, 1, 1, 'SOFT'),
      lap(1, 2, 1, 'SOFT'),
      lap(1, 3, 1, 'SOFT'),
      lap(1, 4, 2, 'HARD'),
      lap(1, 5, 2, 'HARD'),
    ]

    expect(deriveStints(laps)).toEqual([
      { driverId: 1, stintNumber: 1, compound: 'SOFT', firstLap: 1, lastLap: 3, laps: 3 },
      { driverId: 1, stintNumber: 2, compound: 'HARD', firstLap: 4, lastLap: 5, laps: 2 },
    ])
  })

  it('keeps drivers apart and orders by driver then stint, whatever the input order', () => {
    const laps = [lap(2, 1, 1, 'MEDIUM'), lap(1, 2, 2, 'HARD'), lap(1, 1, 1, 'SOFT')]

    expect(deriveStints(laps).map((s) => [s.driverId, s.stintNumber])).toEqual([
      [1, 1],
      [1, 2],
      [2, 1],
    ])
  })

  it('uses the first known tire when early laps have none, and UNKNOWN when none is known', () => {
    const laps = [lap(1, 1, 1, null), lap(1, 2, 1, 'WET'), lap(2, 1, 1, null)]

    const stints = deriveStints(laps)

    expect(stints[0].compound).toBe('WET')
    expect(stints[1].compound).toBe('UNKNOWN')
  })

  it('ignores laps without a stint number', () => {
    expect(deriveStints([lap(1, 1, null, 'SOFT')])).toEqual([])
  })
})

describe('deriveStints with pit lane passes', () => {
  it('merges the stints a safety car pass creates, when the tire age keeps counting', () => {
    // The 2025 Australian GP: laps 2 to 4 each started a new stint on the same intermediates.
    const laps = [
      lap(1, 1, 1, 'INTERMEDIATE', 0),
      lap(1, 2, 2, 'INTERMEDIATE', 2),
      lap(1, 3, 3, 'INTERMEDIATE', 3),
      lap(1, 4, 4, 'INTERMEDIATE', 4),
      lap(1, 5, 4, 'INTERMEDIATE', 5),
    ]

    expect(deriveStints(laps)).toEqual([
      { driverId: 1, stintNumber: 1, compound: 'INTERMEDIATE', firstLap: 1, lastLap: 5, laps: 5 },
    ])
  })

  it('keeps a same-compound stop as two stints when the tire age resets', () => {
    const laps = [
      lap(1, 1, 1, 'HARD', 1),
      lap(1, 2, 1, 'HARD', 2),
      lap(1, 3, 2, 'HARD', 0),
      lap(1, 4, 2, 'HARD', 1),
    ]

    expect(deriveStints(laps).map((s) => [s.stintNumber, s.firstLap, s.lastLap])).toEqual([
      [1, 1, 2],
      [2, 3, 4],
    ])
  })

  it('does not merge when a tire age is unknown', () => {
    const laps = [lap(1, 1, 1, 'SOFT', null), lap(1, 2, 2, 'SOFT', 2), lap(1, 3, 3, 'SOFT', 3)]

    // Stint 2 and 3 can merge with each other, but neither can merge into stint 1.
    expect(deriveStints(laps).map((s) => [s.stintNumber, s.laps])).toEqual([
      [1, 1],
      [2, 2],
    ])
  })

  it('does not merge a different compound even when the age keeps counting', () => {
    const laps = [lap(1, 1, 1, 'SOFT', 5), lap(1, 2, 2, 'HARD', 6)]

    expect(deriveStints(laps)).toHaveLength(2)
  })
})

describe('classifyPitStops', () => {
  it('calls a stop a pit lane pass when no stint starts on it', () => {
    const stints = deriveStints([
      lap(1, 1, 1, 'INTERMEDIATE', 0),
      lap(1, 2, 2, 'INTERMEDIATE', 2),
      lap(1, 3, 2, 'INTERMEDIATE', 3),
      lap(1, 4, 3, 'HARD', 0),
    ])
    const stops = [
      { driver_id: 1, lap_number: 2, lane_seconds: 13, stationary_seconds: null },
      { driver_id: 1, lap_number: 3, lane_seconds: 20, stationary_seconds: 2.4 },
    ]

    const [pass, change] = classifyPitStops(stops, stints)

    expect(pass.pass).toBe(true)
    expect(change.pass).toBe(false)
    expect(change.nextStint?.compound).toBe('HARD')
  })
})

describe('compoundLetter', () => {
  it('has a letter per compound', () => {
    expect(compoundLetter('INTERMEDIATE')).toBe('I')
    expect(compoundLetter('SOMETHING')).toBe('?')
  })
})

describe('compoundColor', () => {
  it('has a color per compound and a gray for anything else', () => {
    expect(compoundColor('SOFT')).toBe('#DA291C')
    expect(compoundColor('SOMETHING')).toBe('#6B7280')
  })
})
