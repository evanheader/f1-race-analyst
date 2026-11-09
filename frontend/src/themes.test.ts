import { describe, expect, it } from 'vitest'
import { contrast } from './contrast'
import { DEFAULT_THEME_ID, getTheme, themes } from './themes'

/** The page ink and muted colors in index.css. Every theme must keep them readable. */
const INK = '#EEF2F8'
const MUTED = '#9AA6BC'

describe('themes', () => {
  it('has 12 themes with unique ids, and Red Bull Racing is the default', () => {
    expect(themes).toHaveLength(12)
    expect(new Set(themes.map((t) => t.id)).size).toBe(12)
    expect(DEFAULT_THEME_ID).toBe('red-bull')
    expect(getTheme('no-such-theme').name).toBe('Red Bull Racing')
  })

  it('computes known contrast ratios correctly', () => {
    expect(contrast('#000000', '#FFFFFF')).toBeCloseTo(21, 5)
    expect(contrast('#FFFFFF', '#FFFFFF')).toBeCloseTo(1, 5)
  })

  it.each(themes.map((t) => [t.id, t] as const))('%s: text is readable on its own page and panels', (_id, t) => {
    for (const ground of [t.bg, t.surface]) {
      expect(contrast(INK, ground)).toBeGreaterThanOrEqual(4.5)
      expect(contrast(MUTED, ground)).toBeGreaterThanOrEqual(4.5)
      expect(contrast(t.accentText, ground)).toBeGreaterThanOrEqual(4.5)
    }
    expect(contrast(t.onAccent, t.accent)).toBeGreaterThanOrEqual(4.5)
  })

  it.each(themes.map((t) => [t.id, t] as const))('%s: the second livery color shows up on the page', (_id, t) => {
    expect(contrast(t.second, t.bg)).toBeGreaterThanOrEqual(3)
  })
})
