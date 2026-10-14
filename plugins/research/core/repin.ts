import type { Ctx } from './io.ts'
import type { Finding } from './types.ts'
import { join, parseRepoUrl } from './paths.ts'
import { locateQuote } from './normalize.ts'
import { lineRange } from './evidence.ts'
import { ensureTree } from './clone.ts'
import { listTopics, loadFindings, loadReferences, mergeFindings } from './store.ts'
import { files } from './paths.ts'
import { setPathsInYaml } from './yaml.ts'
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
  // Every repository resolves and checks out before anything is written: a failure leaves pins and findings as they were.
  const targets: { repo: (typeof repos)[number]; sha: string; dir: string }[] = []
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
    targets.push({ repo, sha, dir: tree.value })
  }
  const moves = targets.filter(target => target.repo.pin !== undefined && target.repo.pin !== target.sha)
  if (moves.length > 0) {
    for (const topic of await listTopics(ctx.io, ctx.cfg)) {
      const findings = await loadFindings(ctx.io, ctx.cfg, topic)
      const before = new Map(findings.map(finding => [finding.id, JSON.stringify(finding)]))
      const changed = new Set<Finding>()
      for (const finding of findings) {
        for (const item of finding.evidence) {
          const target = moves.find(move => item.repo === move.repo.url && item.sha === move.repo.pin)
          if (!CODE_KINDS.includes(item.kind) || target === undefined) continue
          const text = await ctx.io.readText(join(target.dir, item.path ?? ''))
          const found = text === undefined ? undefined : locateQuote(text, item.quote)
          if (found === undefined) {
            // A disputed or superseded finding keeps its status: drifted would lose why it was set aside.
            if (finding.status === 'current') {
              finding.status = 'drifted'
              changed.add(finding)
            }
            result.drifted.push(`${topic}/${finding.id}`)
            continue
          }
          item.sha = target.sha
          item.lines = lineRange(found)
          changed.add(finding)
          result.moved.push(`${topic}/${finding.id}`)
        }
      }
      if (changed.size > 0) await mergeFindings(ctx.io, ctx.cfg, topic, before, [...changed])
    }
  }
  for (const { repo, sha } of targets) {
    repo.pin = sha
    repo.pinned_at = ctx.today
    result.pins.push({ url: repo.url, sha })
  }
  // references.yaml is edited by hand: set the pins in place so its comments and layout survive.
  const at = references.indexOf(ref)
  const updates = repos.flatMap(repo => {
    const index = (ref.repos ?? []).indexOf(repo)
    return [
      [[at, 'repos', index, 'pin'], repo.pin],
      [[at, 'repos', index, 'pinned_at'], repo.pinned_at],
    ] as const
  })
  const path = files.references(ctx.cfg)
  await ctx.io.writeText(path, setPathsInYaml((await ctx.io.readText(path)) ?? '', updates))
  return ok(result)
}
