import { test } from 'node:test'
import assert from 'node:assert/strict'
import { renderReport, reverify } from '../../core/reverify.ts'
import { loadFindings } from '../../core/store.ts'
import { fakeIo } from './fake-io.ts'
import { gitFake } from './git-fake.ts'
import { CFG, LAGO_FILE, SHA, STRIPE_TAX_URL, TODAY, codeFinding, docsFinding, lagoFilePath, seedStudy } from './fixtures.ts'

const verifiedOn = (at: string, via: 'fetch' | 'git' | 'browser') => ({ confidence: 'confirmed' as const, verified: { by: 'verifier', at, via } })

function setup() {
  const io = fakeIo({ [lagoFilePath()]: LAGO_FILE })
  gitFake(io)
  return { io, ctx: { io, cfg: CFG, today: TODAY } }
}

test('due findings whose quote still matches are refreshed and changed ones drift', async () => {
  const { io, ctx } = setup()
  seedStudy(io, { findings: [docsFinding(verifiedOn('2025-01-01', 'fetch')), codeFinding(verifiedOn('2025-01-01', 'git'))] })
  io.pages.set(STRIPE_TAX_URL, { status: 200, text: '<p>Tax is rounded on the invoice total.</p>' })
  const report = await reverify(ctx, { dueOnly: true })
  assert.deepEqual(report, { refreshed: ['tax/lago.rounding'], drifted: ['tax/stripe.rounding'], archived: [], skipped: [] })
  const [docs, code] = await loadFindings(io, CFG, 'tax')
  assert.equal(docs.status, 'drifted')
  assert.equal(code.verified?.at, TODAY)
})

test('findings that are not due are only re-checked when everything is asked for', async () => {
  const { io, ctx } = setup()
  seedStudy(io, { findings: [codeFinding(verifiedOn('2026-10-01', 'git'))] })
  assert.deepEqual((await reverify(ctx, { dueOnly: true })).refreshed, [])
  assert.deepEqual((await reverify(ctx, { dueOnly: false })).refreshed, ['tax/lago.rounding'])
})

test('a browser-verified quote the raw fetch cannot see is skipped, not drifted', async () => {
  const { io, ctx } = setup()
  seedStudy(io, { findings: [docsFinding(verifiedOn('2025-01-01', 'browser'))] })
  io.pages.set(STRIPE_TAX_URL, { status: 200, text: '<div id="app"></div>' })
  const report = await reverify(ctx, { dueOnly: true })
  assert.deepEqual([report.refreshed, report.drifted], [[], []])
  assert.match(report.skipped[0] ?? '', /^tax\/stripe\.rounding \(the quote is not in the fetched page/)
})

test('missing archives are filled for current findings', async () => {
  const { io, ctx } = setup()
  seedStudy(io, { findings: [docsFinding()] })
  io.pages.set(`https://archive.org/wayback/available?url=${encodeURIComponent(STRIPE_TAX_URL)}`, {
    status: 200,
    text: JSON.stringify({ archived_snapshots: { closest: { available: true, url: 'https://web.archive.org/web/1/https://docs.stripe.com/tax' } } }),
  })
  assert.deepEqual((await reverify(ctx, { dueOnly: true })).archived, ['tax/stripe.rounding'])
  const [saved] = await loadFindings(io, CFG, 'tax')
  assert.equal(saved.evidence[0].archive, 'https://web.archive.org/web/1/https://docs.stripe.com/tax')
})

test('renderReport lists each non-empty group', () => {
  assert.equal(renderReport({ refreshed: [], drifted: [], archived: [], skipped: [] }), 'research reverify: nothing changed')
  assert.equal(
    renderReport({ refreshed: ['tax/a.b'], drifted: ['tax/c.d'], archived: [], skipped: [] }),
    '# research reverify\n\n## Drifted (1)\n- tax/c.d\n\n## Refreshed (1)\n- tax/a.b\n',
  )
})

test('a source that cannot be reached is skipped with its reason, not drifted', async () => {
  const { io, ctx } = setup()
  seedStudy(io, { findings: [docsFinding(verifiedOn('2025-01-01', 'fetch'))] })
  io.pages.set(STRIPE_TAX_URL, { status: 503, text: '' })
  const report = await reverify(ctx, { dueOnly: true })
  assert.deepEqual(report.drifted, [])
  assert.match(report.skipped[0] ?? '', /^tax\/stripe\.rounding \(.*answered 503\)$/)
})

test('our own sha missing from a shallow clone is skipped, not drifted', async () => {
  const { io, ctx } = setup()
  const ours = codeFinding({
    id: 'subneo.rounding',
    ref: 'subneo',
    evidence: [{ kind: 'code', repo: 'self', sha: SHA, path: 'internal/tax.go', lines: '1', quote: 'x' }],
    ...verifiedOn('2025-01-01', 'git'),
  })
  seedStudy(io, { findings: [ours] })
  io.onRun = () => ({ exitCode: 128, stdout: '', stderr: 'fatal: not a valid object name' })
  const report = await reverify(ctx, { dueOnly: true })
  assert.deepEqual(report.drifted, [])
  assert.match(report.skipped[0] ?? '', /^tax\/subneo\.rounding \(.*not in this repository/)
})

test('reverify asks Wayback to save pages that have no archive yet', async () => {
  const { io, ctx } = setup()
  seedStudy(io, { findings: [docsFinding()] })
  await reverify(ctx, { dueOnly: true })
  assert.ok(io.fetched.includes(`https://web.archive.org/save/${STRIPE_TAX_URL}`))
})
