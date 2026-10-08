import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseYaml, toYaml } from '../../core/yaml.ts'

test('sha-like and date strings survive a round trip as strings', () => {
  const value = { sha: '1234567e89', at: '2026-10-08', answer: 'per_line' }
  assert.deepEqual(parseYaml(toYaml(value)), value)
})

test('long quotes are not folded across lines', () => {
  const quote = 'word '.repeat(120).trim()
  assert.equal(toYaml({ quote }).trimEnd().split('\n').length, 1)
})

test('an empty document parses as null', () => {
  assert.equal(parseYaml(''), null)
})
