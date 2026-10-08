import type { Ctx, Io } from './io.ts'
import type { Candidate, Config, Finding, Reference, Rejection, Score, Study, StudyMode, Taxonomy } from './types.ts'
import { files } from './paths.ts'
import { parseYaml, toYaml } from './yaml.ts'
import { validateStudy } from './validate.ts'
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

async function readList<T>(io: Io, path: string): Promise<T[]> {
  const loaded = await readYaml(io, path)
  if (loaded.error !== undefined) throw new Error(`${path}: ${loaded.error}`)
  return Array.isArray(loaded.data) ? (loaded.data as T[]) : []
}

export function loadReferences(io: Io, cfg: Config): Promise<Reference[]> {
  return readList<Reference>(io, files.references(cfg))
}

export function loadCandidates(io: Io, cfg: Config): Promise<Candidate[]> {
  return readList<Candidate>(io, files.candidates(cfg))
}

export function loadRejected(io: Io, cfg: Config): Promise<Rejection[]> {
  return readList<Rejection>(io, files.rejected(cfg))
}

export function saveCandidates(io: Io, cfg: Config, candidates: Candidate[]): Promise<void> {
  return io.writeText(files.candidates(cfg), toYaml(candidates))
}

export const EMPTY_TAXONOMY: Taxonomy = { categories: {}, capabilities: {} }

export async function loadTaxonomy(io: Io, cfg: Config): Promise<Taxonomy> {
  const path = files.taxonomy(cfg)
  const loaded = await readYaml(io, path)
  if (loaded.error !== undefined) throw new Error(`${path}: ${loaded.error}`)
  const data = (loaded.data ?? {}) as Partial<Taxonomy>
  return { categories: data.categories ?? {}, capabilities: data.capabilities ?? {} }
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

export function saveReferences(io: Io, cfg: Config, references: Reference[]): Promise<void> {
  return io.writeText(files.references(cfg), toYaml(references))
}

export function saveFindings(io: Io, cfg: Config, topic: string, findings: Finding[]): Promise<void> {
  return io.writeText(files.findings(cfg, topic), toYaml(findings))
}

export function saveAssessment(io: Io, cfg: Config, topic: string, scores: Score[]): Promise<void> {
  return io.writeText(files.assessment(cfg, topic), toYaml(scores))
}

export async function listTopics(io: Io, cfg: Config): Promise<string[]> {
  return (await io.listDirs(files.studies(cfg))).sort()
}

function notesTemplate(topic: string): string {
  const sections = ['Question and decision', 'Paradigms found', 'Trade-offs', 'Pain', 'Where ours stands', 'Candidates', 'Decision']
  return `# ${topic}\n\n${sections.map(section => `## ${section}\n`).join('\n')}`
}

/** A study whose study.yaml passes validation: the only kind tools build on. */
export async function loadValidStudy(ctx: Ctx, topic: string): Promise<OpResult<Study>> {
  if (!isTopic(topic)) return fail(TOPIC_RULE)
  const study = await loadStudy(ctx.io, ctx.cfg, topic)
  if (study === undefined) return fail(`study ${topic} does not exist`)
  const refIds = new Set((await loadReferences(ctx.io, ctx.cfg)).map(ref => ref.id))
  const taxonomy = await loadTaxonomy(ctx.io, ctx.cfg)
  const errors = validateStudy(study, topic, refIds, files.study(ctx.cfg, topic), taxonomy).filter(issue => issue.level === 'error')
  if (errors.length > 0) return fail(`study ${topic} has errors: ${errors.map(issue => issue.message).join('; ')}`)
  return ok(study)
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
  const study: Study = { topic, question: '', decision_needed: '', status: 'draft', mode, references: {}, dimensions: [], criteria: [] }
  const starters: [string, string][] = [
    [studyFile, toYaml(study)],
    [files.findings(ctx.cfg, topic), toYaml([])],
    [files.assessment(ctx.cfg, topic), toYaml([])],
    [files.notes(ctx.cfg, topic), notesTemplate(topic)],
    [files.references(ctx.cfg), toYaml([])],
    [files.taxonomy(ctx.cfg), toYaml(EMPTY_TAXONOMY)],
    [files.candidates(ctx.cfg), toYaml([])],
    [files.rejected(ctx.cfg), toYaml([])],
  ]
  for (const [path, text] of starters) if ((await ctx.io.readText(path)) === undefined) await ctx.io.writeText(path, text)
  return ok({ study, created: true })
}
