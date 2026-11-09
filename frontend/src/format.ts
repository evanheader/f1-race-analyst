/** Seconds as m:ss.sss, for example 88.5 becomes 1:28.500. */
export function formatLapTime(seconds: number): string {
  const totalMs = Math.round(seconds * 1000)
  const minutes = Math.floor(totalMs / 60000)
  const rest = totalMs - minutes * 60000
  return `${minutes}:${(rest / 1000).toFixed(3).padStart(6, '0')}`
}

/** Pit lane and stationary times are a few seconds, so they stay as plain seconds. */
export function formatSeconds(seconds: number | null): string {
  return seconds === null ? '—' : `${seconds.toFixed(3)}s`
}

export function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

/** "albert_park" becomes "Albert Park". */
export function circuitName(ref: string): string {
  return ref
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

/** Whole seconds as m:ss, for axis ticks. */
export function formatClock(seconds: number): string {
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}
