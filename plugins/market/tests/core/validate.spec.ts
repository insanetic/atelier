import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { Issue } from '../../../research/core/index.ts'
import { REFERENCES } from '../../../research/tests/core/fixtures.ts'
import { validateRegistry, validateTaxonomy } from '../../core/validate.ts'
import { REGISTRY, TAXONOMY } from './fixtures.ts'

const text = (issues: Issue[]) => issues.map(issue => issue.message).join('\n')

test('the taxonomy needs kebab-case categories, snake_case capabilities and written definitions', () => {
  assert.deepEqual(validateTaxonomy(TAXONOMY, 'taxonomy.yaml'), [])
  const broken = { categories: { 'Usage Billing': 'x', metering: '' }, capabilities: { 'public-api': 'x' } }
  const out = text(validateTaxonomy(broken, 'taxonomy.yaml'))
  assert.match(out, /categories\.Usage Billing must be kebab-case/)
  assert.match(out, /categories\.metering needs a definition/)
  assert.match(out, /capabilities\.public-api must be snake_case/)
})

test('a taxonomy scope holds include and exclude rules as text', () => {
  assert.deepEqual(validateTaxonomy({ ...TAXONOMY, scope: { include: ['built for B2B software companies'], exclude: ['mobile in-app purchases'] } }, 'f'), [])
  assert.match(text(validateTaxonomy({ ...TAXONOMY, scope: { include: 'B2B' } }, 'f')), /scope\.include must be a list of rules/)
})

test('registry entries hold market facts and a dated stance, checked against the taxonomy and research references', () => {
  assert.deepEqual(validateRegistry(REGISTRY, REFERENCES, TAXONOMY, 'registry.yaml'), [])
  const odd = {
    orb: { status: 'active' },
    lago: { categories: ['billing'], status: 'bought', owned_by: 'adyen', kind: 'product', stance: { tier: 3, overlap: { metering: 'rival' }, reviewed: 'today' } },
  }
  const out = text(validateRegistry(odd, REFERENCES, TAXONOMY, 'registry.yaml'))
  assert.match(out, /orb is not in research\/references\.yaml/)
  assert.match(out, /lago\.categories: billing is not in taxonomy\.yaml/)
  assert.match(out, /lago\.status must be one of active, acquired, sunset, dead/)
  assert.match(out, /lago\.owned_by adyen is not in research\/references\.yaml/)
  assert.match(out, /lago\.kind is not a market fact; reference facts belong in research\/references\.yaml/)
  assert.match(out, /lago\.stance\.tier must be 1, 2 or watch/)
  assert.match(out, /lago\.stance\.overlap\.metering must be direct or adjacent/)
  assert.match(out, /lago\.stance\.reviewed must be YYYY-MM-DD/)
})

test('two registry entries may not share a domain', () => {
  const twins = { ...REGISTRY, stripe: { domains: ['https://www.getlago.com/'] } }
  assert.match(text(validateRegistry(twins, REFERENCES, TAXONOMY, 'f')), /domain getlago\.com is used by lago and stripe/)
})
