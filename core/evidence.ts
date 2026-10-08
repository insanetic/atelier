import type { Ctx, FetchResult, Io } from './io.ts'
import type { Evidence, Via } from './types.ts'
import { join, treeDir } from './paths.ts'
import { containsQuote, htmlToText, locateQuote } from './normalize.ts'
import { CODE_KINDS, parseLines } from './validate.ts'

export const MAX_ARTIFACT_BYTES = 300 * 1024

export type CheckOutcome = { ok: true; via: Via } | { ok: false; reason: string; needsBrowser: boolean }

const pass = (via: Via): CheckOutcome => ({ ok: true, via })
const miss = (reason: string, needsBrowser = false): CheckOutcome => ({ ok: false, reason, needsBrowser })
const isReachable = (page: FetchResult) => page.status >= 200 && page.status < 400

export function lineRange(found: { start: number; end: number }): string {
  return found.start === found.end ? `${found.start}` : `${found.start}-${found.end}`
}

export async function readAtSha(ctx: Ctx, repo: string, sha: string, path: string): Promise<string | undefined> {
  if (repo === 'self') {
    const shown = await ctx.io.run(['git', 'show', `${sha}:${path}`], ctx.cfg.root)
    return shown.exitCode === 0 ? shown.stdout : undefined
  }
  return ctx.io.readText(join(treeDir(ctx.cfg, repo, sha), path))
}

export async function checkEvidence(ctx: Ctx, studyDir: string, evidence: Evidence): Promise<CheckOutcome> {
  if (CODE_KINDS.includes(evidence.kind)) return checkCode(ctx, evidence)
  if (evidence.kind === 'tested') return checkArtifact(ctx.io, studyDir, evidence)
  return checkWeb(ctx.io, evidence)
}

async function checkCode(ctx: Ctx, evidence: Evidence): Promise<CheckOutcome> {
  const { repo = '', sha = '', path = '', lines = '' } = evidence
  const text = await readAtSha(ctx, repo, sha, path)
  if (text === undefined) return miss(`${path} is not available at ${sha.slice(0, 12)}; clone the reference first`)
  const [first, last] = parseLines(lines)
  if (containsQuote(text.split('\n').slice(first - 1, last).join('\n'), evidence.quote)) return pass('git')
  const found = locateQuote(text, evidence.quote)
  return miss(found === undefined ? `the quote is not in ${path}` : `the quote is at lines ${lineRange(found)}, not ${lines}`)
}

async function checkArtifact(io: Io, studyDir: string, evidence: Evidence): Promise<CheckOutcome> {
  const size = await io.size(join(studyDir, evidence.artifact ?? ''))
  if (size === undefined) return miss(`artifact ${evidence.artifact} does not exist`)
  if (size > MAX_ARTIFACT_BYTES) return miss(`artifact ${evidence.artifact} is ${size} bytes; the cap is ${MAX_ARTIFACT_BYTES}`)
  return pass('file')
}

/**
 * A reachable page decides on its own: the archive would hide a changed page.
 * The archive only stands in when the page itself is gone.
 */
async function checkWeb(io: Io, evidence: Evidence): Promise<CheckOutcome> {
  const url = evidence.url ?? ''
  const live = await io.fetchText(url)
  if (isReachable(live)) {
    return containsQuote(htmlToText(live.text), evidence.quote) ? pass('fetch') : miss(`the quote is not in the fetched page of ${url}`, true)
  }
  if (evidence.archive !== undefined) {
    const archived = await io.fetchText(evidence.archive)
    if (isReachable(archived) && containsQuote(htmlToText(archived.text), evidence.quote)) return pass('archive')
  }
  return miss(`${url} answered ${live.status === 0 ? 'nothing' : live.status}`)
}

type Availability = { archived_snapshots?: { closest?: { available?: boolean; url?: string } } }

export async function findArchive(io: Io, url: string): Promise<string | undefined> {
  const answer = await io.fetchText(`https://archive.org/wayback/available?url=${encodeURIComponent(url)}`)
  if (answer.status !== 200) return undefined
  try {
    const closest = (JSON.parse(answer.text) as Availability).archived_snapshots?.closest
    return closest?.available === true && typeof closest.url === 'string' ? closest.url.replace(/^http:/, 'https:') : undefined
  } catch {
    return undefined
  }
}

export async function requestArchive(io: Io, url: string): Promise<void> {
  await io.fetchText(`https://web.archive.org/save/${url}`)
}

export function cachedIo(io: Io): Io {
  const pages = new Map<string, Promise<FetchResult>>()
  return {
    ...io,
    fetchText(url) {
      const hit = pages.get(url) ?? io.fetchText(url)
      pages.set(url, hit)
      return hit
    },
  }
}
