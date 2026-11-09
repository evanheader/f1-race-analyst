import { Link } from 'react-router'
import type { RaceSummary } from '../api'
import { circuitName, formatDate } from '../format'
import { usePrefetchRace } from '../queries'
import CircuitOutline from './CircuitOutline'
import Flag from './Flag'
import Headshot from './Headshot'
import Reveal from './Reveal'

/**
 * One round on the calendar: its number, flag, circuit, name and winner. A round with results links
 * to its race, and hovering or focusing it starts loading the race. A round without results is dimmed
 * and links nowhere.
 */
export default function RoundTile({
  race,
  index,
  latest = false,
  next = false,
}: {
  race: RaceSummary
  index: number
  latest?: boolean
  next?: boolean
}) {
  // An API without the winner field leaves it out, and a race without results has none.
  const winner = race.winner ?? null
  const prefetch = usePrefetchRace(race.id)

  return (
    <Reveal
      as="li"
      index={index % 4}
      className={`group relative flex flex-col gap-3 border-b border-r border-line p-4 transition-colors duration-150 ${
        latest ? 'z-10 bg-surface shadow-[inset_0_0_0_2px_var(--accent)]' : winner ? 'hover:bg-surface' : ''
      } ${next ? 'shadow-[inset_0_0_0_1px_var(--accent)]' : ''}`}
    >
      <span onPointerEnter={winner ? prefetch : undefined} onFocus={winner ? prefetch : undefined} className="contents">
        <div className="flex items-center justify-between gap-2">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className={`num text-xs ${latest || next ? 'text-accent' : 'text-muted'}`}>R{String(race.round).padStart(2, '0')}</span>
            {latest && <span className="eyebrow bg-accent px-1.5 py-0.5 !text-[0.625rem] !text-on-accent">Latest</span>}
            {next && <span className="eyebrow border border-accent px-1.5 py-0.5 !text-[0.625rem] !text-accent">Next</span>}
            {race.has_sprint && <span className="eyebrow border border-line-strong px-1.5 py-0.5 !text-[0.625rem]">Sprint</span>}
          </span>
          <Flag circuitRef={race.circuit_ref} className="!w-7" />
        </div>
        <div className={`mx-auto my-1 aspect-square w-[62%] ${winner ? '' : 'opacity-35'}`}>
          <CircuitOutline circuitRef={race.circuit_ref} reveal className="h-full w-full" />
        </div>
        <div className="mt-auto min-w-0">
          <h3 className={`font-display text-2xl font-extrabold uppercase leading-none ${winner ? '' : 'text-muted'}`}>
            {winner ? (
              <Link to={`/races/${race.id}`} className="card-link">
                {race.name}
              </Link>
            ) : (
              race.name
            )}
          </h3>
          <p className="mt-1.5 truncate text-sm text-muted">
            <span className="hidden sm:inline">{circuitName(race.circuit_ref)} · </span>
            <span className="num">{formatDate(race.date)}</span>
          </p>
          <p className="mt-3 flex items-center gap-2.5 border-t border-line pt-3 text-[0.9375rem]">
            {winner ? (
              <>
                <Headshot name={winner.driver_name} team={winner.team} className="h-8 w-8" />
                <span className="min-w-0 flex-1 truncate font-medium">{winner.driver_name}</span>
                <span className="num text-sm text-muted">
                  <span className="sr-only">Winner </span>
                  {winner.driver_code ?? ''}
                </span>
              </>
            ) : (
              <span className="text-muted">No result yet</span>
            )}
          </p>
        </div>
      </span>
    </Reveal>
  )
}
