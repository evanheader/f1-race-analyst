import type { ReactNode } from 'react'
import { parseBlocks } from '../markdown'

/*
 * A small Markdown reader for the engineer's answers: paragraphs, bullet and numbered lists, headings,
 * **bold**, *italic* and `code`. It builds React elements from text and never sets HTML, so an answer
 * cannot inject markup. Anything else shows as the plain text it is.
 */

const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*\s][^*]*\*|_[^_\s][^_]*_)/g

function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (/^(\*\*|__).+\1$/.test(part)) return <strong key={i} className="font-semibold text-ink">{part.slice(2, -2)}</strong>
    if (/^`.+`$/.test(part)) return <code key={i} className="rounded bg-white/10 px-1 py-0.5 text-[0.875em]">{part.slice(1, -1)}</code>
    if (/^([*_]).+\1$/.test(part)) return <em key={i}>{part.slice(1, -1)}</em>
    return part
  })
}

export default function Markdown({ source }: { source: string }) {
  return (
    <div className="space-y-3 break-words">
      {parseBlocks(source).map((block, i) => {
        if (block.kind === 'h') return <p key={i} className="font-semibold text-ink">{inline(block.text)}</p>
        if (block.kind === 'p') {
          return (
            <p key={i}>
              {block.lines.map((line, j) => (
                <span key={j}>
                  {j > 0 && <br />}
                  {inline(line)}
                </span>
              ))}
            </p>
          )
        }
        const List = block.kind
        return (
          <List key={i} className={`space-y-1.5 pl-5 ${List === 'ul' ? 'list-disc' : 'list-decimal'} marker:text-muted`}>
            {block.items.map((item, j) => (
              <li key={j} className="pl-1">
                {inline(item)}
              </li>
            ))}
          </List>
        )
      })}
    </div>
  )
}
