import { test } from 'node:test'
import assert from 'node:assert/strict'
import { query, renderHits } from '../../core/query.ts'
import { fakeIo } from './fake-io.ts'
import { CFG, TODAY, codeFinding, docsFinding, seedStudy } from './fixtures.ts'

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
