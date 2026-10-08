import { test } from 'node:test'
import assert from 'node:assert/strict'
import { KIT_VERSION } from '../../core/index.ts'

test('core loads under node type stripping', () => {
  assert.equal(KIT_VERSION, '0.1.0')
})
