import { evidenceIssues, isDate } from '../../research/core/index.ts'
import type { Evidence, Issue, Reference } from '../../research/core/index.ts'
import { DELIVERIES, OVERLAPS, SOURCE_MODELS, STATUSES } from './types.ts'
import type { Registry, Rejection, Taxonomy } from './types.ts'

const REF_ID = /^[a-z0-9][a-z0-9-]*$/
const SNAKE_ID = /^[a-z][a-z0-9_]*$/
const ENTRY_KEYS: ReadonlySet<string> = new Set(['vendor', 'owned_by', 'successor', 'aliases', 'domains', 'categories', 'source_model', 'delivery', 'status', 'stance'])

const isText = (value: unknown): value is string => typeof value === 'string' && value.trim() !== ''
const isOneOf = <T extends string>(list: readonly T[], value: unknown): value is T => typeof value === 'string' && (list as readonly string[]).includes(value)
const isMapping = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const error = (file: string, message: string): Issue => ({ level: 'error', kind: 'schema', file, message })

/** Hosts compare without scheme, www. or path: https://www.flexprice.io/ and flexprice.io are one domain. */
export function normalizeDomain(value: string): string {
  return value.trim().toLowerCase().replace(/^[a-z][a-z0-9+.-]*:\/\//, '').replace(/^www\./, '').replace(/[/?#].*$/, '')
}

const categoryIssue = (taxonomy: Taxonomy | undefined, value: unknown) =>
  taxonomy !== undefined && (typeof value !== 'string' || !(value in taxonomy.categories)) ? `${String(value)} is not in taxonomy.yaml` : undefined

function listIssues(value: unknown, at: string): string[] {
  return value !== undefined && (!Array.isArray(value) || !value.every(isText)) ? [`${at} must be a list of text`] : []
}

function entryIssues(entry: Record<string, unknown>, at: string, taxonomy: Taxonomy | undefined): string[] {
  const out: string[] = []
  for (const key of Object.keys(entry)) {
    if (!ENTRY_KEYS.has(key)) out.push(`${at}.${key} is not a market fact; reference facts belong in research/references.yaml`)
  }
  for (const field of ['aliases', 'domains', 'categories', 'delivery'] as const) out.push(...listIssues(entry[field], `${at}.${field}`))
  for (const category of Array.isArray(entry.categories) ? entry.categories : []) {
    const problem = categoryIssue(taxonomy, category)
    if (problem) out.push(`${at}.categories: ${problem}`)
  }
  if (entry.source_model !== undefined && !isOneOf(SOURCE_MODELS, entry.source_model)) out.push(`${at}.source_model must be one of ${SOURCE_MODELS.join(', ')}`)
  if (Array.isArray(entry.delivery) && !entry.delivery.every(item => isOneOf(DELIVERIES, item))) out.push(`${at}.delivery must use ${DELIVERIES.join(', ')}`)
  if (entry.status !== undefined && !isOneOf(STATUSES, entry.status)) out.push(`${at}.status must be one of ${STATUSES.join(', ')}`)
  if (entry.stance !== undefined) {
    const stance = (isMapping(entry.stance) ? entry.stance : {}) as Record<string, unknown>
    if (stance.tier !== 1 && stance.tier !== 2 && stance.tier !== 'watch') out.push(`${at}.stance.tier must be 1, 2 or watch`)
    if (!isMapping(stance.overlap)) out.push(`${at}.stance.overlap must map categories to direct or adjacent`)
    else {
      for (const [category, level] of Object.entries(stance.overlap)) {
        const problem = categoryIssue(taxonomy, category)
        if (problem) out.push(`${at}.stance.overlap.${category}: ${problem}`)
        if (!isOneOf(OVERLAPS, level)) out.push(`${at}.stance.overlap.${category} must be direct or adjacent`)
      }
    }
    if (!isDate(stance.reviewed)) out.push(`${at}.stance.reviewed must be YYYY-MM-DD`)
  }
  return out
}

export function validateTaxonomy(data: unknown, file: string): Issue[] {
  if (!isMapping(data)) return [error(file, 'taxonomy.yaml must map categories and capabilities to definitions')]
  const out: Issue[] = []
  const sections = [
    ['categories', REF_ID, 'kebab-case'],
    ['capabilities', SNAKE_ID, 'snake_case'],
  ] as const
  for (const [section, pattern, shape] of sections) {
    const entries = data[section]
    if (entries === undefined || entries === null) continue
    if (!isMapping(entries)) {
      out.push(error(file, `${section} must map ids to definitions`))
      continue
    }
    for (const [id, definition] of Object.entries(entries)) {
      if (!pattern.test(id)) out.push(error(file, `${section}.${id} must be ${shape}`))
      if (!isText(definition)) out.push(error(file, `${section}.${id} needs a definition`))
    }
  }
  if (data.scope !== undefined) {
    if (!isMapping(data.scope)) out.push(error(file, 'scope must have include and exclude rules'))
    else {
      for (const key of ['include', 'exclude'] as const) {
        const rules = data.scope[key]
        if (rules !== undefined && (!Array.isArray(rules) || !rules.every(isText))) out.push(error(file, `scope.${key} must be a list of rules`))
      }
    }
  }
  return out
}

/** Every entry names a reference research knows; facts, stance and domains are checked; no domain belongs to two entries. */
export function validateRegistry(data: unknown, references: readonly Reference[], taxonomy: Taxonomy | undefined, file: string): Issue[] {
  if (data === null || data === undefined) return []
  if (!isMapping(data)) return [error(file, 'registry.yaml must map reference ids to market facts')]
  const refIds = new Set(references.map(ref => ref.id))
  const out: Issue[] = []
  const domainOwner = new Map<string, string>()
  for (const [id, raw] of Object.entries(data)) {
    if (!refIds.has(id)) out.push(error(file, `${id} is not in research/references.yaml`))
    if (!isMapping(raw)) {
      out.push(error(file, `${id} must map market facts`))
      continue
    }
    out.push(...entryIssues(raw, id, taxonomy).map(message => error(file, message)))
    for (const link of ['owned_by', 'successor'] as const) {
      const target = raw[link]
      if (target !== undefined && (typeof target !== 'string' || !refIds.has(target))) out.push(error(file, `${id}.${link} ${String(target)} is not in research/references.yaml`))
    }
    for (const domain of (Array.isArray(raw.domains) ? raw.domains : []).filter(isText).map(normalizeDomain)) {
      const owner = domainOwner.get(domain)
      if (owner !== undefined && owner !== id) out.push(error(file, `domain ${domain} is used by ${owner} and ${id}`))
      else domainOwner.set(domain, id)
    }
  }
  return out
}

/** Candidates wait for a human; one that is already tracked or rejected must not wait twice. */
export function validateCandidates(
  data: unknown,
  references: readonly Reference[],
  registry: Registry,
  rejected: readonly Rejection[],
  taxonomy: Taxonomy | undefined,
  file: string,
): Issue[] {
  if (!Array.isArray(data)) return [error(file, 'candidates.yaml must be a list')]
  const registeredDomain = new Map(
    Object.entries(registry).flatMap(([id, entry]) => (Array.isArray(entry?.domains) ? entry.domains : []).filter(isText).map(domain => [normalizeDomain(domain), id] as const)),
  )
  const rejectedDomain = new Set(rejected.flatMap(item => (item.domains ?? []).map(normalizeDomain)))
  const refIds = new Set(references.map(ref => ref.id))
  const out: Issue[] = []
  data.forEach((raw: unknown, index) => {
    if (!isMapping(raw)) {
      out.push(error(file, `candidates[${index}] must be a mapping`))
      return
    }
    const at = `candidate ${typeof raw.id === 'string' ? raw.id : `[${index}]`}`
    const problems: string[] = []
    if (typeof raw.id !== 'string' || !REF_ID.test(raw.id)) problems.push('id must be kebab-case')
    else if (refIds.has(raw.id)) problems.push(`id ${raw.id} is already registered`)
    if (!isText(raw.name)) problems.push('name is required')
    if (!Array.isArray(raw.domains) || raw.domains.length === 0 || !raw.domains.every(isText)) problems.push('domains must list at least one domain')
    for (const category of Array.isArray(raw.categories) ? raw.categories : []) {
      const problem = categoryIssue(taxonomy, category)
      if (problem) problems.push(`categories: ${problem}`)
    }
    if (!Array.isArray(raw.found_by) || raw.found_by.length === 0 || !raw.found_by.every(isText)) problems.push('found_by must name the discovery channels')
    if (!Array.isArray(raw.evidence) || raw.evidence.length === 0) problems.push('evidence must show the product exists')
    else (raw.evidence as Evidence[]).forEach((item, i) => problems.push(...evidenceIssues(item, i)))
    if (!isDate(raw.proposed_at)) problems.push('proposed_at must be YYYY-MM-DD')
    for (const domain of Array.isArray(raw.domains) ? raw.domains.filter(isText).map(normalizeDomain) : []) {
      const owner = registeredDomain.get(domain)
      if (owner !== undefined) problems.push(`domain ${domain} is already registered as ${owner}`)
      if (rejectedDomain.has(domain)) problems.push(`domain ${domain} was rejected before`)
    }
    out.push(...problems.map(message => error(file, `${at}: ${message}`)))
  })
  return out
}

export function validateRejected(data: unknown, file: string): Issue[] {
  if (!Array.isArray(data)) return [error(file, 'rejected.yaml must be a list')]
  return data.flatMap((raw: unknown, index) => {
    const item = (isMapping(raw) ? raw : {}) as Partial<Rejection>
    const at = `rejected[${index}]`
    const problems: string[] = []
    if (!isText(item.id)) problems.push(`${at}.id is required`)
    if (!isText(item.name)) problems.push(`${at}.name is required`)
    if (!isText(item.reason)) problems.push(`${at}.reason is required`)
    if (!isDate(item.rejected_at)) problems.push(`${at}.rejected_at must be YYYY-MM-DD`)
    return problems.map(message => error(file, message))
  })
}
