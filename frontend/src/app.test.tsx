import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AskAnswer, Lap, PitStop, RaceResult, RaceSummary } from './api'
import App from './App'

const races: RaceSummary[] = [
  { id: 1, season: 2024, round: 1, name: 'Bahrain Grand Prix', date: '2024-03-02', circuit_ref: 'bahrain', openf1_session_key: 1, winner: null, has_sprint: false },
  {
    id: 2,
    season: 2025,
    round: 1,
    name: 'Australian Grand Prix',
    date: '2025-03-16',
    circuit_ref: 'albert_park',
    openf1_session_key: 10,
    winner: { driver_name: 'Lando Norris', driver_code: 'NOR', team: 'McLaren' },
    has_sprint: true,
  },
  { id: 3, season: 2025, round: 2, name: 'Chinese Grand Prix', date: '2025-03-23', circuit_ref: 'shanghai', openf1_session_key: null, winner: null, has_sprint: false },
]

function result(driver_id: number, code: string, team: string, position: number): RaceResult {
  return {
    driver_id,
    driver_code: code,
    driver_name: `Driver ${code}`,
    driver_number: driver_id,
    team,
    grid: position,
    position,
    position_text: String(position),
    status: 'Finished',
    points: 10,
  }
}

const results = [result(1, 'NOR', 'McLaren', 1), result(2, 'PIA', 'McLaren', 2), result(3, 'VER', 'Red Bull', 3)]

function lap(driver_id: number, lap_number: number, stint_number: number, tire_type: string): Lap {
  return {
    driver_id,
    lap_number,
    lap_time_seconds: 90 + lap_number,
    tire_type,
    tire_age: 1,
    stint_number,
    position: 1,
    is_pit_out_lap: false,
    is_deleted: false,
  }
}

const laps = [
  ...[1, 2, 3].map((n) => lap(1, n, 1, 'SOFT')),
  ...[4, 5].map((n) => lap(1, n, 2, 'HARD')),
  ...[1, 2, 3, 4, 5].map((n) => lap(2, n, 1, 'MEDIUM')),
  ...[1, 2, 3, 4, 5].map((n) => lap(3, n, 1, 'MEDIUM')),
]

const pitStops: PitStop[] = [{ driver_id: 1, lap_number: 3, lane_seconds: 21.5, stationary_seconds: null }]

interface Reply {
  status?: number
  body: unknown
}

/** A fake fetch: every API path is answered from the table, and nothing touches the network. */
function fakeApi(table: Record<string, Reply>) {
  const fetchMock = vi.fn(async (input: string | URL | Request) => {
    const url = new URL(String(input))
    const reply = table[url.pathname] ?? { status: 404, body: { detail: 'Race not found' } }
    const status = reply.status ?? 200
    return { ok: status < 400, status, json: async () => reply.body } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderApp(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

const seasonButton = () => screen.getByRole('button', { name: /Season/ })

describe('race list', () => {
  it('opens on the latest season with results, with a link only for races that have results', async () => {
    fakeApi({ '/races': { body: races } })

    renderApp('/')

    // The latest race is featured, and every round with a result links from the calendar.
    expect(await screen.findByRole('link', { name: 'Open race Australian Grand Prix' })).toHaveAttribute('href', '/races/2')
    expect(screen.getByRole('link', { name: 'Australian Grand Prix' })).toHaveAttribute('href', '/races/2')
    expect(screen.queryByRole('link', { name: 'Chinese Grand Prix' })).not.toBeInTheDocument()
    expect(screen.getByText('No result yet')).toBeInTheDocument()
    expect(screen.queryByText('Bahrain Grand Prix')).not.toBeInTheDocument()
    expect(seasonButton()).toHaveTextContent('2025')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('2025 season')
    expect(screen.getByText('1 of 2 rounds run · 1 winner')).toBeInTheDocument()
  })

  it('lists wins per driver', async () => {
    fakeApi({ '/races': { body: races } })

    renderApp('/')

    const wins = await screen.findByRole('list', { name: 'Wins this season' })
    expect(within(wins).getByText('Lando Norris')).toBeInTheDocument()
    expect(within(wins).getByText('1 win')).toBeInTheDocument()
  })

  it('copes with an API that leaves the winner field out', async () => {
    const old = races.map(({ winner: _winner, ...rest }) => rest)
    fakeApi({ '/races': { body: old } })

    renderApp('/')

    expect((await screen.findAllByRole('heading', { name: 'Australian Grand Prix' })).length).toBeGreaterThan(0)
    expect(screen.queryByText('Winner')).not.toBeInTheDocument()
  })

  it('draws a card without an outline for a circuit the dataset lacks', async () => {
    fakeApi({ '/races': { body: [{ ...races[1], circuit_ref: 'fuji', name: 'Japanese Grand Prix' }] } })

    renderApp('/')

    expect((await screen.findAllByRole('heading', { name: 'Japanese Grand Prix' })).length).toBeGreaterThan(0)
  })

  it('lists the seasons in the picker and switches season', async () => {
    fakeApi({ '/races': { body: races } })
    renderApp('/')
    await screen.findByRole('link', { name: 'Australian Grand Prix' })

    await userEvent.click(seasonButton())
    expect(within(screen.getByRole('listbox')).getAllByRole('option').map((o) => o.textContent)).toEqual(['2025', '2024'])
    await userEvent.click(screen.getByRole('option', { name: '2024' }))

    expect(screen.getAllByRole('heading', { name: 'Bahrain Grand Prix' }).length).toBeGreaterThan(0)
    expect(screen.queryByText('Australian Grand Prix')).not.toBeInTheDocument()
  })

  it('shows an error when the API cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))

    renderApp('/')

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load the races')
  })
})

describe('race detail', () => {
  const api = (extra: Record<string, Reply> = {}) =>
    fakeApi({
      '/races/2': { body: races[1] },
      '/races/2/results': { body: results },
      '/races/2/laps': { body: laps },
      '/races/2/pit-stops': { body: pitStops },
      ...extra,
    })
  const driverButton = (code: string) =>
    within(screen.getByRole('group', { name: 'Drivers to compare' })).getByRole('button', { name: new RegExp(`^${code},`) })

  it('shows the winner, pole and fastest lap, the classification, and the strategy chart with pit stops', async () => {
    api()

    renderApp('/races/2')

    expect(await screen.findByRole('heading', { name: /Australian Grand Prix/ })).toBeInTheDocument()
    const stats = (await screen.findByText('Fastest lap')).closest('dl')!
    expect(stats).toHaveTextContent('WinnerDriver NORMcLaren')
    expect(stats).toHaveTextContent('Fastest lap1:31.000Driver NOR, lap 1')
    const tower = await screen.findByRole('group', { name: 'Drivers to compare' })
    expect(within(tower).getAllByRole('button')).toHaveLength(3)

    const strategy = (await screen.findByRole('heading', { name: 'Race strategy' })).closest('section')!
    expect(within(strategy).getByRole('img', { name: 'NOR: Soft laps 1 to 3, Hard laps 4 to 5' })).toBeInTheDocument()
    expect(within(strategy).getAllByRole('img', { name: /: Medium laps 1 to 5$/ })).toHaveLength(2)
  })

  it('lists stints and stops in the table under the strategy chart, in finishing order', async () => {
    api()
    renderApp('/races/2')
    const strategy = (await screen.findByRole('heading', { name: 'Race strategy' })).closest('section')!

    const rows = within(within(strategy).getByRole('table', { hidden: true })).getAllByRole('row', { hidden: true })

    expect(rows.map((r) => r.textContent)).toEqual([
      'DriverTire stints (laps)Tire stopsPit lane passes',
      'NORSoft 1–3, Hard 4–5Lap 3None',
      'PIAMedium 1–5NoneNone',
      'VERMedium 1–5NoneNone',
    ])
  })

  it('compares the first two finishers, and a fourth pick replaces the oldest', async () => {
    api({ '/races/2/results': { body: [...results, result(4, 'HAM', 'Ferrari', 4)] } })
    renderApp('/races/2')
    await screen.findByRole('group', { name: 'Drivers to compare' })

    expect(driverButton('NOR')).toHaveAttribute('aria-pressed', 'true')
    expect(driverButton('VER')).toHaveAttribute('aria-pressed', 'false')
    await userEvent.click(driverButton('VER'))
    await userEvent.click(driverButton('HAM'))

    expect(driverButton('NOR')).toHaveAttribute('aria-pressed', 'false')
    expect(['PIA', 'VER', 'HAM'].map((c) => driverButton(c).getAttribute('aria-pressed'))).toEqual(['true', 'true', 'true'])
  })

  it('switches the classification to the sprint, and links the rounds either side', async () => {
    api({
      '/races/2/sprint-results': { body: [result(2, 'PIA', 'McLaren', 1)] },
      '/races': { body: [...races, { ...races[1], id: 4, round: 2, name: 'Japanese Grand Prix', circuit_ref: 'suzuka' }] },
    })
    renderApp('/races/2')
    const sessions = await screen.findByRole('group', { name: 'Session' })

    await userEvent.click(within(sessions).getByRole('button', { name: 'Sprint' }))
    expect(screen.getByRole('heading', { name: 'Sprint' })).toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Race classification' })).getByText('PIA')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Next race, Japanese Grand Prix' })[0]).toHaveAttribute('href', '/races/4')
  })

  it('switches the lap chart between the clean and raw views', async () => {
    api()
    renderApp('/races/2')
    const modes = await screen.findByRole('group', { name: 'Laps to show' })

    expect(within(modes).getByRole('button', { name: 'Clean' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(modes).getByRole('button', { name: 'Raw' }))

    expect(within(modes).getByRole('button', { name: 'Raw' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText(/Every timed lap as recorded/)).toBeInTheDocument()
  })

  it('shows results only, with a note, for a race without lap data', async () => {
    fakeApi({
      '/races/3': { body: races[2] },
      '/races/3/results': { body: results },
    })

    renderApp('/races/3')

    expect(await screen.findByText('Lap, tire and pit data start in 2023.')).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Race classification' })).toBeInTheDocument()
    expect(screen.queryByText('Race strategy')).not.toBeInTheDocument()
  })

  it('says so when a race has no results yet', async () => {
    fakeApi({ '/races/3': { body: races[2] }, '/races/3/results': { body: [] } })

    renderApp('/races/3')

    expect(await screen.findByText(/No results yet/)).toBeInTheDocument()
  })

  it('shows a friendly message for an unknown race', async () => {
    fakeApi({})

    renderApp('/races/999')

    expect(await screen.findByRole('heading', { name: 'Race not found' })).toBeInTheDocument()
  })
})

describe('ask the engineer', () => {
  const answer: AskAnswer = {
    answer: 'Norris won.\n- **Piastri** was second.',
    tools_used: [{ name: 'get_race_results', input: { season: 2025, race: 'british' } }],
  }

  it('shows the answer with its formatting and the tools used after clicking an example question', async () => {
    const fetchMock = fakeApi({ '/ask': { body: answer } })
    renderApp('/ask')

    await userEvent.click(screen.getByRole('button', { name: 'Who won the 2025 British Grand Prix?' }))

    expect(await screen.findByText(/Norris won\./)).toBeInTheDocument()
    expect(screen.getByText('Piastri').tagName).toBe('STRONG')
    const chips = screen.getByRole('list', { name: 'Tools used' })
    expect(within(chips).getByText('get_race_results')).toHaveAttribute('title', '{"season":2025,"race":"british"}')
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(JSON.parse(init.body as string)).toEqual({ question: 'Who won the 2025 British Grand Prix?', history: [] })
  })

  it('shows the API message for too many questions', async () => {
    fakeApi({ '/ask': { status: 429, body: { detail: 'Too many questions. Try again in a minute.' } } })
    renderApp('/ask')

    await userEvent.type(screen.getByLabelText('Your question'), 'Who won?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Too many questions. Try again in a minute.')
  })

  it('uses its own wording when a 504 has no message', async () => {
    fakeApi({ '/ask': { status: 504, body: {} } })
    renderApp('/ask')

    await userEvent.type(screen.getByLabelText('Your question'), 'Who won?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('took too long')
  })

  /** Answers /ask from the list in order, and records the body of every call. */
  function sequence(replies: Reply[]) {
    const bodies: { question: string; history: { question: string; answer: string }[] }[] = []
    let n = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        bodies.push(JSON.parse(init.body as string))
        const reply = replies[Math.min(n++, replies.length - 1)]
        const status = reply.status ?? 200
        return { ok: status < 400, status, json: async () => reply.body } as Response
      }),
    )
    return bodies
  }

  async function send(text: string, answered: string) {
    await userEvent.type(screen.getByLabelText('Your question'), text)
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByText(answered)
  }

  it('sends the earlier exchanges with each question, at most three, oldest first', async () => {
    const bodies = sequence([1, 2, 3, 4, 5].map((n) => ({ body: { answer: `Answer ${n}`, tools_used: [] } })))
    renderApp('/ask')

    for (const n of [1, 2, 3, 4, 5]) await send(`Question ${n}`, `Answer ${n}`)

    expect(bodies[0].history).toEqual([])
    expect(bodies[1].history).toEqual([{ question: 'Question 1', answer: 'Answer 1' }])
    expect(bodies[4].history.map((t) => t.question)).toEqual(['Question 2', 'Question 3', 'Question 4'])
    expect(bodies[4].question).toBe('Question 5')
  })

  it('does not send a failed exchange as history, and cuts long answers to 4000 characters', async () => {
    const bodies = sequence([
      { body: { answer: 'x'.repeat(5000), tools_used: [] } },
      { status: 504, body: {} },
      { body: { answer: 'Done', tools_used: [] } },
    ])
    renderApp('/ask')

    await send('First', 'x'.repeat(5000))
    await userEvent.type(screen.getByLabelText('Your question'), 'Second')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('alert')
    await send('Third', 'Done')

    expect(bodies[2].history).toEqual([{ question: 'First', answer: 'x'.repeat(4000) }])
  })

  it('shows a message instead of a blank answer', async () => {
    sequence([{ body: { answer: '', tools_used: [] } }])
    renderApp('/ask')

    await send('Who won?', 'No answer came back. Try asking again.')
  })

  it('clears the conversation with New conversation, which only shows once there is one', async () => {
    const bodies = sequence([{ body: { answer: 'Norris won.', tools_used: [] } }])
    renderApp('/ask')
    expect(screen.queryByRole('button', { name: 'New conversation' })).not.toBeInTheDocument()
    expect(screen.getByText(/remembers your last 3 questions/)).toBeInTheDocument()

    await send('Who won?', 'Norris won.')
    await userEvent.click(screen.getByRole('button', { name: 'New conversation' }))

    expect(screen.queryByText('Norris won.')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Who won the 2025 British Grand Prix?' })).toBeInTheDocument()
    await send('Again', 'Norris won.')
    expect(bodies[1].history).toEqual([])
  })

  it('saves chats in the browser, reopens one to continue it, and deletes one', async () => {
    const bodies = sequence([
      { body: { answer: 'Norris won.', tools_used: [] } },
      { body: { answer: 'Piastri was second.', tools_used: [] } },
      { body: { answer: 'From pole.', tools_used: [] } },
    ])
    const { unmount } = renderApp('/ask')
    await send('Who won?', 'Norris won.')
    await userEvent.click(screen.getByRole('button', { name: 'New conversation' }))
    await send('Who was second?', 'Piastri was second.')
    unmount()

    // A fresh visit lists both chats, newest first, and reopening one carries its history on.
    renderApp('/ask')
    const history = screen.getByRole('complementary', { name: 'Previous chats' })
    const chats = within(history).getAllByRole('button', { name: /question ·/ })
    expect(chats.map((c) => c.textContent?.split('1 question')[0])).toEqual(['Who was second?', 'Who won?'])
    await userEvent.click(chats[1])
    expect(screen.getByText('Norris won.')).toBeInTheDocument()
    await send('From where?', 'From pole.')
    expect(bodies[2].history).toEqual([{ question: 'Who won?', answer: 'Norris won.' }])

    await userEvent.click(within(history).getByRole('button', { name: 'Delete chat: Who was second?' }))
    expect(within(history).queryByText('Who was second?')).not.toBeInTheDocument()
    expect(within(history).getByText('2 questions', { exact: false })).toBeInTheDocument()
  })

  it('stops the question at 500 characters', () => {
    renderApp('/ask')

    expect(screen.getByLabelText('Your question')).toHaveAttribute('maxlength', '500')
  })
})
