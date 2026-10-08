import {
  CONFIDENCES,
  DELIVERIES,
  DIMENSION_TYPES,
  EVIDENCE_KINDS,
  FINDING_KINDS,
  FINDING_STATUSES,
  KANO,
  METHODS,
  OVERLAPS,
  REFERENCE_KINDS,
  REFERENCE_STATUSES,
  ROLES,
  SOURCE_MODELS,
  STUDY_MODES,
  STUDY_STATUSES,
  VIAS,
  VOLATILITIES,
  WARDLEY,
} from './types.ts'
import type { Answer, Criterion, Dimension, Evidence, EvidenceKind, Finding, Issue, Method, Reference, Rejection, Score, Study, Taxonomy } from './types.ts'
import { normalizeText, numbersIn } from './normalize.ts'
import { parseRepoUrl } from './paths.ts'
import { isDate } from './fresh.ts'

export const CODE_KINDS: readonly EvidenceKind[] = ['code', 'api_spec', 'spec']
export const WEB_KINDS: readonly EvidenceKind[] = ['docs', 'blog', 'issue', 'marketing']
export const PRIMARY_KINDS: readonly EvidenceKind[] = ['code', 'api_spec', 'spec', 'docs', 'tested']
export const MAX_QUOTE_CHARS = 300
export const MAX_CODE_LINES = 15
export const FINDING_ID = /^[a-z0-9][a-z0-9-]*\.[a-z][a-z0-9_]*(\.\d+)?$/

const METHOD_OF: Record<EvidenceKind, Method> = {
  tested: 'tested',
  code: 'source',
  api_spec: 'source',
  spec: 'source',
  docs: 'docs',
  blog: 'third_party',
  issue: 'third_party',
  marketing: 'claimed',
}
const REF_ID = /^[a-z0-9][a-z0-9-]*$/
const SNAKE_ID = /^[a-z][a-z0-9_]*$/
const OPTION = /^[a-z0-9][a-z0-9_]*$/
const DURATION = /^P(?!$)(\d+Y)?(\d+M)?(\d+W)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$/
const LEVEL_KEYS = ['1', '2', '3', '4', '5']

export const isSha = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{40}$/.test(value)
const isText = (value: unknown): value is string => typeof value === 'string' && value.trim() !== ''
const isOneOf = <T extends string>(list: readonly T[], value: unknown): value is T => typeof value === 'string' && (list as readonly string[]).includes(value)
const isMapping = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const error = (file: string, message: string): Issue => ({ level: 'error', kind: 'schema', file, message })
const warn = (file: string, message: string, kind: Issue['kind'] = 'schema'): Issue => ({ level: 'warn', kind, file, message })

export function hostOf(url: string): string {
  return /^https?:\/\/([^/?#]+)/i.exec(url)?.[1]?.toLowerCase() ?? ''
}

export function parseLines(lines: string): [number, number] {
  const [first = Number.NaN, last] = lines.split('-').map(Number)
  return [first, last ?? first]
}

export function methodOf(evidence: readonly Evidence[]): Method {
  const methods = evidence.map(item => METHOD_OF[item.kind])
  return METHODS.find(method => methods.includes(method)) ?? 'claimed'
}

export function canConfirm(finding: Finding): boolean {
  if (finding.method === 'claimed') return false
  if (finding.evidence.some(item => PRIMARY_KINDS.includes(item.kind))) return true
  const hosts = new Set(finding.evidence.flatMap(item => (item.url === undefined ? [] : [hostOf(item.url)])))
  return hosts.size >= 2
}

export function answerIssue(dimension: Dimension, answer: Answer): string | undefined {
  if (answer === 'unknown') return undefined
  switch (dimension.type) {
    case 'enum': {
      const options = dimension.options ?? []
      return typeof answer === 'string' && options.includes(answer)
        ? undefined
        : `answer ${JSON.stringify(answer)} is not one of [${options.join(', ')}]; add the option to study.yaml first`
    }
    case 'number':
      return typeof answer === 'number' && Number.isFinite(answer) ? undefined : 'answer must be a number'
    case 'duration':
      return typeof answer === 'string' && DURATION.test(answer) ? undefined : 'answer must be an ISO 8601 duration such as P1D or PT15M'
    case 'bool':
      return typeof answer === 'boolean' ? undefined : 'answer must be true or false'
    case 'text':
      return isText(answer) ? undefined : 'answer must be non-empty text'
  }
}

export function numberGuard(finding: Finding, dimension: Dimension): string | undefined {
  const claimed = new Set<string>()
  if (dimension.type === 'number' && typeof finding.answer === 'number') claimed.add(String(finding.answer))
  for (const number of numbersIn(finding.detail ?? '')) claimed.add(number)
  if (claimed.size === 0) return undefined
  const quoted = new Set(finding.evidence.flatMap(item => numbersIn(normalizeText(item.quote ?? ''))))
  const missing = [...claimed].filter(number => !quoted.has(number))
  return missing.length === 0 ? undefined : `numbers not found in any quote: ${missing.join(', ')}`
}

export function evidenceIssues(item: Evidence, index: number): string[] {
  const at = `evidence[${index}]`
  const out: string[] = []
  if (!isOneOf(EVIDENCE_KINDS, item.kind)) out.push(`${at}.kind must be one of ${EVIDENCE_KINDS.join(', ')}`)
  if (!isText(item.quote)) out.push(`${at}.quote is required`)
  if (CODE_KINDS.includes(item.kind)) {
    if (!isText(item.repo)) out.push(`${at}.repo is required`)
    if (!isSha(item.sha)) out.push(`${at}.sha must be a full 40-character sha`)
    if (!isText(item.path)) out.push(`${at}.path is required`)
    else if (item.path.startsWith('/') || item.path.split('/').includes('..')) out.push(`${at}.path must be relative to the repository root`)
    if (typeof item.lines !== 'string' || !/^\d+(-\d+)?$/.test(item.lines)) out.push(`${at}.lines must be N or N-M`)
    else {
      const [first, last] = parseLines(item.lines)
      if (first < 1 || last < first) out.push(`${at}.lines ${item.lines} is not a valid range`)
      else if (last - first + 1 > MAX_CODE_LINES) out.push(`${at} cites ${last - first + 1} lines; cite at most ${MAX_CODE_LINES}`)
    }
    if (isText(item.quote) && item.quote.split('\n').length > MAX_CODE_LINES) out.push(`${at}.quote spans more than ${MAX_CODE_LINES} lines`)
  } else if (item.kind === 'tested') {
    if (!isText(item.artifact) || !item.artifact.startsWith('artifacts/') || item.artifact.includes('..')) {
      out.push(`${at}.artifact must be a path under artifacts/`)
    }
  } else if (WEB_KINDS.includes(item.kind)) {
    if (typeof item.url !== 'string' || !/^https?:\/\//.test(item.url)) out.push(`${at}.url must be an http(s) URL`)
    if (!isDate(item.retrieved)) out.push(`${at}.retrieved must be YYYY-MM-DD`)
    if (item.archive !== undefined && !/^https?:\/\//.test(item.archive)) out.push(`${at}.archive must be an http(s) URL`)
    if (isText(item.quote) && item.quote.length > MAX_QUOTE_CHARS) out.push(`${at}.quote is ${item.quote.length} characters; quote at most ${MAX_QUOTE_CHARS}`)
  }
  return out
}

export function validateReferences(data: unknown, file: string, taxonomy?: Taxonomy): Issue[] {
  if (!Array.isArray(data)) return [error(file, 'references.yaml must be a list')]
  const out: Issue[] = []
  const seen = new Set<string>()
  const domainOwner = new Map<string, string>()
  data.forEach((raw: unknown, index) => {
    const at = `references[${index}]`
    if (!isMapping(raw)) {
      out.push(error(file, `${at} must be a mapping`))
      return
    }
    const ref = raw as Partial<Reference>
    if (typeof ref.id !== 'string' || !REF_ID.test(ref.id)) out.push(error(file, `${at}.id must be kebab-case`))
    else if (seen.has(ref.id)) out.push(error(file, `${at}.id ${ref.id} is duplicated`))
    else seen.add(ref.id)
    if (!isText(ref.name)) out.push(error(file, `${at}.name is required`))
    if (ref.repos !== undefined && !Array.isArray(ref.repos)) out.push(error(file, `${at}.repos must be a list`))
    const repos: unknown[] = Array.isArray(ref.repos) ? ref.repos : []
    repos.forEach((repoRaw, i) => {
      const repo = (isMapping(repoRaw) ? repoRaw : {}) as Record<string, unknown>
      const where = `${at}.repos[${i}]`
      if (typeof repo.url !== 'string') out.push(error(file, `${where}.url is required`))
      else if (repo.url !== 'self') {
        try {
          parseRepoUrl(repo.url)
        } catch (problem) {
          out.push(error(file, `${where}.url: ${(problem as Error).message}`))
        }
      }
      if (repo.pin !== undefined && !isSha(repo.pin)) out.push(error(file, `${where}.pin must be a full 40-character sha`))
      if (repo.pin !== undefined && !isDate(repo.pinned_at)) out.push(error(file, `${where}.pinned_at must be YYYY-MM-DD when pin is set`))
    })
    out.push(...factIssues(ref, at, taxonomy).map(message => error(file, message)))
    for (const raw of Array.isArray(ref.domains) ? ref.domains : []) {
      if (typeof raw !== 'string' || typeof ref.id !== 'string') continue
      const domain = normalizeDomain(raw)
      const owner = domainOwner.get(domain)
      if (owner !== undefined && owner !== ref.id) out.push(error(file, `domain ${domain} is used by ${owner} and ${ref.id}`))
      else domainOwner.set(domain, ref.id)
    }
  })
  data.forEach((raw: unknown, index) => {
    if (!isMapping(raw)) return
    for (const link of ['owned_by', 'successor'] as const) {
      const target = raw[link]
      if (target !== undefined && (typeof target !== 'string' || !seen.has(target))) {
        out.push(error(file, `references[${index}].${link} ${String(target)} is not a registered reference`))
      }
    }
  })
  return out
}

/** Hosts compare without scheme, www. or path: https://www.flexprice.io/ and flexprice.io are one domain. */
export function normalizeDomain(value: string): string {
  return value.trim().toLowerCase().replace(/^[a-z][a-z0-9+.-]*:\/\//, '').replace(/^www\./, '').replace(/[/?#].*$/, '')
}

const categoryIssue = (taxonomy: Taxonomy | undefined, value: unknown) =>
  taxonomy !== undefined && (typeof value !== 'string' || !(value in (taxonomy.categories ?? {}))) ? `${String(value)} is not in taxonomy.yaml` : undefined

function listIssues(value: unknown, at: string): string[] {
  return value !== undefined && (!Array.isArray(value) || !value.every(isText)) ? [`${at} must be a list of text`] : []
}

function factIssues(ref: Partial<Reference>, at: string, taxonomy: Taxonomy | undefined): string[] {
  const out: string[] = []
  if (ref.kind !== undefined && !isOneOf(REFERENCE_KINDS, ref.kind)) out.push(`${at}.kind must be one of ${REFERENCE_KINDS.join(', ')}`)
  for (const field of ['aliases', 'domains', 'categories', 'delivery'] as const) out.push(...listIssues(ref[field], `${at}.${field}`))
  for (const category of Array.isArray(ref.categories) ? ref.categories : []) {
    const problem = categoryIssue(taxonomy, category)
    if (problem) out.push(`${at}.categories: ${problem}`)
  }
  if (ref.source_model !== undefined && !isOneOf(SOURCE_MODELS, ref.source_model)) out.push(`${at}.source_model must be one of ${SOURCE_MODELS.join(', ')}`)
  if (Array.isArray(ref.delivery) && !ref.delivery.every(item => isOneOf(DELIVERIES, item))) out.push(`${at}.delivery must use ${DELIVERIES.join(', ')}`)
  if (ref.status !== undefined && !isOneOf(REFERENCE_STATUSES, ref.status)) out.push(`${at}.status must be one of ${REFERENCE_STATUSES.join(', ')}`)
  if (ref.stance !== undefined) {
    const stance = (isMapping(ref.stance) ? ref.stance : {}) as Record<string, unknown>
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

/** Candidates wait for a human; one that is already registered or rejected must not wait twice. */
export function validateCandidates(data: unknown, references: readonly Reference[], rejected: readonly Rejection[], taxonomy: Taxonomy | undefined, file: string): Issue[] {
  if (!Array.isArray(data)) return [error(file, 'candidates.yaml must be a list')]
  const registeredDomain = new Map(references.flatMap(ref => (ref.domains ?? []).map(domain => [normalizeDomain(domain), ref.id] as const)))
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

/** Nobody gets forgotten: every competitor overlapping a study's categories is included or excluded with a reason. */
export function coverageIssues(study: Study, references: readonly Reference[], file: string): Issue[] {
  const categories = Array.isArray(study.categories) ? study.categories : []
  if (categories.length === 0) return []
  const out: Issue[] = []
  for (const ref of references) {
    const overlap = isMapping(ref.stance?.overlap) ? ref.stance.overlap : {}
    const hit = categories.find(category => category in overlap)
    if (hit === undefined || ref.id in study.references || (study.excluded ?? {})[ref.id] !== undefined) continue
    out.push(warn(file, `${ref.id} overlaps ${hit}: include it or add it to excluded with a reason`))
  }
  return out
}

function criterionIssues(criteria: unknown[], file: string): Issue[] {
  const out: Issue[] = []
  const ids = new Set<string>()
  criteria.forEach((raw, index) => {
    const at = `criteria[${index}]`
    const criterion = (isMapping(raw) ? raw : {}) as Partial<Criterion>
    if (typeof criterion.id !== 'string' || !SNAKE_ID.test(criterion.id)) out.push(error(file, `${at}.id must be snake_case`))
    else if (ids.has(criterion.id)) out.push(error(file, `${at}.id ${criterion.id} is duplicated`))
    else ids.add(criterion.id)
    if (!isText(criterion.ask)) out.push(error(file, `${at}.ask is required`))
    const levels = isMapping(criterion.levels) ? criterion.levels : undefined
    if (!levels) {
      out.push(error(file, `${at}.levels must map 1..5 to descriptions`))
      return
    }
    const keys = Object.keys(levels)
    if (!keys.every(key => LEVEL_KEYS.includes(key))) out.push(error(file, `${at}.levels keys must be 1..5`))
    if (!['1', '3', '5'].every(key => isText(levels[key]))) out.push(error(file, `${at}.levels needs written descriptions for at least 1, 3 and 5`))
  })
  return out
}

function dimensionIssues(dimensions: unknown[], file: string): Issue[] {
  const out: Issue[] = []
  const ids = new Set<string>()
  dimensions.forEach((raw, index) => {
    const at = `dimensions[${index}]`
    const dim = (isMapping(raw) ? raw : {}) as Partial<Dimension>
    if (typeof dim.id !== 'string' || !SNAKE_ID.test(dim.id)) out.push(error(file, `${at}.id must be snake_case`))
    else if (ids.has(dim.id)) out.push(error(file, `${at}.id ${dim.id} is duplicated`))
    else ids.add(dim.id)
    if (!isText(dim.ask)) out.push(error(file, `${at}.ask is required`))
    if (!isOneOf(DIMENSION_TYPES, dim.type)) out.push(error(file, `${at}.type must be one of ${DIMENSION_TYPES.join(', ')}`))
    if (dim.type === 'enum') {
      const options: unknown[] = Array.isArray(dim.options) ? dim.options : []
      if (options.length < 2) out.push(error(file, `${at}.options needs at least two options`))
      if (!options.every(option => typeof option === 'string' && OPTION.test(option))) out.push(error(file, `${at}.options must be snake_case`))
      if (new Set(options).size !== options.length) out.push(error(file, `${at}.options has duplicates`))
    } else if (dim.options !== undefined) out.push(error(file, `${at}.options only applies to enum dimensions`))
    if (!isOneOf(VOLATILITIES, dim.volatility)) out.push(error(file, `${at}.volatility must be one of ${VOLATILITIES.join(', ')}`))
    if (dim.kano !== undefined && !isOneOf(KANO, dim.kano)) out.push(error(file, `${at}.kano must be one of ${KANO.join(', ')}`))
    if (dim.wardley !== undefined && !isOneOf(WARDLEY, dim.wardley)) out.push(error(file, `${at}.wardley must be one of ${WARDLEY.join(', ')}`))
  })
  return out
}

export function validateStudy(data: unknown, topic: string, refIds: ReadonlySet<string>, file: string, taxonomy?: Taxonomy): Issue[] {
  if (!isMapping(data)) return [error(file, 'study.yaml must be a mapping')]
  const study = data as Partial<Study>
  const out: Issue[] = []
  if (study.topic !== topic) out.push(error(file, `topic must be "${topic}" (the directory name)`))
  if (!isOneOf(STUDY_STATUSES, study.status)) out.push(error(file, `status must be one of ${STUDY_STATUSES.join(', ')}`))
  if (!isOneOf(STUDY_MODES, study.mode)) out.push(error(file, `mode must be one of ${STUDY_MODES.join(', ')}`))
  if (study.status !== 'draft') {
    if (!isText(study.question)) out.push(error(file, 'question is required once the study leaves draft'))
    if (!isText(study.decision_needed)) out.push(error(file, 'decision_needed is required once the study leaves draft'))
  }
  let hasOurs = false
  if (!isMapping(study.references)) out.push(error(file, 'references must map reference ids to roles'))
  else {
    for (const [id, roles] of Object.entries(study.references)) {
      if (!refIds.has(id)) out.push(error(file, `references.${id} is not in references.yaml`))
      const list: unknown[] = Array.isArray(roles) ? roles : [roles]
      if (list.length === 0 || !list.every(role => isOneOf(ROLES, role))) out.push(error(file, `references.${id} roles must be from ${ROLES.join(', ')}`))
      if (list.includes('ours')) hasOurs = true
    }
  }
  if (!Array.isArray(study.dimensions)) out.push(error(file, 'dimensions must be a list'))
  else out.push(...dimensionIssues(study.dimensions, file))
  if (!Array.isArray(study.criteria)) out.push(error(file, 'criteria must be a list'))
  else out.push(...criterionIssues(study.criteria, file))
  if (study.status === 'decided') {
    const decision = study.decision
    if (!isMapping(decision)) out.push(error(file, 'decision is required when status is decided'))
    else {
      if (!isText(decision.chosen)) out.push(error(file, 'decision.chosen is required'))
      if (!isDate(decision.decided_at)) out.push(error(file, 'decision.decided_at must be YYYY-MM-DD'))
      if (!Array.isArray(decision.cites) || decision.cites.length === 0) out.push(error(file, 'decision.cites must list the finding ids the decision rests on'))
      if (!isText(decision.revisit_when)) out.push(error(file, 'decision.revisit_when is required'))
      if (!isMapping(decision.snapshot)) out.push(error(file, 'decision.snapshot is missing; record decisions with research decide'))
    }
  }
  if (study.categories !== undefined) {
    if (!Array.isArray(study.categories)) out.push(error(file, 'categories must be a list of taxonomy categories'))
    else {
      for (const category of study.categories) {
        const problem = categoryIssue(taxonomy, category)
        if (problem) out.push(error(file, `categories: ${problem}`))
      }
    }
  }
  if (study.excluded !== undefined) {
    if (!isMapping(study.excluded)) out.push(error(file, 'excluded must map reference ids to reasons'))
    else {
      for (const [id, reason] of Object.entries(study.excluded)) {
        if (!refIds.has(id)) out.push(error(file, `excluded.${id} is not in references.yaml`))
        if (!isText(reason)) out.push(error(file, `excluded.${id} needs a reason`))
        if (isMapping(study.references) && id in study.references) out.push(error(file, `${id} is both referenced and excluded`))
      }
    }
  }
  if (!hasOurs && Array.isArray(study.dimensions) && study.dimensions.length > 0) {
    out.push(warn(file, 'no reference has the ours role; our design is not compared'))
  }
  return out
}

export function validateFinding(raw: unknown, study: Study, file: string): Issue[] {
  if (!isMapping(raw)) return [error(file, 'a finding must be a mapping')]
  const finding = raw as Partial<Finding>
  const out: string[] = []
  if (typeof finding.id !== 'string' || !FINDING_ID.test(finding.id)) out.push('id must look like <ref>.<dimension>[.<n>]')
  else if (typeof finding.ref === 'string' && typeof finding.dimension === 'string') {
    const base = `${finding.ref}.${finding.dimension}`
    const isOwn = finding.id === base || (finding.id.startsWith(`${base}.`) && /^\d+$/.test(finding.id.slice(base.length + 1)))
    if (!isOwn) out.push(`id must be ${base} or ${base}.<n>`)
  }
  if (typeof finding.ref !== 'string' || !(finding.ref in study.references)) out.push(`ref ${String(finding.ref)} is not a reference of study ${study.topic}`)
  const dimension = study.dimensions.find(dim => dim.id === finding.dimension)
  if (!dimension) out.push(`dimension ${String(finding.dimension)} is not a dimension of study ${study.topic}`)
  if (!isOneOf(FINDING_KINDS, finding.kind)) out.push('kind must be answer or pain')
  if (finding.answer === undefined) out.push('answer is required')
  else if (dimension) {
    const problem = answerIssue(dimension, finding.answer)
    if (problem) out.push(problem)
  }
  const isUnknown = finding.answer === 'unknown'
  const evidence = Array.isArray(finding.evidence) ? (finding.evidence as Evidence[]) : undefined
  if (!evidence) out.push('evidence must be a list')
  if (isUnknown && (!Array.isArray(finding.searched) || finding.searched.length === 0 || !finding.searched.every(isText))) {
    out.push('an unknown answer needs searched: what was looked at')
  }
  if (!isUnknown && evidence?.length === 0) out.push('at least one evidence item is required')
  if (finding.kind === 'pain' && !isText(finding.detail)) out.push('a pain finding needs detail describing the pain')
  evidence?.forEach((item, index) => out.push(...evidenceIssues(item, index)))
  if (!isOneOf(METHODS, finding.method)) out.push(`method must be one of ${METHODS.join(', ')}`)
  else if (evidence && evidence.length > 0 && finding.method !== methodOf(evidence)) out.push(`method must be ${methodOf(evidence)} for this evidence`)
  if (!isOneOf(CONFIDENCES, finding.confidence)) out.push(`confidence must be one of ${CONFIDENCES.join(', ')}`)
  if (finding.method === 'claimed' && finding.confidence === 'confirmed') out.push('vendor claims (marketing) cannot be confirmed')
  if (finding.confidence !== 'unverified' && finding.verified === undefined) out.push(`confidence ${String(finding.confidence)} requires verified`)
  const verified = finding.verified as Record<string, unknown> | undefined
  if (verified !== undefined && (!isText(verified.by) || !isDate(verified.at) || !isOneOf(VIAS, verified.via))) {
    out.push('verified needs by, at (YYYY-MM-DD) and via')
  }
  if (!isOneOf(FINDING_STATUSES, finding.status)) out.push(`status must be one of ${FINDING_STATUSES.join(', ')}`)
  if (dimension && evidence && !isUnknown) {
    const problem = numberGuard(finding as Finding, dimension)
    if (problem) out.push(problem)
  }
  const label = typeof finding.id === 'string' ? finding.id : '(no id)'
  return out.map(message => error(file, `finding ${label}: ${message}`))
}

export function validateFindings(data: unknown, study: Study, file: string): Issue[] {
  if (!Array.isArray(data)) return [error(file, 'findings.yaml must be a list')]
  const out: Issue[] = []
  const seen = new Set<string>()
  for (const raw of data) {
    out.push(...validateFinding(raw, study, file))
    const id = isMapping(raw) ? raw.id : undefined
    if (typeof id !== 'string') continue
    if (seen.has(id)) out.push(error(file, `finding ${id} is duplicated`))
    seen.add(id)
  }
  return out
}

export function validateScore(raw: unknown, study: Study, findingIds: ReadonlySet<string>, file: string): Issue[] {
  if (!isMapping(raw)) return [error(file, 'a score must be a mapping')]
  const score = raw as Partial<Score>
  const out: string[] = []
  if (typeof score.ref !== 'string' || !(score.ref in study.references)) out.push(`ref ${String(score.ref)} is not a reference of study ${study.topic}`)
  if (!study.criteria.some(criterion => criterion.id === score.criterion)) out.push(`criterion ${String(score.criterion)} is not a criterion of study ${study.topic}`)
  const isLevel = score.level === 'unknown' || (typeof score.level === 'number' && Number.isInteger(score.level) && score.level >= 1 && score.level <= 5)
  if (!isLevel) out.push('level must be 1-5 or unknown')
  const because: unknown[] = Array.isArray(score.because) ? score.because : []
  if (!Array.isArray(score.because)) out.push('because must be a list of finding ids')
  if (typeof score.level === 'number' && because.length === 0) out.push('a numeric level must cite the findings it rests on')
  for (const id of because) if (typeof id !== 'string' || !findingIds.has(id)) out.push(`because cites ${String(id)}, which does not exist`)
  if (!isMapping(score.by) || !isText(score.by.agent) || !isDate(score.by.at)) out.push('by needs agent and at (YYYY-MM-DD)')
  return out.map(message => error(file, `score ${String(score.ref)}/${String(score.criterion)}: ${message}`))
}

export function validateScores(data: unknown, study: Study, findingIds: ReadonlySet<string>, file: string): Issue[] {
  if (!Array.isArray(data)) return [error(file, 'assessment.yaml must be a list')]
  const out: Issue[] = []
  const seen = new Set<string>()
  for (const raw of data) {
    out.push(...validateScore(raw, study, findingIds, file))
    const key = isMapping(raw) ? `${String(raw.ref)}/${String(raw.criterion)}` : ''
    if (seen.has(key)) out.push(error(file, `score ${key} is duplicated`))
    seen.add(key)
  }
  return out
}

export function citationIssues(notes: string, topic: string, index: ReadonlyMap<string, ReadonlySet<string>>, file: string): Issue[] {
  const out: Issue[] = []
  for (const match of notes.matchAll(/\[f:(?:([a-z0-9-]+)\/)?([^\]\s]+)\]/g)) {
    const owner = match[1] ?? topic
    if (!index.get(owner)?.has(match[2] ?? '')) out.push(error(file, `citation ${match[0]} does not resolve`))
  }
  return out
}

/**
 * The freshness gate runs once, in `research decide`, which stores what each cited
 * finding stood on. Here a decision only needs that snapshot; evidence that moved
 * on afterwards asks for a revisit and never fails a later check.
 */
export function decidedGate(study: Study, findings: readonly Finding[], file: string): Issue[] {
  if (study.status !== 'decided' || study.decision === undefined) return []
  const { decided_at: decidedAt, cites, snapshot = {} } = study.decision
  const byId = new Map(findings.map(finding => [finding.id, finding]))
  const out: Issue[] = []
  for (const id of cites) {
    const finding = byId.get(id)
    const taken = snapshot[id]
    if (finding === undefined) out.push(error(file, `decision cites ${id}, which does not exist`))
    else if (taken === undefined) out.push(error(file, `decision has no snapshot of ${id}; record decisions with research decide`))
    else {
      const change =
        finding.status !== 'current'
          ? `is ${finding.status}`
          : finding.verified === undefined
            ? 'was re-recorded and is unverified'
            : finding.confidence !== taken.confidence
              ? `is now ${finding.confidence}`
              : undefined
      if (change !== undefined) out.push(warn(file, `decision cites ${id}, which ${change} since ${decidedAt}; revisit the decision`, 'freshness'))
    }
  }
  return out
}
