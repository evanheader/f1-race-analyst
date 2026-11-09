import { useMemo } from 'react'
import type { Lap, PitStop, RaceResult } from '../api'
import { formatSeconds } from '../format'
import { classifyPitStops, COMPOUND_COLORS, compoundColor, compoundLetter, deriveStints } from '../stints'

/** A stint shows its compound letter when it covers at least this share of the race. */
const LETTER_MIN_SHARE = 0.04
const TICK_EVERY = 10

const compoundName = (compound: string) => compound.charAt(0) + compound.slice(1).toLowerCase()

/** Tyre colors toned toward the page, so the chart reads as data rather than a wall of color. */
const muted = (compound: string) => `color-mix(in srgb, ${compoundColor(compound)} 55%, var(--bg))`

export default function StrategyChart({
  laps,
  pitStops,
  results,
}: {
  laps: Lap[]
  pitStops: PitStop[]
  results: RaceResult[]
}) {
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
    <section aria-labelledby="strategy-heading" className="panel space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <h2 id="strategy-heading" className="heading">
          Race strategy
        </h2>
        <p className="text-[0.8125rem] text-muted">Finishing order</p>
      </div>
      <ul aria-label="Legend" className="flex flex-wrap gap-x-4 gap-y-1 text-[0.8125rem] text-muted">
        {compounds.map((c) => (
          <li key={c} className="flex items-center gap-1.5">
            <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: muted(c) }} />
            {compoundName(c)}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="inline-block h-3.5 w-0.5 bg-ink" />
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
            {rows.map(({ result, code, stints: own, stops: ownStops }) => {
              const label = `${code}: ${own.map((s) => `${compoundName(s.compound)} laps ${s.firstLap} to ${s.lastLap}`).join(', ')}`
              return (
                <li key={result.driver_id} className="flex items-center gap-2">
                  <span className="num sticky left-0 z-10 w-10 shrink-0 bg-bg text-[0.8125rem] text-muted">{code}</span>
                  <div role="img" aria-label={label} className="relative h-4 flex-1 bg-ink/[0.03]">
                    {ticks.map((t) => (
                      <span key={t} aria-hidden="true" className="absolute inset-y-0 w-px bg-ink/[0.06]" style={{ left: x(t) }} />
                    ))}
                    {own.map((s) => (
                      <div
                        key={s.stintNumber}
                        aria-hidden="true"
                        className="num absolute inset-y-0 overflow-hidden rounded-[2px] text-center text-[0.625rem] leading-4 text-ink"
                        style={{
                          left: x(s.firstLap - 1),
                          width: `calc(${x(s.lastLap - s.firstLap + 1)} - 2px)`,
                          background: muted(s.compound),
                        }}
                      >
                        {(s.lastLap - s.firstLap + 1) / raceLaps >= LETTER_MIN_SHARE && compoundLetter(s.compound)}
                      </div>
                    ))}
                    {ownStops.map((p) =>
                      p.pass ? (
                        <span
                          key={p.lap_number}
                          aria-hidden="true"
                          className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink bg-bg"
                          style={{ left: x(p.lap_number - 0.5) }}
                        />
                      ) : (
                        <span
                          key={p.lap_number}
                          aria-hidden="true"
                          className="absolute -inset-y-[2px] w-0.5 -translate-x-1/2 bg-ink shadow-[0_0_0_1.5px_var(--bg)]"
                          style={{ left: x((p.nextStint?.firstLap ?? p.lap_number + 1) - 1) }}
                        />
                      ),
                    )}
                  </div>
                  <span className="w-4 shrink-0" />
                </li>
              )
            })}
          </ol>
          <p className="mt-1.5 pl-12 text-xs text-muted">Lap</p>
        </div>
      </div>
      {pitStops.length === 0 && <p className="text-[0.8125rem] text-muted">No pit stops are recorded for this race.</p>}

      <details className="text-sm">
        <summary className="eyebrow cursor-pointer hover:!text-ink">Show as table</summary>
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
