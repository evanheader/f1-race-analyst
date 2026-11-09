import { useMemo, useState } from 'react'
import type { Lap, PitStop, RaceResult } from '../api'
import { formatSeconds } from '../format'
import {
  classifyPitStops,
  COMPOUND_COLORS,
  compoundColor,
  compoundLetter,
  deriveStints,
  type ClassifiedPitStop,
} from '../stints'

// Bars on these colors read better with dark text.
const DARK_TEXT = new Set(['MEDIUM', 'HARD', 'INTERMEDIATE'])
/** A stint shows its compound letter when it covers at least this share of the race. */
const LETTER_MIN_SHARE = 0.04
const TICK_EVERY = 10

const compoundName = (compound: string) => compound.charAt(0) + compound.slice(1).toLowerCase()

function describeStop(code: string, stop: ClassifiedPitStop): string {
  const stationary =
    stop.stationary_seconds === null
      ? 'stationary time not recorded'
      : `${formatSeconds(stop.stationary_seconds)} stationary`
  const lane = `${formatSeconds(stop.lane_seconds)} in the pit lane`
  if (stop.pass) return `${code}, lap ${stop.lap_number}: drove through the pit lane, same tires, ${lane}`
  const to = stop.nextStint ? `, on to ${compoundName(stop.nextStint.compound).toLowerCase()}` : ''
  return `${code}, lap ${stop.lap_number}: pit stop, ${stationary}, ${lane}${to}`
}

export default function StrategyChart({
  laps,
  pitStops,
  results,
}: {
  laps: Lap[]
  pitStops: PitStop[]
  results: RaceResult[]
}) {
  const [hint, setHint] = useState('')
  const stints = useMemo(() => deriveStints(laps), [laps])
  const stops = useMemo(() => classifyPitStops(pitStops, stints), [pitStops, stints])
  const raceLaps = Math.max(1, ...stints.map((s) => s.lastLap))
  const compounds = Object.keys(COMPOUND_COLORS).filter(
    (c) => c !== 'UNKNOWN' || stints.some((s) => s.compound === 'UNKNOWN'),
  )
  // Finishing order, as the results table has it.
  const rows = results
    .map((r) => ({
      result: r,
      code: r.driver_code ?? r.driver_name,
      stints: stints.filter((s) => s.driverId === r.driver_id),
      stops: stops.filter((p) => p.driver_id === r.driver_id),
    }))
    .filter((row) => row.stints.length > 0)
  const x = (lap: number) => `${(lap / raceLaps) * 100}%`
  const ticks = Array.from({ length: Math.floor(raceLaps / TICK_EVERY) }, (_, i) => (i + 1) * TICK_EVERY)

  return (
    <section aria-labelledby="strategy-heading" className="panel space-y-3 p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 id="strategy-heading" className="heading">
          Race strategy
        </h2>
        <p className="text-[0.8125rem] text-muted">Finishing order. Hover or focus a stop to read it.</p>
      </div>
      <ul aria-label="Legend" className="flex flex-wrap gap-x-4 gap-y-1 text-[0.8125rem] text-muted">
        {compounds.map((c) => (
          <li key={c} className="flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: compoundColor(c) }} />
            {compoundName(c)}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-3.5 w-1 rounded-full bg-ink" />
          Tire stop
        </li>
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full border-2 border-ink" />
          Pit lane pass, same tires
        </li>
      </ul>

      <div className="-mx-1 overflow-x-auto">
        <div className="min-w-[36rem] px-1">
          <div className="flex items-end gap-2 pb-1 text-xs text-muted">
            <span className="w-10 shrink-0" />
            <div className="relative h-4 flex-1" aria-hidden="true">
              {ticks.map((t) => (
                <span key={t} className="num absolute -translate-x-1/2" style={{ left: x(t) }}>
                  {t}
                </span>
              ))}
            </div>
            <span className="w-4 shrink-0" />
          </div>
          <ol className="space-y-1">
            {rows.map(({ result, code, stints: own, stops: ownStops }) => (
              <li key={result.driver_id} className="group flex items-center gap-2">
                <span className="num sticky left-0 z-10 w-10 shrink-0 bg-surface text-[0.8125rem] text-muted group-hover:text-ink">{code}</span>
                <div className="relative h-5 flex-1 rounded-md bg-white/[0.03]">
                  {ticks.map((t) => (
                    <span key={t} aria-hidden="true" className="absolute inset-y-0 w-px bg-white/[0.06]" style={{ left: x(t) }} />
                  ))}
                  {own.map((s) => (
                    <div
                      key={s.stintNumber}
                      title={`${code}: ${compoundName(s.compound)}, laps ${s.firstLap} to ${s.lastLap}`}
                      className="num absolute inset-y-0 overflow-hidden rounded-[5px] text-center text-[0.6875rem] leading-5 shadow-[inset_0_1px_0_rgb(255_255_255/0.35),inset_0_-1px_0_rgb(0_0_0/0.2)]"
                      style={{
                        left: x(s.firstLap - 1),
                        width: `calc(${x(s.lastLap - s.firstLap + 1)} - 2px)`,
                        background: compoundColor(s.compound),
                        color: DARK_TEXT.has(s.compound) ? '#0A0D12' : '#FFFFFF',
                      }}
                    >
                      {(s.lastLap - s.firstLap + 1) / raceLaps >= LETTER_MIN_SHARE && compoundLetter(s.compound)}
                    </div>
                  ))}
                  {ownStops.map((p) => {
                    const text = describeStop(code, p)
                    return p.pass ? (
                      <span
                        key={p.lap_number}
                        title={text}
                        onPointerEnter={() => setHint(text)}
                        className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink bg-surface shadow"
                        style={{ left: x(p.lap_number - 0.5) }}
                      />
                    ) : (
                      <button
                        key={p.lap_number}
                        type="button"
                        title={text}
                        aria-label={text}
                        onPointerEnter={() => setHint(text)}
                        onFocus={() => setHint(text)}
                        className="absolute -inset-y-[3px] flex w-3 -translate-x-1/2 justify-center rounded-full"
                        style={{ left: x((p.nextStint?.firstLap ?? p.lap_number + 1) - 1) }}
                      >
                        <span aria-hidden="true" className="h-full w-1 rounded-full bg-ink shadow-[0_0_0_1.5px_var(--surface)]" />
                      </button>
                    )
                  })}
                </div>
                <span className="w-4 shrink-0" />
              </li>
            ))}
          </ol>
          <p className="mt-1.5 pl-12 text-xs text-muted">Lap</p>
        </div>
      </div>
      <p role="status" className="min-h-[1.5rem] text-[0.8125rem]">
        {hint || (pitStops.length === 0 ? 'No pit stops are recorded for this race.' : '')}
      </p>

      <details className="text-sm">
        <summary className="cursor-pointer text-accent-text">Show as table</summary>
        <div className="table-wrap mt-2">
          <table className="timing">
            <caption className="sr-only">Tire stints and pit stops per driver</caption>
            <thead>
              <tr>
                <th>Driver</th>
                <th>Tire stints (laps)</th>
                <th>Tire stops</th>
                <th>Pit lane passes</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ code, stints: own, stops: ownStops }) => (
                <tr key={code}>
                  <td className="num">{code}</td>
                  <td className="!whitespace-normal">
                    {own.map((s) => `${compoundName(s.compound)} ${s.firstLap}–${s.lastLap}`).join(', ')}
                  </td>
                  <td className="!whitespace-normal">
                    {ownStops
                      .filter((p) => !p.pass)
                      .map(
                        (p) =>
                          `Lap ${p.lap_number}${p.stationary_seconds === null ? '' : ` (${formatSeconds(p.stationary_seconds)})`}`,
                      )
                      .join(', ') || 'None'}
                  </td>
                  <td className="!whitespace-normal">
                    {ownStops
                      .filter((p) => p.pass)
                      .map((p) => `Lap ${p.lap_number}`)
                      .join(', ') || 'None'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  )
}
