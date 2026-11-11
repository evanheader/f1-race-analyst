import { useState, type CSSProperties, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, type Lap, type RaceResult, type RaceSummary } from '../api'
import CircuitOutline from '../components/CircuitOutline'
import Flag from '../components/Flag'
import Headshot from '../components/Headshot'
import LapChart from '../components/LapChart'
import { Loading, LoadError } from '../components/Status'
import StrategyChart from '../components/StrategyChart'
import TimingTower from '../components/TimingTower'
import { circuitName, formatDate, formatLapTime, formatRound } from '../format'
import { useLaps, usePitStops, usePrefetchRace, useRace, useRaces, useResults, useSprintResults } from '../queries'

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
  return { time: best.lap_time_seconds as number, lap: best.lap_number, driver: driver?.driver_name ?? 'Unknown', team: driver?.team }
}

function Stat({ label, value, detail, face, accent = false }: { label: string; value: string; detail?: string; face?: ReactNode; accent?: boolean }) {
  return (
    <div className="flex min-w-0 items-start gap-3 border-t border-line pt-3">
      {face}
      <div className="min-w-0">
        <dt className="eyebrow">{label}</dt>
        <dd className={`mt-1.5 text-lg font-medium leading-snug ${accent ? 'num text-accent' : ''}`}>{value}</dd>
        {detail && <dd className="truncate text-[0.8125rem] text-muted">{detail}</dd>}
      </div>
    </div>
  )
}

function PagerLink({ race, direction }: { race: RaceSummary; direction: 'previous' | 'next' }) {
  const prefetch = usePrefetchRace(race.id)
  const back = direction === 'previous'
  return (
    <Link
      to={`/races/${race.id}`}
      onPointerEnter={prefetch}
      onFocus={prefetch}
      aria-label={`${back ? 'Previous' : 'Next'} race, ${race.name}`}
      className={`btn group max-w-full !justify-start gap-3 !py-2 ${back ? '' : 'flex-row-reverse text-right'}`}
    >
      <span aria-hidden="true" className="text-lg leading-none">
        {back ? '←' : '→'}
      </span>
      <span className="min-w-0 leading-tight">
        <span className="eyebrow block !text-[0.625rem]">
          {back ? 'Previous' : 'Next'} · {formatRound(race.round)}
        </span>
        <span className="block truncate text-sm font-semibold">{race.name}</span>
      </span>
    </Link>
  )
}

/** The rounds either side of this one in its season that have results, so there is something to open. */
function RacePager({ raceId, season }: { raceId: number; season: number }) {
  const { data: races } = useRaces()
  const rounds = (races ?? []).filter((r) => r.season === season).sort((a, b) => a.round - b.round)
  const at = rounds.findIndex((r) => r.id === raceId)
  if (at === -1) return null
  const prev = rounds.slice(0, at).findLast((r) => r.winner)
  const next = rounds.slice(at + 1).find((r) => r.winner)
  if (!prev && !next) return null
  return (
    <nav aria-label="Other races" className="grid grid-cols-2 gap-3">
      <div className="min-w-0">{prev && <PagerLink race={prev} direction="previous" />}</div>
      <div className="flex min-w-0 justify-end">{next && <PagerLink race={next} direction="next" />}</div>
    </nav>
  )
}

/** Keyed by the race id, so moving to another race starts with fresh picks and the Grand Prix tab. */
export default function RaceDetailPage() {
  const id = Number(useParams().id)
  return <RacePage key={id} raceId={id} />
}

function RacePage({ raceId }: { raceId: number }) {
  const race = useRace(raceId)
  const results = useResults(raceId)
  const sprint = useSprintResults(raceId, race.isSuccess)
  const hasLapData = race.data?.openf1_session_key != null
  const laps = useLaps(raceId, hasLapData)
  const pitStops = usePitStops(raceId, hasLapData)
  // Drivers on the lap chart, in the order they were picked. Null means the default: the first two finishers.
  const [picked, setPicked] = useState<number[] | null>(null)
  const [session, setSession] = useState<'race' | 'sprint'>('race')

  if (race.error instanceof ApiError && race.error.status === 404) {
    return (
      <div>
        <h1 className="display">Race not found</h1>
        <p className="mt-3 text-muted">
          There is no race with that address.{' '}
          <Link className="underline decoration-line-strong underline-offset-[3px]" to="/">
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
  const sprintRows = sprint.data ?? []
  const sprintWinner = sprintRows.find((r) => r.position === 1 && r.position_text === '1')
  const showSprint = session === 'sprint' && sprintRows.length > 0
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

  const rise = (i: number) => ({ '--i': i }) as CSSProperties

  return (
    <div className="space-y-12">
      <header className="grid items-end gap-8 md:grid-cols-[minmax(0,1fr)_15rem] lg:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="min-w-0">
          <Link className="rise eyebrow inline-flex items-center gap-2 hover:!text-ink" to={`/?season=${season}`}>
            <span aria-hidden="true">↑</span> All {season} races
          </Link>
          <p className="rise mt-8 flex flex-wrap items-center gap-x-3 gap-y-1 text-base text-muted" style={rise(1)}>
            <Flag circuitRef={circuit_ref} className="!w-9" />
            <span>{circuitName(circuit_ref)}</span>
            <span className="num">{formatRound(round)}</span>
            <span className="num">{formatDate(date)}</span>
          </p>
          <h1 className="rise display mt-3 !text-[clamp(3rem,9vw,6.5rem)]" style={rise(2)}>
            {name} <span className="text-muted">{season}</span>
          </h1>
          {rows.length > 0 && (
            <dl className="rise mt-10 grid max-w-4xl grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-[repeat(auto-fit,minmax(9.5rem,1fr))]" style={rise(3)}>
              {winner && (
                <Stat label="Winner" value={winner.driver_name} detail={winner.team} face={<Headshot name={winner.driver_name} team={winner.team} className="mt-0.5 hidden h-12 w-12 lg:block" />} />
              )}
              {pole && <Stat label="Pole" value={pole.driver_name} detail={pole.team} />}
              {fastest && <Stat label="Fastest lap" value={formatLapTime(fastest.time)} detail={`${fastest.driver}, lap ${fastest.lap}`} accent />}
              {lapCount ? <Stat label="Laps" value={String(lapCount)} /> : null}
              {sprintWinner && <Stat label="Sprint winner" value={sprintWinner.driver_name} detail={sprintWinner.team} />}
            </dl>
          )}
        </div>
        <CircuitOutline circuitRef={circuit_ref} draw className="mx-auto hidden w-full max-w-[19rem] md:block" />
      </header>

      <RacePager raceId={raceId} season={season} />

      {results.isPending && <Loading what="results" />}
      {results.error && <LoadError error={results.error} what="the results" />}
      {results.data && rows.length === 0 && (
        <p className="panel text-muted">No results yet. They appear here once the race has been run and loaded.</p>
      )}

      {rows.length > 0 && (
        <div className="grid grid-cols-[minmax(0,1fr)] items-start gap-12 lg:grid-cols-[31rem_minmax(0,1fr)] lg:gap-14">
          <section aria-labelledby="classification-heading" className="panel lg:sticky lg:top-24">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="classification-heading" className="heading">
                {showSprint ? 'Sprint' : 'Classification'}
              </h2>
              {sprintRows.length > 0 && (
                <div role="group" aria-label="Session" className="segmented">
                  <button type="button" aria-pressed={!showSprint} onClick={() => setSession('race')}>
                    Grand Prix
                  </button>
                  <button type="button" aria-pressed={showSprint} onClick={() => setSession('sprint')}>
                    Sprint
                  </button>
                </div>
              )}
            </div>
            {showSprint ? (
              <TimingTower results={sprintRows} />
            ) : (
              <TimingTower results={rows} selected={selected} onToggle={hasLapData ? toggle : undefined} />
            )}
          </section>
          <div className="min-w-0 space-y-14">
            {!hasLapData && (
              <p className="panel text-muted">Lap, tire and pit data start in 2023.</p>
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

      <div className="border-t border-line pt-8">
        <RacePager raceId={raceId} season={season} />
      </div>
    </div>
  )
}
