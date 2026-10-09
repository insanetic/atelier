import { test } from 'node:test'
import assert from 'node:assert/strict'
import { files, loadReferences, loadStudy, renderOp, runCheck, toYaml } from '../../../research/core/index.ts'
import { fakeIo } from '../../../research/tests/core/fake-io.ts'
import type { FakeIo } from '../../../research/tests/core/fake-io.ts'
import { docsFinding } from '../../../research/tests/core/fixtures.ts'
import { approveCandidate, listReferences, proposeCandidate, rejectCandidate, renderReferences, syncLandscape } from '../../core/registry.ts'
import type { CandidateInput } from '../../core/registry.ts'
import { marketFiles } from '../../core/paths.ts'
import { loadCandidates, loadRegistry, loadRejected } from '../../core/store.ts'
import { CFG, TODAY, seedMarket } from './fixtures.ts'

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
  seedMarket(io)
  io.pages.set('https://flexprice.io', { status: 200, text: '<h1>Open-source usage-based billing</h1>' })
  return { io, ctx: ctxOf(io) }
}

test('proposeCandidate records a new product with checked evidence and a normalized domain', async () => {
  const { io, ctx } = seeded()
  assert.equal(renderOp(await proposeCandidate(ctx, flexprice), 'proposed'), 'proposed')
  const [saved] = await loadCandidates(io, CFG)
  assert.deepEqual(saved?.domains, ['flexprice.io'])
  assert.equal(saved?.proposed_at, TODAY)
})

test('a product already tracked or rejected is not proposed again', async () => {
  const { io, ctx } = seeded()
  const known = await proposeCandidate(ctx, { ...flexprice, id: 'lago-billing', name: 'Lago Billing', domains: ['getlago.com'] })
  assert.match(renderOp(known, ''), /already registered as lago/)
  io.files.set(marketFiles.rejected(CFG), toYaml([{ id: 'flexprice', name: 'Flexprice', domains: ['flexprice.io'], reason: 'out of scope', rejected_at: '2026-10-01' }]))
  assert.match(renderOp(await proposeCandidate(ctx, flexprice), ''), /was rejected on 2026-10-01: out of scope/)
})

test('a second channel finding the same candidate is merged into it', async () => {
  const { io, ctx } = seeded()
  await proposeCandidate(ctx, flexprice)
  assert.match(renderOp(await proposeCandidate(ctx, { ...flexprice, id: 'flex-price', found_by: ['show-hn'] }), 'merged'), /^merged/)
  const candidates = await loadCandidates(io, CFG)
  assert.equal(candidates.length, 1)
  assert.deepEqual(candidates[0]?.found_by, ['github-topics', 'show-hn'])
})

test('a candidate whose evidence page is gone is rejected', async () => {
  const { io, ctx } = seeded()
  io.pages.set('https://flexprice.io', { status: 404, text: '' })
  assert.match(renderOp(await proposeCandidate(ctx, flexprice), ''), /^rejected:\n- evidence\[0\]: .*answered 404/)
})

test('approving writes facts to research/references.yaml and market facts to registry.yaml, keeping comments', async () => {
  const { io, ctx } = seeded()
  io.files.set(files.references(CFG), `# facts only\n${io.files.get(files.references(CFG))}`)
  io.files.set(marketFiles.registry(CFG), `# stances are a first guess\n${io.files.get(marketFiles.registry(CFG))}`)
  await proposeCandidate(ctx, flexprice)
  assert.equal((await approveCandidate(ctx, 'flexprice')).ok, true)
  assert.match(io.files.get(files.references(CFG)) ?? '', /^# facts only\n/)
  assert.match(io.files.get(marketFiles.registry(CFG)) ?? '', /^# stances are a first guess\n/)
  assert.deepEqual((await loadReferences(io, CFG)).find(ref => ref.id === 'flexprice'), { id: 'flexprice', name: 'Flexprice', kind: 'product' })
  assert.deepEqual((await loadRegistry(io, CFG)).flexprice, { domains: ['flexprice.io'], categories: ['usage-billing'], status: 'active' })
  assert.deepEqual(await loadCandidates(io, CFG), [])
  assert.deepEqual(await runCheck(ctx), [])
})

test('rejecting records the reason so the product is not proposed again', async () => {
  const { io, ctx } = seeded()
  await proposeCandidate(ctx, flexprice)
  assert.equal((await rejectCandidate(ctx, 'flexprice', 'a hobby project')).ok, true)
  assert.deepEqual((await loadRejected(io, CFG)).map(item => [item.id, item.reason, item.rejected_at]), [['flexprice', 'a hobby project', TODAY]])
  assert.match(renderOp(await rejectCandidate(ctx, 'flexprice', ''), ''), /a reason is required/)
})

test('listReferences filters tracked references by category, tier and verified capability', async () => {
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
  assert.match(renderReferences(rows), /^stripe {2}Stripe {2}product {2}tier 1 {2}subscription-billing {2}public_api: verified$/m)
})

test('syncLandscape keeps one deep study: one question per capability, every active tracked reference plus ours', async () => {
  const { io, ctx } = seeded()
  await syncLandscape(ctx)
  const landscape = await loadStudy(io, CFG, 'landscape')
  assert.equal(landscape?.mode, 'deep')
  assert.deepEqual(landscape?.dimensions.map(dim => [dim.id, dim.type]), [['public_api', 'bool'], ['self_hosted', 'bool']])
  assert.deepEqual(landscape?.references, { lago: 'competitor', stripe: 'competitor', subneo: 'ours' })
  io.files.set(files.study(CFG, 'landscape'), `# kept\n${io.files.get(files.study(CFG, 'landscape'))}`)
  await syncLandscape(ctx)
  assert.match(io.files.get(files.study(CFG, 'landscape')) ?? '', /^# kept\n/)
  assert.deepEqual(await runCheck(ctx), [])
})
