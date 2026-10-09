import { CONFIDENCES, DIMENSION_TYPES, EVIDENCE_KINDS, FINDING_KINDS, FINDING_STATUSES, KANO, METHODS, REFERENCE_KINDS, RESERVED_DIMENSIONS, REUSE_TYPES, ROLES, STUDY_MODES, STUDY_STATUSES, VIAS, VOLATILITIES, WARDLEY } from './types.ts'
import type { Answer, Criterion, Dimension, Evidence, EvidenceKind, Finding, Issue, Method, Reference, Score, Study } from './types.ts'
import { normalizeText, numbersIn } from './normalize.ts'
import { parseRepoUrl } from './paths.ts'
import { isDate } from './fresh.ts'
import { licenseGuard } from './license.ts'
import { citationsOf } from './notes.ts'

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

export function numberGuard(finding: Finding, dimension: Dimension | undefined): string | undefined {
  const claimed = new Set<string>()
  if (dimension?.type === 'number' && typeof finding.answer === 'number') claimed.add(String(finding.answer))
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

const REFERENCE_KEYS: ReadonlySet<string> = new Set(['id', 'name', 'kind', 'docs', 'api_spec', 'repos', 'license', 'note'])

export function validateReferences(data: unknown, file: string): Issue[] {
  if (!Array.isArray(data)) return [error(file, 'references.yaml must be a list')]
  const out: Issue[] = []
  const seen = new Set<string>()
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
    if (ref.kind !== undefined && !isOneOf(REFERENCE_KINDS, ref.kind)) out.push(error(file, `${at}.kind must be one of ${REFERENCE_KINDS.join(', ')}`))
    for (const key of Object.keys(raw)) {
      if (!REFERENCE_KEYS.has(key)) out.push(error(file, `${at}.${key} is not a reference fact; market data belongs in research/market/ (the market plugin)`))
    }
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
  })
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
    else if ((RESERVED_DIMENSIONS as readonly string[]).includes(dim.id)) out.push(error(file, `${at}.id ${dim.id} is reserved for findings not tied to a dimension`))
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

export function validateStudy(data: unknown, topic: string, refIds: ReadonlySet<string>, file: string): Issue[] {
  if (!isMapping(data)) return [error(file, 'study.yaml must be a mapping')]
  const study = data as Partial<Study>
  const out: Issue[] = []
  if (study.topic !== topic) out.push(error(file, `topic must be "${topic}" (the directory name)`))
  if (!isOneOf(STUDY_STATUSES, study.status)) out.push(error(file, `status must be one of ${STUDY_STATUSES.join(', ')}`))
  if ((study.mode as string) === 'full') out.push(error(file, 'mode full is now deep; set mode: deep'))
  else if (!isOneOf(STUDY_MODES, study.mode)) out.push(error(file, `mode must be one of ${STUDY_MODES.join(', ')}`))
  const isDraft = study.status === 'draft'
  if (!isDraft && !isText(study.question)) out.push(error(file, 'question is required once the study leaves draft'))
  if (study.mode === 'deep' && !isDraft) {
    if (!isText(study.decision_needed)) out.push(error(file, 'decision_needed is required for a deep study once it leaves draft'))
    if (!Array.isArray(study.criteria) || study.criteria.length === 0) out.push(error(file, 'a deep study needs at least one criterion once it leaves draft'))
  }
  if (study.greenfield !== undefined && typeof study.greenfield !== 'boolean') out.push(error(file, 'greenfield must be true or false'))
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
  if (study.criteria !== undefined) {
    if (!Array.isArray(study.criteria)) out.push(error(file, 'criteria must be a list'))
    else out.push(...criterionIssues(study.criteria, file))
  }
  if (study.status === 'brief') {
    if (study.mode !== 'brief') out.push(error(file, 'status brief needs mode brief'))
    const finished = study.finished as unknown
    if (!isMapping(finished) || !isDate(finished.at) || typeof finished.cites !== 'number') out.push(error(file, 'finished is missing; finish a brief with research finish'))
  }
  if (study.status === 'decided') {
    if (study.mode !== 'deep') out.push(error(file, 'only a deep study is decided; set mode: deep and record the decision with research decide'))
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
  for (const key of ['categories', 'excluded']) {
    if (key in study) out.push(error(file, `${key} is gone in research 0.2: studies pick their references per task; remove it`))
  }
  if (!hasOurs && study.greenfield !== true && Array.isArray(study.dimensions) && study.dimensions.length > 0) {
    out.push(warn(file, 'no reference has the ours role; our design is not compared (set greenfield: true when nothing of ours exists yet)'))
  }
  return out
}

export const MAX_SHORT_ANSWER = 120

function reuseIssues(finding: Partial<Finding>, evidence: readonly Evidence[]): string[] {
  const out: string[] = []
  if (!isText(finding.detail)) out.push('a reuse finding needs detail: why it is worth reusing')
  const reuse: unknown = finding.reuse
  if (!isMapping(reuse)) return [...out, 'a reuse finding needs reuse: type, url and license']
  if (!isOneOf(REUSE_TYPES, reuse.type)) out.push(`reuse.type must be one of ${REUSE_TYPES.join(', ')}`)
  if (typeof reuse.url !== 'string' || !/^https?:\/\//.test(reuse.url)) out.push('reuse.url must be an http(s) URL')
  if (!isText(reuse.license)) out.push('reuse.license is required (or unknown)')
  else {
    const problem = licenseGuard(reuse.license, evidence)
    if (problem) out.push(problem)
  }
  return out
}

export function validateFinding(raw: unknown, study: Study, file: string): Issue[] {
  if (!isMapping(raw)) return [error(file, 'a finding must be a mapping')]
  const finding = raw as Partial<Finding>
  const out: string[] = []
  const isLoose = finding.dimension === undefined
  if (!isOneOf(FINDING_KINDS, finding.kind)) out.push(`kind must be one of ${FINDING_KINDS.join(', ')}`)
  else if (isLoose && finding.kind === 'answer') out.push('an answer needs a dimension')
  const segment = isLoose ? finding.kind : finding.dimension
  if (typeof finding.id !== 'string' || !FINDING_ID.test(finding.id)) out.push('id must look like <ref>.<dimension>[.<n>] or <ref>.<pain|reuse>.<n>')
  else if (typeof finding.ref === 'string' && typeof segment === 'string') {
    const base = `${finding.ref}.${segment}`
    const suffix = finding.id.startsWith(`${base}.`) ? finding.id.slice(base.length + 1) : undefined
    const isNumbered = suffix !== undefined && /^\d+$/.test(suffix)
    if (isLoose && !isNumbered) out.push(`id must be ${base}.<n>`)
    if (!isLoose && finding.id !== base && !isNumbered) out.push(`id must be ${base} or ${base}.<n>`)
  }
  if (typeof finding.ref !== 'string' || !(finding.ref in study.references)) out.push(`ref ${String(finding.ref)} is not a reference of study ${study.topic}`)
  const dimension = isLoose ? undefined : study.dimensions.find(dim => dim.id === finding.dimension)
  if (!isLoose && !dimension) out.push(`dimension ${String(finding.dimension)} is not a dimension of study ${study.topic}`)
  if (finding.answer === undefined) out.push('answer is required')
  else if (dimension) {
    const problem = answerIssue(dimension, finding.answer)
    if (problem) out.push(problem)
  } else if (isLoose && finding.answer !== 'unknown' && (!isText(finding.answer) || finding.answer.length > MAX_SHORT_ANSWER)) {
    out.push(`answer must be a short text of at most ${MAX_SHORT_ANSWER} characters`)
  }
  const isUnknown = finding.answer === 'unknown'
  const evidence = Array.isArray(finding.evidence) ? (finding.evidence as Evidence[]) : undefined
  if (!evidence) out.push('evidence must be a list')
  if (isUnknown && (!Array.isArray(finding.searched) || finding.searched.length === 0 || !finding.searched.every(isText))) {
    out.push('an unknown answer needs searched: what was looked at')
  }
  if (!isUnknown && evidence?.length === 0) out.push('at least one evidence item is required')
  if (finding.kind === 'pain' && !isText(finding.detail)) out.push('a pain finding needs detail describing the pain')
  if (finding.kind === 'reuse') out.push(...reuseIssues(finding, evidence ?? []))
  else if (finding.reuse !== undefined) out.push('reuse only applies to kind reuse')
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
  if (evidence && !isUnknown) {
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
  if (!(study.criteria ?? []).some(criterion => criterion.id === score.criterion)) out.push(`criterion ${String(score.criterion)} is not a criterion of study ${study.topic}`)
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
  return citationsOf(notes, topic)
    .filter(cite => !index.get(cite.topic)?.has(cite.id))
    .map(cite => error(file, `citation ${cite.raw} does not resolve`))
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

/**
 * research finish checks a brief's citations once. Afterwards a cited finding
 * that lost its footing asks for a refresh and never fails a later check.
 */
export function briefGate(study: Study, notes: string, findings: readonly Finding[], file: string): Issue[] {
  if (study.status !== 'brief') return []
  const byId = new Map(findings.map(finding => [finding.id, finding]))
  const since = study.finished?.at ?? 'it was finished'
  const ids = new Set(citationsOf(notes, study.topic).filter(cite => cite.topic === study.topic).map(cite => cite.id))
  const out: Issue[] = []
  for (const id of ids) {
    const finding = byId.get(id)
    if (finding === undefined) continue
    const change = finding.status !== 'current' ? `is ${finding.status}` : finding.verified === undefined ? 'is unverified' : undefined
    if (change !== undefined) out.push(warn(file, `the brief cites ${id}, which ${change} since ${since}; refresh the brief`, 'freshness'))
  }
  return out
}
