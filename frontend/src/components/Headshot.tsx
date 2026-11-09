import { useState } from 'react'
import photos from '../data/driverPhotos.json'
import { teamColor } from '../teamColors'

// Three hair shapes, picked from the driver's name, so a list of drivers does not look cloned.
const HAIR = [
  'M12 17c0-6 3.6-9.5 8-9.5s8 3.5 8 9.5c-1.2-2.8-3.6-4.4-8-4.4s-6.8 1.6-8 4.4z',
  'M11.6 18c-.4-7 3.4-10.6 8.4-10.6 5.2 0 8.8 3.4 8.4 10.6-.8-1.8-1.6-3-2.6-3.6-2.4 1-6.6 1-9.6-.6-1.6.8-3.2 2.4-4.6 4.2z',
  'M12.2 15.6c.8-5 3.8-7.8 7.8-7.8 4.4 0 7.4 3 7.8 8-2.2-1.6-5-2.4-7.8-2.4s-5.6.8-7.8 2.2z',
]

const photoPaths: Record<string, string> = photos

/**
 * The 2026 grid's photos from formula1.com's image CDN, cropped to the face. Keyed by the driver
 * name in the database; the CDN does the crop, so nothing is stored here but the path.
 */
function photoUrl(name: string): string | null {
  const path = photoPaths[name]
  return path ? `https://media.formula1.com/image/upload/c_thumb,g_face,z_0.7,w_160,h_160/q_auto/v1740000001/${path}` : null
}

/**
 * A driver's headshot: their formula1.com photo when they are on the 2026 grid, otherwise (or if the
 * photo fails to load) an original illustrated portrait in the team's color. Decorative: the
 * driver's name is always next to it.
 */
export default function Headshot({ name, team, className = '' }: { name: string; team: string; className?: string }) {
  const [failed, setFailed] = useState(false)
  const photo = failed ? null : photoUrl(name)
  const hair = HAIR[[...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % HAIR.length]
  return (
    <span aria-hidden="true" className={`block shrink-0 overflow-hidden rounded-full bg-[var(--portrait)] ring-1 ring-line-strong ${className}`}>
      {photo ? (
        <img src={photo} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} className="block h-full w-full object-cover" />
      ) : (
        <svg viewBox="0 0 40 40" className="block h-full w-full">
          <path d="M4 40c1.2-7.2 7-10.8 16-10.8S34.8 32.8 36 40z" fill={teamColor(team)} opacity="0.55" />
          <path d="M16.6 28.6h6.8l-1 3.2h-4.8z" fill="#6E747C" />
          <path d="M14.4 29.6 20 34l5.6-4.4" fill="none" stroke="#ECEAE4" strokeWidth="1" opacity="0.5" />
          <ellipse cx="20" cy="19" rx="7.4" ry="8.6" fill="#6E747C" />
          <path d={hair} fill="#2A2D31" />
        </svg>
      )}
    </span>
  )
}
