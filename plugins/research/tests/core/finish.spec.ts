import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { Finding, Study } from '../../core/types.ts'
import { finish } from '../../core/finish.ts'
import { runCheck } from '../../core/check.ts'
import { files } from '../../core/paths.ts'
import { loadStudy } from '../../core/store.ts'
import { toYaml } from '../../core/yaml.ts'
import { fakeIo } from './fake-io.ts'
import { CFG, TODAY, docsFinding, seedStudy, study } from './fixtures.ts'

const verifiedDocs = (over: Partial<Finding> = {}) => docsFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: TODAY, via: 'fetch' }, ...over })

const brief = (cite = '[f:stripe.rounding]') => `# tax

Cost: 410k tokens, 24 min

## Answer
Most engines round per line.

## Who solved it
Stripe (product), Lago (open source).

## Approaches
Per-line rounding ${cite}.

## What to reuse
Stripe's tax docs ${cite}.

## Pitfalls
Drift between lines and total ${cite}.

## Ours against theirs
We round per invoice ${cite}.

## Recommendation
Round per line ${cite}.

## Open questions
None.
`

function seeded(notes: string, findings: Finding[] = [verifiedDocs()], over: Partial<Study> = {}) {
  const io = fakeIo()
  seedStudy(io, { study: study({ mode: 'brief', ...over }), findings, notes })
  return { io, ctx: { io, cfg: CFG, today: TODAY } }
}

const errorsOf = (out: Awaited<ReturnType<typeof finish>>) => (out.ok ? '' : out.errors.join('\n'))

test('finish closes a brief whose sections are complete and whose citations are verified', async () => {
  const { io, ctx } = seeded(brief())
  io.files.set(files.study(CFG, 'tax'), `# kept\n${io.files.get(files.study(CFG, 'tax'))}`)
  const out = await finish(ctx, 'tax')
  assert.deepEqual(out.ok ? out.value : out.errors, { at: TODAY, cites: 1 })
  assert.match(io.files.get(files.study(CFG, 'tax')) ?? '', /^# kept\n/)
  const saved = await loadStudy(io, CFG, 'tax')
  assert.equal(saved?.status, 'brief')
  assert.deepEqual(saved?.finished, { at: TODAY, cites: 1 })
  assert.deepEqual(await runCheck(ctx), [])
})

test('finish refuses a missing, decorated or misordered heading', async () => {
  const notes = [
    brief().replace('## Pitfalls\n', ''),
    brief().replace('## Answer\n', '## Answer (draft)\n'),
    `${brief().replace(/## Answer\n[\s\S]*?(?=## Who solved it)/, '')}## Answer\nlate\n`,
  ]
  for (const text of notes) assert.match(errorsOf(await finish(seeded(text).ctx, 'tax')), /study\.md needs exactly these sections, in order: Answer, Who solved it/)
})

test('a heading inside a code fence does not count', async () => {
  const fenced = brief().replace('## Open questions\nNone.\n', '```\n## Open questions\n```\n')
  assert.match(errorsOf(await finish(seeded(fenced).ctx, 'tax')), /study\.md needs exactly these sections/)
})

test('finish refuses weak citations and a claiming section without any, and writes nothing', async () => {
  const cases: [string, Finding[], RegExp][] = [
    [brief(), [docsFinding()], /stripe\.rounding is not verified/],
    [brief(), [verifiedDocs({ status: 'disputed' })], /stripe\.rounding is disputed/],
    [brief(), [verifiedDocs({ status: 'drifted' })], /stripe\.rounding has drifted/],
    [brief(), [verifiedDocs({ verified: { by: 'verifier', at: '2024-01-01', via: 'fetch' } })], /stripe\.rounding is past its slow TTL/],
    [brief('[f:stripe.vat]'), [verifiedDocs()], /stripe\.vat does not exist/],
    [brief().replace('Drift between lines and total [f:stripe.rounding].', 'Drift between lines and total.'), [verifiedDocs()], /section Pitfalls cites no finding/],
  ]
  for (const [notes, findings, reason] of cases) {
    const { io, ctx } = seeded(notes, findings)
    const before = io.files.get(files.study(CFG, 'tax'))
    assert.match(errorsOf(await finish(ctx, 'tax')), reason)
    assert.equal(io.files.get(files.study(CFG, 'tax')), before)
  }
})

test('a greenfield brief has a Greenfield section instead of Ours against theirs', async () => {
  const notes = brief().replace('## Ours against theirs\nWe round per invoice [f:stripe.rounding].', '## Greenfield\nBuild per-line rounding first.')
  const { ctx } = seeded(notes, [verifiedDocs()], { greenfield: true, references: { lago: 'code-read', stripe: 'specialist' } })
  assert.equal((await finish(ctx, 'tax')).ok, true)
})

test('finish closes only a brief', async () => {
  const { ctx } = seeded(brief(), [verifiedDocs()], { mode: 'deep' })
  assert.match(errorsOf(await finish(ctx, 'tax')), /study tax is mode deep; finish closes a brief/)
})

test('after finishing, a cited finding that is later disputed only warns', async () => {
  const { io, ctx } = seeded(brief())
  await finish(ctx, 'tax')
  io.files.set(files.findings(CFG, 'tax'), toYaml([docsFinding({ status: 'disputed' })]))
  const issues = await runCheck(ctx)
  assert.deepEqual(issues.map(issue => `${issue.level}/${issue.kind}`), ['warn/freshness'])
  assert.match(issues[0]?.message ?? '', /the brief cites stripe\.rounding, which is disputed since 2026-10-08; refresh the brief/)
})
