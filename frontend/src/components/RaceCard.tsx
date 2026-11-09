import type { CSSProperties } from 'react'
import { Link } from 'react-router'
import type { RaceSummary } from '../api'
import { circuitName, formatDate } from '../format'
import { usePrefetchRace } from '../queries'
import { teamCardColor } from '../teamColors'
import CircuitOutline from './CircuitOutline'
import Flag from './Flag'

/**
 * One race on the calendar, shaded in the winning team's color, so a season reads as who won where.
 * A race with results has an "Open analysis" link that covers the whole card; hovering or focusing the
 * card starts loading the race. A race without results has nothing to open, so it has no link.
 */
export default function RaceCard({ race, featured = false }: { race: RaceSummary; featured?: boolean }) {
  // An API without the winner field leaves it out, and a race without results has none.
  const winner = race.winner ?? null
  const prefetch = usePrefetchRace(race.id)
  const style = { '--c': teamCardColor(winner?.team) } as CSSProperties

  return (
    <li
      className={`team-shade ${winner ? 'lift' : ''} relative flex flex-col rounded-[var(--radius-card)] border border-white/10 shadow-[0_18px_40px_-24px_rgb(0_0_0/0.8)] ${
        featured ? 'min-h-[17rem] p-6 sm:p-7' : 'min-h-[14rem] p-5'
      }`}
      style={style}
      onPointerEnter={winner ? prefetch : undefined}
      onFocus={winner ? prefetch : undefined}
    >
      <CircuitOutline
        circuitRef={race.circuit_ref}
        tone="light"
        className={`pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 ${
          featured ? 'h-52 w-52 opacity-70 sm:right-10' : 'h-32 w-32 opacity-45'
        }`}
      />
      <p className="flex items-center gap-2 text-[0.8125rem] text-white/80">
        <Flag circuitRef={race.circuit_ref} />
        <span>
          Round <span className="num text-white">{race.round}</span>
        </span>
        <span aria-hidden="true" className="h-3 w-px bg-white/25" />
        <span className="num text-white">{formatDate(race.date)}</span>
      </p>
      <h2 className={`${featured ? 'display !text-[clamp(1.9rem,4vw,2.75rem)]' : 'title'} mt-3 max-w-[16ch] text-white`}>
        {race.name}
      </h2>
      <p className="mt-1 text-sm text-white/75">{circuitName(race.circuit_ref)}</p>

      <div className="mt-auto flex flex-wrap items-end justify-between gap-3 pt-5">
        {winner ? (
          <>
            <p className="text-sm text-white/80">
              Winner <span className="ml-1 font-semibold text-white">{winner.driver_name}</span>
            </p>
            <Link
              to={`/races/${race.id}`}
              className="card-link btn !min-h-9 !border-white/20 !bg-black/25 !px-3.5 text-sm text-white backdrop-blur-sm"
            >
              Open analysis <span className="sr-only">for {race.name}</span>
            </Link>
          </>
        ) : (
          <p className="text-sm text-white/80">No result yet</p>
        )}
      </div>
    </li>
  )
}
