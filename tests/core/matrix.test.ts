import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildMatrix, cellText, describeFinding, renderMatrix } from '../../core/matrix.ts'
import { LAGO_URL, TODAY, codeFinding, docsFinding, study } from './fixtures.ts'

test('buildMatrix places answers per dimension and reference with their state', () => {
  const verified = docsFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: TODAY, via: 'fetch' } })
  const matrix = buildMatrix(study(), [verified, codeFinding()], TODAY)
  assert.deepEqual(matrix.refs, ['lago', 'stripe', 'subneo'])
  const [rounding] = matrix.rows
  assert.equal(cellText(rounding.cells[0]), 'per_invoice [?]')
  assert.equal(cellText(rounding.cells[1]), `per_line [ok ${TODAY}]`)
  assert.equal(cellText(rounding.cells[2]), '-')
  assert.deepEqual(matrix.counts, { missing: 4, verified: 1, unverified: 1, stale: 0, drifted: 0, disputed: 0, unknown: 0 })
})

test('pain and superseded findings stay out of the cells', () => {
  const pain = docsFinding({ id: 'stripe.rounding.2', kind: 'pain', detail: 'Per-line rounding drifts from the invoice total' })
  const old = docsFinding({ status: 'superseded' })
  assert.equal(cellText(buildMatrix(study(), [pain, old], TODAY).rows[0].cells[1]), '-')
})

test('renderMatrix prints a markdown table and the status line', () => {
  const out = renderMatrix(buildMatrix(study(), [codeFinding()], TODAY))
  assert.match(out, /^\| dimension \| lago \| stripe \| subneo \|$/m)
  assert.match(out, /^\| rounding \| per_invoice \[\?\] \| - \| - \|$/m)
  assert.match(out, /study tax: 0 ok · 1 unverified · 0 stale · 0 drifted · 0 disputed · 5 missing/)
})

test('describeFinding shows the answer, state and each source', () => {
  assert.deepEqual(describeFinding(codeFinding()), [
    'lago.rounding: per_invoice [unverified, current]',
    `- code ${LAGO_URL}@aaaaaaaaaaaa:app/services/taxes.rb#L2-3: "round(total_tax)"`,
  ])
})
