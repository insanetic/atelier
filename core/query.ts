import type { Ctx } from './io.ts'
import type { Finding } from './types.ts'
import { stateOf } from './fresh.ts'
import type { CellState } from './fresh.ts'
import { listTopics, loadFindings, loadStudy } from './store.ts'

export type QueryInput = { ref?: string; dimension?: string; study?: string; state?: CellState; text?: string }
export type QueryHit = { study: string; finding: Finding; state: CellState }

export async function query(ctx: Ctx, input: QueryInput): Promise<QueryHit[]> {
  const topics = input.study === undefined ? await listTopics(ctx.io, ctx.cfg) : [input.study]
  const needle = input.text?.toLowerCase()
  const hits: QueryHit[] = []
  for (const topic of topics) {
    const study = await loadStudy(ctx.io, ctx.cfg, topic)
    if (study === undefined) continue
    for (const finding of await loadFindings(ctx.io, ctx.cfg, topic)) {
      if (finding.status === 'superseded') continue
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

export function renderHits(hits: readonly QueryHit[]): string {
  if (hits.length === 0) return 'no findings match'
  return hits
    .map(({ study, finding, state }) => {
      const detail = finding.detail === undefined ? '' : ` (${finding.detail})`
      return `${study}/${finding.id} [${state}] ${finding.ref} ${finding.dimension} = ${String(finding.answer)}${detail}`
    })
    .join('\n')
}
