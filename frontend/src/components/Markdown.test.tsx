import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { parseBlocks } from '../markdown'
import Markdown from './Markdown'

describe('parseBlocks', () => {
  it('splits paragraphs on blank lines and groups list items', () => {
    const source = 'Copy. Verstappen won.\n\n- **Early:** P3\n- Late: P1\n\n1. One\n2. Two\nAfter'

    expect(parseBlocks(source)).toEqual([
      { kind: 'p', lines: ['Copy. Verstappen won.'] },
      { kind: 'ul', items: ['**Early:** P3', 'Late: P1'] },
      { kind: 'ol', items: ['One', 'Two'] },
      { kind: 'p', lines: ['After'] },
    ])
  })
})

describe('Markdown', () => {
  it('renders bold, lists and line breaks without showing the asterisks', () => {
    const { container } = render(<Markdown source={'Copy.\n- **Low point:** 104 points behind\n- Recovery'} />)

    expect(screen.getByText('Low point:').tagName).toBe('STRONG')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(container.textContent).not.toContain('**')
  })

  it('shows markup in an answer as text, never as HTML', () => {
    const { container } = render(<Markdown source={'<img src=x onerror=alert(1)> **bold**'} />)

    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('<img src=x onerror=alert(1)>')
  })
})
