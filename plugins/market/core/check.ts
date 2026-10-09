import { files, readYaml } from '../../research/core/index.ts'
import type { Ctx, Issue, Reference } from '../../research/core/index.ts'
import { marketFiles } from './paths.ts'
import { validateCandidates, validateRegistry, validateRejected, validateTaxonomy } from './validate.ts'
import type { Registry, Rejection, Taxonomy } from './types.ts'

const error = (file: string, message: string): Issue => ({ level: 'error', kind: 'schema', file, message })
const isMapping = (item: unknown): item is Record<string, unknown> => item !== null && typeof item === 'object' && !Array.isArray(item)

/** Every rule over research/market/, offline; research/references.yaml is read, never judged (that is research check's job). */
export async function runMarketCheck(ctx: Ctx): Promise<Issue[]> {
  const issues: Issue[] = []
  const taxonomyFile = marketFiles.taxonomy(ctx.cfg)
  const taxonomyYaml = await readYaml(ctx.io, taxonomyFile)
  if (taxonomyYaml.error !== undefined) issues.push(error(taxonomyFile, taxonomyYaml.error))
  else if (!taxonomyYaml.missing) issues.push(...validateTaxonomy(taxonomyYaml.data, taxonomyFile))
  const taxonomy: Taxonomy | undefined = isMapping(taxonomyYaml.data)
    ? { categories: isMapping(taxonomyYaml.data.categories) ? (taxonomyYaml.data.categories as Record<string, string>) : {}, capabilities: {} }
    : undefined
  const refsFile = files.references(ctx.cfg)
  const refsYaml = await readYaml(ctx.io, refsFile)
  if (refsYaml.error !== undefined) issues.push(error(refsFile, `${refsYaml.error}; run research check`))
  const references = Array.isArray(refsYaml.data) ? (refsYaml.data as unknown[]).filter(isMapping).map(item => item as Reference) : []
  const registryFile = marketFiles.registry(ctx.cfg)
  const registryYaml = await readYaml(ctx.io, registryFile)
  if (registryYaml.error !== undefined) issues.push(error(registryFile, registryYaml.error))
  else issues.push(...validateRegistry(registryYaml.data, references, taxonomy, registryFile))
  const registry = (isMapping(registryYaml.data) ? registryYaml.data : {}) as Registry
  const rejectedFile = marketFiles.rejected(ctx.cfg)
  const rejectedYaml = await readYaml(ctx.io, rejectedFile)
  if (rejectedYaml.error !== undefined) issues.push(error(rejectedFile, rejectedYaml.error))
  else if (!rejectedYaml.missing) issues.push(...validateRejected(rejectedYaml.data, rejectedFile))
  const rejected = Array.isArray(rejectedYaml.data) ? (rejectedYaml.data as unknown[]).filter(isMapping).map(item => item as Rejection) : []
  const candidatesFile = marketFiles.candidates(ctx.cfg)
  const candidatesYaml = await readYaml(ctx.io, candidatesFile)
  if (candidatesYaml.error !== undefined) issues.push(error(candidatesFile, candidatesYaml.error))
  else if (!candidatesYaml.missing) issues.push(...validateCandidates(candidatesYaml.data, references, registry, rejected, taxonomy, candidatesFile))
  return issues
}

export function renderMarketIssues(issues: readonly Issue[]): string {
  if (issues.length === 0) return 'market check: no issues'
  return issues.map(issue => `${issue.level} ${issue.file}: ${issue.message}`).join('\n')
}
