import { readYaml, toYaml } from '../../research/core/index.ts'
import type { Config, Io } from '../../research/core/index.ts'
import type { Candidate, Registry, Rejection, Taxonomy } from './types.ts'
import { marketFiles } from './paths.ts'

const isMapping = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)

async function readList<T>(io: Io, path: string): Promise<T[]> {
  const loaded = await readYaml(io, path)
  if (loaded.error !== undefined) throw new Error(`${path}: ${loaded.error}`)
  return Array.isArray(loaded.data) ? (loaded.data as T[]) : []
}

export function loadCandidates(io: Io, cfg: Config): Promise<Candidate[]> {
  return readList<Candidate>(io, marketFiles.candidates(cfg))
}

export function saveCandidates(io: Io, cfg: Config, candidates: Candidate[]): Promise<void> {
  return io.writeText(marketFiles.candidates(cfg), toYaml(candidates))
}

export function loadRejected(io: Io, cfg: Config): Promise<Rejection[]> {
  return readList<Rejection>(io, marketFiles.rejected(cfg))
}

export async function loadTaxonomy(io: Io, cfg: Config): Promise<Taxonomy> {
  const path = marketFiles.taxonomy(cfg)
  const loaded = await readYaml(io, path)
  if (loaded.error !== undefined) throw new Error(`${path}: ${loaded.error}`)
  const data = (isMapping(loaded.data) ? loaded.data : {}) as Partial<Taxonomy>
  const taxonomy: Taxonomy = { categories: data.categories ?? {}, capabilities: data.capabilities ?? {} }
  if (data.scope !== undefined) taxonomy.scope = data.scope
  return taxonomy
}

export async function loadRegistry(io: Io, cfg: Config): Promise<Registry> {
  const path = marketFiles.registry(cfg)
  const loaded = await readYaml(io, path)
  if (loaded.error !== undefined) throw new Error(`${path}: ${loaded.error}`)
  return isMapping(loaded.data) ? (loaded.data as Registry) : {}
}
