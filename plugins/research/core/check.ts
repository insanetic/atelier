import type { Ctx } from './io.ts'
import type { Finding, Issue, Reference, Study } from './types.ts'
import { files } from './paths.ts'
import { listTopics, loadNotes, readYaml } from './store.ts'
import { citationIssues, decidedGate, validateFinding, validateFindings, validateReferences, validateScores, validateStudy } from './validate.ts'
import { isStale, stalePins } from './fresh.ts'

type Bundle = { topic: string; study: Study; findings: Finding[]; ids: Set<string> }

const error = (file: string, message: string): Issue => ({ level: 'error', kind: 'schema', file, message })
const stale = (file: string, message: string): Issue => ({ level: 'warn', kind: 'freshness', file, message })
const idOf = (item: unknown) => (item !== null && typeof item === 'object' ? (item as { id?: unknown }).id : undefined)
const isMapping = (item: unknown): item is Record<string, unknown> => item !== null && typeof item === 'object' && !Array.isArray(item)

/** Every schema, integrity and freshness rule, offline: no fetches and no git. */
export async function runCheck(ctx: Ctx): Promise<Issue[]> {
  const issues: Issue[] = []
  const refsFile = files.references(ctx.cfg)
  const refs = await readYaml(ctx.io, refsFile)
  if (refs.error !== undefined) issues.push(error(refsFile, refs.error))
  else if (!refs.missing) issues.push(...validateReferences(refs.data, refsFile))
  const references = Array.isArray(refs.data) ? (refs.data as unknown[]).filter(isMapping).map(item => item as Reference) : []
  const refIds = new Set(references.map(ref => ref.id))
  const bundles: Bundle[] = []
  for (const topic of await listTopics(ctx.io, ctx.cfg)) {
    const studyFile = files.study(ctx.cfg, topic)
    const loaded = await readYaml(ctx.io, studyFile)
    if (loaded.missing || loaded.error !== undefined) {
      issues.push(error(studyFile, loaded.error ?? 'study.yaml is missing'))
      continue
    }
    const studyIssues = validateStudy(loaded.data, topic, refIds, studyFile)
    issues.push(...studyIssues)
    if (studyIssues.some(issue => issue.level === 'error')) continue
    const study = loaded.data as Study
    const findingsFile = files.findings(ctx.cfg, topic)
    const found = await readYaml(ctx.io, findingsFile)
    if (found.error !== undefined) {
      issues.push(error(findingsFile, found.error))
      continue
    }
    const data = found.missing ? [] : found.data
    issues.push(...validateFindings(data, study, findingsFile))
    const entries: unknown[] = Array.isArray(data) ? data : []
    // The gates below read dates and statuses: they only see records that passed validation.
    const valid = entries.filter(raw => validateFinding(raw, study, findingsFile).length === 0) as Finding[]
    const ids = new Set(entries.map(idOf).filter((id): id is string => typeof id === 'string'))
    bundles.push({ topic, study, findings: valid, ids })
  }
  const index = new Map(bundles.map(bundle => [bundle.topic, bundle.ids]))
  for (const { topic, study, findings } of bundles) {
    const scoresFile = files.assessment(ctx.cfg, topic)
    const scores = await readYaml(ctx.io, scoresFile)
    if (scores.error !== undefined) issues.push(error(scoresFile, scores.error))
    else if (!scores.missing) issues.push(...validateScores(scores.data, study, index.get(topic) ?? new Set<string>(), scoresFile))
    issues.push(...citationIssues(await loadNotes(ctx.io, ctx.cfg, topic), topic, index, files.notes(ctx.cfg, topic)))
    issues.push(...decidedGate(study, findings, files.study(ctx.cfg, topic)))
    issues.push(...freshness(study, findings, ctx.today, files.findings(ctx.cfg, topic)))
  }
  for (const pin of stalePins(references, ctx.today)) {
    issues.push(stale(refsFile, `${pin.ref}: pin of ${pin.url} is from ${pin.pinned_at}; run research repin ${pin.ref}`))
  }
  return issues
}

function freshness(study: Study, findings: readonly Finding[], today: string, file: string): Issue[] {
  const out: Issue[] = []
  for (const finding of findings) {
    if (finding.status === 'drifted') {
      out.push(stale(file, `${finding.id}: drifted; its source no longer holds the quote`))
      continue
    }
    if (finding.status !== 'current' || finding.verified === undefined) continue
    const dimension = study.dimensions.find(dim => dim.id === finding.dimension)
    if (isStale(finding, dimension, today)) {
      out.push(stale(file, `${finding.id}: verified ${finding.verified.at}, past its ${dimension?.volatility ?? 'fast'} TTL`))
    }
  }
  return out
}

export function renderIssues(issues: readonly Issue[]): string {
  if (issues.length === 0) return 'research check: no issues'
  return issues.map(issue => `${issue.level} ${issue.file}: ${issue.message}`).join('\n')
}
