import type { Ctx } from './io.ts'
import { files } from './paths.ts'
import { loadAssessment, loadFindings, loadValidStudy, saveAssessment, saveFindings } from './store.ts'
import { deleteInYaml } from './yaml.ts'
import { KeyedLock } from './lock.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

export type DropResult = { findings: string[]; scores: number }

/** Takes a reference out of one study: its role, its findings and its scores. Citations left behind are research check's to report. */
export async function drop(ctx: Ctx, topic: string, ref: string, lock = new KeyedLock()): Promise<OpResult<DropResult>> {
  const loaded = await loadValidStudy(ctx, topic)
  if (!loaded.ok) return loaded
  if (!(ref in loaded.value.references)) return fail(`${ref} is not a reference of study ${topic}`)
  return lock.run(topic, async () => {
    const findings = await loadFindings(ctx.io, ctx.cfg, topic)
    const scores = await loadAssessment(ctx.io, ctx.cfg, topic)
    const path = files.study(ctx.cfg, topic)
    await ctx.io.writeText(path, deleteInYaml((await ctx.io.readText(path)) ?? '', ['references', ref]))
    await saveFindings(ctx.io, ctx.cfg, topic, findings.filter(finding => finding.ref !== ref))
    const kept = scores.filter(score => score.ref !== ref)
    await saveAssessment(ctx.io, ctx.cfg, topic, kept)
    return ok({ findings: findings.filter(finding => finding.ref === ref).map(finding => finding.id), scores: scores.length - kept.length })
  })
}
