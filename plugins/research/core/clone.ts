import type { Ctx } from './io.ts'
import { join, treeDir } from './paths.ts'
import { loadReferences } from './store.ts'
import { isSha } from './validate.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

async function headOf(ctx: Ctx, dir: string): Promise<string | undefined> {
  const head = await ctx.io.run(['git', '-C', dir, 'rev-parse', 'HEAD'])
  return head.exitCode === 0 ? head.stdout.trim() : undefined
}

/** A shallow checkout of exactly one commit, kept per sha under the cache. */
export async function ensureTree(ctx: Ctx, url: string, sha: string): Promise<OpResult<string>> {
  // Both reach git's argv: a value starting with "-" would be read as an option (--upload-pack runs commands).
  if (!isSha(sha)) return fail(`${sha} is not a full 40-character sha`)
  let dir: string
  try {
    dir = treeDir(ctx.cfg, url, sha)
  } catch (problem) {
    return fail((problem as Error).message)
  }
  if ((await headOf(ctx, dir)) === sha) return ok(dir)
  const steps: string[][] = []
  if (!(await ctx.io.exists(join(dir, '.git')))) {
    steps.push(['git', 'init', '-q', dir], ['git', '-C', dir, 'remote', 'add', '--', 'origin', url])
  }
  steps.push(
    ['git', '-C', dir, 'fetch', '-q', '--depth', '1', '--', 'origin', sha],
    ['git', '-C', dir, '-c', 'advice.detachedHead=false', '-c', 'core.symlinks=false', 'checkout', '-q', '--detach', 'FETCH_HEAD'],
  )
  for (const argv of steps) {
    const done = await ctx.io.run(argv)
    if (done.exitCode !== 0) return fail(`${argv.join(' ')} failed: ${done.stderr.trim()}`)
  }
  return (await headOf(ctx, dir)) === sha ? ok(dir) : fail(`the checkout of ${url} did not land on ${sha}`)
}

export async function cloneRef(ctx: Ctx, refId: string): Promise<OpResult<string[]>> {
  const ref = (await loadReferences(ctx.io, ctx.cfg)).find(candidate => candidate.id === refId)
  if (ref === undefined) return fail(`reference ${refId} is not in references.yaml`)
  const repos = (ref.repos ?? []).filter(repo => repo.url !== 'self')
  if (repos.length === 0) return fail(`reference ${refId} has no repositories to clone`)
  const dirs: string[] = []
  for (const repo of repos) {
    if (repo.pin === undefined) return fail(`${repo.url} has no pin; run research repin ${refId}`)
    const tree = await ensureTree(ctx, repo.url, repo.pin)
    if (!tree.ok) return tree
    dirs.push(tree.value)
  }
  return ok(dirs)
}
