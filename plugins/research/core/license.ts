import type { Evidence } from './types.ts'
import { normalizeText } from './normalize.ts'

/** The SPDX id and the names a licence's own text uses, normalized (lower case, single spaces). */
const LICENSE_NAMES: Record<string, readonly string[]> = {
  mit: ['mit', 'mit license'],
  'apache-2.0': ['apache-2.0', 'apache license version 2.0', 'apache license, version 2.0', 'apache license 2.0'],
  'bsd-2-clause': ['bsd-2-clause', 'bsd 2-clause'],
  'bsd-3-clause': ['bsd-3-clause', 'bsd 3-clause'],
  'mpl-2.0': ['mpl-2.0', 'mozilla public license version 2.0', 'mozilla public license, v. 2.0'],
  'gpl-2.0': ['gpl-2.0', 'gnu general public license version 2', 'gnu general public license, version 2'],
  'gpl-3.0': ['gpl-3.0', 'gnu general public license version 3', 'gnu general public license, version 3'],
  'lgpl-2.1': ['lgpl-2.1', 'gnu lesser general public license version 2.1'],
  'lgpl-3.0': ['lgpl-3.0', 'gnu lesser general public license version 3'],
  'agpl-3.0': ['agpl-3.0', 'gnu affero general public license version 3', 'gnu affero general public license'],
  isc: ['isc', 'isc license'],
  unlicense: ['unlicense', 'this is free and unencumbered software released into the public domain'],
}

/** A whole phrase: "mit" is not in "submit", "gpl-3.0" is not in "agpl-3.0". */
function hasPhrase(text: string, phrase: string): boolean {
  const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`(^|[^a-z0-9])${escaped}($|[^a-z0-9])`).test(text)
}

/** The licence a reuse finding names must be visible in one of its quotes, or be unknown. */
export function licenseGuard(license: string, evidence: readonly Evidence[]): string | undefined {
  if (license === 'unknown') return undefined
  const names = LICENSE_NAMES[license.trim().toLowerCase()] ?? [normalizeText(license)]
  const quotes = evidence.map(item => normalizeText(item.quote ?? ''))
  if (names.some(name => quotes.some(quote => hasPhrase(quote, name)))) return undefined
  return `license ${license} is not in any quote; quote the licence file or the package page, or use unknown`
}
