/** The blocks of a Markdown answer: paragraphs, headings and lists. Inline marks are read by the Markdown component. */
export type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'h'; text: string }
  | { kind: 'ul' | 'ol'; items: string[] }

const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/
const HEADING = /^\s*#{1,6}\s+(.*)$/

export function parseBlocks(source: string): Block[] {
  const blocks: Block[] = []
  for (const line of source.replace(/\r\n/g, '\n').split('\n')) {
    const last = blocks.at(-1)
    const bullet = BULLET.exec(line)
    const numbered = NUMBERED.exec(line)
    const heading = HEADING.exec(line)
    if (line.trim() === '') {
      blocks.push({ kind: 'p', lines: [] })
    } else if (bullet || numbered) {
      const kind = bullet ? 'ul' : 'ol'
      const item = (bullet ?? numbered)![1]
      if (last?.kind === kind) last.items.push(item)
      else blocks.push({ kind, items: [item] })
    } else if (heading) {
      blocks.push({ kind: 'h', text: heading[1] })
    } else if (last?.kind === 'p') {
      last.lines.push(line)
    } else {
      blocks.push({ kind: 'p', lines: [line] })
    }
  }
  return blocks.filter((b) => b.kind !== 'p' || b.lines.length > 0)
}
