import { circuitArt } from '../circuits'

/**
 * The circuit as a line drawing: a chalk stroke with a thin graphite stroke offset beside it.
 * Draws nothing when the circuit has no outline. `draw` makes the line draw itself once on load;
 * `reveal` draws it when a surrounding <Reveal> scrolls into view.
 */
export default function CircuitOutline({
  circuitRef,
  draw = false,
  reveal = false,
  className = '',
}: {
  circuitRef: string
  draw?: boolean
  reveal?: boolean
  className?: string
}) {
  const path = circuitArt(circuitRef)?.path
  if (!path) return null
  return (
    <svg
      viewBox="0 0 100 100"
      aria-hidden="true"
      focusable="false"
      className={`circuit ${draw ? 'circuit-draw' : ''} ${reveal ? 'circuit-reveal' : ''} ${className}`}
      fill="none"
      strokeLinejoin="round"
      strokeLinecap="round"
    >
      <path d={path} pathLength={1} className="circuit-2" stroke="var(--muted)" strokeOpacity={0.7} strokeWidth={0.7} transform="translate(1.8 1.8)" />
      <path d={path} pathLength={1} className="circuit-1" stroke="var(--ink)" strokeWidth={2.2} />
    </svg>
  )
}
