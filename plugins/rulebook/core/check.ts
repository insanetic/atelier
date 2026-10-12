import { ENTRY_ID, isReview, parseRulesFile } from './parse.ts'
import type { Entry, Issue, RulesFile, SourceFile } from './types.ts'

const LINE_ORDER = ['Good', 'Bad', 'Checked by', 'Waiver', 'Why']
const LABEL = /^- (Good|Bad|Checked by|Waiver|Why):/gm
/** A check named by its file: `internal/guard_test.go`, `src/mocks/rbac.spec.ts`, `.github/workflows/ci.yml`. */
const FILE_PATH = /^\.?[\w@+-][\w.@+-]*(?:\/[\w.@+-]+)+\.[A-Za-z]\w*$/

export interface Catalog {
  readonly files: readonly RulesFile[]
  readonly entries: readonly Entry[]
}

export function loadCatalog(files: readonly SourceFile[]): Catalog {
  const parsed = [...files].sort((a, b) => a.path.localeCompare(b.path)).map(parseRulesFile)
  return { files: parsed, entries: parsed.flatMap(file => file.entries) }
}

/** The files the catalog names as checks, for the caller to look up: a path that is gone checks nothing. */
export function checkFiles(catalog: Catalog): string[] {
  const paths = catalog.entries
    .filter(entry => entry.level !== 'RETIRED')
    .flatMap(entry => entry.checks.flatMap(check => [check.kind, ...check.names]))
    .filter(name => FILE_PATH.test(name))
  return [...new Set(paths)].sort()
}

function structure(catalog: Catalog): Issue[] {
  const issues: Issue[] = []
  for (const file of catalog.files) {
    const { frontmatter } = file
    if (frontmatter.isUnclosed) issues.push({ file: file.path, line: 1, message: 'the frontmatter has no closing `---`, so the file loads in every session; close it' })
    if (frontmatter.otherKeys.length > 0)
      issues.push({ file: file.path, line: 1, message: `the frontmatter holds ${frontmatter.otherKeys.map(key => `\`${key}:\``).join(', ')}; only \`paths:\` is read, remove the rest` })
    if (frontmatter.paths?.length === 0) issues.push({ file: file.path, line: 1, message: '`paths:` is empty; list the globs or remove the frontmatter' })
    for (const heading of file.malformed)
      issues.push({ file: file.path, line: heading.line, message: 'an entry heading reads `### <AREA>-<nnn> [MUST|SHOULD|RETIRED] <rule>`, the number three digits' })
  }
  const first = new Map<string, Entry>()
  for (const entry of catalog.entries) {
    const earlier = first.get(entry.id)
    if (earlier === undefined) first.set(entry.id, entry)
    else issues.push({ file: entry.file, line: entry.line, id: entry.id, message: `the ID is already used at ${earlier.file}:${earlier.line}; take the next free number (\`rulebook next ${entry.prefix}\`)` })
  }
  return issues
}

function grammar(entry: Entry, missing: ReadonlySet<string>): Issue[] {
  if (entry.level === 'RETIRED') return []
  const at = { file: entry.file, line: entry.line, id: entry.id }
  const issues: Issue[] = []
  if (entry.checks.length === 0) issues.push({ ...at, message: 'add a `- Checked by:` line that names the check, or `review`' })
  else if (entry.checks.every(isReview) && !/^- (?:Good|Bad):/m.test(entry.body))
    issues.push({ ...at, message: 'an entry checked only by review needs a `- Good:` or a `- Bad:` line' })
  const order = [...entry.body.matchAll(LABEL)].map(match => LINE_ORDER.indexOf(match[1] ?? ''))
  if (order.some((position, index) => index > 0 && position < (order[index - 1] ?? 0)))
    issues.push({ ...at, message: 'the lines come in the order Good, Bad, Checked by, Waiver, Why' })
  if (entry.level === 'SHOULD' && !/\bOutweighed\b/.test(entry.body))
    issues.push({ ...at, message: 'a SHOULD says what can outweigh it, in a sentence that starts with `Outweighed`' })
  for (const name of entry.checks.flatMap(check => [check.kind, ...check.names]))
    if (missing.has(name)) issues.push({ ...at, message: `\`Checked by:\` names ${name}, which does not exist; name the check that enforces the entry, or \`review\`` })
  return issues
}

function citations(catalog: Catalog, sources: readonly SourceFile[]): Issue[] {
  const byId = new Map(catalog.entries.map(entry => [entry.id, entry]))
  const prefixes = new Set(catalog.entries.map(entry => entry.prefix))
  const retiredLines = new Set(catalog.entries.filter(entry => entry.level === 'RETIRED').map(entry => `${entry.file}:${entry.line}`))
  // A heading the grammar refuses is reported once, as a heading.
  const malformed = new Set(catalog.files.flatMap(file => file.malformed.map(heading => `${file.path}:${heading.line}`)))
  const issues: Issue[] = []
  for (const source of sources) {
    let isFenced = false
    source.text.split('\n').forEach((line, index) => {
      if (line.trimStart().startsWith('```')) isFenced = !isFenced
      // An example entry inside a fence defines nothing and cites nothing.
      if (isFenced && /^\s*### /.test(line)) return
      if (malformed.has(`${source.path}:${index + 1}`)) return
      const isRetiredHeading = retiredLines.has(`${source.path}:${index + 1}`)
      for (const match of line.matchAll(ENTRY_ID)) {
        const id = match[0]
        if (!prefixes.has(match[1] ?? '')) continue
        const cited = byId.get(id)
        if (cited === undefined) issues.push({ file: source.path, line: index + 1, message: `cites ${id}, which is no entry; cite an existing ID` })
        else if (cited.level === 'RETIRED' && !isRetiredHeading) issues.push({ file: source.path, line: index + 1, message: `cites ${id}, which is retired (${cited.title}); cite its replacement or drop the citation` })
      }
    })
  }
  return issues
}

/**
 * Everything a machine can decide about a catalog. `citing` are the other files that cite entries (skills,
 * CLAUDE.md, AGENTS.md); `missing` are the paths of `checkFiles` that do not exist.
 */
export function check(files: readonly SourceFile[], citing: readonly SourceFile[] = [], missing: ReadonlySet<string> = new Set()): Issue[] {
  const catalog = loadCatalog(files)
  const issues = [...structure(catalog), ...catalog.entries.flatMap(entry => grammar(entry, missing)), ...citations(catalog, [...files, ...citing])]
  return issues.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line)
}

export function renderIssues(issues: readonly Issue[]): string {
  return issues.map(issue => `${issue.file}:${issue.line} ${issue.id === undefined ? '' : `${issue.id}: `}${issue.message}`).join('\n')
}
