import type { Ctx, Io } from './io.ts'
import type { Config, Finding, Reference, Score, Study, StudyMode } from './types.ts'
import { files } from './paths.ts'
import { parseYaml, toYaml } from './yaml.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

export type Loaded = { data: unknown; missing: boolean; error?: string }

const TOPIC = /^[a-z0-9][a-z0-9-]*$/

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
  return loaded.data !== null && typeof loaded.data === 'object' ? (loaded.data as Study) : undefined
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

export async function createStudy(ctx: Ctx, topic: string, mode: StudyMode): Promise<OpResult<{ study: Study; created: boolean }>> {
  if (!TOPIC.test(topic)) return fail(`topic ${topic} must be kebab-case, e.g. tax or plan-change`)
  const existing = await loadStudy(ctx.io, ctx.cfg, topic)
  if (existing !== undefined) return ok({ study: existing, created: false })
  const study: Study = { topic, question: '', decision_needed: '', status: 'draft', mode, references: {}, dimensions: [], criteria: [] }
  await ctx.io.writeText(files.study(ctx.cfg, topic), toYaml(study))
  await saveFindings(ctx.io, ctx.cfg, topic, [])
  await saveAssessment(ctx.io, ctx.cfg, topic, [])
  await ctx.io.writeText(files.notes(ctx.cfg, topic), notesTemplate(topic))
  if ((await ctx.io.readText(files.references(ctx.cfg))) === undefined) await saveReferences(ctx.io, ctx.cfg, [])
  return ok({ study, created: true })
}
