function channel(hex: string, i: number): number {
  const c = parseInt(hex.slice(i, i + 2), 16) / 255
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  return 0.2126 * channel(hex, 1) + 0.7152 * channel(hex, 3) + 0.0722 * channel(hex, 5)
}

/** WCAG 2.x contrast ratio between two #RRGGBB colors. */
export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** Mixes a #RRGGBB color with black, as CSS color-mix(in srgb, color share, black) does. */
export function darken(hex: string, share: number): string {
  const part = (i: number) =>
    Math.round(parseInt(hex.slice(i, i + 2), 16) * share)
      .toString(16)
      .padStart(2, '0')
  return `#${part(1)}${part(3)}${part(5)}`.toUpperCase()
}
