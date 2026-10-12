import type { Check, Entry, Frontmatter, Level, RulesFile, SourceFile } from './types.ts'

export const ENTRY_ID = /\b([A-Z][A-Z0-9]*)-(\d{3})\b/g
const HEADING = /^### ([A-Z][A-Z0-9]*)-(\d{3}) \[(MUST|SHOULD|RETIRED)\] (\S.*)$/
const ENTRY_LIKE = /^### [A-Z][A-Z0-9]*-\d+\b/

const unquote = (value: string) => value.trim().replace(/^(['"])(.*)\1$/, '$2')

/** The frontmatter of a rules file. Only `paths:` is read; it is a YAML list, an inline list or a comma string. */
export function parseFrontmatter(text: string): Frontmatter {
  const lines = text.split('\n')
  if (lines[0]?.trim() !== '---') return { paths: undefined, otherKeys: [], isUnclosed: false, lines: 0 }
  const end = lines.findIndex((line, index) => index > 0 && line.trim() === '---')
  if (end === -1) return { paths: undefined, otherKeys: [], isUnclosed: true, lines: 0 }
  let paths: string[] | undefined
  const otherKeys: string[] = []
  let isInPaths = false
  for (const line of lines.slice(1, end)) {
    const key = /^([A-Za-z_][\w-]*):(.*)$/.exec(line)
    if (key !== null) {
      isInPaths = key[1] === 'paths'
      if (!isInPaths) otherKeys.push(key[1] ?? '')
      else {
        const inline = (key[2] ?? '').trim().replace(/^\[(.*)\]$/, '$1')
        paths = inline === '' ? [] : inline.split(',').map(unquote).filter(glob => glob !== '')
      }
    } else if (isInPaths) {
      const item = /^\s*-\s+(.+)$/.exec(line)
      if (item !== null) paths?.push(unquote(item[1] ?? ''))
    }
  }
  return { paths, otherKeys, isUnclosed: false, lines: end + 1 }
}

/**
 * The parts of a `Checked by:` value, split at `;`. Text in parentheses is a note, never a name:
 * `eslint \`a\`, \`b\` (see \`c\`); internal/guard_test.go; review` gives eslint [a, b], the path, review.
 */
export function parseCheckedBy(value: string): Check[] {
  return value
    .replace(/\([^)]*\)/g, '')
    .split(';')
    .map(part => part.trim())
    .filter(part => part !== '')
    .map(part => ({
      kind: (part.split(/\s/, 1)[0] ?? '').replace(/^`|[`:,.]+$/g, ''),
      names: [...part.matchAll(/`([^`]+)`/g)].map(match => match[1] ?? ''),
    }))
}

export const isReview = (check: Check) => check.kind === 'review'

/** One rules file. Fenced code blocks are skipped, so the grammar's own example is no entry. */
export function parseRulesFile(file: SourceFile): RulesFile {
  const entries: Entry[] = []
  const malformed: { line: number; text: string }[] = []
  let isFenced = false
  let open: { id: string; prefix: string; level: Level; title: string; line: number; body: string[] } | undefined
  const close = () => {
    if (open === undefined) return
    const body = open.body.join('\n').replace(/\s+$/, '')
    const checkedBy = /^- Checked by: ((?:.|\n {2,}\S)*)/m.exec(body)?.[1]?.replace(/\n\s+/g, ' ')
    entries.push({ ...open, file: file.path, body, checks: checkedBy === undefined ? [] : parseCheckedBy(checkedBy) })
    open = undefined
  }
  file.text.split('\n').forEach((line, index) => {
    if (line.trimStart().startsWith('```')) isFenced = !isFenced
    if (isFenced) {
      open?.body.push(line)
      return
    }
    if (!line.startsWith('#')) {
      open?.body.push(line)
      return
    }
    close()
    const heading = HEADING.exec(line)
    if (heading !== null) {
      const prefix = heading[1] ?? ''
      open = { id: `${prefix}-${heading[2] ?? ''}`, prefix, level: heading[3] as Level, title: heading[4] ?? '', line: index + 1, body: [] }
    } else if (ENTRY_LIKE.test(line)) malformed.push({ line: index + 1, text: line })
  })
  close()
  return { path: file.path, frontmatter: parseFrontmatter(file.text), entries, malformed }
}

/** The entry as it is written: its heading and everything under it. */
export function entryText(entry: Entry): string {
  const heading = `### ${entry.id} [${entry.level}] ${entry.title}`
  return entry.body.trim() === '' ? heading : `${heading}\n${entry.body.replace(/^\n+/, '\n')}`
}
