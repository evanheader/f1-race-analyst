import { describe, expect, it } from 'vitest'
import type { Lap } from './api'
import { buildChartData, cleanLaps, median, slowLapRanges } from './lapChart'

function lap(driver_id: number, lap_number: number, lap_time_seconds: number | null, extra: Partial<Lap> = {}): Lap {
  return {
    driver_id,
    lap_number,
    lap_time_seconds,
    tire_type: 'MEDIUM',
    tire_age: 1,
    stint_number: 1,
    position: 1,
    is_pit_out_lap: false,
    is_deleted: false,
    ...extra,
  }
}

/** Ten steady laps for one driver, with the given changes by lap number. */
function steady(driver: number, changes: Record<number, Partial<Lap> & { t?: number | null }> = {}): Lap[] {
  return Array.from({ length: 10 }, (_, i) => {
    const n = i + 1
    const { t, ...extra } = changes[n] ?? {}
    return lap(driver, n, t === undefined ? 90 + (n % 2) * 0.4 : t, extra)
  })
}

describe('median', () => {
  it('takes the middle value, or the mean of the two middle values', () => {
    expect(median([3, 1, 2])).toBe(2)
    expect(median([4, 1, 3, 2])).toBe(2.5)
  })
})

describe('cleanLaps', () => {
  it('drops pit out laps and the in lap before them, deleted laps and laps without a time', () => {
    const laps = steady(1, { 3: { t: null }, 5: { is_deleted: true }, 7: { is_pit_out_lap: true, t: 110 }, 6: { t: 105 } })

    expect(cleanLaps(laps, []).map((l) => l.lap_number)).toEqual([1, 2, 4, 8, 9, 10])
  })

  it('drops laps slower than 107% of the driver median, and keeps fast ones, such as dry laps after rain', () => {
    const laps = steady(1, { 2: { t: 82 }, 4: { t: 97 }, 8: { t: 96 } })

    // 97 is 107.5% of the 90.2 median, 96 is 106.4%.
    expect(cleanLaps(laps, []).map((l) => l.lap_number)).toEqual([1, 2, 3, 5, 6, 7, 8, 9, 10])
  })

  it('drops laps in a slow run for the whole field', () => {
    expect(cleanLaps(steady(1), [[4, 6]]).map((l) => l.lap_number)).toEqual([1, 2, 3, 7, 8, 9, 10])
  })
})

describe('buildChartData', () => {
  it('in the clean view, plots only racing laps and counts the ones it hid', () => {
    const laps = [...steady(1, { 5: { t: 140 } }), ...steady(2), ...steady(3, { 2: { t: null } })]

    const data = buildChartData(laps, [1, 2], 'clean')!

    // Driver 1's slow lap 5 is hidden, and the one-lap gap is bridged with a flagged straight-line value.
    expect(data.rows.find((r) => r.lap === 5)).toEqual({ lap: 5, d2: 90.4, d1: 90, i1: true })
    expect(data.rows.some((r) => 'd3' in r)).toBe(false)
    expect(data.hidden).toBe(1)
  })

  it('in the clean view, leaves a gap of more than 3 hidden laps broken', () => {
    const laps = steady(1, { 3: { t: 140 }, 4: { t: 140 }, 5: { t: 140 }, 6: { t: 140 } })

    const data = buildChartData(laps, [1], 'clean')!

    // Laps 3 to 6 keep their rows but have no point, so the line breaks there instead of jumping across.
    expect(data.rows.filter((r) => 'd1' in r).map((r) => r.lap)).toEqual([1, 2, 7, 8, 9, 10])
    expect(data.rows.map((r) => r.lap)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    expect([data.firstLap, data.lastLap]).toEqual([1, 10])
  })

  it('in the raw view, plots every timed lap, pit out and deleted laps included', () => {
    const laps = steady(1, { 2: { t: 140, is_pit_out_lap: true }, 3: { is_deleted: true, t: 91 }, 4: { t: null } })

    const data = buildChartData(laps, [1], 'raw')!

    expect(data.rows.map((r) => r.d1)).toEqual([90.4, 140, 91, undefined, 90.4, 90, 90.4, 90, 90.4, 90])
    expect(data.hidden).toBe(0)
    expect(data.yMax).toBe(140.5)
  })

  it('pads the y axis by half a second beyond the plotted laps, on whole half seconds', () => {
    const data = buildChartData([lap(1, 1, 90.2), lap(1, 2, 91.7)], [1], 'raw')!

    expect(data.yMin).toBe(89.5)
    expect(data.yMax).toBe(92.5)
  })

  it('reports where the whole field was slow, from every driver and not only the chosen ones', () => {
    const laps = [1, 2, 3, 4, 5, 6].flatMap((n) => [1, 2, 3].map((d) => lap(d, n, n === 3 || n === 4 ? 150 : 90)))

    expect(buildChartData(laps, [1])?.slowRanges).toEqual([[3, 4]])
  })

  it('returns null when nothing is plottable', () => {
    expect(buildChartData([lap(1, 1, null)], [1])).toBeNull()
    expect(buildChartData([lap(1, 1, null)], [1], 'raw')).toBeNull()
  })
})

describe('slowLapRanges', () => {
  it('ignores one driver having a slow lap when the rest of the field is not', () => {
    const laps = [lap(1, 1, 90), lap(2, 1, 90), lap(3, 1, 200), lap(1, 2, 90), lap(2, 2, 90), lap(3, 2, 90)]

    expect(slowLapRanges(laps)).toEqual([])
  })

  it('counts pit out laps, because a safety car can send the whole field through the pit lane', () => {
    const laps = [1, 2, 3, 4].flatMap((n) =>
      [1, 2, 3].map((d) => lap(d, n, n === 2 ? 150 : 90, { is_pit_out_lap: n === 2 })),
    )

    expect(slowLapRanges(laps)).toEqual([[2, 2]])
  })

  it('splits separate runs of slow laps', () => {
    const times = [90, 90, 90, 90, 90, 90, 140, 90, 90, 90, 90, 140, 140, 90, 90]
    const laps = times.map((t, i) => lap(1, i + 1, t))

    expect(slowLapRanges(laps)).toEqual([
      [7, 7],
      [12, 13],
    ])
  })
})
