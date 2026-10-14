import type { Ctx, FetchResult, Io } from './io.ts'
import type { Evidence, Via } from './types.ts'
import { join, treeDir } from './paths.ts'
import { containsQuote, htmlToText, locateQuote, pageText } from './normalize.ts'
import { CODE_KINDS, isSha, parseLines } from './validate.ts'

export const MAX_ARTIFACT_BYTES = 300 * 1024

/**
 * Why a check failed, which decides what each caller does with it:
 * - absent: the source is there and the quote is not (add rejects, reverify drifts)
 * - removed: the page or file is gone (add rejects, reverify drifts)
 * - hidden: the source cannot show the quote to a text check: a page rendered by JavaScript, or a screenshot (add warns, browser check)
 * - blocked: the server refuses automated clients (add warns, browser check, reverify skips)
 * - unreachable: nothing could be checked: no answer, no checkout, a commit not in the repo (add rejects, reverify skips)
 */
export type Miss = 'absent' | 'removed' | 'hidden' | 'blocked' | 'unreachable'
export type CheckOutcome = { ok: true; via: Via } | { ok: false; reason: string; miss: Miss }

const pass = (via: Via): CheckOutcome => ({ ok: true, via })
const miss = (reason: string, kind: Miss): CheckOutcome => ({ ok: false, reason, miss: kind })
const isReachable = (page: FetchResult) => page.status >= 200 && page.status < 400

export function lineRange(found: { start: number; end: number }): string {
  return found.start === found.end ? `${found.start}` : `${found.start}-${found.end}`
}

type Source = { text: string } | { reason: string; isFileMissing: boolean }

/** Our own code is read with git in the repository that holds research/, whatever the session's root. */
export async function readAtSha(ctx: Ctx, repo: string, sha: string, path: string): Promise<Source> {
  // sha reaches git's argv: only a full hex sha can never be read as an option.
  if (!isSha(sha)) return { reason: `${sha} is not a full 40-character sha`, isFileMissing: false }
  if (repo === 'self') {
    const known = await ctx.io.run(['git', 'cat-file', '-e', `${sha}^{commit}`], ctx.cfg.dir)
    if (known.exitCode !== 0) return { reason: `commit ${sha.slice(0, 12)} is not in this repository; fetch its history`, isFileMissing: false }
    const shown = await ctx.io.run(['git', 'show', `${sha}:${path}`], ctx.cfg.dir)
    return shown.exitCode === 0 ? { text: shown.stdout } : { reason: `${path} does not exist at ${sha.slice(0, 12)}`, isFileMissing: true }
  }
  let dir: string
  try {
    dir = treeDir(ctx.cfg, repo, sha)
  } catch (problem) {
    return { reason: (problem as Error).message, isFileMissing: false }
  }
  if (!(await ctx.io.exists(dir))) return { reason: `${repo} is not checked out at ${sha.slice(0, 12)}; clone the reference first`, isFileMissing: false }
  const text = await ctx.io.readText(join(dir, path))
  return text === undefined ? { reason: `${path} does not exist at ${sha.slice(0, 12)}`, isFileMissing: true } : { text }
}

export async function checkEvidence(ctx: Ctx, studyDir: string, evidence: Evidence): Promise<CheckOutcome> {
  if (CODE_KINDS.includes(evidence.kind)) return checkCode(ctx, evidence)
  if (evidence.kind === 'tested') return checkArtifact(ctx.io, studyDir, evidence)
  return checkWeb(ctx.io, evidence)
}

async function checkCode(ctx: Ctx, evidence: Evidence): Promise<CheckOutcome> {
  const { repo = '', sha = '', path = '', lines = '' } = evidence
  const source = await readAtSha(ctx, repo, sha, path)
  if (!('text' in source)) return miss(source.reason, source.isFileMissing ? 'removed' : 'unreachable')
  const [first, last] = parseLines(lines)
  if (containsQuote(source.text.split('\n').slice(first - 1, last).join('\n'), evidence.quote)) return pass('git')
  const found = locateQuote(source.text, evidence.quote)
  return miss(found === undefined ? `the quote is not in ${path}` : `the quote is at lines ${lineRange(found)}, not ${lines}`, 'absent')
}

const IMAGE = /\.(?:png|jpe?g|gif|webp)$/i

/** A transcript must hold the quote; a screenshot cannot be read as text, so a person or the verifier looks at it. */
async function checkArtifact(io: Io, studyDir: string, evidence: Evidence): Promise<CheckOutcome> {
  const artifact = evidence.artifact ?? ''
  const path = join(studyDir, artifact)
  const size = await io.size(path)
  if (size === undefined) return miss(`artifact ${artifact} does not exist`, 'removed')
  if (size > MAX_ARTIFACT_BYTES) return miss(`artifact ${artifact} is ${size} bytes; the cap is ${MAX_ARTIFACT_BYTES}`, 'absent')
  if (IMAGE.test(artifact)) return miss(`artifact ${artifact} is an image; the quote can only be checked by looking at it`, 'hidden')
  return containsQuote((await io.readText(path)) ?? '', evidence.quote, { markup: true }) ? pass('file') : miss(`the quote is not in artifact ${artifact}`, 'absent')
}

const EMPTY_MOUNT = /<div\b[^>]*\bid=["'](?:root|app|__next|__nuxt|___gatsby|svelte)["'][^>]*>\s*<\/div>/i
const NOSCRIPT_NOTICE = /<noscript\b[^>]*>[\s\S]{0,400}?(?:enable|requires?|turn on)\s+javascript/i
/** Less readable text than this, and the page is most likely drawn in the browser. */
const MIN_STATIC_TEXT = 200

/**
 * A page that misses the quote but carries its own text is a wrong quote. Only
 * a page that looks drawn by JavaScript (an empty mount node, a noscript
 * notice, almost no text) earns a browser check instead.
 */
export function looksClientRendered(html: string): boolean {
  if (EMPTY_MOUNT.test(html) || NOSCRIPT_NOTICE.test(html)) return true
  return htmlToText(html).replace(/\s+/g, ' ').trim().length < MIN_STATIC_TEXT
}

/**
 * A reachable page decides on its own: the archive would hide a changed page.
 * The archive only stands in when the page itself cannot be read.
 */
async function checkWeb(io: Io, evidence: Evidence): Promise<CheckOutcome> {
  const url = evidence.url ?? ''
  const live = await io.fetchText(url)
  if (isReachable(live)) {
    if (containsQuote(pageText(live.text), evidence.quote, { markup: true })) return pass('fetch')
    return looksClientRendered(live.text)
      ? miss(`the quote is not in the raw page of ${url}, which looks rendered by JavaScript`, 'hidden')
      : miss(`the quote is not in the page of ${url}; quote the page verbatim`, 'absent')
  }
  if (evidence.archive !== undefined) {
    const archived = await io.fetchText(evidence.archive)
    if (isReachable(archived) && containsQuote(pageText(archived.text), evidence.quote, { markup: true })) return pass('archive')
  }
  const answered = `${url} answered ${live.status === 0 ? 'nothing' : live.status}`
  if (live.status === 0) return miss(answered, 'unreachable')
  if (live.status === 404 || live.status === 410) return miss(answered, 'removed')
  return miss(answered, 'blocked')
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
