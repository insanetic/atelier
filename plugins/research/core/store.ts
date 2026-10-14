import type { Ctx, Io } from './io.ts'
import type { Config, Finding, Reference, Score, Study, StudyMode } from './types.ts'
import { files } from './paths.ts'
import { parseYaml, toYaml } from './yaml.ts'
import { validateStudy } from './validate.ts'
import { notesTemplate } from './notes.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

export type Loaded = { data: unknown; missing: boolean; error?: string }

export const TOPIC = /^[a-z0-9][a-z0-9-]*$/
export const TOPIC_RULE = 'study must be a kebab-case topic such as tax or plan-change'
export const isTopic = (value: unknown): value is string => typeof value === 'string' && TOPIC.test(value)

export async function readYaml(io: Io, path: string): Promise<Loaded> {
  const text = await io.readText(path)
  if (text === undefined) return { data: undefined, missing: true }
  try {
    return { data: parseYaml(text), missing: false }
  } catch (problem) {
    return { data: undefined, missing: false, error: (problem as Error).message }
  }
}

/**
 * A missing file is an empty list; a file that is there but holds no list is
 * refused, as saving over it would lose whatever it held.
 */
async function readList<T>(io: Io, path: string): Promise<T[]> {
  const loaded = await readYaml(io, path)
  if (loaded.error !== undefined) throw new Error(`${path}: ${loaded.error}`)
  if (loaded.missing) return []
  if (!Array.isArray(loaded.data)) throw new Error(`${path}: expected a list of records; fix or restore the file`)
  return loaded.data as T[]
}

export function loadReferences(io: Io, cfg: Config): Promise<Reference[]> {
  return readList<Reference>(io, files.references(cfg))
}

export function loadFindings(io: Io, cfg: Config, topic: string): Promise<Finding[]> {
  return readList<Finding>(io, files.findings(cfg, topic))
}

export function loadAssessment(io: Io, cfg: Config, topic: string): Promise<Score[]> {
  return readList<Score>(io, files.assessment(cfg, topic))
}

export async function loadStudy(io: Io, cfg: Config, topic: string): Promise<Study | undefined> {
  const path = files.study(cfg, topic)
  const loaded = await readYaml(io, path)
  if (loaded.error !== undefined) throw new Error(`${path}: ${loaded.error}`)
  return loaded.data !== null && typeof loaded.data === 'object' && !Array.isArray(loaded.data) ? (loaded.data as Study) : undefined
}

export async function loadNotes(io: Io, cfg: Config, topic: string): Promise<string> {
  return (await io.readText(files.notes(cfg, topic))) ?? ''
}

export function saveFindings(io: Io, cfg: Config, topic: string, findings: Finding[]): Promise<void> {
  return io.writeText(files.findings(cfg, topic), toYaml(findings))
}

/**
 * Writes back findings that were changed from a copy loaded earlier. The file is
 * read again first, so records added meanwhile survive, and a record changed
 * meanwhile keeps the newer version. Returns the ids that were left alone.
 */
export async function mergeFindings(io: Io, cfg: Config, topic: string, before: ReadonlyMap<string, string>, changed: readonly Finding[]): Promise<string[]> {
  const byId = new Map(changed.map(finding => [finding.id, finding]))
  const kept: string[] = []
  const latest = (await loadFindings(io, cfg, topic)).map(finding => {
    const next = byId.get(finding.id)
    if (next === undefined) return finding
    if (JSON.stringify(finding) !== before.get(finding.id)) {
      kept.push(finding.id)
      return finding
    }
    return next
  })
  await saveFindings(io, cfg, topic, latest)
  return kept
}

export function saveAssessment(io: Io, cfg: Config, topic: string, scores: Score[]): Promise<void> {
  return io.writeText(files.assessment(cfg, topic), toYaml(scores))
}

export async function listTopics(io: Io, cfg: Config): Promise<string[]> {
  return (await io.listDirs(files.studies(cfg))).sort()
}

/** The errors validation finds in a study, as one message, or undefined. */
export async function studyErrors(ctx: Ctx, topic: string, study: Study): Promise<string | undefined> {
  const refIds = new Set((await loadReferences(ctx.io, ctx.cfg)).map(ref => ref.id))
  const errors = validateStudy(study, topic, refIds, files.study(ctx.cfg, topic)).filter(issue => issue.level === 'error')
  return errors.length === 0 ? undefined : errors.map(issue => issue.message).join('; ')
}

/** A study whose study.yaml passes validation: the only kind tools build on. */
export async function loadValidStudy(ctx: Ctx, topic: string): Promise<OpResult<Study>> {
  if (!isTopic(topic)) return fail(TOPIC_RULE)
  const study = await loadStudy(ctx.io, ctx.cfg, topic)
  if (study === undefined) return fail(`study ${topic} does not exist`)
  const errors = await studyErrors(ctx, topic, study)
  return errors === undefined ? ok(study) : fail(`study ${topic} has errors: ${errors}`)
}

/** Creates the files of a new study; never overwrites one that exists. */
export async function createStudy(ctx: Ctx, topic: string, mode: StudyMode): Promise<OpResult<{ study: Study; created: boolean }>> {
  if (!isTopic(topic)) return fail(TOPIC_RULE)
  const studyFile = files.study(ctx.cfg, topic)
  if ((await ctx.io.readText(studyFile)) !== undefined) {
    const existing = await loadStudy(ctx.io, ctx.cfg, topic)
    if (existing === undefined) return fail(`${studyFile}: study.yaml is empty or not a mapping; fix it by hand`)
    return ok({ study: existing, created: false })
  }
  const study: Study =
    mode === 'deep'
      ? { topic, question: '', decision_needed: '', status: 'draft', mode, references: {}, dimensions: [], criteria: [] }
      : { topic, question: '', status: 'draft', mode, references: {}, dimensions: [] }
  const starters: [string, string][] = [
    [studyFile, toYaml(study)],
    [files.findings(ctx.cfg, topic), toYaml([])],
    [files.assessment(ctx.cfg, topic), toYaml([])],
    [files.notes(ctx.cfg, topic), notesTemplate(topic, mode)],
    [files.references(ctx.cfg), toYaml([])],
  ]
  for (const [path, text] of starters) if ((await ctx.io.readText(path)) === undefined) await ctx.io.writeText(path, text)
  return ok({ study, created: true })
}
