export interface Theme {
  id: string
  name: string
  /** The team's color from the 2026 team cards: page glow, hero and card gradients, selected states. */
  team: string
  /** The livery's second color: the pinstripe under the header and small highlights. Reads on `bg`. */
  second: string
  /** The page and its panels, tinted from the team color and always dark. */
  bg: string
  surface: string
  /** Buttons and the focus ring. */
  accent: string
  /** The accent when used as text on the dark page and panels. */
  accentText: string
  /** Text on an accent background. */
  onAccent: string
}

export const DEFAULT_THEME_ID = 'red-bull'
export const THEME_STORAGE_KEY = 'f1ra-theme'

const DARK = '#0A0D12'
const WHITE = '#FFFFFF'

// Team colors are sampled from the 2026 team card artwork the user supplied, not official values.
export const themes: Theme[] = [
  { id: 'red-bull', name: 'Red Bull Racing', team: '#2B5AA0', second: '#FFC906', bg: '#0A0F1D', surface: '#111A2D', accent: '#2F62B0', accentText: '#8EB2EE', onAccent: WHITE },
  { id: 'mercedes', name: 'Mercedes', team: '#14A893', second: '#C6CDD2', bg: '#08110F', surface: '#0F1D1A', accent: '#19B49E', accentText: '#4FD8C2', onAccent: DARK },
  { id: 'ferrari', name: 'Ferrari', team: '#B00025', second: '#FFD12E', bg: '#130A0C', surface: '#1F1114', accent: '#C8102E', accentText: '#FF7A8A', onAccent: WHITE },
  { id: 'mclaren', name: 'McLaren', team: '#E47818', second: '#47C7FC', bg: '#120E0A', surface: '#1D1711', accent: '#F07A16', accentText: '#F7A05A', onAccent: DARK },
  { id: 'racing-bulls', name: 'Racing Bulls', team: '#1F3FC4', second: '#E8E8EE', bg: '#0A0D20', surface: '#121733', accent: '#3557D6', accentText: '#97ACFF', onAccent: WHITE },
  { id: 'alpine', name: 'Alpine', team: '#0A78B0', second: '#FF87BC', bg: '#08111A', surface: '#0F1B28', accent: '#0A72A8', accentText: '#5FBDEB', onAccent: WHITE },
  { id: 'haas', name: 'Haas', team: '#5E676D', second: '#E6002B', bg: '#0E0F11', surface: '#18191C', accent: '#D4002A', accentText: '#FF7383', onAccent: WHITE },
  { id: 'audi', name: 'Audi', team: '#BE2A0A', second: '#C8CED4', bg: '#120B09', surface: '#1E1310', accent: '#C42E0E', accentText: '#FF8466', onAccent: WHITE },
  { id: 'williams', name: 'Williams', team: '#1D4FB8', second: '#64C4FF', bg: '#070F1E', surface: '#0E192F', accent: '#2659C8', accentText: '#86B4FF', onAccent: WHITE },
  { id: 'aston-martin', name: 'Aston Martin', team: '#187854', second: '#CEDC00', bg: '#06100C', surface: '#0D1C16', accent: '#CEDC00', accentText: '#CEDC00', onAccent: DARK },
  { id: 'cadillac', name: 'Cadillac', team: '#7A8488', second: '#FFFFFF', bg: '#0B0B0C', surface: '#161618', accent: '#E5E5E5', accentText: '#E5E5E5', onAccent: DARK },
  { id: 'pitwall', name: 'Pit Wall Blue', team: '#2F6FE0', second: '#93C5FD', bg: '#0B1220', surface: '#121C2E', accent: '#3B82F6', accentText: '#7FB0FA', onAccent: DARK },
]

export function getTheme(id: string | null | undefined): Theme {
  return themes.find((t) => t.id === id) ?? getTheme(DEFAULT_THEME_ID)
}

export function loadThemeId(): string {
  try {
    return getTheme(localStorage.getItem(THEME_STORAGE_KEY)).id
  } catch {
    return DEFAULT_THEME_ID
  }
}

export function saveThemeId(id: string) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, id)
  } catch {
    // Storage can be blocked. The theme still applies for this visit.
  }
}

/** Sets data-theme and the CSS variables the Tailwind tokens read. */
export function applyTheme(id: string) {
  const theme = getTheme(id)
  const root = document.documentElement
  root.dataset.theme = theme.id
  root.style.setProperty('--bg', theme.bg)
  root.style.setProperty('--surface', theme.surface)
  root.style.setProperty('--team', theme.team)
  root.style.setProperty('--second', theme.second)
  root.style.setProperty('--accent', theme.accent)
  root.style.setProperty('--accent-text', theme.accentText)
  root.style.setProperty('--on-accent', theme.onAccent)
}
