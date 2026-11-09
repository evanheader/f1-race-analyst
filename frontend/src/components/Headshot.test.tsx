import { fireEvent, render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Headshot from './Headshot'

describe('headshot', () => {
  it('shows the face-cropped photo for a driver on the 2026 grid', () => {
    const { container } = render(<Headshot name="Nico Hülkenberg" team="Audi" />)
    expect(container.querySelector('img')?.getAttribute('src')).toMatch(/c_thumb,g_face.*\/audi\/nichul01\//)
  })

  it('draws the illustration for a driver without a photo, or when the photo fails', () => {
    const { container } = render(<Headshot name="Michael Schumacher" team="Ferrari" />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.querySelector('svg')).not.toBeNull()

    const { container: broken } = render(<Headshot name="Lando Norris" team="McLaren" />)
    fireEvent.error(broken.querySelector('img')!)
    expect(broken.querySelector('img')).toBeNull()
    expect(broken.querySelector('svg')).not.toBeNull()
  })
})
