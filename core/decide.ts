import type { Ctx } from './io.ts'
import type { Decision } from './types.ts'
import { files } from './paths.ts'
import { isStale } from './fresh.ts'
import { loadFindings, loadValidStudy } from './store.ts'
import { setInYaml } from './yaml.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

export type DecideInput = { study: string; chosen: string; cites: string[]; revisit_when: string }

/**
 * The freshness gate of a study: refuses citations that are not current,
 * verified and within their TTL, then records the decision with a snapshot of
 * each one. study.yaml keeps its hand-written comments.
 */
export async function decide(ctx: Ctx, input: DecideInput): Promise<OpResult<Decision>> {
  const problems: string[] = []
  if (typeof input.chosen !== 'string' || input.chosen.trim() === '') problems.push('chosen is required')
  if (!Array.isArray(input.cites) || input.cites.length === 0) problems.push('cites must name at least one finding')
  if (typeof input.revisit_when !== 'string' || input.revisit_when.trim() === '') problems.push('revisit_when is required')
  if (problems.length > 0) return fail(...problems)
  const loaded = await loadValidStudy(ctx, input.study)
  if (!loaded.ok) return loaded
  const byId = new Map((await loadFindings(ctx.io, ctx.cfg, input.study)).map(finding => [finding.id, finding]))
  const snapshot: NonNullable<Decision['snapshot']> = {}
  for (const id of input.cites) {
    const finding = byId.get(id)
    const dimension = loaded.value.dimensions.find(dim => dim.id === finding?.dimension)
    if (finding === undefined) problems.push(`${id} does not exist`)
    else if (finding.status === 'disputed') problems.push(`${id} is disputed`)
    else if (finding.status === 'drifted') problems.push(`${id} has drifted; re-research it first`)
    else if (finding.status !== 'current') problems.push(`${id} is ${finding.status}`)
    else if (finding.verified === undefined || finding.confidence === 'unverified') problems.push(`${id} is not verified`)
    else if (isStale(finding, dimension, ctx.today)) problems.push(`${id} is past its ${dimension?.volatility ?? 'fast'} TTL; re-verify it first`)
    else snapshot[id] = { verified_at: finding.verified.at, confidence: finding.confidence }
  }
  if (problems.length > 0) return fail(...problems)
  const decision: Decision = { chosen: input.chosen, decided_at: ctx.today, cites: input.cites, revisit_when: input.revisit_when, snapshot }
  const path = files.study(ctx.cfg, input.study)
  await ctx.io.writeText(path, setInYaml((await ctx.io.readText(path)) ?? '', { status: 'decided', decision }))
  return ok(decision)
}
