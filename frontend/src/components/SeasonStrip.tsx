import { Link } from 'react-router'
import type { RaceSummary } from '../api'
import { teamCardColor } from '../teamColors'

/** Wins per driver in the season, most first, with the team of their latest win. */
function winsByDriver(races: RaceSummary[]) {
  const wins = new Map<string, { driver: string; team: string; wins: number }>()
  for (const race of races) {
    const winner = race.winner ?? null
    if (!winner) continue
    const entry = wins.get(winner.driver_name) ?? { driver: winner.driver_name, team: winner.team, wins: 0 }
    entry.wins += 1
    entry.team = winner.team
    wins.set(winner.driver_name, entry)
  }
  return [...wins.values()].sort((a, b) => b.wins - a.wins || a.driver.localeCompare(b.driver))
}

/**
 * The season at a glance: one block per round in the winning team's color, then wins per driver.
 * Rounds without a result are drawn hollow and open nothing. Every other block opens its race.
 */
export default function SeasonStrip({ races }: { races: RaceSummary[] }) {
  const winners = winsByDriver(races)
  return (
    <section aria-labelledby="season-strip-heading" className="space-y-3">
      <h2 id="season-strip-heading" className="sr-only">
        Winner of each round
      </h2>
      <ol className="flex h-11 gap-1">
        {races.map((race) => {
          const winner = race.winner ?? null
          const label = winner
            ? `Round ${race.round}, ${race.name}, won by ${winner.driver_name}`
            : `Round ${race.round}, ${race.name}, no result yet`
          if (!winner) {
            return (
              <li key={race.id} className="min-w-0 flex-1" title={label}>
                <span className="sr-only">{label}</span>
                <span aria-hidden="true" className="block h-full rounded-md border border-dashed border-white/25" />
              </li>
            )
          }
          return (
            <li key={race.id} className="min-w-0 flex-1">
              <Link
                to={`/races/${race.id}`}
                aria-label={label}
                title={label}
                className="block h-full rounded-md shadow-[inset_0_1px_0_rgb(255_255_255/0.25)] transition-transform duration-150 hover:-translate-y-0.5 hover:brightness-125"
                style={{ background: teamCardColor(winner.team) }}
              />
            </li>
          )
        })}
      </ol>
      {winners.length > 0 && (
        <ul aria-label="Wins this season" className="flex flex-wrap gap-1.5">
          {winners.map((w) => (
            <li
              key={w.driver}
              className="flex items-center gap-2 rounded-full border border-line bg-white/[0.04] py-1 pl-1.5 pr-3 text-[0.8125rem]"
            >
              <span aria-hidden="true" className="h-3 w-3 rounded-full" style={{ background: teamCardColor(w.team) }} />
              <span className="font-medium">{w.driver}</span>
              <span className="num text-muted">
                {w.wins} {w.wins === 1 ? 'win' : 'wins'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
