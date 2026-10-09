import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { Finding } from '../../core/types.ts'
import { addFinding, renderOp, setScore, verifyFinding } from '../../core/findings.ts'
import type { AddFindingInput } from '../../core/findings.ts'
import { KeyedLock } from '../../core/lock.ts'
import { files, treeDir } from '../../core/paths.ts'
import { loadAssessment, loadFindings, saveFindings } from '../../core/store.ts'
import { toYaml } from '../../core/yaml.ts'
import { fakeIo } from './fake-io.ts'
import { CFG, LAGO_FILE, LAGO_URL, SHA, STRIPE_TAX_URL, TODAY, codeFinding, docsFinding, lagoFilePath, seedStudy, study } from './fixtures.ts'

function seeded(findings: Finding[] = []) {
  const io = fakeIo({ [lagoFilePath()]: LAGO_FILE })
  seedStudy(io, { findings })
  io.pages.set(STRIPE_TAX_URL, { status: 200, text: '<p>Tax is rounded per line item.</p>' })
  return { io, ctx: { io, cfg: CFG, today: TODAY } }
}

const stripeInput: AddFindingInput = {
  study: 'tax',
  ref: 'stripe',
  dimension: 'rounding',
  answer: 'per_line',
  evidence: [{ kind: 'docs', url: STRIPE_TAX_URL, quote: 'Tax is rounded per line item.' }],
}
const lagoInput: AddFindingInput = {
  study: 'tax',
  ref: 'lago',
  dimension: 'rounding',
  answer: 'per_invoice',
  evidence: [{ kind: 'code', repo: LAGO_URL, sha: SHA, path: 'app/services/taxes.rb', lines: '3', quote: 'round(total_tax)' }],
}

test('addFinding records a web finding, stamps retrieved and looks up an archive without saving one', async () => {
  const { io, ctx } = seeded()
  const out = await addFinding(ctx, stripeInput)
  assert.equal(renderOp(out, out.ok ? `recorded ${out.value.id}` : ''), 'recorded stripe.rounding')
  const [saved] = await loadFindings(io, CFG, 'tax')
  assert.equal(saved.id, 'stripe.rounding')
  assert.equal(saved.method, 'docs')
  assert.equal(saved.confidence, 'unverified')
  assert.equal(saved.evidence[0].retrieved, TODAY)
  assert.ok(io.fetched.includes(`https://archive.org/wayback/available?url=${encodeURIComponent(STRIPE_TAX_URL)}`))
  assert.ok(!io.fetched.includes(`https://web.archive.org/save/${STRIPE_TAX_URL}`))
})

test('re-recording the same ref and dimension replaces the answer', async () => {
  const { io, ctx } = seeded([docsFinding({ answer: 'per_invoice', evidence: [{ kind: 'docs', url: STRIPE_TAX_URL, quote: 'Tax is rounded per line item.', retrieved: '2026-01-01' }] })])
  await addFinding(ctx, stripeInput)
  const saved = await loadFindings(io, CFG, 'tax')
  assert.equal(saved.length, 1)
  assert.equal(saved[0].answer, 'per_line')
})

test('pain findings get the next free suffix', async () => {
  const { io, ctx } = seeded()
  const pain = { ...stripeInput, kind: 'pain' as const, detail: 'Per-line rounding drifts from the invoice total' }
  await addFinding(ctx, pain)
  await addFinding(ctx, pain)
  assert.deepEqual((await loadFindings(io, CFG, 'tax')).map(f => f.id), ['stripe.rounding.2', 'stripe.rounding.3'])
})

test('addFinding rejects answers outside the options without writing', async () => {
  const { io, ctx } = seeded()
  const out = await addFinding(ctx, { ...stripeInput, answer: 'per_order' })
  assert.match(renderOp(out, ''), /^rejected:\n- finding stripe.rounding: answer "per_order" is not one of/)
  assert.deepEqual(await loadFindings(io, CFG, 'tax'), [])
})

test('addFinding rejects code evidence whose lines do not hold the quote', async () => {
  const { ctx } = seeded()
  const out = await addFinding(ctx, { ...lagoInput, evidence: [{ ...lagoInput.evidence[0], lines: '1' }] })
  assert.equal(out.ok, false)
  assert.match(renderOp(out, ''), /the quote is at lines 3, not 1/)
})

test('a page that hides the quote is recorded with a browser warning', async () => {
  const { io, ctx } = seeded()
  io.pages.set(STRIPE_TAX_URL, { status: 200, text: '<div id="app"></div>' })
  const out = await addFinding(ctx, stripeInput)
  assert.equal(out.ok, true)
  assert.match(renderOp(out, 'recorded'), /warning: evidence\[0\]: .* the verifier must confirm it in a browser/)
})

test('addFinding refuses a study whose study.yaml has errors', async () => {
  const { io, ctx } = seeded()
  io.files.set(files.study(CFG, 'tax'), toYaml(study({ references: { nobody: 'competitor' } })))
  const out = await addFinding(ctx, stripeInput)
  assert.match(renderOp(out, ''), /study tax has errors: references.nobody is not in references.yaml/)
})

test('verifyFinding confirms primary evidence and records how', async () => {
  const { io, ctx } = seeded([codeFinding()])
  const out = await verifyFinding(ctx, { study: 'tax', id: 'lago.rounding', outcome: 'confirmed' })
  assert.equal(out.ok, true)
  const [saved] = await loadFindings(io, CFG, 'tax')
  assert.deepEqual(saved.verified, { by: 'verifier', at: TODAY, via: 'git' })
  assert.equal(saved.confidence, 'confirmed')
})

test('verifyFinding refuses confirmed for a single third-party source', async () => {
  const blog = docsFinding({ method: 'third_party', evidence: [{ kind: 'blog', url: STRIPE_TAX_URL, quote: 'Tax is rounded per line item.', retrieved: TODAY }] })
  const { ctx } = seeded([blog])
  const out = await verifyFinding(ctx, { study: 'tax', id: 'stripe.rounding', outcome: 'confirmed' })
  assert.match(renderOp(out, ''), /use likely/)
})

test('verifyFinding accepts a browser-confirmed quote that the raw fetch cannot see', async () => {
  const { io, ctx } = seeded([docsFinding()])
  io.pages.set(STRIPE_TAX_URL, { status: 200, text: '<div id="app"></div>' })
  assert.equal((await verifyFinding(ctx, { study: 'tax', id: 'stripe.rounding', outcome: 'confirmed' })).ok, false)
  const out = await verifyFinding(ctx, { study: 'tax', id: 'stripe.rounding', outcome: 'confirmed', browser_confirmed: true })
  assert.equal(out.ok && out.value.verified?.via, 'browser')
})

test('disputed clears verification and keeps the note', async () => {
  const verified = docsFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: TODAY, via: 'fetch' } })
  const { io, ctx } = seeded([verified])
  await verifyFinding(ctx, { study: 'tax', id: 'stripe.rounding', outcome: 'disputed', note: 'The page says per invoice.' })
  const [saved] = await loadFindings(io, CFG, 'tax')
  assert.equal(saved.status, 'disputed')
  assert.equal(saved.verified, undefined)
  assert.equal(saved.note, 'The page says per invoice.')
})

test('setScore upserts by ref and criterion', async () => {
  const { io, ctx } = seeded([docsFinding()])
  const input = { study: 'tax', ref: 'stripe', criterion: 'edge_cases', level: 2, because: ['stripe.rounding'], agent: 'analyst' }
  await setScore(ctx, input)
  await setScore(ctx, { ...input, level: 3, confirmed_by: 'human' })
  const scores = await loadAssessment(io, CFG, 'tax')
  assert.equal(scores.length, 1)
  assert.deepEqual(scores[0], { ref: 'stripe', criterion: 'edge_cases', level: 3, because: ['stripe.rounding'], by: { agent: 'analyst', confirmed_by: 'human', at: TODAY } })
})

test('KeyedLock runs tasks for one key one at a time', async () => {
  const lock = new KeyedLock()
  const order: string[] = []
  const slow = lock.run('tax', async () => {
    order.push('a:start')
    await new Promise(resolve => setTimeout(resolve, 20))
    order.push('a:end')
  })
  const fast = lock.run('tax', async () => {
    order.push('b')
  })
  await Promise.all([slow, fast])
  assert.deepEqual(order, ['a:start', 'a:end', 'b'])
})

test('a failed task does not block the next one', async () => {
  const lock = new KeyedLock()
  await assert.rejects(lock.run('tax', async () => { throw new Error('boom') }), /boom/)
  assert.equal(await lock.run('tax', async () => 'next'), 'next')
})

test('concurrent addFinding calls under the study lock all persist', async () => {
  const { io, ctx } = seeded()
  const lock = new KeyedLock()
  await Promise.all([lock.run('tax', () => addFinding(ctx, stripeInput)), lock.run('tax', () => addFinding(ctx, lagoInput))])
  assert.deepEqual((await loadFindings(io, CFG, 'tax')).map(f => f.id).sort(), ['lago.rounding', 'stripe.rounding'])
})

test('a page that blocks automated clients is recorded with a browser warning', async () => {
  const { io, ctx } = seeded()
  io.pages.set(STRIPE_TAX_URL, { status: 403, text: 'Forbidden' })
  const out = await addFinding(ctx, stripeInput)
  assert.equal(out.ok, true)
  assert.match(renderOp(out, 'recorded'), /warning: evidence\[0\]: .*answered 403.*the verifier must confirm it in a browser/)
})

test('a blocked page is checked against its archive copy', async () => {
  const { io, ctx } = seeded()
  const archive = 'https://web.archive.org/web/1/https://docs.stripe.com/tax'
  io.pages.set(STRIPE_TAX_URL, { status: 403, text: '' })
  io.pages.set(`https://archive.org/wayback/available?url=${encodeURIComponent(STRIPE_TAX_URL)}`, {
    status: 200,
    text: JSON.stringify({ archived_snapshots: { closest: { available: true, url: archive } } }),
  })
  io.pages.set(archive, { status: 200, text: '<p>Tax is rounded per line item.</p>' })
  assert.equal(renderOp(await addFinding(ctx, stripeInput), 'recorded'), 'recorded')
  assert.equal((await loadFindings(io, CFG, 'tax'))[0].evidence[0].archive, archive)
})

test('a page that is gone is rejected', async () => {
  const { io, ctx } = seeded()
  io.pages.set(STRIPE_TAX_URL, { status: 404, text: '' })
  assert.match(renderOp(await addFinding(ctx, stripeInput), ''), /^rejected:\n- evidence\[0\]: .*answered 404/)
})

test("an explicit id must belong to the finding's own ref and dimension", async () => {
  const { io, ctx } = seeded([docsFinding()])
  const out = await addFinding(ctx, { ...lagoInput, id: 'stripe.rounding' })
  assert.match(renderOp(out, ''), /id must be lago\.rounding or lago\.rounding\.<n>/)
  assert.equal((await loadFindings(io, CFG, 'tax'))[0].ref, 'stripe')
})

test('verifyFinding refuses an unknown outcome', async () => {
  const { io, ctx } = seeded([docsFinding()])
  const out = await verifyFinding(ctx, { study: 'tax', id: 'stripe.rounding', outcome: 'rejected' as 'likely' })
  assert.match(renderOp(out, ''), /outcome must be confirmed, likely or disputed/)
  assert.equal((await loadFindings(io, CFG, 'tax'))[0].confidence, 'unverified')
})

test('study names that are not topics are refused before any file is touched', async () => {
  const { ctx } = seeded()
  const outs = [
    await addFinding(ctx, { ...stripeInput, study: '../../x' }),
    await verifyFinding(ctx, { study: '../x', id: 'a.b', outcome: 'likely' }),
    await setScore(ctx, { study: '../x', ref: 'a', criterion: 'b', level: 1, because: [], agent: 'analyst' }),
  ]
  for (const out of outs) assert.match(renderOp(out, ''), /study must be a kebab-case topic/)
})

test('addFinding checks sources outside the study lock and writes under it', async () => {
  const { io, ctx } = seeded()
  const lock = new KeyedLock()
  const occupant = lock.run('tax', async () => {
    await new Promise(resolve => setTimeout(resolve, 40))
    await saveFindings(io, CFG, 'tax', [codeFinding()])
  })
  const adding = addFinding(ctx, stripeInput, lock)
  await new Promise(resolve => setTimeout(resolve, 10))
  assert.ok(io.fetched.includes(STRIPE_TAX_URL), 'the source check waited for the lock')
  await Promise.all([occupant, adding])
  assert.deepEqual((await loadFindings(io, CFG, 'tax')).map(f => f.id).sort(), ['lago.rounding', 'stripe.rounding'])
})

test('addFinding numbers pain and reuse findings without a dimension from 1', async () => {
  const { io, ctx } = seeded()
  io.files.set(`${treeDir(CFG, LAGO_URL, SHA)}/LICENSE`, 'GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007\n')
  const reuse: AddFindingInput = {
    study: 'tax',
    ref: 'lago',
    kind: 'reuse',
    answer: 'lago tax service',
    detail: 'Rounds once per invoice',
    reuse: { type: 'code', url: LAGO_URL, license: 'AGPL-3.0' },
    evidence: [{ kind: 'code', repo: LAGO_URL, sha: SHA, path: 'LICENSE', lines: '1-2', quote: 'GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3' }],
  }
  assert.equal(renderOp(await addFinding(ctx, reuse), 'ok'), 'ok')
  assert.equal(renderOp(await addFinding(ctx, reuse), 'ok'), 'ok')
  const pain: AddFindingInput = { ...stripeInput, dimension: undefined, kind: 'pain', answer: 'Rounding drift', detail: 'Per-line rounding drifts from the invoice total' }
  assert.equal(renderOp(await addFinding(ctx, pain), 'ok'), 'ok')
  const saved = await loadFindings(io, CFG, 'tax')
  assert.deepEqual(saved.map(f => f.id), ['lago.reuse.1', 'lago.reuse.2', 'stripe.pain.1'])
  assert.equal('dimension' in (saved[2] ?? {}), false)
  assert.deepEqual(saved[0]?.reuse, { type: 'code', url: LAGO_URL, license: 'AGPL-3.0' })
})
