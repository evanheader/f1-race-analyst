/**
 * Team colors for chart lines and marks, keyed by the team name stored in the database. They are
 * bright so a thin line reads on the dark panels, and they do not change with the theme.
 */
const TEAM_COLORS: Record<string, string> = {
  McLaren: '#FF8000',
  Ferrari: '#E80020',
  'Red Bull': '#3671C6',
  Mercedes: '#27F4D2',
  'Aston Martin': '#229971',
  'Alpine F1 Team': '#0090FF',
  Williams: '#64C4FF',
  'RB F1 Team': '#6692FF',
  AlphaTauri: '#5E8FAA',
  'Haas F1 Team': '#B6BABD',
  Audi: '#F50537',
  Sauber: '#52E252',
  'Alfa Romeo': '#C92D4B',
  'Cadillac F1 Team': '#E8E8E8',
}

const FALLBACK_TEAM_COLOR = '#9CA3AF'

export function teamColor(team: string): string {
  return TEAM_COLORS[team] ?? FALLBACK_TEAM_COLOR
}
