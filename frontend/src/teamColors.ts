/**
 * Team colors for chart lines and marks, keyed by the team name stored in the database. They are
 * bright so a thin line reads on the dark panels, and they do not change with the theme.
 */
export const TEAM_COLORS: Record<string, string> = {
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

export const FALLBACK_TEAM_COLOR = '#9CA3AF'

export function teamColor(team: string): string {
  return TEAM_COLORS[team] ?? FALLBACK_TEAM_COLOR
}

/**
 * Deeper team colors for the large shaded areas: race cards and the race page header. Current teams
 * follow the 2026 team card artwork (as the themes do); earlier race winners have approximate livery
 * colors so every season's cards are colored by who won.
 */
export const TEAM_CARD_COLORS: Record<string, string> = {
  McLaren: '#E47818',
  Ferrari: '#B00025',
  'Red Bull': '#2B5AA0',
  Mercedes: '#14A893',
  'Aston Martin': '#187854',
  'Alpine F1 Team': '#0A78B0',
  Williams: '#1D4FB8',
  'RB F1 Team': '#1F3FC4',
  'Haas F1 Team': '#5E676D',
  Audi: '#BE2A0A',
  'Cadillac F1 Team': '#7A8488',
  Sauber: '#2E9E3E',
  'Alfa Romeo': '#9B1B30',
  AlphaTauri: '#2B4562',
  'Toro Rosso': '#2B3F8F',
  'Racing Point': '#D9729F',
  'Lotus F1': '#A8862A',
  Renault: '#D9AE00',
  Brawn: '#8DB82E',
  'BMW Sauber': '#2C5AA0',
  Honda: '#8A9096',
  Jordan: '#D4B000',
}

export const FALLBACK_CARD_COLOR = '#4B5563'

export function teamCardColor(team: string | null | undefined): string {
  return (team && TEAM_CARD_COLORS[team]) || FALLBACK_CARD_COLOR
}
