import type { Ctx } from './io.ts'
import type { Answer, Evidence, Finding, FindingKind, Reuse, Score, Via } from './types.ts'
import { files } from './paths.ts'
import { TOPIC_RULE, isTopic, loadAssessment, loadFindings, loadValidStudy, saveAssessment, saveFindings } from './store.ts'
import { WEB_KINDS, canConfirm, methodOf, validateFinding, validateScore } from './validate.ts'
import { checkEvidence, findArchive } from './evidence.ts'
import { KeyedLock } from './lock.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

export type AddFindingInput = {
  study: string
  ref: string
  dimension?: string
  kind?: FindingKind
  answer: Answer
  detail?: string
  searched?: string[]
  evidence: Evidence[]
  reuse?: Reuse
  id?: string
}

export type VerifyInput = {
  study: string
  id: string
  outcome: 'confirmed' | 'likely' | 'disputed'
  browser_confirmed?: boolean
  by?: string
  note?: string
}

export type SetScoreInput = {
  study: string
  ref: string
  criterion: string
  level: number | 'unknown'
  because: string[]
  agent: string
  confirmed_by?: string
}

const OUTCOMES: readonly string[] = ['confirmed', 'likely', 'disputed']
const VIA_RANK: readonly Via[] = ['git', 'file', 'fetch', 'archive', 'browser']
const BROWSER = 'the verifier must confirm it in a browser'

function upsert<T>(list: readonly T[], isSame: (item: T) => boolean, item: T): T[] {
  const index = list.findIndex(isSame)
  return index === -1 ? [...list, item] : list.map((existing, i) => (i === index ? item : existing))
}

function nextId(findings: readonly Finding[], ref: string, segment: string, kind: FindingKind, first: number): string {
  const base = `${ref}.${segment}`
  if (kind === 'answer') return base
  const taken = new Set(findings.map(finding => finding.id))
  let n = first
  while (taken.has(`${base}.${n}`)) n++
  return `${base}.${n}`
}

const sameRecord = (a: Finding, b: Finding) => JSON.stringify([a.answer, a.evidence]) === JSON.stringify([b.answer, b.evidence])

/**
 * Validates and checks a finding, then writes it. The network work runs outside
 * the study lock; only load, upsert and save hold it, so parallel researchers
 * neither lose records nor wait on each other's fetches.
 */
export async function addFinding(ctx: Ctx, input: AddFindingInput, lock = new KeyedLock()): Promise<OpResult<Finding>> {
  if (!isTopic(input.study)) return fail(TOPIC_RULE)
  if (!Array.isArray(input.evidence)) return fail('evidence must be a list')
  const loaded = await loadValidStudy(ctx, input.study)
  if (!loaded.ok) return loaded
  const kind = input.kind ?? 'answer'
  // A pain or reuse finding without a dimension is numbered from 1 under its kind; one under a dimension starts at 2, after the answer.
  const segment = input.dimension ?? kind
  const first = input.dimension === undefined ? 1 : 2
  const evidence: Evidence[] = input.evidence.map(item =>
    WEB_KINDS.includes(item.kind) && item.retrieved === undefined ? { ...item, retrieved: ctx.today } : { ...item },
  )
  const draft: Finding = {
    id: input.id ?? (kind === 'answer' ? `${input.ref}.${segment}` : `${input.ref}.${segment}.${first}`),
    ref: input.ref,
    ...(input.dimension === undefined ? {} : { dimension: input.dimension }),
    kind,
    answer: input.answer,
    evidence,
    method: methodOf(evidence),
    confidence: 'unverified',
    status: 'current',
  }
  if (input.detail !== undefined) draft.detail = input.detail
  if (input.reuse !== undefined) draft.reuse = input.reuse
  if (input.searched !== undefined) draft.searched = input.searched
  const invalid = validateFinding(draft, loaded.value, files.findings(ctx.cfg, input.study))
  if (invalid.length > 0) return fail(...invalid.map(issue => issue.message))
  for (const item of evidence) {
    if (!WEB_KINDS.includes(item.kind) || item.archive !== undefined || item.url === undefined) continue
    const archived = await findArchive(ctx.io, item.url)
    if (archived !== undefined) item.archive = archived
  }
  const errors: string[] = []
  const warnings: string[] = []
  const studyDir = files.studyDir(ctx.cfg, input.study)
  for (const [index, item] of evidence.entries()) {
    const outcome = await checkEvidence(ctx, studyDir, item)
    if (outcome.ok) continue
    if (outcome.miss === 'hidden' || outcome.miss === 'blocked') warnings.push(`evidence[${index}]: ${outcome.reason}; ${BROWSER}`)
    else errors.push(`evidence[${index}]: ${outcome.reason}`)
  }
  if (errors.length > 0) return fail(...errors)
  const finding = await lock.run(input.study, async () => {
    const findings = await loadFindings(ctx.io, ctx.cfg, input.study)
    const stored: Finding = { ...draft, id: input.id ?? nextId(findings, input.ref, segment, kind, first) }
    await saveFindings(ctx.io, ctx.cfg, input.study, upsert(findings, existing => existing.id === stored.id, stored))
    return stored
  })
  return ok(finding, warnings)
}

export async function verifyFinding(ctx: Ctx, input: VerifyInput, lock = new KeyedLock()): Promise<OpResult<Finding>> {
  if (!isTopic(input.study)) return fail(TOPIC_RULE)
  if (!OUTCOMES.includes(input.outcome)) return fail('outcome must be confirmed, likely or disputed')
  const finding = (await loadFindings(ctx.io, ctx.cfg, input.study)).find(existing => existing.id === input.id)
  if (finding === undefined) return fail(`finding ${input.id} does not exist in study ${input.study}`)
  let updated: Finding
  if (input.outcome === 'disputed') {
    const { verified: _dropped, ...rest } = finding
    updated = { ...rest, confidence: 'unverified', status: 'disputed' }
  } else {
    if (finding.answer === 'unknown') return fail('an unknown answer cannot be verified; research it or leave it unverified')
    if (input.outcome === 'confirmed' && !canConfirm(finding)) {
      return fail('confirmed needs primary evidence (code, api_spec, spec, docs, tested) or secondary sources from two different hosts; use likely')
    }
    const vias: Via[] = []
    const studyDir = files.studyDir(ctx.cfg, input.study)
    for (const [index, item] of finding.evidence.entries()) {
      const outcome = await checkEvidence(ctx, studyDir, item)
      if (outcome.ok) vias.push(outcome.via)
      else if ((outcome.miss === 'hidden' || outcome.miss === 'blocked') && input.browser_confirmed === true) vias.push('browser')
      else return fail(`evidence[${index}]: ${outcome.reason}`)
    }
    const via = VIA_RANK.find(candidate => vias.includes(candidate)) ?? 'browser'
    updated = { ...finding, confidence: input.outcome, status: 'current', verified: { by: input.by ?? 'verifier', at: ctx.today, via } }
  }
  if (input.note !== undefined) updated.note = input.note
  return lock.run(input.study, async () => {
    const findings = await loadFindings(ctx.io, ctx.cfg, input.study)
    const current = findings.find(existing => existing.id === input.id)
    if (current === undefined || !sameRecord(current, finding)) {
      return fail<Finding>(`finding ${input.id} changed while it was being verified; verify it again`)
    }
    await saveFindings(ctx.io, ctx.cfg, input.study, upsert(findings, existing => existing.id === updated.id, updated))
    return ok(updated)
  })
}

export async function setScore(ctx: Ctx, input: SetScoreInput, lock = new KeyedLock()): Promise<OpResult<Score>> {
  if (!isTopic(input.study)) return fail(TOPIC_RULE)
  const loaded = await loadValidStudy(ctx, input.study)
  if (!loaded.ok) return loaded
  return lock.run(input.study, async () => {
    const findings = await loadFindings(ctx.io, ctx.cfg, input.study)
    const by: Score['by'] = { agent: input.agent, at: ctx.today }
    if (input.confirmed_by !== undefined) by.confirmed_by = input.confirmed_by
    const score: Score = { ref: input.ref, criterion: input.criterion, level: input.level, because: input.because ?? [], by }
    const invalid = validateScore(score, loaded.value, new Set(findings.map(finding => finding.id)), files.assessment(ctx.cfg, input.study))
    if (invalid.length > 0) return fail<Score>(...invalid.map(issue => issue.message))
    const scores = await loadAssessment(ctx.io, ctx.cfg, input.study)
    const isSame = (existing: Score) => existing.ref === score.ref && existing.criterion === score.criterion
    await saveAssessment(ctx.io, ctx.cfg, input.study, upsert(scores, isSame, score))
    return ok(score)
  })
}

export function renderOp(result: OpResult<unknown>, success: string): string {
  if (!result.ok) return ['rejected:', ...result.errors.map(problem => `- ${problem}`)].join('\n')
  return [success, ...result.warnings.map(warning => `warning: ${warning}`)].join('\n')
}
