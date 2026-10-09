import type { Ctx } from './io.ts'
import type { Finding, FindingKind } from './types.ts'
import { stateOf } from './fresh.ts'
import type { CellState } from './fresh.ts'
import { describeFinding } from './matrix.ts'
import { isTopic, listTopics, loadFindings, loadReferences, loadStudy } from './store.ts'
import { validateFinding, validateStudy } from './validate.ts'

export type QueryInput = { ref?: string; dimension?: string; study?: string; state?: CellState; text?: string; id?: string; kind?: FindingKind }
export type QueryHit = { study: string; finding: Finding; state: CellState }

/** Searches valid findings of valid studies; `research check` is where broken records are reported. */
export async function query(ctx: Ctx, input: QueryInput): Promise<QueryHit[]> {
  if (input.study !== undefined && !isTopic(input.study)) return []
  const topics = input.study === undefined ? await listTopics(ctx.io, ctx.cfg) : [input.study]
  const refIds = new Set((await loadReferences(ctx.io, ctx.cfg)).map(ref => ref.id))
  const needle = input.text?.toLowerCase()
  const hits: QueryHit[] = []
  for (const topic of topics) {
    const study = await loadStudy(ctx.io, ctx.cfg, topic)
    if (study === undefined || validateStudy(study, topic, refIds, '').some(issue => issue.level === 'error')) continue
    for (const finding of await loadFindings(ctx.io, ctx.cfg, topic)) {
      if (validateFinding(finding, study, '').length > 0 || finding.status === 'superseded') continue
      if (input.id !== undefined && finding.id !== input.id) continue
      if (input.kind !== undefined && finding.kind !== input.kind) continue
      if (input.ref !== undefined && finding.ref !== input.ref) continue
      if (input.dimension !== undefined && finding.dimension !== input.dimension) continue
      const state = stateOf(finding, study.dimensions.find(dim => dim.id === finding.dimension), ctx.today)
      if (input.state !== undefined && state !== input.state) continue
      const haystack = JSON.stringify([finding.answer, finding.detail, finding.evidence.map(item => item.quote)]).toLowerCase()
      if (needle !== undefined && !haystack.includes(needle)) continue
      hits.push({ study: topic, finding, state })
    }
  }
  return hits
}

/** One header line per hit, then its detail, note and every evidence source with its quote. */
export function renderHits(hits: readonly QueryHit[]): string {
  if (hits.length === 0) return 'no findings match'
  return hits
    .map(({ study, finding, state }) => {
      const header = `${study}/${finding.id} [${state}] ${finding.ref} ${finding.dimension ?? finding.kind} = ${String(finding.answer)}`
      return [header, ...describeFinding(finding).slice(1).map(line => `  ${line}`)].join('\n')
    })
    .join('\n')
}
