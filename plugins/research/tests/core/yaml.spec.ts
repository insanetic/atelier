import { test } from 'node:test'
import assert from 'node:assert/strict'
import { appendToYamlList, parseYaml, toYaml } from '../../core/yaml.ts'

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

test('appending to an empty flow list writes a readable block list', () => {
  const out = appendToYamlList('[]\n', { id: 'meterflow', reason: 'too early' })
  assert.equal(out, '- id: meterflow\n  reason: too early\n')
  assert.equal(appendToYamlList(out, { id: 'lotus', reason: 'stale' }), '- id: meterflow\n  reason: too early\n- id: lotus\n  reason: stale\n')
  assert.equal(appendToYamlList('[ { id: a } ]\n', { id: 'b' }), '- id: a\n- id: b\n')
})
