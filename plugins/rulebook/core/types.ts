export type Level = 'MUST' | 'SHOULD' | 'RETIRED'

/** One part of a `Checked by:` line: `eslint \`a\`, \`b\`` or `internal/guard_test.go` or `review`. */
export interface Check {
  /** The first word: the tool (`eslint`), a file path, or `review`. */
  readonly kind: string
  /** The backticked names after it. */
  readonly names: readonly string[]
}

export interface Entry {
  readonly id: string
  readonly prefix: string
  readonly level: Level
  readonly title: string
  readonly file: string
  /** 1-based line of the heading. */
  readonly line: number
  /** The lines under the heading, up to the next heading. */
  readonly body: string
  readonly checks: readonly Check[]
}

/** A file as the caller read it: the path relative to the repository root, forward slashes. */
export interface SourceFile {
  readonly path: string
  readonly text: string
}

export interface Frontmatter {
  /** The globs of `paths:`; undefined when the file has none and loads in every session. */
  readonly paths: readonly string[] | undefined
  /** Top-level keys other than `paths`. */
  readonly otherKeys: readonly string[]
  /** An opening `---` without its closing one. */
  readonly isUnclosed: boolean
  /** How many lines the frontmatter block takes, fences included. */
  readonly lines: number
}

export interface RulesFile {
  readonly path: string
  readonly frontmatter: Frontmatter
  readonly entries: readonly Entry[]
  /** Headings that start like an entry and do not follow the grammar. */
  readonly malformed: readonly { readonly line: number; readonly text: string }[]
}

export interface Issue {
  readonly file: string
  readonly line: number
  readonly id?: string
  readonly message: string
}
