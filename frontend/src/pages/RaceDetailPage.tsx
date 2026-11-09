import { useState, type CSSProperties } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, type Lap, type RaceResult } from '../api'
import CircuitOutline from '../components/CircuitOutline'
import Flag from '../components/Flag'
import LapChart from '../components/LapChart'
import { Loading, LoadError } from '../components/Status'
import StrategyChart from '../components/StrategyChart'
import TimingTower from '../components/TimingTower'
import { circuitName, formatDate, formatLapTime } from '../format'
import { useLaps, usePitStops, useRace, useResults } from '../queries'
import { teamCardColor } from '../teamColors'

const MAX_COMPARED = 3

/** The fastest timed lap that was not deleted, with who set it. */
function fastestLap(laps: Lap[], results: RaceResult[]) {
  let best: Lap | null = null
  for (const l of laps) {
    if (l.lap_time_seconds === null || l.is_deleted) continue
    if (!best || l.lap_time_seconds < (best.lap_time_seconds as number)) best = l
  }
  if (!best) return null
  const driver = results.find((r) => r.driver_id === best.driver_id)
  return { time: best.lap_time_seconds as number, lap: best.lap_number, driver: driver?.driver_name ?? 'Unknown' }
}

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[0.8125rem] text-white/75">{label}</dt>
      <dd className="mt-0.5 truncate font-semibold text-white">{value}</dd>
      {detail && <dd className="truncate text-[0.8125rem] text-white/75">{detail}</dd>}
    </div>
  )
}

export default function RaceDetailPage() {
  const raceId = Number(useParams().id)
  const race = useRace(raceId)
  const results = useResults(raceId)
  const hasLapData = race.data?.openf1_session_key != null
  const laps = useLaps(raceId, hasLapData)
  const pitStops = usePitStops(raceId, hasLapData)
  // Drivers on the lap chart, in the order they were picked. Null means the default: the first two finishers.
  const [picked, setPicked] = useState<number[] | null>(null)

  if (race.error instanceof ApiError && race.error.status === 404) {
    return (
      <div>
        <h1 className="display">Race not found</h1>
        <p className="mt-3 text-muted">
          There is no race with that address.{' '}
          <Link className="text-accent-text underline" to="/">
            Back to the races
          </Link>
        </p>
      </div>
    )
  }
  if (race.error) return <LoadError error={race.error} what="this race" />
  if (!race.data) return <Loading what="the race" />

  const { name, season, round, date, circuit_ref } = race.data
  const rows = results.data ?? []
  const winner = rows.find((r) => r.position === 1 && r.position_text === '1')
  const pole = rows.find((r) => r.grid === 1)
  const fastest = laps.data ? fastestLap(laps.data, rows) : null
  // The last lap with a time: the data can hold one more, untimed record after the flag.
  const lapCount = laps.data?.reduce((max, l) => (l.lap_time_seconds === null ? max : Math.max(max, l.lap_number)), 0)
  const selected = picked ?? rows.slice(0, 2).map((r) => r.driver_id)
  const chosen = selected.map((id) => rows.find((r) => r.driver_id === id)).filter((r) => r !== undefined)

  function toggle(id: number) {
    setPicked(selected.includes(id) ? selected.filter((d) => d !== id) : [...selected, id].slice(-MAX_COMPARED))
  }

  const heroStyle = { '--c': teamCardColor(winner?.team) } as CSSProperties

  return (
    <div className="space-y-6">
      <header
        className="team-shade grid items-center gap-6 rounded-[var(--radius-hero)] border border-white/10 p-6 shadow-[0_30px_60px_-30px_rgb(0_0_0/0.9)] sm:p-8 md:grid-cols-[minmax(0,1fr)_16rem] lg:grid-cols-[minmax(0,1fr)_20rem]"
        style={heroStyle}
      >
        <div className="min-w-0 space-y-5">
          <Link className="text-sm text-white/80 underline-offset-2 hover:text-white hover:underline" to={`/?season=${season}`}>
            All {season} races
          </Link>
          <div className="space-y-3">
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-white/85">
              <Flag circuitRef={circuit_ref} />
              <span>{circuitName(circuit_ref)}</span>
              <span aria-hidden="true" className="h-3 w-px bg-white/30" />
              <span>
                Round <span className="num text-white">{round}</span>
              </span>
              <span aria-hidden="true" className="h-3 w-px bg-white/30" />
              <span className="num text-white">{formatDate(date)}</span>
            </p>
            <h1 className="display text-white">
              {name} <span className="text-white/60">{season}</span>
            </h1>
          </div>
          {rows.length > 0 && (
            <dl className="grid max-w-2xl grid-cols-2 gap-x-6 gap-y-4 border-t border-white/15 pt-5 sm:grid-cols-4">
              {winner && <Stat label="Winner" value={winner.driver_name} detail={winner.team} />}
              {pole && <Stat label="Pole" value={pole.driver_name} detail={pole.team} />}
              {fastest && <Stat label="Fastest lap" value={formatLapTime(fastest.time)} detail={`${fastest.driver}, lap ${fastest.lap}`} />}
              {lapCount ? <Stat label="Laps" value={String(lapCount)} /> : null}
            </dl>
          )}
        </div>
        <CircuitOutline circuitRef={circuit_ref} draw className="mx-auto hidden w-full max-w-[20rem] drop-shadow-[0_0_24px_rgb(255_255_255/0.25)] md:block" />
      </header>

      {results.isPending && <Loading what="results" />}
      {results.error && <LoadError error={results.error} what="the results" />}
      {results.data && rows.length === 0 && (
        <p className="panel p-5 text-muted">No results yet. They appear here once the race has been run and loaded.</p>
      )}

      {rows.length > 0 && (
        <div className="grid items-start gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
          <div className="lg:sticky lg:top-20">
            <TimingTower results={rows} selected={selected} onToggle={hasLapData ? toggle : undefined} />
          </div>
          <div className="min-w-0 space-y-6">
            {!hasLapData && (
              <p className="panel p-5 text-muted">Lap, tire and pit data start in 2023.</p>
            )}
            {hasLapData && laps.isPending && <div role="status" className="skeleton h-96"><span className="sr-only">Loading lap data…</span></div>}
            {laps.error && <LoadError error={laps.error} what="the lap data" />}
            {laps.data && (
              <>
                <LapChart laps={laps.data} chosen={chosen} />
                {pitStops.isPending && <div className="skeleton h-80" />}
                {pitStops.error && <LoadError error={pitStops.error} what="the pit stops" />}
                {!pitStops.isPending && (
                  <StrategyChart laps={laps.data} pitStops={pitStops.data ?? []} results={rows} />
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
