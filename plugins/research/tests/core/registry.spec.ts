import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { Issue } from '../../core/types.ts'
import { coverageIssues, validateReferences, validateStudy, validateTaxonomy } from '../../core/validate.ts'
import { approveCandidate, listReferences, proposeCandidate, rejectCandidate, renderReferences, syncLandscape } from '../../core/registry.ts'
import type { CandidateInput } from '../../core/registry.ts'
import { renderIssues, runCheck } from '../../core/check.ts'
import { renderOp } from '../../core/findings.ts'
import { files } from '../../core/paths.ts'
import { loadCandidates, loadReferences, loadRejected, loadStudy, loadTaxonomy } from '../../core/store.ts'
import { toYaml } from '../../core/yaml.ts'
import { fakeIo } from './fake-io.ts'
import type { FakeIo } from './fake-io.ts'
import { CFG, REFERENCES, TAXONOMY, TODAY, docsFinding, seedStudy, study } from './fixtures.ts'

const text = (issues: Issue[]) => issues.map(issue => issue.message).join('\n')
const REF_IDS = new Set(REFERENCES.map(ref => ref.id))
const ctxOf = (io: FakeIo) => ({ io, cfg: CFG, today: TODAY })

const flexprice: CandidateInput = {
  id: 'flexprice',
  name: 'Flexprice',
  domains: ['https://www.flexprice.io/'],
  categories: ['usage-billing'],
  found_by: ['github-topics'],
  evidence: [{ kind: 'docs', url: 'https://flexprice.io', quote: 'Open-source usage-based billing' }],
}

function seeded() {
  const io = fakeIo()
  seedStudy(io)
  io.pages.set('https://flexprice.io', { status: 200, text: '<h1>Open-source usage-based billing</h1>' })
  return { io, ctx: ctxOf(io) }
}

test('the taxonomy needs kebab-case categories, snake_case capabilities and written definitions', () => {
  assert.deepEqual(validateTaxonomy(TAXONOMY, 'taxonomy.yaml'), [])
  const broken = { categories: { 'Usage Billing': 'x', metering: '' }, capabilities: { 'public-api': 'x' } }
  const out = text(validateTaxonomy(broken, 'taxonomy.yaml'))
  assert.match(out, /categories\.Usage Billing must be kebab-case/)
  assert.match(out, /categories\.metering needs a definition/)
  assert.match(out, /capabilities\.public-api must be snake_case/)
})

test('references carry facts and an optional dated stance, checked against the taxonomy', () => {
  assert.deepEqual(validateReferences(REFERENCES, 'references.yaml', TAXONOMY), [])
  const odd = [
    { id: 'orb', name: 'Orb', kind: 'company', categories: ['billing'], status: 'bought', owned_by: 'adyen', stance: { tier: 3, overlap: { metering: 'rival' }, reviewed: 'today' } },
  ]
  const out = text(validateReferences(odd, 'references.yaml', TAXONOMY))
  assert.match(out, /kind must be one of product, standard, approach, ours/)
  assert.match(out, /categories: billing is not in taxonomy\.yaml/)
  assert.match(out, /status must be one of active, acquired, sunset, dead/)
  assert.match(out, /owned_by adyen is not a registered reference/)
  assert.match(out, /stance\.tier must be 1, 2 or watch/)
  assert.match(out, /stance\.overlap\.metering: metering is not in taxonomy\.yaml/)
  assert.match(out, /stance\.overlap\.metering must be direct or adjacent/)
  assert.match(out, /stance\.reviewed must be YYYY-MM-DD/)
})

test('two references may not share a domain', () => {
  const twins = [...REFERENCES, { id: 'lago-cloud', name: 'Lago Cloud', domains: ['getlago.com'] }]
  assert.match(text(validateReferences(twins, 'references.yaml', TAXONOMY)), /domain getlago\.com is used by lago and lago-cloud/)
})

test('a study must cover every competitor that overlaps its categories', () => {
  const scoped = study({ categories: ['usage-billing'], references: { stripe: 'competitor', subneo: 'ours' } })
  assert.match(text(coverageIssues(scoped, REFERENCES, 'f')), /lago overlaps usage-billing: include it or add it to excluded with a reason/)
  assert.deepEqual(coverageIssues({ ...scoped, excluded: { lago: 'no tax engine' } }, REFERENCES, 'f'), [])
  assert.deepEqual(coverageIssues(study({ categories: ['usage-billing'] }), REFERENCES, 'f'), [])
  assert.deepEqual(coverageIssues(study(), REFERENCES, 'f'), [])
})

test('study categories come from the taxonomy and exclusions name registered references', () => {
  const bad = study({ categories: ['billing'], excluded: { orb: 'acquired' } })
  const out = text(validateStudy(bad, 'tax', REF_IDS, 'study.yaml', TAXONOMY))
  assert.match(out, /categories: billing is not in taxonomy\.yaml/)
  assert.match(out, /excluded\.orb is not in references\.yaml/)
})

test('proposeCandidate records a new product with checked evidence and a normalized domain', async () => {
  const { io, ctx } = seeded()
  const out = await proposeCandidate(ctx, flexprice)
  assert.equal(renderOp(out, 'proposed'), 'proposed')
  const [saved] = await loadCandidates(io, CFG)
  assert.deepEqual(saved?.domains, ['flexprice.io'])
  assert.deepEqual(saved?.found_by, ['github-topics'])
  assert.equal(saved?.proposed_at, TODAY)
})

test('a product already registered or rejected is not proposed again', async () => {
  const { io, ctx } = seeded()
  const known = await proposeCandidate(ctx, { ...flexprice, id: 'lago-billing', name: 'Lago Billing', domains: ['getlago.com'] })
  assert.match(renderOp(known, ''), /already registered as lago/)
  io.files.set(files.rejected(CFG), toYaml([{ id: 'flexprice', name: 'Flexprice', domains: ['flexprice.io'], reason: 'out of scope', rejected_at: '2026-10-01' }]))
  assert.match(renderOp(await proposeCandidate(ctx, flexprice), ''), /was rejected on 2026-10-01: out of scope/)
})

test('a second channel finding the same candidate is merged into it', async () => {
  const { io, ctx } = seeded()
  await proposeCandidate(ctx, flexprice)
  const again = await proposeCandidate(ctx, { ...flexprice, id: 'flex-price', found_by: ['show-hn'] })
  assert.match(renderOp(again, 'merged'), /^merged/)
  const candidates = await loadCandidates(io, CFG)
  assert.equal(candidates.length, 1)
  assert.deepEqual(candidates[0]?.found_by, ['github-topics', 'show-hn'])
})

test('a candidate whose evidence page is gone is rejected', async () => {
  const { io, ctx } = seeded()
  io.pages.set('https://flexprice.io', { status: 404, text: '' })
  assert.match(renderOp(await proposeCandidate(ctx, flexprice), ''), /^rejected:\n- evidence\[0\]: .*answered 404/)
})

test('approving moves a candidate into the registry; rejecting records the reason', async () => {
  const { io, ctx } = seeded()
  await proposeCandidate(ctx, flexprice)
  await proposeCandidate(ctx, { ...flexprice, id: 'meterflow', name: 'MeterFlow', domains: ['meterflow.dev'], evidence: [{ kind: 'docs', url: 'https://flexprice.io', quote: 'Open-source usage-based billing' }] })
  assert.equal((await approveCandidate(ctx, 'flexprice')).ok, true)
  assert.equal((await rejectCandidate(ctx, 'meterflow', 'a hobby project')).ok, true)
  const registered = (await loadReferences(io, CFG)).find(ref => ref.id === 'flexprice')
  assert.deepEqual(registered, { id: 'flexprice', name: 'Flexprice', kind: 'product', status: 'active', domains: ['flexprice.io'], categories: ['usage-billing'] })
  assert.deepEqual((await loadRejected(io, CFG)).map(item => [item.id, item.reason, item.rejected_at]), [['meterflow', 'a hobby project', TODAY]])
  assert.deepEqual(await loadCandidates(io, CFG), [])
})

test('listReferences filters by category, tier and verified capability', async () => {
  const { io, ctx } = seeded()
  assert.deepEqual((await listReferences(ctx, { category: 'usage-billing' })).map(row => row.ref.id), ['lago'])
  assert.deepEqual((await listReferences(ctx, { tier: '1' })).map(row => row.ref.id), ['lago', 'stripe'])
  await syncLandscape(ctx)
  const apiFinding = docsFinding({
    id: 'stripe.public_api',
    dimension: 'public_api',
    answer: true,
    evidence: [{ kind: 'docs', url: 'https://docs.stripe.com/api', quote: 'The Stripe API is organized around REST.', retrieved: TODAY }],
    confidence: 'confirmed',
    verified: { by: 'verifier', at: TODAY, via: 'fetch' },
  })
  io.files.set(files.findings(CFG, 'landscape'), toYaml([apiFinding]))
  const rows = await listReferences(ctx, { capability: 'public_api' })
  assert.deepEqual(rows.map(row => [row.ref.id, row.capability]), [['stripe', 'verified']])
  assert.match(renderReferences(rows), /^stripe\s+Stripe\s+product\s+tier 1\s+subscription-billing\s+public_api: verified$/m)
})

test('syncLandscape keeps one study whose questions are the capabilities and whose references are the registry', async () => {
  const { io, ctx } = seeded()
  await syncLandscape(ctx)
  const landscape = await loadStudy(io, CFG, 'landscape')
  assert.deepEqual(landscape?.dimensions.map(dim => [dim.id, dim.type]), [['public_api', 'bool'], ['self_hosted', 'bool']])
  assert.deepEqual(landscape?.references, { lago: 'competitor', stripe: 'competitor', subneo: 'ours' })
  io.files.set(files.study(CFG, 'landscape'), `# kept\n${io.files.get(files.study(CFG, 'landscape'))}`)
  await syncLandscape(ctx)
  assert.match(io.files.get(files.study(CFG, 'landscape')) ?? '', /^# kept\n/)
  assert.deepEqual(await runCheck(ctx), [])
})

test('check reports candidates that collide with the registry and studies that miss a competitor', async () => {
  const { io, ctx } = seeded()
  io.files.set(files.candidates(CFG), toYaml([{ ...flexprice, id: 'lago2', domains: ['getlago.com'], found_by: ['x'], proposed_at: TODAY }]))
  io.files.set(files.study(CFG, 'tax'), toYaml(study({ categories: ['usage-billing'], references: { stripe: 'competitor', subneo: 'ours' } })))
  const rendered = renderIssues(await runCheck(ctx))
  assert.match(rendered, /candidate lago2: domain getlago\.com is already registered as lago/)
  assert.match(rendered, /warn .*lago overlaps usage-billing/)
})

test('a taxonomy scope holds include and exclude rules as text', async () => {
  const scoped = { ...TAXONOMY, scope: { include: ['built for B2B software companies'], exclude: ['mobile in-app purchases'] } }
  assert.deepEqual(validateTaxonomy(scoped, 'taxonomy.yaml'), [])
  assert.match(text(validateTaxonomy({ ...TAXONOMY, scope: { include: 'B2B' } }, 'taxonomy.yaml')), /scope\.include must be a list of rules/)
  const io = fakeIo()
  io.files.set(files.taxonomy(CFG), toYaml(scoped))
  assert.deepEqual((await loadTaxonomy(io, CFG)).scope, scoped.scope)
})
