import { test } from 'node:test'
import assert from 'node:assert/strict'
import { addDays, isStale, stalePins, stateOf, todayFromMs } from '../../core/fresh.ts'
import { REFERENCES, docsFinding, study } from './fixtures.ts'

const rounding = study().dimensions[0]
const verifiedAt = (at: string) => docsFinding({ confidence: 'confirmed', verified: { by: 'verifier', at, via: 'fetch' } })

test('addDays crosses months and years', () => {
  assert.equal(addDays('2026-12-20', 15), '2027-01-04')
  assert.equal(todayFromMs(Date.UTC(2026, 9, 8, 23, 59)), '2026-10-08')
})

test('a slow dimension goes stale after 365 days', () => {
  assert.equal(isStale(verifiedAt('2025-10-08'), rounding, '2026-10-08'), false)
  assert.equal(isStale(verifiedAt('2025-10-07'), rounding, '2026-10-08'), true)
})

test('stateOf ranks disputed and drifted above verification', () => {
  assert.equal(stateOf(docsFinding({ status: 'disputed' }), rounding, '2026-10-08'), 'disputed')
  assert.equal(stateOf(docsFinding({ status: 'drifted' }), rounding, '2026-10-08'), 'drifted')
  assert.equal(stateOf(docsFinding({ answer: 'unknown' }), rounding, '2026-10-08'), 'unknown')
  assert.equal(stateOf(docsFinding(), rounding, '2026-10-08'), 'unverified')
  assert.equal(stateOf(verifiedAt('2026-10-01'), rounding, '2026-10-08'), 'verified')
})

test('stalePins reports pins older than 180 days', () => {
  assert.deepEqual(stalePins(REFERENCES, '2026-10-08'), [])
  assert.deepEqual(stalePins(REFERENCES, '2027-04-01'), [{ ref: 'lago', url: 'https://github.com/getlago/lago-api', pinned_at: '2026-10-01' }])
})
