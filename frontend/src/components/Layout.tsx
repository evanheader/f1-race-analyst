import { NavLink, Outlet } from 'react-router'
import ThemePicker from './ThemePicker'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-full px-3.5 py-1.5 text-sm font-semibold transition-colors duration-150 ${
    isActive ? 'bg-white/10 text-ink' : 'text-muted hover:bg-white/5 hover:text-ink'
  }`

const link = 'text-accent-text underline underline-offset-2 hover:text-ink'

/** Three slanted bars, an original mark for the site. Decorative: the name is next to it. */
function Mark() {
  return (
    <svg viewBox="0 0 28 16" aria-hidden="true" className="h-4 w-7">
      <path d="M6 0h7L7 16H0z" fill="var(--team)" />
      <path d="M15 0h6l-6 16H9z" fill="var(--team)" opacity="0.7" />
      <path d="M23 0h5l-6 16h-5z" fill="var(--second)" />
    </svg>
  )
}

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 bg-bg/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2.5 sm:px-6">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <NavLink to="/" className="flex items-center gap-2.5">
              <Mark />
              <span className="text-[1.0625rem] font-extrabold italic tracking-tight [font-stretch:125%]">
                F1 Race Analyst
              </span>
            </NavLink>
            <nav aria-label="Main" className="flex gap-1">
              <NavLink to="/" end className={navClass}>
                Races
              </NavLink>
              <NavLink to="/ask" className={navClass}>
                Ask the engineer
              </NavLink>
            </nav>
          </div>
          <ThemePicker />
        </div>
        {/* A livery pinstripe: the team color with a hairline of its second color. */}
        <div aria-hidden="true" data-testid="livery-stripe" className="absolute inset-x-0 -bottom-px">
          <div className="h-[2px] bg-team" />
          <div className="h-px bg-second" />
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <Outlet />
      </main>
      <footer className="border-t border-line text-[0.8125rem] text-muted">
        <div className="mx-auto max-w-7xl space-y-1.5 px-4 py-8 sm:px-6">
          <p>Unofficial fan project, not affiliated with Formula 1 or any team.</p>
          <p>
            Data from{' '}
            <a className={link} href="https://github.com/jolpica/jolpica-f1">
              Jolpica
            </a>{' '}
            and{' '}
            <a className={link} href="https://openf1.org/">
              OpenF1
            </a>
            . Circuit outlines from{' '}
            <a className={link} href="https://github.com/bacinger/f1-circuits">
              f1-circuits
            </a>{' '}
            (MIT) and flags from{' '}
            <a className={link} href="https://github.com/lipis/flag-icons">
              flag-icons
            </a>{' '}
            (MIT). Source on{' '}
            <a className={link} href="https://github.com/evanheader/f1-race-analyst">
              GitHub
            </a>
            .
          </p>
          <p>
            Race data is loaded into PostgreSQL and served by a FastAPI API. The engineer is Claude,
            using read-only tools over that data.
          </p>
        </div>
      </footer>
    </div>
  )
}
