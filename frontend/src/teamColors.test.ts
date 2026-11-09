import { describe, expect, it } from 'vitest'
import { contrast, darken } from './contrast'
import { FALLBACK_CARD_COLOR, TEAM_CARD_COLORS, teamCardColor } from './teamColors'

/** Card text sits on the darkest end of the gradient: the team color mixed with black, as in index.css. */
const CARD_TEXT_SHARE = 0.62

describe('team card colors', () => {
  it.each(Object.entries({ ...TEAM_CARD_COLORS, fallback: FALLBACK_CARD_COLOR }))(
    '%s: white text reads on the shaded card',
    (_team, color) => {
      expect(contrast('#FFFFFF', darken(color, CARD_TEXT_SHARE))).toBeGreaterThanOrEqual(4.5)
    },
  )

  it('falls back to grey for a team without a color, or no team at all', () => {
    expect(teamCardColor('Minardi')).toBe(FALLBACK_CARD_COLOR)
    expect(teamCardColor(null)).toBe(FALLBACK_CARD_COLOR)
    expect(teamCardColor('Ferrari')).toBe('#B00025')
  })
})
