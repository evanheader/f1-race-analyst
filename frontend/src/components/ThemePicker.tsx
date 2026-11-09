import { useState } from 'react'
import { applyTheme, loadThemeId, saveThemeId, themes } from '../themes'
import Listbox from './Listbox'

/** The team's color with a sliver of its second color. Decorative: the name is always next to it. */
function Swatch({ team, second }: { team: string; second: string }) {
  return (
    <span
      aria-hidden="true"
      className="h-3.5 w-3.5 shrink-0 rounded-full shadow-[0_0_0_1px_rgb(255_255_255/0.25)]"
      style={{ background: `linear-gradient(135deg, ${team} 0 68%, ${second} 68%)` }}
    />
  )
}

const options = themes.map((t) => ({
  value: t.id,
  label: t.name,
  content: (
    <>
      <Swatch team={t.team} second={t.second} />
      {t.name}
    </>
  ),
}))

export default function ThemePicker() {
  const [id, setId] = useState(loadThemeId)

  function choose(next: string) {
    setId(next)
    applyTheme(next)
    saveThemeId(next)
  }

  return <Listbox label="Theme" options={options} value={id} onChange={choose} alignEnd />
}
