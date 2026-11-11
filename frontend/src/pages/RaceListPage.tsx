import { useMemo, type CSSProperties } from 'react'
import { Link, useSearchParams } from 'react-router'
import type { RaceSummary } from '../api'
import CircuitOutline from '../components/CircuitOutline'
import Flag from '../components/Flag'
import Headshot from '../components/Headshot'
import Listbox from '../components/Listbox'
import Reveal from '../components/Reveal'
import RoundTile from '../components/RoundTile'
import { LoadError } from '../components/Status'
import { circuitName, formatDate, formatRound } from '../format'
import { usePrefetchRace, useRaces } from '../queries'

/** Wins per driver in the season, most first, with the team of their latest win. */
function winsByDriver(races: RaceSummary[]) {
  const wins = new Map<string, { driver: string; code: string | null; team: string; wins: number }>()
  for (const race of races) {
    const winner = race.winner ?? null
    if (!winner) continue
    const entry = wins.get(winner.driver_name) ?? { driver: winner.driver_name, code: winner.driver_code, team: winner.team, wins: 0 }
    entry.wins += 1
    entry.team = winner.team
    wins.set(winner.driver_name, entry)
  }
  return [...wins.values()].sort((a, b) => b.wins - a.wins || a.driver.localeCompare(b.driver))
}

function Skeleton() {
  return (
    <div role="status" className="space-y-6">
      <span className="sr-only">Loading races…</span>
      <div className="skeleton h-40 max-w-xl" />
      <div className="grid grid-cols-2 gap-px lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="skeleton h-64" />
        ))}
      </div>
    </div>
  )
}

/** The latest round with a result, set over the foot of the season numerals. */
function Latest({ race, next }: { race: RaceSummary; next?: RaceSummary }) {
  const winner = race.winner!
  const prefetch = usePrefetchRace(race.id)
  return (
    <section
      aria-labelledby="latest-heading"
      className="rise relative grid gap-6 border border-line-strong bg-surface p-5 sm:p-7 md:grid-cols-[minmax(0,1fr)_14rem] lg:-mt-[clamp(3rem,7vw,6.5rem)] lg:ml-[30%]"
      style={{ '--i': 2 } as CSSProperties}
    >
      <span aria-hidden="true" className="absolute -left-px -right-px -top-px h-[3px] bg-accent" />
      <div className="min-w-0">
        <p className="eyebrow flex items-center gap-2">
          <span id="latest-heading">{next ? 'Latest round' : 'Season finale'}</span>
        </p>
        <p className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-base text-muted">
          <Flag circuitRef={race.circuit_ref} className="!w-8" />
          <span>{circuitName(race.circuit_ref)}</span>
          <span className="num">{formatRound(race.round)}</span>
          <span className="num">{formatDate(race.date)}</span>
        </p>
        <h2 className="display mt-2 !text-[clamp(2.25rem,5vw,3.75rem)]">{race.name}</h2>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-5 border-t border-line pt-5">
          <div className="flex items-center gap-3">
            <Headshot name={winner.driver_name} team={winner.team} className="h-14 w-14" />
            <div className="leading-tight">
              <p className="eyebrow">Winner</p>
              <p className="mt-1 text-xl font-medium">
                {winner.driver_name} <span className="num ml-1 text-sm text-muted">{winner.driver_code}</span>
              </p>
              <p className="text-sm text-muted">{winner.team}</p>
            </div>
          </div>
          <Link to={`/races/${race.id}`} onPointerEnter={prefetch} onFocus={prefetch} className="btn btn-primary">
            Open race <span className="sr-only">{race.name}</span>
            <svg aria-hidden="true" viewBox="0 0 16 16" className="arrow h-4 w-4">
              <path d="M2 8h11M9 4l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.8" />
            </svg>
          </Link>
        </div>
        {next && (
          <p className="mt-5 text-[0.8125rem] text-muted">
            Next <span className="num ml-2 text-ink">{formatRound(next.round)}</span>{' '}
            <span className="text-ink">{next.name}</span> · <span className="num">{formatDate(next.date)}</span>
          </p>
        )}
      </div>
      <CircuitOutline circuitRef={race.circuit_ref} draw className="mx-auto hidden w-full max-w-[14rem] self-center md:block" />
    </section>
  )
}

function Winners({ races }: { races: RaceSummary[] }) {
  const winners = winsByDriver(races)
  const most = winners[0]?.wins ?? 1
  if (winners.length === 0) return null
  return (
    <Reveal as="section" className="panel">
      <h2 className="heading">
        Winners
      </h2>
      <ol aria-label="Wins this season" className="mt-4">
        {winners.map((w, i) => (
          <li key={w.driver} className="grid grid-cols-[1.25rem_2.5rem_minmax(0,1fr)_3.75rem] items-center gap-3 border-b border-line py-2.5 sm:grid-cols-[1.5rem_2.75rem_minmax(14rem,22rem)_minmax(4rem,1fr)_4rem] sm:gap-5">
            <span className={`num text-right text-sm ${i === 0 ? 'text-accent' : 'text-muted'}`}>{i + 1}</span>
            <Headshot name={w.driver} team={w.team} className="h-10 w-10 sm:h-11 sm:w-11" />
            <span className="min-w-0 truncate text-lg font-medium">
              {w.driver} <span className="ml-1 hidden text-sm font-normal text-muted sm:inline">{w.team}</span>
            </span>
            <span aria-hidden="true" className="hidden h-1.5 bg-line sm:block">
              <span className={`block h-full ${i === 0 ? 'bg-accent' : 'bg-ink'}`} style={{ width: `${(w.wins / most) * 100}%` }} />
            </span>
            <span className="num text-right text-sm">
              {w.wins} {w.wins === 1 ? 'win' : 'wins'}
            </span>
          </li>
        ))}
      </ol>
    </Reveal>
  )
}

export default function RaceListPage() {
  const { data: races, error, isPending } = useRaces()
  const [params, setParams] = useSearchParams()

  const seasons = useMemo(
    () => [...new Set((races ?? []).map((r) => r.season))].sort((a, b) => b - a),
    [races],
  )
  const options = useMemo(() => seasons.map((s) => ({ value: String(s), label: String(s) })), [seasons])
  // The latest season with at least one result, so the page opens on races that can be analysed.
  const latest = seasons.find((s) => (races ?? []).some((r) => r.season === s && r.winner)) ?? seasons[0]
  const requested = Number(params.get('season'))
  const season = seasons.includes(requested) ? requested : latest
  const shown = (races ?? []).filter((r) => r.season === season)

  const run = shown.filter((r) => r.winner)
  const lastRun = run.at(-1)
  const next = shown.find((r) => !r.winner)
  const winnerCount = new Set(run.map((r) => r.winner?.driver_name)).size

  return (
    <div className="space-y-16 sm:space-y-24">
      <div>
        <div className="rise flex flex-wrap items-center justify-end gap-4">
          {seasons.length > 0 && (
            <Listbox
              label="Season"
              options={options}
              value={String(season)}
              onChange={(value) => setParams({ season: value })}
              alignEnd
            />
          )}
        </div>
        <h1
          className="rise font-display text-[clamp(7rem,30vw,21rem)] font-extrabold uppercase leading-[0.8] tracking-[-0.02em]"
          style={{ '--i': 1 } as CSSProperties}
        >
          {season ?? 'Races'}
          {season && <span className="sr-only"> season</span>}
        </h1>
        {shown.length > 0 && (
          <p className="rise num mt-5 text-sm text-muted" style={{ '--i': 1 } as CSSProperties}>
            {run.length === shown.length ? `${shown.length} rounds` : `${run.length} of ${shown.length} rounds run`}
            {winnerCount > 0 && ` · ${winnerCount} ${winnerCount === 1 ? 'winner' : 'winners'}`}
          </p>
        )}
        {lastRun && (
          <div className="mt-8 lg:mt-0">
            <Latest race={lastRun} next={next} />
          </div>
        )}
      </div>

      {isPending && <Skeleton />}
      {error && <LoadError error={error} what="the races" />}
      {races && shown.length === 0 && <p className="text-muted">No races loaded yet.</p>}

      {shown.length > 0 && (
        <>
          <Winners races={shown} />
          <section aria-labelledby="calendar-heading" className="panel">
            <h2 id="calendar-heading" className="heading">
              Every round
            </h2>
            <ol className="mt-5 grid grid-cols-2 border-l border-t border-line md:grid-cols-3 lg:grid-cols-4">
              {shown.map((race, i) => (
                <RoundTile key={race.id} race={race} index={i} latest={race.id === lastRun?.id} next={race.id === next?.id} />
              ))}
            </ol>
          </section>
        </>
      )}
    </div>
  )
}
