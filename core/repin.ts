import type { Ctx } from './io.ts'
import { join, parseRepoUrl, treeDir } from './paths.ts'
import { locateQuote } from './normalize.ts'
import { lineRange } from './evidence.ts'
import { ensureTree } from './clone.ts'
import { listTopics, loadFindings, loadReferences, saveFindings, saveReferences } from './store.ts'
import { CODE_KINDS, isSha } from './validate.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

export type RepinResult = { pins: { url: string; sha: string }[]; moved: string[]; drifted: string[] }

async function remoteHead(ctx: Ctx, url: string): Promise<string | undefined> {
  const listed = await ctx.io.run(['git', 'ls-remote', '--', url, 'HEAD'])
  const sha = listed.stdout.split(/\s+/)[0]
  return listed.exitCode === 0 && isSha(sha) ? sha : undefined
}

/** Moves a reference to a new commit; code findings follow their quote or drift. */
export async function repin(ctx: Ctx, refId: string, toSha?: string): Promise<OpResult<RepinResult>> {
  const references = await loadReferences(ctx.io, ctx.cfg)
  const ref = references.find(candidate => candidate.id === refId)
  if (ref === undefined) return fail(`reference ${refId} is not in references.yaml`)
  const repos = (ref.repos ?? []).filter(repo => repo.url !== 'self')
  if (repos.length === 0) return fail(`reference ${refId} has no repositories to pin`)
  if (toSha !== undefined && (!isSha(toSha) || repos.length > 1)) {
    return fail('--to takes a full 40-character sha and works for a reference with exactly one repository')
  }
  const result: RepinResult = { pins: [], moved: [], drifted: [] }
  const topics = await listTopics(ctx.io, ctx.cfg)
  for (const repo of repos) {
    try {
      parseRepoUrl(repo.url)
    } catch (problem) {
      return fail((problem as Error).message)
    }
    const sha = toSha ?? (await remoteHead(ctx, repo.url))
    if (sha === undefined) return fail(`cannot resolve HEAD of ${repo.url}`)
    const tree = await ensureTree(ctx, repo.url, sha)
    if (!tree.ok) return tree
    const previous = repo.pin
    if (previous !== undefined && previous !== sha) {
      for (const topic of topics) {
        const findings = await loadFindings(ctx.io, ctx.cfg, topic)
        let isChanged = false
        for (const finding of findings) {
          for (const item of finding.evidence) {
            if (!CODE_KINDS.includes(item.kind) || item.repo !== repo.url || item.sha !== previous) continue
            isChanged = true
            const text = await ctx.io.readText(join(treeDir(ctx.cfg, repo.url, sha), item.path ?? ''))
            const found = text === undefined ? undefined : locateQuote(text, item.quote)
            if (found === undefined) {
              finding.status = 'drifted'
              result.drifted.push(`${topic}/${finding.id}`)
              continue
            }
            item.sha = sha
            item.lines = lineRange(found)
            result.moved.push(`${topic}/${finding.id}`)
          }
        }
        if (isChanged) await saveFindings(ctx.io, ctx.cfg, topic, findings)
      }
    }
    repo.pin = sha
    repo.pinned_at = ctx.today
    result.pins.push({ url: repo.url, sha })
  }
  await saveReferences(ctx.io, ctx.cfg, references)
  return ok(result)
}
