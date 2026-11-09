import type { RaceResult } from '../api'
import { teamColor } from '../teamColors'
import Headshot from './Headshot'

/** Places gained from the grid to the flag: "▲12", "▼3", or "–". A pit lane start has no grid slot to compare. */
function placesChange(r: RaceResult) {
  if (r.grid === 0) return { text: 'Pit', className: 'text-muted', title: 'Started from the pit lane' }
  const gained = r.grid - r.position
  if (gained > 0) return { text: `▲${gained}`, className: 'text-good', title: `Gained ${gained} from P${r.grid}` }
  if (gained < 0) return { text: `▼${-gained}`, className: 'text-muted', title: `Lost ${-gained} from P${r.grid}` }
  return { text: '–', className: 'text-muted', title: `Held P${r.grid}` }
}

/** Classified finishers have a number; "Finished" and "+1 Lap" are normal results, anything else is a retirement reason. */
const classified = (r: RaceResult) => /^\d+$/.test(r.position_text)
const normalStatus = (s: string) => s === 'Finished' || /^\+\d+ Laps?$/.test(s) || s === 'Lapped'

// Position, team stripe, headshot, driver, places, points, pick dot.
const COLUMNS = 'grid grid-cols-[1.5rem_2px_2.5rem_minmax(0,1fr)_3rem_2.5rem_0.625rem] items-center gap-x-3'

function Row({ r, selected }: { r: RaceResult; selected?: boolean }) {
  const change = placesChange(r)
  return (
    <>
      <span
        className={`num text-right text-sm ${r.position === 1 && classified(r) ? 'text-accent' : r.position <= 3 && classified(r) ? 'text-ink' : 'text-muted'}`}
      >
        {r.position_text}
      </span>
      <span aria-hidden="true" className="h-9 w-0.5" style={{ background: teamColor(r.team) }} />
      <Headshot name={r.driver_name} team={r.team} className="h-10 w-10" />
      <span className="min-w-0 text-left leading-tight">
        <span className="flex items-baseline gap-2">
          <span className="num text-base font-medium text-ink">{r.driver_code ?? '—'}</span>
          <span className="min-w-0 text-[0.9375rem] leading-snug text-ink sm:truncate">{r.driver_name}</span>
        </span>
        <span className="block truncate text-[0.8125rem] text-muted">
          {r.team}
          {!normalStatus(r.status) && <span className="text-bad">{`, ${r.status}`}</span>}
        </span>
      </span>
      <span title={change.title} className={`num text-right text-sm ${change.className}`}>
        <span className="sr-only">{change.title}: </span>
        <span aria-hidden="true">{change.text}</span>
      </span>
      <span className="num text-right text-sm font-medium text-ink">{r.points > 0 ? r.points : ''}</span>
      {selected !== undefined ? (
        <span
          aria-hidden="true"
          className="h-2.5 w-2.5 rounded-full border transition-colors"
          style={{ borderColor: selected ? 'var(--ink)' : 'var(--line-strong)', background: selected ? 'var(--ink)' : 'transparent' }}
        />
      ) : (
        <span />
      )}
    </>
  )
}

/**
 * The classification, styled like a timing tower: places gained or lost from the grid, and points.
 * When `onToggle` is given, each row is a toggle that puts the driver on the lap chart.
 */
export default function TimingTower({
  results,
  selected = [],
  onToggle,
}: {
  results: RaceResult[]
  selected?: number[]
  onToggle?: (driverId: number) => void
}) {
  return (
    <div>
      {onToggle && <p className="text-[0.8125rem] text-muted">Pick up to 3 drivers for the lap chart.</p>}
      <div aria-hidden="true" className={`${COLUMNS} eyebrow mt-4 px-3 pb-2 !text-[0.6875rem]`}>
        <span className="text-right">P</span>
        <span />
        <span />
        <span>Driver</span>
        <span className="text-right">+/−</span>
        <span className="text-right">Pts</span>
        <span />
      </div>
      <ol
        role={onToggle ? 'group' : undefined}
        aria-label={onToggle ? 'Drivers to compare' : 'Race classification'}
        className="border-t border-line"
      >
        {results.map((r) => {
          const on = selected.includes(r.driver_id)
          const rowClass = `${COLUMNS} w-full px-3 py-1.5`
          return (
            <li key={r.driver_id} className="border-b border-line">
              {onToggle ? (
                <button
                  type="button"
                  aria-pressed={on}
                  aria-label={`${r.driver_code ?? r.driver_name}, P${r.position_text}, ${r.driver_name}`}
                  onClick={() => onToggle(r.driver_id)}
                  className={`${rowClass} transition-colors duration-100 hover:bg-surface ${on ? 'bg-surface' : ''}`}
                >
                  <Row r={r} selected={on} />
                </button>
              ) : (
                <div className={rowClass}>
                  <Row r={r} />
                </div>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
