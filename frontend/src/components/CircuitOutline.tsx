import { circuitArt } from '../circuits'

/**
 * The circuit as a line drawing: a main stroke and a thin second stroke offset beside it.
 * `tone="light"` draws it in white for a shaded card; the default uses the theme's team colors.
 * Draws nothing when the circuit has no outline. `draw` makes the line draw itself once.
 */
export default function CircuitOutline({
  circuitRef,
  draw = false,
  tone = 'team',
  className = '',
}: {
  circuitRef: string
  draw?: boolean
  tone?: 'team' | 'light'
  className?: string
}) {
  const path = circuitArt(circuitRef)?.path
  if (!path) return null
  const [main, second] = tone === 'light' ? ['#FFFFFF', 'rgb(255 255 255 / 0.5)'] : ['#FFFFFF', 'var(--second)']
  return (
    <svg
      viewBox="0 0 100 100"
      aria-hidden="true"
      focusable="false"
      className={`circuit ${draw ? 'circuit-draw' : ''} ${className}`}
      fill="none"
      strokeLinejoin="round"
      strokeLinecap="round"
    >
      <path d={path} pathLength={1} className="circuit-2" stroke={second} strokeWidth={0.7} transform="translate(1.8 1.8)" />
      <path d={path} pathLength={1} className="circuit-1" stroke={main} strokeWidth={tone === 'light' ? 1.8 : 2.2} />
    </svg>
  )
}
