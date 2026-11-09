import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { ApiError, MAX_HISTORY, MAX_HISTORY_ANSWER_LENGTH, MAX_QUESTION_LENGTH, ask } from '../api'
import type { AskAnswer, AskTurn } from '../api'
import Markdown from '../components/Markdown'
import { loadChats, saveChats, upsertChat, type SavedChat } from '../chatHistory'

const EXAMPLES = [
  'Who won the 2025 British Grand Prix?',
  'How many pit stops did Hamilton make at Silverstone in 2025, and what tires did he use?',
  'Who was leading the 2025 British Grand Prix at the end of lap 30?',
  'When did Norris take the championship lead in 2025?',
]

interface Exchange {
  id: number
  question: string
  result?: { answer: AskAnswer } | { error: string }
}

const FALLBACK_MESSAGES: Record<number, string> = {
  422: `That question can't be sent. Keep it to ${MAX_QUESTION_LENGTH} characters.`,
  429: 'Too many questions. Try again in a minute.',
  502: 'The engineer is unavailable right now. Try again in a moment.',
  503: 'The engineer is not available right now.',
  504: 'The engineer took too long to answer. Try a simpler question.',
}

const EMPTY_ANSWER = 'No answer came back. Try asking again.'

/** The last few completed exchanges, oldest first. Failed ones are left out, and long answers are cut to what the API accepts. */
function recentHistory(log: Exchange[]): AskTurn[] {
  return log
    .flatMap((x) => (x.result && 'answer' in x.result ? [{ question: x.question, answer: x.result.answer.answer }] : []))
    .filter((turn) => turn.answer.trim() !== '')
    .slice(-MAX_HISTORY)
    .map((turn) => ({ ...turn, answer: turn.answer.slice(0, MAX_HISTORY_ANSWER_LENGTH) }))
}

/** Friendly text for a failed question. The API's own message wins when it sent one. */
function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.detail ?? FALLBACK_MESSAGES[error.status] ?? 'Something went wrong. Try again in a moment.'
  }
  return 'Could not reach the API. Check that it is running, then try again.'
}

export default function AskPage() {
  const [question, setQuestion] = useState('')
  const [log, setLog] = useState<Exchange[]>([])
  const [pending, setPending] = useState(false)
  const nextId = useRef(1)
  const bottom = useRef<HTMLDivElement>(null)
  // Earlier chats saved in this browser, and the one on screen (null until its first answer).
  const [chats, setChats] = useState<SavedChat[]>(loadChats)
  const [chatId, setChatId] = useState<string | null>(null)

  function storeChats(next: SavedChat[]) {
    saveChats(next)
    setChats(next)
  }

  function newConversation() {
    setLog([])
    setChatId(null)
  }

  function openChat(chat: SavedChat) {
    setLog(chat.exchanges.map((x) => ({ id: nextId.current++, question: x.question, result: x.result })))
    setChatId(chat.id)
  }

  function deleteChat(id: string) {
    storeChats(chats.filter((c) => c.id !== id))
    if (id === chatId) newConversation()
  }

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'nearest' })
  }, [log, pending])

  async function submit(text: string) {
    const trimmed = text.trim()
    if (!trimmed || pending) return
    const id = nextId.current++
    setLog((l) => [...l, { id, question: trimmed }])
    setQuestion('')
    setPending(true)
    let result: Exchange['result']
    try {
      result = { answer: await ask(trimmed, recentHistory(log)) }
    } catch (error) {
      result = { error: errorMessage(error) }
    }
    setLog((l) => l.map((x) => (x.id === id ? { ...x, result } : x)))
    setPending(false)
    // Save the chat so far, including this exchange.
    const saveId = chatId ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const exchanges = [
      ...log.flatMap((x) => (x.result ? [{ question: x.question, result: x.result }] : [])),
      { question: trimmed, result },
    ]
    setChatId(saveId)
    storeChats(upsertChat(loadChats(), { id: saveId, updatedAt: Date.now(), exchanges }))
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-16 lg:grid-cols-[minmax(0,1fr)_18rem] lg:gap-14">
    <div className="min-w-0 max-w-3xl space-y-12">
      <div className="space-y-5">
        <p className="rise eyebrow flex items-center gap-2">
          <span aria-hidden="true" className="h-2 w-2 rounded-full bg-accent" />
          Team radio
        </p>
        <h1 className="rise display !text-[clamp(3rem,10vw,6.5rem)]" style={{ '--i': 1 } as CSSProperties}>
          Ask the engineer
        </h1>
        <p className="rise max-w-prose text-muted" style={{ '--i': 2 } as CSSProperties}>
          Ask about F1 results, laps, tires, pit stops and the championship. The engineer remembers your last{' '}
          {MAX_HISTORY} questions in a chat, and every chat is saved in this browser.
        </p>
      </div>

      {log.length === 0 && (
        <div className="rise" style={{ '--i': 3 } as CSSProperties}>
          <p className="eyebrow">Try one of these</p>
          <ul className="mt-3 border-t border-line">
            {EXAMPLES.map((q) => (
              <li key={q}>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => submit(q)}
                  className="group flex w-full items-center justify-between gap-4 border-b border-line py-3.5 text-left text-[0.9375rem] transition-colors hover:text-ink disabled:opacity-45"
                >
                  {q}
                  <span aria-hidden="true" className="text-muted transition-transform duration-200 group-hover:translate-x-1 group-hover:text-accent">→</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div role="log" aria-label="Conversation" className="space-y-8">
        {log.map((x) => (
          <div key={x.id} className="space-y-5">
            <div>
              <p aria-hidden="true" className="eyebrow">You</p>
              <span className="sr-only">You asked: </span>
              <p className="mt-2 whitespace-pre-wrap break-words text-lg">{x.question}</p>
            </div>
            {x.result === undefined && (
              <p role="status" className="eyebrow flex items-center gap-2.5 !text-accent">
                <span aria-hidden="true" className="radio-pulse h-2 w-2 rounded-full bg-accent" />
                The engineer is checking the data…
              </p>
            )}
            {x.result && 'error' in x.result && (
              <p role="alert" className="border-l-2 border-accent bg-surface p-4">
                {x.result.error}
              </p>
            )}
            {x.result && 'answer' in x.result && (
              <div className="border-l border-line-strong pl-5">
                <p aria-hidden="true" className="eyebrow mb-3 flex items-center gap-2 !text-accent">
                  <span className="h-2 w-2 rounded-full bg-accent" />
                  Engineer
                </p>
                <span className="sr-only">The engineer answered: </span>
                {x.result.answer.answer.trim() === '' ? (
                  <p>{EMPTY_ANSWER}</p>
                ) : (
                  <Markdown source={x.result.answer.answer} />
                )}
                {x.result.answer.tools_used.length > 0 && (
                  <div className="mt-5">
                    <ul aria-label="Tools used" className="flex flex-wrap gap-1.5">
                      {x.result.answer.tools_used.map((t, i) => (
                        <li
                          key={i}
                          title={JSON.stringify(t.input)}
                          className="num rounded-[2px] border border-line-strong px-2 py-1 text-xs text-muted"
                        >
                          {t.name}
                        </li>
                      ))}
                    </ul>
                    <details className="mt-3 text-[0.8125rem] text-muted">
                      <summary className="eyebrow cursor-pointer hover:!text-ink">Tool inputs</summary>
                      <pre className="num mt-2 overflow-x-auto bg-surface p-3 text-xs">
                        {x.result.answer.tools_used
                          .map((t) => `${t.name} ${JSON.stringify(t.input)}`)
                          .join('\n')}
                      </pre>
                    </details>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit(question)
        }}
        className="sticky bottom-4 z-10 space-y-2 border border-line-strong bg-surface p-3 focus-within:border-ink shadow-[0_24px_60px_-24px_rgb(0_0_0/0.45)]"
      >
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <textarea
          id="question"
          value={question}
          maxLength={MAX_QUESTION_LENGTH}
          rows={2}
          placeholder="Ask the engineer about a race, a driver or a season"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit(question)
            }
          }}
          className="w-full resize-none bg-transparent px-2 py-1.5 text-ink placeholder:text-muted focus-visible:outline-none"
        />
        <div className="flex items-center justify-between gap-3 px-1">
          <span className="num text-xs text-muted">
            {question.length}/{MAX_QUESTION_LENGTH}
          </span>
          <div className="flex gap-2">
            {log.length > 0 && (
              <button type="button" className="btn !min-h-9" disabled={pending} onClick={newConversation}>
                New conversation
              </button>
            )}
            <button type="submit" disabled={pending || !question.trim()} className="btn btn-primary !min-h-9 !px-5">
              Ask
            </button>
          </div>
        </div>
      </form>
    </div>

    <aside aria-labelledby="history-heading" className="lg:sticky lg:top-24 lg:self-start">
      <h2 id="history-heading" className="eyebrow">
        Previous chats
      </h2>
      {chats.length === 0 ? (
        <p className="mt-3 text-sm text-muted">Your chats are saved in this browser and listed here.</p>
      ) : (
        <ul className="mt-3 border-t border-line">
          {chats.map((c) => {
            const first = c.exchanges[0]?.question ?? 'Chat'
            const active = c.id === chatId
            const when = new Date(c.updatedAt).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
            return (
              <li key={c.id} className="flex items-stretch border-b border-line">
                <button
                  type="button"
                  aria-current={active ? 'true' : undefined}
                  disabled={pending}
                  onClick={() => openChat(c)}
                  className={`min-w-0 flex-1 px-3 py-3 text-left transition-colors hover:bg-surface disabled:opacity-45 ${
                    active ? 'bg-surface shadow-[inset_3px_0_0_var(--accent)]' : ''
                  }`}
                >
                  <span className="line-clamp-2 text-sm font-medium">{first}</span>
                  <span className="num mt-1 block text-xs text-muted">
                    {c.exchanges.length} {c.exchanges.length === 1 ? 'question' : 'questions'} · {when}
                  </span>
                </button>
                <button
                  type="button"
                  aria-label={`Delete chat: ${first}`}
                  disabled={pending}
                  onClick={() => deleteChat(c.id)}
                  className="px-3 text-lg leading-none text-muted transition-colors hover:text-accent disabled:opacity-45"
                >
                  ×
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </aside>
    </div>
  )
}
