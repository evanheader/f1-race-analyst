import circuits from './data/circuits.json'

// Only the flags of countries that hosted a race are bundled, not the whole flag-icons set.
const flagFiles = import.meta.glob(
  '/node_modules/flag-icons/flags/4x3/{ae,at,au,az,be,bh,br,ca,cn,de,es,fr,gb,hu,in,it,jp,kr,mc,mx,my,nl,pt,qa,ru,sa,sg,tr,us}.svg',
  { eager: true, query: '?url', import: 'default' },
) as Record<string, string>

interface CircuitArt {
  /** ISO 3166-1 alpha-2, lowercase. */
  country: string
  /** An SVG path in a 0..100 box, or null when no outline is known. */
  path: string | null
}

const table: Record<string, CircuitArt> = circuits

export function circuitArt(circuitRef: string): CircuitArt | null {
  return table[circuitRef] ?? null
}

export function flagUrl(country: string): string | null {
  return flagFiles[`/node_modules/flag-icons/flags/4x3/${country}.svg`] ?? null
}
