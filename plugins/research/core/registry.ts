import type { Ctx } from './io.ts'
import type { Candidate, Evidence, Reference, Rejection, Role } from './types.ts'
import { files } from './paths.ts'
import { createStudy, loadCandidates, loadFindings, loadReferences, loadRejected, loadStudy, loadTaxonomy, saveCandidates } from './store.ts'
import { WEB_KINDS, normalizeDomain, validateCandidates } from './validate.ts'
import { checkEvidence } from './evidence.ts'
import { stateOf } from './fresh.ts'
import type { CellState } from './fresh.ts'
import { KeyedLock } from './lock.ts'
import { appendToYamlList, setInYaml } from './yaml.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

export type CandidateInput = { id: string; name: string; domains: string[]; categories: string[]; found_by: string[]; evidence: Evidence[]; note?: string }
export type ReferenceFilter = { category?: string; tier?: string; capability?: string; kind?: string }
export type ReferenceRow = { ref: Reference; capability?: CellState; capabilityId?: string }

const REGISTRY = 'registry'
export const LANDSCAPE = 'landscape'
const sameName = (a: unknown, b: unknown) => typeof a === 'string' && typeof b === 'string' && a.trim().toLowerCase() === b.trim().toLowerCase()
const sharesDomain = (domains: readonly string[] | undefined, wanted: readonly string[]) => (domains ?? []).map(normalizeDomain).some(domain => wanted.includes(domain))

/**
 * Records a discovered product for a human to approve. Products already
 * registered or rejected are refused by id, name, alias or domain; a product
 * another channel already proposed is merged, so found_by shows every channel.
 */
export async function proposeCandidate(ctx: Ctx, input: CandidateInput, lock = new KeyedLock()): Promise<OpResult<{ candidate: Candidate; merged: boolean }>> {
  if (!Array.isArray(input.domains) || !Array.isArray(input.found_by) || !Array.isArray(input.evidence)) return fail('domains, found_by and evidence must be lists')
  const domains = [...new Set(input.domains.map(normalizeDomain).filter(domain => domain !== ''))]
  const evidence: Evidence[] = input.evidence.map(item =>
    WEB_KINDS.includes(item.kind) && item.retrieved === undefined ? { ...item, retrieved: ctx.today } : { ...item },
  )
  const draft: Candidate = {
    id: input.id,
    name: input.name,
    domains,
    categories: input.categories ?? [],
    found_by: input.found_by,
    evidence,
    proposed_at: ctx.today,
  }
  if (input.note !== undefined) draft.note = input.note
  const references = await loadReferences(ctx.io, ctx.cfg)
  const rejected = await loadRejected(ctx.io, ctx.cfg)
  const known = references.find(
    ref => ref.id === draft.id || sameName(ref.name, draft.name) || (ref.aliases ?? []).some(alias => sameName(alias, draft.name)) || sharesDomain(ref.domains, domains),
  )
  if (known !== undefined) return fail(`${draft.name} is already registered as ${known.id}`)
  const refused = rejected.find(item => item.id === draft.id || sameName(item.name, draft.name) || sharesDomain(item.domains, domains))
  if (refused !== undefined) return fail(`${draft.name} was rejected on ${refused.rejected_at}: ${refused.reason}`)
  const invalid = validateCandidates([draft], references, rejected, await loadTaxonomy(ctx.io, ctx.cfg), files.candidates(ctx.cfg))
  if (invalid.length > 0) return fail(...invalid.map(issue => issue.message))
  const errors: string[] = []
  const warnings: string[] = []
  for (const [index, item] of evidence.entries()) {
    const outcome = await checkEvidence(ctx, files.registry(ctx.cfg), item)
    if (outcome.ok) continue
    if (outcome.miss === 'hidden' || outcome.miss === 'blocked') warnings.push(`evidence[${index}]: ${outcome.reason}; confirm it in a browser before approving`)
    else errors.push(`evidence[${index}]: ${outcome.reason}`)
  }
  if (errors.length > 0) return fail(...errors)
  return lock.run(REGISTRY, async () => {
    const candidates = await loadCandidates(ctx.io, ctx.cfg)
    const twin = candidates.find(item => item.id === draft.id || sameName(item.name, draft.name) || sharesDomain(item.domains, domains))
    if (twin === undefined) {
      await saveCandidates(ctx.io, ctx.cfg, [...candidates, draft])
      return ok({ candidate: draft, merged: false }, warnings)
    }
    const merged: Candidate = {
      ...twin,
      categories: [...new Set([...twin.categories, ...draft.categories])],
      found_by: [...new Set([...twin.found_by, ...draft.found_by])],
      evidence: [...twin.evidence, ...draft.evidence.filter(item => !twin.evidence.some(existing => existing.url === item.url))],
    }
    await saveCandidates(ctx.io, ctx.cfg, candidates.map(item => (item === twin ? merged : item)))
    return ok({ candidate: merged, merged: true }, warnings)
  })
}

export async function approveCandidate(ctx: Ctx, id: string, lock = new KeyedLock()): Promise<OpResult<Reference>> {
  return lock.run(REGISTRY, async () => {
    const candidates = await loadCandidates(ctx.io, ctx.cfg)
    const candidate = candidates.find(item => item.id === id)
    if (candidate === undefined) return fail<Reference>(`candidate ${id} does not exist`)
    const reference: Reference = { id: candidate.id, name: candidate.name, kind: 'product', status: 'active', domains: candidate.domains, categories: candidate.categories }
    const path = files.references(ctx.cfg)
    await ctx.io.writeText(path, appendToYamlList((await ctx.io.readText(path)) ?? '', reference))
    await saveCandidates(ctx.io, ctx.cfg, candidates.filter(item => item !== candidate))
    return ok(reference)
  })
}

export async function rejectCandidate(ctx: Ctx, id: string, reason: string, lock = new KeyedLock()): Promise<OpResult<Rejection>> {
  if (typeof reason !== 'string' || reason.trim() === '') return fail('a reason is required, so the product is not proposed again')
  return lock.run(REGISTRY, async () => {
    const candidates = await loadCandidates(ctx.io, ctx.cfg)
    const candidate = candidates.find(item => item.id === id)
    if (candidate === undefined) return fail<Rejection>(`candidate ${id} does not exist`)
    const rejection: Rejection = { id: candidate.id, name: candidate.name, domains: candidate.domains, reason, rejected_at: ctx.today }
    const path = files.rejected(ctx.cfg)
    await ctx.io.writeText(path, appendToYamlList((await ctx.io.readText(path)) ?? '', rejection))
    await saveCandidates(ctx.io, ctx.cfg, candidates.filter(item => item !== candidate))
    return ok(rejection)
  })
}

/** Registered references by category, tier, kind, or a capability the landscape study verified. */
export async function listReferences(ctx: Ctx, filter: ReferenceFilter): Promise<ReferenceRow[]> {
  let rows: ReferenceRow[] = (await loadReferences(ctx.io, ctx.cfg)).map(ref => ({ ref }))
  if (filter.category !== undefined) rows = rows.filter(row => (row.ref.categories ?? []).includes(filter.category ?? ''))
  if (filter.tier !== undefined) rows = rows.filter(row => row.ref.stance !== undefined && String(row.ref.stance.tier) === filter.tier)
  if (filter.kind !== undefined) rows = rows.filter(row => (row.ref.kind ?? 'product') === filter.kind)
  if (filter.capability === undefined) return rows
  const capability = filter.capability
  const landscape = await loadStudy(ctx.io, ctx.cfg, LANDSCAPE)
  const dimension = landscape?.dimensions.find(dim => dim.id === capability)
  if (landscape === undefined || dimension === undefined) return []
  const findings = await loadFindings(ctx.io, ctx.cfg, LANDSCAPE)
  return rows.flatMap(row => {
    const finding = findings.find(item => item.ref === row.ref.id && item.dimension === capability && item.kind === 'answer' && item.status !== 'superseded')
    if (finding === undefined || finding.answer !== true) return []
    return [{ ...row, capability: stateOf(finding, dimension, ctx.today), capabilityId: capability }]
  })
}

export function renderReferences(rows: readonly ReferenceRow[]): string {
  if (rows.length === 0) return 'no references match'
  return rows
    .map(({ ref, capability, capabilityId }) => {
      const tier = ref.stance === undefined ? '-' : `tier ${ref.stance.tier}`
      const cells = [ref.id, ref.name, ref.kind ?? 'product', tier, (ref.categories ?? []).join(',') || '-']
      if (capability !== undefined && capabilityId !== undefined) cells.push(`${capabilityId}: ${capability}`)
      return cells.join('  ')
    })
    .join('\n')
}

function landscapeRole(ref: Reference): Role {
  if (ref.kind === 'ours') return 'ours'
  if (ref.kind === 'standard') return 'standard'
  return ref.stance === undefined ? 'specialist' : 'competitor'
}

/**
 * Keeps the standing landscape study in step with the registry: one yes/no
 * question per taxonomy capability, every active reference. Its findings carry
 * the evidence behind "who has a public API"; hand-written comments survive.
 */
export async function syncLandscape(ctx: Ctx): Promise<OpResult<{ dimensions: number; references: number }>> {
  const taxonomy = await loadTaxonomy(ctx.io, ctx.cfg)
  const references = (await loadReferences(ctx.io, ctx.cfg)).filter(ref => (ref.status ?? 'active') === 'active')
  const made = await createStudy(ctx, LANDSCAPE, 'full')
  if (!made.ok) return made
  const dimensions = Object.entries(taxonomy.capabilities).map(([id, ask]) => ({ id, ask, type: 'bool', volatility: 'medium' }))
  const roles = Object.fromEntries(references.map(ref => [ref.id, landscapeRole(ref)]))
  const path = files.study(ctx.cfg, LANDSCAPE)
  const updated = setInYaml((await ctx.io.readText(path)) ?? '', {
    question: 'Which capabilities does each registered reference have?',
    decision_needed: 'Which references a benchmark selects by capability',
    references: roles,
    dimensions,
  })
  await ctx.io.writeText(path, updated)
  return ok({ dimensions: dimensions.length, references: references.length })
}
