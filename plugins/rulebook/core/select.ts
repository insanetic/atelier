import type { Catalog } from './check.ts'
import { matchesGlob } from './glob.ts'
import { entryText, isReview } from './parse.ts'
import type { Entry } from './types.ts'

export interface Applied {
  readonly file: string
  /** `always` for a file without `paths:`, else the first glob that matched and the changed file it matched. */
  readonly because: string
}

export interface Selection {
  readonly applied: readonly Applied[]
  /** The live entries of those files that review checks, alone or beside a machine check. */
  readonly review: readonly Entry[]
  /** How many live entries of those files a machine checks in full. */
  readonly machineOnly: number
}

/** The rule files that govern `changed` (root-relative paths) and the entries only a reviewer can judge. */
export function rulesFor(catalog: Catalog, changed: readonly string[]): Selection {
  const applied: Applied[] = []
  for (const file of catalog.files) {
    const { paths } = file.frontmatter
    if (paths === undefined) applied.push({ file: file.path, because: 'always' })
    else {
      const hit = paths.flatMap(glob => changed.filter(path => matchesGlob(path, glob)).map(path => `${glob} matches ${path}`))[0]
      if (hit !== undefined) applied.push({ file: file.path, because: hit })
    }
  }
  const files = new Set(applied.map(item => item.file))
  const live = catalog.entries.filter(entry => files.has(entry.file) && entry.level !== 'RETIRED')
  const review = live.filter(entry => entry.checks.length === 0 || entry.checks.some(isReview))
  return { applied, review, machineOnly: live.length - review.length }
}

export function renderSelection(selection: Selection, isIdsOnly: boolean): string {
  const head = [
    `Rule files that apply (${selection.applied.length}):`,
    ...selection.applied.map(item => `- ${item.file} (${item.because})`),
    '',
    `Entries for review (${selection.review.length}); machine-checked in full and left to the gate: ${selection.machineOnly}`,
  ]
  const entries = selection.review.map(entry =>
    isIdsOnly ? `- ${entry.id} [${entry.level}] ${entry.title} (${entry.file}:${entry.line})` : `\n<!-- ${entry.file}:${entry.line} -->\n${entryText(entry)}`,
  )
  return [...head, ...entries].join('\n')
}

/** The next free ID of a prefix: one past the highest number ever used, retired entries included. */
export function nextId(catalog: Catalog, prefix: string): string {
  const used = catalog.entries.filter(entry => entry.prefix === prefix).map(entry => Number(entry.id.slice(prefix.length + 1)))
  return `${prefix}-${String(Math.max(0, ...used) + 1).padStart(3, '0')}`
}
