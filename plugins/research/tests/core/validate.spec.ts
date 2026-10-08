import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { Issue } from '../../core/types.ts'
import {
  canConfirm,
  citationIssues,
  decidedGate,
  methodOf,
  validateFinding,
  validateFindings,
  validateReferences,
  validateScore,
  validateStudy,
} from '../../core/validate.ts'
import { LAGO_URL, REFERENCES, codeFinding, docsFinding, study } from './fixtures.ts'

const text = (issues: Issue[]) => issues.map(item => item.message).join('\n')
const REF_IDS = new Set(REFERENCES.map(ref => ref.id))

test('valid fixtures have no issues', () => {
  assert.deepEqual(validateReferences(REFERENCES, 'references.yaml'), [])
  assert.deepEqual(validateStudy(study(), 'tax', REF_IDS, 'study.yaml'), [])
  assert.deepEqual(validateFinding(docsFinding(), study(), 'findings.yaml'), [])
  assert.deepEqual(validateFinding(codeFinding(), study(), 'findings.yaml'), [])
})

test('a pin that YAML parsed as a number is reported', () => {
  const broken = [{ id: 'lago', name: 'Lago', repos: [{ url: LAGO_URL, pin: 1.2e40, pinned_at: '2026-10-01' }] }]
  assert.match(text(validateReferences(broken, 'f')), /pin must be a full 40-character sha/)
})

test('study references must exist in references.yaml', () => {
  assert.match(text(validateStudy(study({ references: { avalara: 'specialist', subneo: 'ours' } }), 'tax', REF_IDS, 'f')), /references.avalara is not in references.yaml/)
})

test('enum dimensions need at least two snake_case options', () => {
  const s = study({ dimensions: [{ id: 'rounding', ask: 'x', type: 'enum', options: ['Per Line'], volatility: 'slow' }] })
  assert.match(text(validateStudy(s, 'tax', REF_IDS, 'f')), /options needs at least two options/)
})

test('a decided study needs a decision', () => {
  assert.match(text(validateStudy(study({ status: 'decided' }), 'tax', REF_IDS, 'f')), /decision is required when status is decided/)
})

test('a study without an ours reference gets a warning', () => {
  const issues = validateStudy(study({ references: { stripe: 'competitor' } }), 'tax', REF_IDS, 'f')
  assert.equal(issues.length, 1)
  assert.equal(issues[0].level, 'warn')
})

test('answers must be one of the options', () => {
  assert.match(text(validateFinding(docsFinding({ answer: 'per_order' }), study(), 'f')), /is not one of \[per_line, per_invoice\]/)
})

test('unknown answers need searched and may have no evidence', () => {
  assert.match(text(validateFinding(docsFinding({ answer: 'unknown', evidence: [], method: 'claimed' }), study(), 'f')), /needs searched/)
  assert.deepEqual(validateFinding(docsFinding({ answer: 'unknown', evidence: [], method: 'claimed', searched: ['docs.stripe.com/tax'] }), study(), 'f'), [])
})

test('numbers in detail must appear in a quote', () => {
  assert.match(text(validateFinding(docsFinding({ detail: 'Rounded to 4 decimals' }), study(), 'f')), /numbers not found in any quote: 4/)
})

test('number answers must appear in a quote', () => {
  const f = docsFinding({ id: 'stripe.max_rates', dimension: 'max_rates', answer: 5, evidence: [{ kind: 'docs', url: 'https://docs.stripe.com/tax', quote: 'Up to 5 tax rates per line.', retrieved: '2026-10-08' }] })
  assert.deepEqual(validateFinding(f, study(), 'f'), [])
  assert.match(text(validateFinding({ ...f, answer: 6 }, study(), 'f')), /numbers not found in any quote: 6/)
})

test('code evidence needs a full sha and at most 15 lines', () => {
  const f = codeFinding({ evidence: [{ kind: 'code', repo: LAGO_URL, sha: 'abc', path: 'a.rb', lines: '1-20', quote: 'x' }] })
  const issues = text(validateFinding(f, study(), 'f'))
  assert.match(issues, /full 40-character sha/)
  assert.match(issues, /cite at most 15/)
})

test('web quotes are capped at 300 characters', () => {
  const f = docsFinding({ evidence: [{ kind: 'docs', url: 'https://docs.stripe.com/tax', quote: 'x'.repeat(301), retrieved: '2026-10-08' }] })
  assert.match(text(validateFinding(f, study(), 'f')), /quote at most 300/)
})

test('marketing-only findings cannot be confirmed', () => {
  const f = docsFinding({
    evidence: [{ kind: 'marketing', url: 'https://stripe.com/tax', quote: 'Tax is rounded per line item.', retrieved: '2026-10-08' }],
    method: 'claimed',
    confidence: 'confirmed',
    verified: { by: 'verifier', at: '2026-10-08', via: 'fetch' },
  })
  assert.match(text(validateFinding(f, study(), 'f')), /cannot be confirmed/)
})

test('duplicate finding ids are reported', () => {
  assert.match(text(validateFindings([docsFinding(), docsFinding()], study(), 'f')), /stripe.rounding is duplicated/)
})

test('methodOf picks the strongest evidence', () => {
  assert.equal(methodOf([{ kind: 'blog', quote: 'q' }, { kind: 'code', quote: 'q' }]), 'source')
  assert.equal(methodOf([{ kind: 'marketing', quote: 'q' }]), 'claimed')
})

test('canConfirm needs primary evidence or secondary sources from two hosts', () => {
  const blog = (url: string) => ({ kind: 'blog' as const, url, quote: 'q', retrieved: '2026-10-08' })
  assert.equal(canConfirm(docsFinding()), true)
  assert.equal(canConfirm(docsFinding({ method: 'third_party', evidence: [blog('https://a.dev/x')] })), false)
  assert.equal(canConfirm(docsFinding({ method: 'third_party', evidence: [blog('https://a.dev/x'), blog('https://b.dev/y')] })), true)
})

test('scores cite existing findings and use levels 1-5', () => {
  const score = { ref: 'stripe', criterion: 'edge_cases', level: 3, because: ['stripe.rounding'], by: { agent: 'analyst', at: '2026-10-08' } }
  assert.deepEqual(validateScore(score, study(), new Set(['stripe.rounding']), 'f'), [])
  assert.match(text(validateScore({ ...score, because: ['stripe.vat'] }, study(), new Set(['stripe.rounding']), 'f')), /cites stripe.vat, which does not exist/)
  assert.match(text(validateScore({ ...score, level: 7 }, study(), new Set(['stripe.rounding']), 'f')), /level must be 1-5 or unknown/)
})

test('citations in study.md must resolve', () => {
  const index = new Map([['tax', new Set(['stripe.rounding'])], ['invoicing', new Set(['lago.numbering'])]])
  assert.deepEqual(citationIssues('see [f:stripe.rounding] and [f:invoicing/lago.numbering]', 'tax', index, 'study.md'), [])
  assert.match(text(citationIssues('see [f:stripe.vat]', 'tax', index, 'study.md')), /\[f:stripe.vat\] does not resolve/)
})

test('decided gate: a decision must carry a snapshot of what it cited', () => {
  const decision = { chosen: 'a', decided_at: '2026-10-20', cites: ['stripe.rounding'], revisit_when: 'x' }
  const fresh = docsFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: '2026-10-08', via: 'fetch' } })
  const unsnapped = study({ status: 'decided', decision: { ...decision, snapshot: {} } })
  assert.match(text(decidedGate(unsnapped, [fresh], 'f')), /no snapshot of stripe\.rounding; record decisions with research decide/)
  const snapped = study({ status: 'decided', decision: { ...decision, snapshot: { 'stripe.rounding': { verified_at: '2026-10-08', confidence: 'confirmed' } } } })
  assert.deepEqual(decidedGate(snapped, [fresh], 'f'), [])
})

test('decided gate: evidence that changed after the decision only warns', () => {
  const decision = { chosen: 'a', decided_at: '2026-10-20', cites: ['stripe.rounding'], revisit_when: 'x', snapshot: { 'stripe.rounding': { verified_at: '2026-10-08', confidence: 'confirmed' as const } } }
  const decided = study({ status: 'decided', decision })
  for (const later of [docsFinding(), docsFinding({ status: 'disputed' }), docsFinding({ status: 'drifted', confidence: 'confirmed', verified: { by: 'v', at: '2026-10-08', via: 'fetch' } })]) {
    const issues = decidedGate(decided, [later], 'f')
    assert.deepEqual(issues.map(issue => `${issue.level}/${issue.kind}`), ['warn/freshness'])
    assert.match(issues[0].message, /revisit the decision/)
  }
})

test("a finding id must belong to the finding's own ref and dimension", () => {
  assert.match(text(validateFinding(docsFinding({ id: 'lago.rounding' }), study(), 'f')), /id must be stripe\.rounding or stripe\.rounding\.<n>/)
  assert.deepEqual(validateFinding(docsFinding({ id: 'stripe.rounding.2' }), study(), 'f'), [])
})

test('code evidence paths stay inside the checkout', () => {
  const f = codeFinding({ evidence: [{ ...codeFinding().evidence[0], path: '../../../../.ssh/id_rsa' }] })
  assert.match(text(validateFinding(f, study(), 'f')), /path must be relative to the repository root/)
})
