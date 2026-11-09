import type { RaceResult } from '../api'
import { teamColor } from '../teamColors'

/** Places gained from the grid to the flag: "+12", "−3", or "0". A pit lane start has no grid slot to compare. */
function placesChange(r: RaceResult) {
  if (r.grid === 0) return { text: 'Pit', className: 'text-muted', title: 'Started from the pit lane' }
  const gained = r.grid - r.position
  if (gained > 0) return { text: `+${gained}`, className: 'text-good', title: `Gained ${gained} from P${r.grid}` }
  if (gained < 0) return { text: `−${-gained}`, className: 'text-bad', title: `Lost ${-gained} from P${r.grid}` }
  return { text: '0', className: 'text-muted', title: `Held P${r.grid}` }
}

/** Classified finishers have a number; "Finished" and "+1 Lap" are normal results, anything else is a retirement reason. */
const classified = (r: RaceResult) => /^\d+$/.test(r.position_text)
const normalStatus = (s: string) => s === 'Finished' || /^\+\d+ Laps?$/.test(s) || s === 'Lapped'

function Row({ r, selected }: { r: RaceResult; selected?: boolean }) {
  const change = placesChange(r)
  const color = teamColor(r.team)
  return (
    <>
      <span className={`num w-6 shrink-0 text-right ${r.position <= 3 && classified(r) ? 'text-ink' : 'text-muted'}`}>
        {r.position_text}
      </span>
      <span aria-hidden="true" className="h-8 w-[3px] shrink-0 rounded-full" style={{ background: color }} />
      <span className="min-w-0 flex-1 text-left leading-tight">
        <span className="flex items-baseline gap-2">
          <span className="num text-[0.9375rem] text-ink">{r.driver_code ?? '—'}</span>
          <span className="truncate text-[0.8125rem] text-muted">{r.driver_name}</span>
        </span>
        <span className="block truncate text-xs text-muted">
          {r.team}
          {!normalStatus(r.status) && <span className="text-bad">{`, ${r.status}`}</span>}
        </span>
      </span>
      <span title={change.title} className={`num w-8 shrink-0 text-right text-[0.8125rem] ${change.className}`}>
        {change.text}
      </span>
      <span className="num w-7 shrink-0 text-right text-ink">{r.points > 0 ? r.points : ''}</span>
      {selected !== undefined && (
        <span
          aria-hidden="true"
          className="h-2.5 w-2.5 shrink-0 rounded-full border-2 transition-colors"
          style={{ borderColor: selected ? color : 'rgb(255 255 255 / 0.2)', background: selected ? color : 'transparent' }}
        />
      )}
    </>
  )
}

/**
 * The classification, styled like a timing tower. When `onToggle` is given, each row is a toggle that
 * puts the driver on the lap chart.
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
    <section aria-labelledby="classification-heading" className="panel overflow-hidden">
      <div className="flex items-baseline justify-between gap-3 px-4 pb-2 pt-4">
        <h2 id="classification-heading" className="heading">
          Classification
        </h2>
        <p className="text-xs text-muted">
          <abbr title="Places gained or lost from the grid" className="no-underline">
            +/−
          </abbr>{' '}
          and points
        </p>
      </div>
      {onToggle && <p className="px-4 pb-2 text-[0.8125rem] text-muted">Pick up to 3 drivers for the lap chart.</p>}
      <ol
        role={onToggle ? 'group' : undefined}
        aria-label={onToggle ? 'Drivers to compare' : 'Race classification'}
        className="pb-2"
      >
        {results.map((r) => {
          const on = selected.includes(r.driver_id)
          const rowClass = 'flex w-full items-center gap-3 px-4 py-1.5'
          return (
            <li key={r.driver_id}>
              {onToggle ? (
                <button
                  type="button"
                  aria-pressed={on}
                  aria-label={`${r.driver_code ?? r.driver_name}, P${r.position_text}, ${r.driver_name}`}
                  onClick={() => onToggle(r.driver_id)}
                  className={`${rowClass} transition-colors duration-100 hover:bg-white/[0.05] ${on ? 'bg-white/[0.06]' : ''}`}
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
    </section>
  )
}
