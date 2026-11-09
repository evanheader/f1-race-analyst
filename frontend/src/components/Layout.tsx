import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { applyScheme, loadScheme, saveScheme, type ColorScheme } from '../colorScheme'

/** A tab: the current one is filled, with an accent bar along its foot. */
const tabClass = (active: boolean) =>
  `relative px-3 py-2 text-[0.9375rem] font-semibold transition-colors duration-150 sm:px-4 ${
    active
      ? 'bg-surface text-ink after:absolute after:inset-x-0 after:-bottom-px after:h-[3px] after:bg-accent'
      : 'text-muted hover:text-ink'
  }`

function ThemeToggle() {
  const [scheme, setScheme] = useState<ColorScheme>(loadScheme)
  const light = scheme === 'light'
  function toggle() {
    const next = light ? 'dark' : 'light'
    applyScheme(next)
    saveScheme(next)
    setScheme(next)
  }
  return (
    <button
      type="button"
      aria-pressed={light}
      aria-label="Light theme"
      title={light ? 'Switch to dark' : 'Switch to light'}
      onClick={toggle}
      className="grid h-10 w-10 place-items-center text-muted transition-colors hover:text-ink"
    >
      <svg viewBox="0 0 20 20" aria-hidden="true" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6">
        {light ? (
          <path d="M16.5 12.3A7 7 0 0 1 7.7 3.5a7 7 0 1 0 8.8 8.8z" />
        ) : (
          <>
            <circle cx="10" cy="10" r="3.4" />
            <path d="M10 1.5v2M10 16.5v2M1.5 10h2M16.5 10h2M4 4l1.4 1.4M14.6 14.6 16 16M4 16l1.4-1.4M14.6 5.4 16 4" />
          </>
        )}
      </svg>
    </button>
  )
}

const link = 'text-ink underline decoration-line-strong underline-offset-[3px] hover:decoration-ink'

/** An original mark: a bracket with a timing line ending in a signal dot. Decorative: the name is next to it. */
function Mark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-[1.375rem] w-[1.375rem]" fill="none" strokeWidth="2.4" strokeLinecap="square">
      <path d="M4 4v16M4 4h5M4 20h5" stroke="var(--ink)" />
      <path d="M11 12h9" stroke="var(--muted)" />
      <circle cx="20" cy="12" r="2" fill="var(--accent)" stroke="none" />
    </svg>
  )
}

export default function Layout() {
  // A race page belongs to the Races tab too.
  const { pathname } = useLocation()
  const racesActive = pathname === '/' || pathname.startsWith('/races/')
  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-50 focus:bg-ink focus:px-4 focus:py-2 focus:text-bg">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-4 py-3 sm:px-10">
          <NavLink to="/" className="flex items-center gap-2 font-display text-[1.375rem] font-extrabold uppercase leading-none tracking-[0.02em]">
            <Mark />
            <span className="hidden min-[440px]:inline">Race Analyst</span>
            <span className="sr-only min-[440px]:hidden">Race Analyst</span>
          </NavLink>
          <div className="flex items-center gap-2 sm:gap-4">
            <nav aria-label="Main" className="flex border border-line-strong">
              <NavLink to="/" aria-current={racesActive ? 'page' : undefined} className={() => tabClass(racesActive)}>
                Races
              </NavLink>
              <NavLink to="/ask" className={({ isActive }) => tabClass(isActive)}>
                Engineer
              </NavLink>
            </nav>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-7xl flex-1 px-4 pb-24 pt-10 sm:px-10 sm:pt-14">
        <Outlet />
      </main>
      <footer className="border-t border-line text-[0.8125rem] text-muted">
        <div className="mx-auto grid max-w-7xl gap-2 px-4 py-8 sm:px-10 md:grid-cols-[1fr_auto] md:gap-8">
          <div className="space-y-1">
            <p>Unofficial fan project, not affiliated with Formula 1 or any team.</p>
            <p>How this works: race data is loaded into PostgreSQL and served by a FastAPI API. The engineer is Claude, using read-only tools over that data.</p>
          </div>
          <p>
            Data{' '}
            <a className={link} href="https://github.com/jolpica/jolpica-f1">
              Jolpica
            </a>{' '}
            ·{' '}
            <a className={link} href="https://openf1.org/">
              OpenF1
            </a>{' '}
            · Circuits{' '}
            <a className={link} href="https://github.com/bacinger/f1-circuits">
              f1-circuits
            </a>{' '}
            · Flags{' '}
            <a className={link} href="https://github.com/lipis/flag-icons">
              flag-icons
            </a>{' '}
            ·{' '}
            <a className={link} href="https://github.com/evanheader/f1-race-analyst">
              Source
            </a>
          </p>
        </div>
      </footer>
    </div>
  )
}
