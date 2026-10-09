import { KeyedLock, WEB_KINDS, appendToYamlList, checkEvidence, createStudy, fail, files, loadFindings, loadReferences, loadStudy, ok, setInYaml, stateOf } from '../../research/core/index.ts'
import type { CellState, Ctx, Dimension, Evidence, OpResult, Reference, Role } from '../../research/core/index.ts'
import { marketFiles } from './paths.ts'
import { loadCandidates, loadRegistry, loadRejected, loadTaxonomy, saveCandidates } from './store.ts'
import { normalizeDomain, validateCandidates } from './validate.ts'
import type { Candidate, Entry, Rejection } from './types.ts'

export type CandidateInput = { id: string; name: string; domains: string[]; categories: string[]; found_by: string[]; evidence: Evidence[]; note?: string }
export type ReferenceFilter = { category?: string; tier?: string; capability?: string; kind?: string }
export type ReferenceRow = { ref: Reference; entry: Entry; capability?: CellState; capabilityId?: string }

const MARKET = 'market'
export const LANDSCAPE = 'landscape'
const sameName = (a: unknown, b: unknown) => typeof a === 'string' && typeof b === 'string' && a.trim().toLowerCase() === b.trim().toLowerCase()
const sharesDomain = (domains: readonly string[] | undefined, wanted: readonly string[]) => (domains ?? []).map(normalizeDomain).some(domain => wanted.includes(domain))

/**
 * Records a discovered product for a human to approve. Products already
 * tracked or rejected are refused by id, name, alias or domain; a product
 * another channel already proposed is merged, so found_by shows every channel.
 */
export async function proposeCandidate(ctx: Ctx, input: CandidateInput, lock = new KeyedLock()): Promise<OpResult<{ candidate: Candidate; merged: boolean }>> {
  if (!Array.isArray(input.domains) || !Array.isArray(input.found_by) || !Array.isArray(input.evidence)) return fail('domains, found_by and evidence must be lists')
  const domains = [...new Set(input.domains.map(normalizeDomain).filter(domain => domain !== ''))]
  const evidence: Evidence[] = input.evidence.map(item =>
    WEB_KINDS.includes(item.kind) && item.retrieved === undefined ? { ...item, retrieved: ctx.today } : { ...item },
  )
  const draft: Candidate = { id: input.id, name: input.name, domains, categories: input.categories ?? [], found_by: input.found_by, evidence, proposed_at: ctx.today }
  if (input.note !== undefined) draft.note = input.note
  const references = await loadReferences(ctx.io, ctx.cfg)
  const registry = await loadRegistry(ctx.io, ctx.cfg)
  const rejected = await loadRejected(ctx.io, ctx.cfg)
  const known = references.find(ref => {
    const entry = registry[ref.id]
    return ref.id === draft.id || sameName(ref.name, draft.name) || (entry?.aliases ?? []).some(alias => sameName(alias, draft.name)) || sharesDomain(entry?.domains, domains)
  })
  if (known !== undefined) return fail(`${draft.name} is already registered as ${known.id}`)
  const refused = rejected.find(item => item.id === draft.id || sameName(item.name, draft.name) || sharesDomain(item.domains, domains))
  if (refused !== undefined) return fail(`${draft.name} was rejected on ${refused.rejected_at}: ${refused.reason}`)
  const invalid = validateCandidates([draft], references, registry, rejected, await loadTaxonomy(ctx.io, ctx.cfg), marketFiles.candidates(ctx.cfg))
  if (invalid.length > 0) return fail(...invalid.map(issue => issue.message))
  const errors: string[] = []
  const warnings: string[] = []
  for (const [index, item] of evidence.entries()) {
    const outcome = await checkEvidence(ctx, marketFiles.dir(ctx.cfg), item)
    if (outcome.ok) continue
    if (outcome.miss === 'hidden' || outcome.miss === 'blocked') warnings.push(`evidence[${index}]: ${outcome.reason}; confirm it in a browser before approving`)
    else errors.push(`evidence[${index}]: ${outcome.reason}`)
  }
  if (errors.length > 0) return fail(...errors)
  return lock.run(MARKET, async () => {
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

/** Facts go to research/references.yaml, market facts to registry.yaml; both keep their comments. */
export async function approveCandidate(ctx: Ctx, id: string, lock = new KeyedLock()): Promise<OpResult<{ reference: Reference; entry: Entry }>> {
  return lock.run(MARKET, async () => {
    const candidates = await loadCandidates(ctx.io, ctx.cfg)
    const candidate = candidates.find(item => item.id === id)
    if (candidate === undefined) return fail<{ reference: Reference; entry: Entry }>(`candidate ${id} does not exist`)
    if ((await loadReferences(ctx.io, ctx.cfg)).some(ref => ref.id === id)) return fail<{ reference: Reference; entry: Entry }>(`${id} is already in research/references.yaml`)
    const reference: Reference = { id: candidate.id, name: candidate.name, kind: 'product' }
    const entry: Entry = { domains: candidate.domains, categories: candidate.categories, status: 'active' }
    const refsPath = files.references(ctx.cfg)
    await ctx.io.writeText(refsPath, appendToYamlList((await ctx.io.readText(refsPath)) ?? '', reference))
    const registryPath = marketFiles.registry(ctx.cfg)
    await ctx.io.writeText(registryPath, setInYaml((await ctx.io.readText(registryPath)) ?? '', { [candidate.id]: entry }))
    await saveCandidates(ctx.io, ctx.cfg, candidates.filter(item => item !== candidate))
    return ok({ reference, entry })
  })
}

export async function rejectCandidate(ctx: Ctx, id: string, reason: string, lock = new KeyedLock()): Promise<OpResult<Rejection>> {
  if (typeof reason !== 'string' || reason.trim() === '') return fail('a reason is required, so the product is not proposed again')
  return lock.run(MARKET, async () => {
    const candidates = await loadCandidates(ctx.io, ctx.cfg)
    const candidate = candidates.find(item => item.id === id)
    if (candidate === undefined) return fail<Rejection>(`candidate ${id} does not exist`)
    const rejection: Rejection = { id: candidate.id, name: candidate.name, domains: candidate.domains, reason, rejected_at: ctx.today }
    const path = marketFiles.rejected(ctx.cfg)
    await ctx.io.writeText(path, appendToYamlList((await ctx.io.readText(path)) ?? '', rejection))
    await saveCandidates(ctx.io, ctx.cfg, candidates.filter(item => item !== candidate))
    return ok(rejection)
  })
}

/** Tracked references (those with a registry entry) by category, tier, kind, or a capability the landscape study verified. */
export async function listReferences(ctx: Ctx, filter: ReferenceFilter): Promise<ReferenceRow[]> {
  const registry = await loadRegistry(ctx.io, ctx.cfg)
  let rows: ReferenceRow[] = (await loadReferences(ctx.io, ctx.cfg)).flatMap(ref => {
    const entry = registry[ref.id]
    return entry === undefined ? [] : [{ ref, entry }]
  })
  if (filter.category !== undefined) rows = rows.filter(row => (row.entry.categories ?? []).includes(filter.category ?? ''))
  if (filter.tier !== undefined) rows = rows.filter(row => row.entry.stance !== undefined && String(row.entry.stance.tier) === filter.tier)
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
    .map(({ ref, entry, capability, capabilityId }) => {
      const tier = entry.stance === undefined ? '-' : `tier ${entry.stance.tier}`
      const cells = [ref.id, ref.name, ref.kind ?? 'product', tier, (entry.categories ?? []).join(',') || '-']
      if (capability !== undefined && capabilityId !== undefined) cells.push(`${capabilityId}: ${capability}`)
      return cells.join('  ')
    })
    .join('\n')
}

function landscapeRole(ref: Reference, entry: Entry | undefined): Role {
  if (ref.kind === 'ours') return 'ours'
  if (ref.kind === 'standard') return 'standard'
  return entry?.stance === undefined ? 'specialist' : 'competitor'
}

/**
 * Keeps the standing landscape study in step with the registry: one yes/no
 * question per taxonomy capability; every active tracked reference, plus ours.
 * A reference or capability that has left the registry but already has
 * findings is kept (and reported), so research check stays clean; a kept
 * reference is taken out deliberately with research drop. Hand-written comments survive.
 */
export async function syncLandscape(ctx: Ctx): Promise<OpResult<{ dimensions: number; references: number; kept: string[] }>> {
  const taxonomy = await loadTaxonomy(ctx.io, ctx.cfg)
  const registry = await loadRegistry(ctx.io, ctx.cfg)
  const references = (await loadReferences(ctx.io, ctx.cfg)).filter(ref => {
    const entry = registry[ref.id]
    return ref.kind === 'ours' || (entry !== undefined && (entry.status ?? 'active') === 'active')
  })
  const previous = await loadStudy(ctx.io, ctx.cfg, LANDSCAPE)
  const findings = previous === undefined ? [] : await loadFindings(ctx.io, ctx.cfg, LANDSCAPE)
  const made = await createStudy(ctx, LANDSCAPE, 'deep')
  if (!made.ok) return made
  const dimensions: Dimension[] = Object.entries(taxonomy.capabilities).map(([id, ask]) => ({ id, ask, type: 'bool', volatility: 'medium' }))
  const roles: Record<string, Role | Role[]> = Object.fromEntries(references.map(ref => [ref.id, landscapeRole(ref, registry[ref.id])]))
  const kept: string[] = []
  for (const [id, role] of Object.entries(previous?.references ?? {})) {
    if (id in roles || !findings.some(finding => finding.ref === id)) continue
    roles[id] = role
    kept.push(id)
  }
  for (const dimension of previous?.dimensions ?? []) {
    if (dimensions.some(dim => dim.id === dimension.id) || !findings.some(finding => finding.dimension === dimension.id)) continue
    dimensions.push(dimension)
    kept.push(dimension.id)
  }
  const path = files.study(ctx.cfg, LANDSCAPE)
  const updated = setInYaml((await ctx.io.readText(path)) ?? '', {
    question: 'Which capabilities does each tracked reference have?',
    decision_needed: 'Which references a benchmark selects by capability',
    references: roles,
    dimensions,
  })
  await ctx.io.writeText(path, updated)
  return ok({ dimensions: dimensions.length, references: Object.keys(roles).length, kept })
}
