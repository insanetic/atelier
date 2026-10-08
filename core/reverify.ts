import type { Ctx } from './io.ts'
import type { Finding } from './types.ts'
import { files } from './paths.ts'
import { listTopics, loadFindings, loadStudy, saveFindings } from './store.ts'
import { CODE_KINDS, WEB_KINDS } from './validate.ts'
import { isStale } from './fresh.ts'
import { cachedIo, checkEvidence, findArchive, requestArchive } from './evidence.ts'
import { ensureTree } from './clone.ts'

export type ReverifyReport = { refreshed: string[]; drifted: string[]; archived: string[]; skipped: string[] }

type Verdict = { kind: 'ok' } | { kind: 'drifted' } | { kind: 'skipped'; reason: string }

/** Re-runs the deterministic checks; no model involved. Each URL is fetched once per run. */
export async function reverify(ctx: Ctx, options: { dueOnly: boolean }): Promise<ReverifyReport> {
  const run: Ctx = { ...ctx, io: cachedIo(ctx.io) }
  const report: ReverifyReport = { refreshed: [], drifted: [], archived: [], skipped: [] }
  for (const topic of await listTopics(run.io, run.cfg)) {
    const study = await loadStudy(run.io, run.cfg, topic)
    if (study === undefined) continue
    const findings = await loadFindings(run.io, run.cfg, topic)
    let isChanged = false
    for (const finding of findings) {
      if (finding.status !== 'current') continue
      const label = `${topic}/${finding.id}`
      for (const item of finding.evidence) {
        if (!WEB_KINDS.includes(item.kind) || item.archive !== undefined || item.url === undefined) continue
        const archived = await findArchive(run.io, item.url)
        if (archived === undefined) {
          await requestArchive(run.io, item.url)
          continue
        }
        item.archive = archived
        isChanged = true
        report.archived.push(label)
      }
      const verified = finding.verified
      if (verified === undefined) continue
      const dimension = study.dimensions.find(dim => dim.id === finding.dimension)
      if (options.dueOnly && !isStale(finding, dimension, run.today)) continue
      const verdict = await recheck(run, topic, finding)
      if (verdict.kind === 'skipped') {
        report.skipped.push(`${label} (${verdict.reason})`)
        continue
      }
      isChanged = true
      if (verdict.kind === 'ok') {
        finding.verified = { ...verified, at: run.today }
        report.refreshed.push(label)
      } else {
        finding.status = 'drifted'
        report.drifted.push(label)
      }
    }
    if (isChanged) await saveFindings(run.io, run.cfg, topic, findings)
  }
  return report
}

async function recheck(ctx: Ctx, topic: string, finding: Finding): Promise<Verdict> {
  for (const item of finding.evidence) {
    if (CODE_KINDS.includes(item.kind) && item.repo !== undefined && item.repo !== 'self' && item.sha !== undefined) {
      const tree = await ensureTree(ctx, item.repo, item.sha)
      if (!tree.ok) return { kind: 'skipped', reason: tree.errors.join('; ') }
    }
    const outcome = await checkEvidence(ctx, files.studyDir(ctx.cfg, topic), item)
    if (outcome.ok) continue
    // Only a source that answered without the quote has changed; one that could not be read says nothing.
    if (outcome.miss === 'blocked' || outcome.miss === 'unreachable') return { kind: 'skipped', reason: outcome.reason }
    if (outcome.miss === 'hidden' && finding.verified?.via === 'browser') return { kind: 'skipped', reason: outcome.reason }
    return { kind: 'drifted' }
  }
  return { kind: 'ok' }
}

export function renderReport(report: ReverifyReport): string {
  const section = (title: string, ids: readonly string[]) => (ids.length === 0 ? [] : [`## ${title} (${ids.length})`, ...ids.map(id => `- ${id}`), ''])
  const body = [
    ...section('Drifted', report.drifted),
    ...section('Refreshed', report.refreshed),
    ...section('Archived', report.archived),
    ...section('Skipped (need a browser check)', report.skipped),
  ]
  return body.length === 0 ? 'research reverify: nothing changed' : ['# research reverify', '', ...body].join('\n')
}
