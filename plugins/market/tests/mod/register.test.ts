import { describe, expect, test } from 'claude-code/testing'
import { ROOT, world } from './world.ts'

const START = { cwd: ROOT, surface: 'terminal' as const, isInteractive: true }

describe('registry', () => {
  test('refs lists the tracked references of a category', async ($, on) => {
    world(on)
    await $.session.start(START)
    const out = await $.tool.call({ tool: 'mcp__market__refs', category: 'subscription-billing' })
    expect(String(out.result)).toContain('stripe  Stripe  product  -  subscription-billing')
  })

  test('propose_candidate queues a product the registry does not know, merges a second channel and refuses a known one', async ($, on) => {
    const files = world(on, { 'https://flexprice.io': '<h1>Open-source usage-based billing</h1>' })
    await $.session.start(START)
    const input = {
      tool: 'mcp__market__propose_candidate',
      id: 'flexprice',
      name: 'Flexprice',
      domains: ['flexprice.io'],
      categories: ['subscription-billing'],
      found_by: ['github'],
      evidence: [{ kind: 'docs', url: 'https://flexprice.io', quote: 'Open-source usage-based billing' }],
    }
    expect(String((await $.tool.call(input)).result)).toBe('proposed flexprice (found by github)')
    expect(files.get(`${ROOT}/research/market/candidates.yaml`)).toContain('id: flexprice')
    expect(String((await $.tool.call({ ...input, found_by: ['launches'] })).result)).toBe('merged into candidate flexprice (found by github, launches)')
    expect(String((await $.tool.call({ ...input, id: 'stripe-billing', name: 'Stripe', domains: ['stripe.com'] })).result)).toContain('already registered as stripe')
  })
})
