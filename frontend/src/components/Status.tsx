import { useEffect, useState } from 'react'
import { ApiError } from '../api'

/** Shown while a request runs. After 4 seconds it says so, because a cold server can be slow. */
export function Loading({ what }: { what: string }) {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), 4000)
    return () => clearTimeout(timer)
  }, [])
  return (
    <p role="status" className="text-muted">
      {slow ? 'Warming up, one moment…' : `Loading ${what}…`}
    </p>
  )
}

export function LoadError({ error, what }: { error: unknown; what: string }) {
  const detail = error instanceof ApiError && error.detail ? ` ${error.detail}.` : ''
  return (
    <p role="alert" className="border-l-2 border-accent bg-surface p-3 text-ink">
      Could not load {what}.{detail} Check that the API is running, then reload the page.
    </p>
  )
}
