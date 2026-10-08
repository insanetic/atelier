import { test } from 'node:test'
import assert from 'node:assert/strict'
import { renderIssues, runCheck } from '../../core/check.ts'
import { files } from '../../core/paths.ts'
import { fakeIo } from './fake-io.ts'
import type { FakeIo } from './fake-io.ts'
import type { RepoRef } from '../../core/types.ts'
import { CFG, LAGO_URL, SHA, TODAY, codeFinding, docsFinding, seedStudy } from './fixtures.ts'

const ctxOf = (io: FakeIo, today = TODAY) => ({ io, cfg: CFG, today })

test('a clean product has no issues', async () => {
  const io = fakeIo()
  seedStudy(io, { findings: [docsFinding()], notes: '# tax\nSee [f:stripe.rounding].\n' })
  assert.deepEqual(await runCheck(ctxOf(io)), [])
  assert.equal(renderIssues([]), 'research check: no issues')
})

test('schema errors, dangling citations and stale findings are reported by kind', async () => {
  const io = fakeIo()
  const old = codeFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: '2024-01-01', via: 'git' } })
  seedStudy(io, { findings: [docsFinding({ answer: 'per_order' }), old], notes: 'See [f:stripe.vat].' })
  const issues = await runCheck(ctxOf(io))
  assert.deepEqual(issues.map(issue => `${issue.level}/${issue.kind}`).sort(), ['error/schema', 'error/schema', 'warn/freshness'])
  const rendered = renderIssues(issues)
  assert.match(rendered, /answer "per_order" is not one of/)
  assert.match(rendered, /citation \[f:stripe.vat\] does not resolve/)
  assert.match(rendered, /lago.rounding: verified 2024-01-01, past its slow TTL/)
})

test('a study directory without study.yaml is an error, not a crash', async () => {
  const io = fakeIo({ [`${files.studyDir(CFG, 'ghost')}/artifacts/x.png`]: 'x' })
  seedStudy(io)
  assert.match(renderIssues(await runCheck(ctxOf(io))), /ghost\/study\.yaml: study\.yaml is missing/)
})

test('null entries in findings.yaml are errors, not crashes', async () => {
  const io = fakeIo()
  seedStudy(io)
  io.files.set(files.findings(CFG, 'tax'), '- null\n')
  assert.match(renderIssues(await runCheck(ctxOf(io))), /a finding must be a mapping/)
})

test('stale pins are freshness warnings', async () => {
  const io = fakeIo()
  seedStudy(io)
  const issues = await runCheck(ctxOf(io, '2027-06-01'))
  assert.deepEqual(issues.map(issue => issue.kind), ['freshness'])
  assert.match(issues[0].message, /lago: pin of https:\/\/github.com\/getlago\/lago-api is from 2026-10-01; run research repin lago/)
})

test('hand-edited dates that are not ISO are errors, not crashes', async () => {
  const io = fakeIo()
  seedStudy(io, {
    references: [
      { id: 'lago', name: 'Lago', repos: [{ url: LAGO_URL, pin: SHA, pinned_at: '2026-10-8' }] },
      { id: 'stripe', name: 'Stripe' },
      { id: 'subneo', name: 'Subneo' },
    ],
    findings: [docsFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: '2026/10/08', via: 'fetch' } })],
  })
  const rendered = renderIssues(await runCheck(ctxOf(io)))
  assert.match(rendered, /pinned_at must be YYYY-MM-DD/)
  assert.match(rendered, /verified needs by, at \(YYYY-MM-DD\) and via/)
})

test('repos that is not a list is an error, not a crash', async () => {
  const io = fakeIo()
  const repos = 'https://github.com/getlago/lago-api' as unknown as RepoRef[]
  seedStudy(io, { references: [{ id: 'lago', name: 'Lago', repos }, { id: 'stripe', name: 'Stripe' }, { id: 'subneo', name: 'Subneo' }] })
  assert.match(renderIssues(await runCheck(ctxOf(io))), /references\[0\]\.repos must be a list/)
})
