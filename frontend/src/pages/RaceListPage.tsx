import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import Listbox from '../components/Listbox'
import RaceCard from '../components/RaceCard'
import SeasonStrip from '../components/SeasonStrip'
import { LoadError } from '../components/Status'
import { useRaces } from '../queries'

function Skeleton() {
  return (
    <div role="status" className="space-y-6">
      <span className="sr-only">Loading races…</span>
      <div className="skeleton h-11" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="skeleton h-56" />
        ))}
      </div>
    </div>
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
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div>
          <h1 className="display">{season ? `${season} season` : 'Races'}</h1>
          {shown.length > 0 && (
            <p className="mt-3 text-muted">
              {run.length === shown.length
                ? `${shown.length} rounds`
                : `${run.length} of ${shown.length} rounds run`}
              {winnerCount > 0 && `, ${winnerCount} different ${winnerCount === 1 ? 'winner' : 'winners'}`}.
            </p>
          )}
        </div>
        {seasons.length > 0 && (
          <Listbox
            label="Season"
            options={options}
            value={String(season)}
            onChange={(value) => setParams({ season: value })}
          />
        )}
      </div>

      {isPending && <Skeleton />}
      {error && <LoadError error={error} what="the races" />}
      {races && shown.length === 0 && <p className="text-muted">No races loaded yet.</p>}

      {shown.length > 0 && (
        <>
          <SeasonStrip races={shown} />

          {lastRun && (
            <section aria-labelledby="featured-heading" className="space-y-3">
              <h2 id="featured-heading" className="heading">
                {next ? 'Latest and next' : 'Season finale'}
              </h2>
              <ul className={`grid gap-4 ${next ? 'lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]' : ''}`}>
                <RaceCard race={lastRun} featured />
                {next && <RaceCard race={next} />}
              </ul>
            </section>
          )}

          <section aria-labelledby="calendar-heading" className="space-y-3">
            <h2 id="calendar-heading" className="heading">
              Every round
            </h2>
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {shown.map((race) => (
                <RaceCard key={race.id} race={race} />
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  )
}
