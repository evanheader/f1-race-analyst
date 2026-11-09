import { useEffect, useRef, useState } from 'react'
import { ApiError, MAX_HISTORY, MAX_HISTORY_ANSWER_LENGTH, MAX_QUESTION_LENGTH, ask } from '../api'
import type { AskAnswer, AskTurn } from '../api'
import Markdown from '../components/Markdown'

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
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div className="space-y-3">
        <h1 className="display">Ask the engineer</h1>
        <p className="max-w-prose text-muted">
          Ask about F1 results, laps, tires, pit stops and the championship. The engineer remembers your last{' '}
          {MAX_HISTORY} questions on this page. Reloading the page starts over.
        </p>
      </div>

      {log.length === 0 && (
        <div className="space-y-2">
          <p className="text-sm text-muted">Try one of these</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {EXAMPLES.map((q) => (
              <li key={q}>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => submit(q)}
                  className="panel lift h-full w-full p-4 text-left text-[0.9375rem] hover:border-line-strong"
                >
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div role="log" aria-label="Conversation" className="space-y-5">
        {log.map((x) => (
          <div key={x.id} className="space-y-4">
            <div className="ml-auto w-fit max-w-[90%] rounded-2xl rounded-br-md border border-white/10 bg-[color-mix(in_srgb,var(--team)_28%,var(--surface))] px-4 py-2.5 shadow-lg sm:max-w-[75%]">
              <span className="sr-only">You asked: </span>
              <p className="whitespace-pre-wrap break-words">{x.question}</p>
            </div>
            {x.result === undefined && (
              <p role="status" className="flex items-center gap-2.5 text-sm text-accent-text">
                <span aria-hidden="true" className="radio-pulse h-2 w-2 rounded-full bg-second" />
                The engineer is checking the data…
              </p>
            )}
            {x.result && 'error' in x.result && (
              <p role="alert" className="panel border-bad/40 p-4">
                {x.result.error}
              </p>
            )}
            {x.result && 'answer' in x.result && (
              <div className="panel max-w-[95%] p-4 sm:max-w-[88%] sm:p-5">
                <p aria-hidden="true" className="mb-2 flex items-center gap-2 text-[0.8125rem] font-semibold text-accent-text">
                  <span className="h-2 w-2 rounded-full bg-second" />
                  Race engineer
                </p>
                <span className="sr-only">The engineer answered: </span>
                {x.result.answer.answer.trim() === '' ? (
                  <p>{EMPTY_ANSWER}</p>
                ) : (
                  <Markdown source={x.result.answer.answer} />
                )}
                {x.result.answer.tools_used.length > 0 && (
                  <div className="mt-4 border-t border-line pt-3">
                    <ul aria-label="Tools used" className="flex flex-wrap gap-1.5">
                      {x.result.answer.tools_used.map((t, i) => (
                        <li
                          key={i}
                          title={JSON.stringify(t.input)}
                          className="rounded-full border border-line bg-white/[0.03] px-2.5 py-0.5 text-xs text-muted"
                        >
                          {t.name}
                        </li>
                      ))}
                    </ul>
                    <details className="mt-2 text-[0.8125rem] text-muted">
                      <summary className="cursor-pointer hover:text-ink">Tool inputs</summary>
                      <pre className="mt-2 overflow-x-auto rounded-lg bg-black/30 p-3 text-xs">
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
        className="panel sticky bottom-4 z-10 space-y-2 p-3 shadow-[0_24px_60px_-20px_rgb(0_0_0/0.9)]"
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
          className="w-full resize-none rounded-lg bg-transparent px-2 py-1.5 text-ink placeholder:text-muted focus-visible:outline-none"
        />
        <div className="flex items-center justify-between gap-3 px-1">
          <span className="num text-xs text-muted">
            {question.length}/{MAX_QUESTION_LENGTH}
          </span>
          <div className="flex gap-2">
            {log.length > 0 && (
              <button type="button" className="btn !min-h-9" disabled={pending} onClick={() => setLog([])}>
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
  )
}
