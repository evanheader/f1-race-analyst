import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import Listbox from './Listbox'

const options = ['2025', '2024', '2023', '2022', '2021', '2020', '2019'].map((y) => ({ value: y, label: y }))

function Harness() {
  const [value, setValue] = useState('2024')
  return <Listbox label="Season" options={options} value={value} onChange={setValue} />
}

const button = () => screen.getByRole('button', { name: /Season/ })

describe('Listbox', () => {
  it('shows the current value and opens on click with the selected option active', async () => {
    render(<Harness />)

    expect(button()).toHaveTextContent('2024')
    expect(button()).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(button())

    expect(button()).toHaveAttribute('aria-expanded', 'true')
    const list = screen.getByRole('listbox', { name: 'Season' })
    expect(list).toHaveFocus()
    expect(list).toHaveAttribute('aria-activedescendant', screen.getByRole('option', { name: '2024' }).id)
    expect(screen.getByRole('option', { name: '2024' })).toHaveAttribute('aria-selected', 'true')
  })

  it('opens from the button with ArrowDown', async () => {
    render(<Harness />)
    button().focus()

    await userEvent.keyboard('{ArrowDown}')

    expect(screen.getByRole('listbox')).toBeInTheDocument()
  })

  it('moves with the arrow keys, Home and End without selecting', async () => {
    render(<Harness />)
    await userEvent.click(button())
    const list = screen.getByRole('listbox')
    const active = () => document.getElementById(list.getAttribute('aria-activedescendant')!)

    await userEvent.keyboard('{ArrowDown}')
    expect(active()).toHaveTextContent('2023')
    await userEvent.keyboard('{ArrowUp}{ArrowUp}')
    expect(active()).toHaveTextContent('2025')
    await userEvent.keyboard('{ArrowUp}')
    expect(active()).toHaveTextContent('2025')
    await userEvent.keyboard('{End}')
    expect(active()).toHaveTextContent('2019')
    await userEvent.keyboard('{Home}')
    expect(active()).toHaveTextContent('2025')
    expect(button()).toHaveTextContent('2024')
  })

  it.each(['{Enter}', ' '])('selects the active option with %j, closes and returns focus to the button', async (key) => {
    render(<Harness />)
    await userEvent.click(button())

    await userEvent.keyboard(`{ArrowDown}${key}`)

    expect(button()).toHaveTextContent('2023')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(button()).toHaveFocus()
  })

  it('closes on Escape without changing the value, and returns focus to the button', async () => {
    render(<Harness />)
    await userEvent.click(button())

    await userEvent.keyboard('{ArrowDown}{Escape}')

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(button()).toHaveTextContent('2024')
    expect(button()).toHaveFocus()
  })

  it('closes on Tab', async () => {
    render(<Harness />)
    await userEvent.click(button())

    await userEvent.tab()

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('closes when the page outside is clicked', async () => {
    render(
      <>
        <p>Elsewhere</p>
        <Harness />
      </>,
    )
    await userEvent.click(button())

    await userEvent.click(screen.getByText('Elsewhere'))

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('jumps by first character, and cycles when the character repeats', async () => {
    const named = ['Ferrari', 'Haas', 'Mercedes', 'McLaren'].map((n) => ({ value: n, label: n }))
    render(<Listbox label="Team" options={named} value="Ferrari" onChange={() => {}} />)
    await userEvent.click(screen.getByRole('button', { name: /Team/ }))
    const list = screen.getByRole('listbox')
    const active = () => document.getElementById(list.getAttribute('aria-activedescendant')!)

    await userEvent.keyboard('m')
    expect(active()).toHaveTextContent('Mercedes')
    await userEvent.keyboard('m')
    expect(active()).toHaveTextContent('McLaren')
    await userEvent.keyboard('m')
    expect(active()).toHaveTextContent('Mercedes')
  })

  it('selects an option by click', async () => {
    render(<Harness />)
    await userEvent.click(button())

    await userEvent.click(screen.getByRole('option', { name: '2021' }))

    expect(button()).toHaveTextContent('2021')
  })
})
