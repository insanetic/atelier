import type { Ctx } from './io.ts'
import type { Answer, Evidence, Finding, FindingKind, Score, Study, Via } from './types.ts'
import { files } from './paths.ts'
import { loadAssessment, loadFindings, loadReferences, loadStudy, saveAssessment, saveFindings } from './store.ts'
import { WEB_KINDS, canConfirm, methodOf, validateFinding, validateScore, validateStudy } from './validate.ts'
import { checkEvidence, findArchive, requestArchive } from './evidence.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

export type AddFindingInput = {
  study: string
  ref: string
  dimension: string
  kind?: FindingKind
  answer: Answer
  detail?: string
  searched?: string[]
  evidence: Evidence[]
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

const VIA_RANK: readonly Via[] = ['git', 'file', 'fetch', 'archive', 'browser']

function upsert<T>(list: readonly T[], isSame: (item: T) => boolean, item: T): T[] {
  const index = list.findIndex(isSame)
  return index === -1 ? [...list, item] : list.map((existing, i) => (i === index ? item : existing))
}

function nextId(findings: readonly Finding[], ref: string, dimension: string, kind: FindingKind): string {
  const base = `${ref}.${dimension}`
  if (kind === 'answer') return base
  const taken = new Set(findings.map(finding => finding.id))
  let n = 2
  while (taken.has(`${base}.${n}`)) n++
  return `${base}.${n}`
}

async function validStudy(ctx: Ctx, topic: string): Promise<OpResult<Study>> {
  const study = await loadStudy(ctx.io, ctx.cfg, topic)
  if (study === undefined) return fail(`study ${topic} does not exist; run /study ${topic}`)
  const refIds = new Set((await loadReferences(ctx.io, ctx.cfg)).map(ref => ref.id))
  const errors = validateStudy(study, topic, refIds, files.study(ctx.cfg, topic)).filter(issue => issue.level === 'error')
  if (errors.length > 0) return fail(`study ${topic} has errors: ${errors.map(issue => issue.message).join('; ')}`)
  return ok(study)
}

export async function addFinding(ctx: Ctx, input: AddFindingInput): Promise<OpResult<Finding>> {
  if (typeof input.study !== 'string' || !Array.isArray(input.evidence)) return fail('study (text) and evidence (a list) are required')
  const loaded = await validStudy(ctx, input.study)
  if (!loaded.ok) return loaded
  const findings = await loadFindings(ctx.io, ctx.cfg, input.study)
  const kind = input.kind ?? 'answer'
  const evidence: Evidence[] = input.evidence.map(item =>
    WEB_KINDS.includes(item.kind) && item.retrieved === undefined ? { ...item, retrieved: ctx.today } : { ...item },
  )
  const finding: Finding = {
    id: input.id ?? nextId(findings, input.ref, input.dimension, kind),
    ref: input.ref,
    dimension: input.dimension,
    kind,
    answer: input.answer,
    evidence,
    method: methodOf(evidence),
    confidence: 'unverified',
    status: 'current',
  }
  if (input.detail !== undefined) finding.detail = input.detail
  if (input.searched !== undefined) finding.searched = input.searched
  const invalid = validateFinding(finding, loaded.value, files.findings(ctx.cfg, input.study))
  if (invalid.length > 0) return fail(...invalid.map(issue => issue.message))
  const errors: string[] = []
  const warnings: string[] = []
  const studyDir = files.studyDir(ctx.cfg, input.study)
  for (const [index, item] of evidence.entries()) {
    const outcome = await checkEvidence(ctx, studyDir, item)
    if (outcome.ok) continue
    if (outcome.needsBrowser) warnings.push(`evidence[${index}]: ${outcome.reason}; the verifier must confirm it in a browser`)
    else errors.push(`evidence[${index}]: ${outcome.reason}`)
  }
  if (errors.length > 0) return fail(...errors)
  for (const item of evidence) {
    if (!WEB_KINDS.includes(item.kind) || item.archive !== undefined || item.url === undefined) continue
    const archived = await findArchive(ctx.io, item.url)
    if (archived === undefined) await requestArchive(ctx.io, item.url)
    else item.archive = archived
  }
  await saveFindings(ctx.io, ctx.cfg, input.study, upsert(findings, existing => existing.id === finding.id, finding))
  return ok(finding, warnings)
}

export async function verifyFinding(ctx: Ctx, input: VerifyInput): Promise<OpResult<Finding>> {
  const findings = await loadFindings(ctx.io, ctx.cfg, input.study)
  const finding = findings.find(existing => existing.id === input.id)
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
      else if (outcome.needsBrowser && input.browser_confirmed === true) vias.push('browser')
      else return fail(`evidence[${index}]: ${outcome.reason}`)
    }
    const via = VIA_RANK.find(candidate => vias.includes(candidate)) ?? 'browser'
    updated = { ...finding, confidence: input.outcome, status: 'current', verified: { by: input.by ?? 'verifier', at: ctx.today, via } }
  }
  if (input.note !== undefined) updated.note = input.note
  await saveFindings(ctx.io, ctx.cfg, input.study, upsert(findings, existing => existing.id === updated.id, updated))
  return ok(updated)
}

export async function setScore(ctx: Ctx, input: SetScoreInput): Promise<OpResult<Score>> {
  const loaded = await validStudy(ctx, input.study)
  if (!loaded.ok) return loaded
  const findings = await loadFindings(ctx.io, ctx.cfg, input.study)
  const by: Score['by'] = { agent: input.agent, at: ctx.today }
  if (input.confirmed_by !== undefined) by.confirmed_by = input.confirmed_by
  const score: Score = { ref: input.ref, criterion: input.criterion, level: input.level, because: input.because ?? [], by }
  const invalid = validateScore(score, loaded.value, new Set(findings.map(finding => finding.id)), files.assessment(ctx.cfg, input.study))
  if (invalid.length > 0) return fail(...invalid.map(issue => issue.message))
  const scores = await loadAssessment(ctx.io, ctx.cfg, input.study)
  await saveAssessment(ctx.io, ctx.cfg, input.study, upsert(scores, existing => existing.ref === score.ref && existing.criterion === score.criterion, score))
  return ok(score)
}

export function renderOp(result: OpResult<unknown>, success: string): string {
  if (!result.ok) return ['rejected:', ...result.errors.map(problem => `- ${problem}`)].join('\n')
  return [success, ...result.warnings.map(warning => `warning: ${warning}`)].join('\n')
}
