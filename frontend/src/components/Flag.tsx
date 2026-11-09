import { circuitArt, flagUrl } from '../circuits'

/** The flag of the country that hosts a circuit. Decorative: the race name is always next to it. */
export default function Flag({ circuitRef, className = '' }: { circuitRef: string; className?: string }) {
  const country = circuitArt(circuitRef)?.country
  const url = country ? flagUrl(country) : null
  if (!url) return null
  return <img src={url} alt="" aria-hidden="true" className={`flag ${className}`} />
}
