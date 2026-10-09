import { test } from 'node:test'
import assert from 'node:assert/strict'
import { query, renderHits } from '../../core/query.ts'
import { fakeIo } from './fake-io.ts'
import { files } from '../../core/paths.ts'
import { toYaml } from '../../core/yaml.ts'
import { CFG, TODAY, codeFinding, docsFinding, seedStudy, study } from './fixtures.ts'

test('query filters by ref, state, dimension and text', async () => {
  const io = fakeIo()
  seedStudy(io, { findings: [docsFinding(), codeFinding()] })
  const ctx = { io, cfg: CFG, today: TODAY }
  assert.deepEqual((await query(ctx, { ref: 'lago' })).map(hit => hit.finding.id), ['lago.rounding'])
  assert.deepEqual((await query(ctx, { text: 'ROUND(total' })).map(hit => hit.finding.id), ['lago.rounding'])
  assert.deepEqual(await query(ctx, { state: 'verified' }), [])
  assert.match(renderHits(await query(ctx, { dimension: 'rounding' })), /^tax\/stripe\.rounding \[unverified\] stripe rounding = per_line$/m)
  assert.equal(renderHits([]), 'no findings match')
})

test('query skips malformed findings instead of crashing', async () => {
  const io = fakeIo()
  seedStudy(io)
  io.files.set(files.findings(CFG, 'tax'), toYaml([docsFinding(), { id: 'lago.rounding', ref: 'lago', dimension: 'rounding' }]))
  assert.deepEqual((await query({ io, cfg: CFG, today: TODAY }, {})).map(hit => hit.finding.id), ['stripe.rounding'])
})

test('query filters by id and kind and shows the evidence', async () => {
  const io = fakeIo()
  const pain = docsFinding({ id: 'stripe.rounding.2', kind: 'pain', detail: 'Per-line rounding drifts from the invoice total' })
  seedStudy(io, { findings: [docsFinding(), pain] })
  const ctx = { io, cfg: CFG, today: TODAY }
  assert.deepEqual((await query(ctx, { kind: 'pain' })).map(hit => hit.finding.id), ['stripe.rounding.2'])
  assert.match(renderHits(await query(ctx, { id: 'stripe.rounding' })), /docs https:\/\/docs\.stripe\.com\/tax: "Tax is rounded per line item\."/)
})

test('query refuses a study name that is not a topic', async () => {
  const io = fakeIo()
  seedStudy(io)
  io.files.set('/repo/research/other/study.yaml', toYaml(study({ topic: '../other' })))
  io.files.set('/repo/research/other/findings.yaml', toYaml([docsFinding()]))
  assert.deepEqual(await query({ io, cfg: CFG, today: TODAY }, { study: '../other' }), [])
})

test('a finding without a dimension is labelled by its kind', async () => {
  const io = fakeIo()
  const pain = docsFinding({ id: 'stripe.pain.1', dimension: undefined, kind: 'pain', answer: 'Rounding drift', detail: 'Per-line rounding drifts from the invoice total' })
  seedStudy(io, { findings: [pain] })
  assert.match(renderHits(await query({ io, cfg: CFG, today: TODAY }, {})), /^tax\/stripe\.pain\.1 \[unverified\] stripe pain = Rounding drift$/m)
})
