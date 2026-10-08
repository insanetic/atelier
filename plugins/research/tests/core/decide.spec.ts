import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { Finding } from '../../core/types.ts'
import { decide } from '../../core/decide.ts'
import { renderIssues, runCheck } from '../../core/check.ts'
import { verifyFinding } from '../../core/findings.ts'
import { files } from '../../core/paths.ts'
import { loadStudy } from '../../core/store.ts'
import { fakeIo } from './fake-io.ts'
import { CFG, TODAY, docsFinding, seedStudy } from './fixtures.ts'

const verified = (over: Partial<Finding> = {}) =>
  docsFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: '2026-10-01', via: 'fetch' }, ...over })
const input = { study: 'tax', chosen: 'engine', cites: ['stripe.rounding'], revisit_when: 'Stripe changes how it rounds' }

function seeded(findings: Finding[]) {
  const io = fakeIo()
  seedStudy(io, { findings })
  return { io, ctx: { io, cfg: CFG, today: TODAY } }
}

test('decide records the decision with a snapshot and keeps hand-written comments', async () => {
  const { io, ctx } = seeded([verified()])
  io.files.set(files.study(CFG, 'tax'), `# frame written by hand\n${io.files.get(files.study(CFG, 'tax'))}`)
  const out = await decide(ctx, input)
  assert.equal(out.ok, true)
  assert.match(io.files.get(files.study(CFG, 'tax')) ?? '', /^# frame written by hand\n/)
  const saved = await loadStudy(io, CFG, 'tax')
  assert.equal(saved?.status, 'decided')
  assert.deepEqual(saved?.decision, {
    chosen: 'engine',
    decided_at: TODAY,
    cites: ['stripe.rounding'],
    revisit_when: 'Stripe changes how it rounds',
    snapshot: { 'stripe.rounding': { verified_at: '2026-10-01', confidence: 'confirmed' } },
  })
  assert.deepEqual(await runCheck(ctx), [])
})

test('decide refuses citations that are unverified, disputed, drifted, stale or missing', async () => {
  const cases: [Finding[], RegExp][] = [
    [[docsFinding()], /stripe\.rounding is not verified/],
    [[verified({ status: 'disputed' })], /stripe\.rounding is disputed/],
    [[verified({ status: 'drifted' })], /stripe\.rounding has drifted/],
    [[verified({ verified: { by: 'verifier', at: '2024-01-01', via: 'fetch' } })], /stripe\.rounding is past its slow TTL/],
    [[], /stripe\.rounding does not exist/],
  ]
  for (const [findings, reason] of cases) {
    const { io, ctx } = seeded(findings)
    const before = io.files.get(files.study(CFG, 'tax'))
    const out = await decide(ctx, input)
    assert.match(out.ok ? '' : out.errors.join('\n'), reason)
    assert.equal(io.files.get(files.study(CFG, 'tax')), before)
  }
})

test('decide needs a chosen candidate, citations and a revisit trigger', async () => {
  const { ctx } = seeded([verified()])
  const out = await decide(ctx, { ...input, chosen: '', cites: [], revisit_when: '' })
  const errors = out.ok ? '' : out.errors.join('\n')
  assert.match(errors, /chosen is required/)
  assert.match(errors, /cites must name at least one finding/)
  assert.match(errors, /revisit_when is required/)
})

test('after a decision, a disputed citation warns to revisit and never fails check', async () => {
  const { ctx } = seeded([verified()])
  await decide(ctx, input)
  await verifyFinding(ctx, { study: 'tax', id: 'stripe.rounding', outcome: 'disputed', note: 'wrong page' })
  const issues = await runCheck(ctx)
  assert.equal(issues.some(issue => issue.level === 'error'), false)
  assert.match(renderIssues(issues), /revisit the decision/)
})
