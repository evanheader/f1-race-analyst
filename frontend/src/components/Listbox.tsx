import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

export interface ListboxOption {
  value: string
  /** Plain text: the accessible name, and what type-ahead matches. */
  label: string
  /** What to draw in the row and in the button, when it is more than the label. */
  content?: ReactNode
}

interface Props {
  label: string
  options: ListboxOption[]
  value: string
  onChange: (value: string) => void
  /** Open the popup toward the left on wide screens, for a control at the right edge of the page. */
  alignEnd?: boolean
}

/** Rows shown before the list scrolls. */
const VISIBLE_ROWS = 5

/** A select that shows about five rows at a time. Follows the WAI-ARIA collapsible listbox pattern. */
export default function Listbox({ label, options, value, onChange, alignEnd = false }: Props) {
  const base = useId()
  const labelId = `${base}-label`
  const buttonId = `${base}-button`
  const listId = `${base}-list`
  const optionId = (i: number) => `${base}-option-${i}`

  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLUListElement>(null)

  const selectedIndex = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  )
  const current = options[selectedIndex]

  function show() {
    setActive(selectedIndex)
    setOpen(true)
  }

  function close(returnFocus: boolean) {
    setOpen(false)
    if (returnFocus) button.current?.focus()
  }

  function choose(index: number) {
    if (options[index].value !== value) onChange(options[index].value)
    close(true)
  }

  // Focus moves into the list when it opens, so the keys act on it.
  useEffect(() => {
    if (open) list.current?.focus()
  }, [open])

  // Keep the active row visible. The selected row is the active one when the list opens.
  useEffect(() => {
    if (open) document.getElementById(`${base}-option-${active}`)?.scrollIntoView?.({ block: 'nearest' })
  }, [open, active, base])

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [open])

  function onButtonKeyDown(e: KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      show()
    }
  }

  function onListKeyDown(e: KeyboardEvent) {
    const last = options.length - 1
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActive((i) => Math.min(i + 1, last))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActive((i) => Math.max(i - 1, 0))
        break
      case 'Home':
        e.preventDefault()
        setActive(0)
        break
      case 'End':
        e.preventDefault()
        setActive(last)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        choose(active)
        break
      case 'Escape':
        e.preventDefault()
        close(true)
        break
      case 'Tab':
        // Focus goes back to the button first, so Tab moves on from there.
        close(true)
        break
      default:
        if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
          const letter = e.key.toLowerCase()
          // Start after the active row, so repeating a letter cycles through the matches.
          const order = [...options.keys()].map((_, n) => (active + 1 + n) % options.length)
          const match = order.find((i) => options[i].label.toLowerCase().startsWith(letter))
          if (match !== undefined) setActive(match)
        }
    }
  }

  return (
    <div ref={root} className="relative flex items-center gap-2">
      <span id={labelId} className="text-sm text-muted">
        {label}
      </span>
      <button
        ref={button}
        id={buttonId}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-labelledby={`${labelId} ${buttonId}`}
        onClick={() => (open ? close(false) : show())}
        onKeyDown={onButtonKeyDown}
        className="btn min-w-[7rem] !justify-between !gap-3 !px-3"
      >
        <span className="flex items-center gap-2">{current.content ?? current.label}</span>
        <svg aria-hidden="true" viewBox="0 0 10 6" className="h-1.5 w-2.5 text-muted">
          <path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </button>
      {open && (
        <ul
          ref={list}
          id={listId}
          role="listbox"
          tabIndex={-1}
          aria-labelledby={labelId}
          aria-activedescendant={optionId(active)}
          onKeyDown={onListKeyDown}
          className={`listbox absolute top-full z-40 mt-2 min-w-full overflow-y-auto rounded-xl border border-line-strong bg-raised p-1 shadow-[0_24px_48px_-12px_rgb(0_0_0/0.8)] ${
            alignEnd ? 'left-0 sm:left-auto sm:right-0' : 'left-0'
          }`}
          style={{ maxHeight: `${VISIBLE_ROWS * 2.25 + 0.5}rem` }}
        >
          {options.map((o, i) => (
            <li
              key={o.value}
              id={optionId(i)}
              role="option"
              aria-selected={o.value === value}
              onClick={() => choose(i)}
              onPointerMove={() => active !== i && setActive(i)}
              className={`flex h-9 cursor-pointer items-center gap-2.5 whitespace-nowrap rounded-lg px-2.5 text-sm ${
                i === active ? 'bg-white/10' : ''
              } ${o.value === value ? 'font-semibold' : ''}`}
            >
              {o.content ?? o.label}
              {o.value === value && (
                <svg aria-hidden="true" viewBox="0 0 12 10" className="ml-auto h-2.5 w-3 pl-1 text-accent-text">
                  <path d="M1 5l3.5 3.5L11 1" fill="none" stroke="currentColor" strokeWidth="1.8" />
                </svg>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
