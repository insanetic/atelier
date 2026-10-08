import { describe, expect, test } from 'claude-code/testing'
import { FINDINGS, ROOT, clocks, opened, world } from './world.ts'

const START = { cwd: ROOT, surface: 'terminal' as const, isInteractive: true }

describe('guard', () => {
  test('denies Edit on findings.yaml', async ($, on) => {
    world(on)
    on('tool.call', { tool: 'Edit' }, () => ({ result: 'edited' }))
    const out = await $.tool.call({ tool: 'Edit', file_path: FINDINGS, old_string: 'a', new_string: 'b' })
    expect(out.deny).toContain('add_finding')
  })

  test('lets Edit through for study.md', async ($, on) => {
    world(on)
    on('tool.call', { tool: 'Edit' }, () => ({ result: 'edited' }))
    const out = await $.tool.call({ tool: 'Edit', file_path: `${ROOT}/research/studies/tax/study.md`, old_string: 'a', new_string: 'b' })
    expect(out.deny).toBeUndefined()
  })

  test('denies a Bash redirect into assessment.yaml and lets reads through', async ($, on) => {
    world(on)
    on('tool.call', { tool: 'Bash' }, () => ({ result: 'ran' }))
    const write = await $.tool.call({ tool: 'Bash', command: 'echo x >> research/studies/tax/assessment.yaml' })
    expect(write.deny).toContain('set_score')
    const readOnly = await $.tool.call({ tool: 'Bash', command: 'cat research/studies/tax/findings.yaml | head' })
    expect(readOnly.deny).toBeUndefined()
  })
})

describe('tools', () => {
  test('add_finding records a finding whose quote is on the page', async ($, on) => {
    const files = world(on, { 'https://docs.stripe.com/tax': '<p>Tax is rounded per line item.</p>' })
    await $.session.start(START)
    const out = await $.tool.call({
      tool: 'mcp__research__add_finding',
      study: 'tax',
      ref: 'stripe',
      dimension: 'rounding',
      answer: 'per_line',
      evidence: [{ kind: 'docs', url: 'https://docs.stripe.com/tax', quote: 'Tax is rounded per line item.' }],
    })
    expect(out.result).toBe('recorded stripe.rounding (docs, unverified)')
    expect(files.get(FINDINGS)).toContain('answer: per_line')
  })

  test('add_finding rejects an answer outside the options', async ($, on) => {
    world(on)
    await $.session.start(START)
    const out = await $.tool.call({ tool: 'mcp__research__add_finding', study: 'tax', ref: 'stripe', dimension: 'rounding', answer: 'per_order', evidence: [] })
    expect(String(out.result)).toContain('is not one of [per_line, per_invoice]')
  })

  test('matrix answers with the table and fills the pane', async ($, on) => {
    world(on)
    await $.session.start(START)
    const out = await $.tool.call({ tool: 'mcp__research__matrix', study: 'tax' })
    expect(String(out.result)).toContain('| dimension | stripe |')
    expect(opened).toContain('research-study')
    const props = { title: 'Study tax', isFocused: false, bodyColumns: 100, placement: 'dock' as const, scroll: { offset: 0, bodyRows: 40 }, view: {} }
    const ui = await $.ui.mount({ plugin: 'research', surface: 'terminal', component: 'Pane', props, requestId: 'research-study' })
    expect(await ui.find({ type: 'Text', text: /rounding/ })).toBeDefined()
    await ui.unmount()
  })
})

describe('network', () => {
  test('add_finding gives up on a page that never answers', async ($, on) => {
    world(on, {}, ['https://docs.stripe.com/tax'])
    await $.session.start(START)
    const call = $.tool.call({
      tool: 'mcp__research__add_finding',
      study: 'tax',
      ref: 'stripe',
      dimension: 'rounding',
      answer: 'per_line',
      evidence: [{ kind: 'docs', url: 'https://docs.stripe.com/tax', quote: 'Tax is rounded per line item.' }],
    })
    for (let step = 0; step < 20; step++) await clocks.current?.advance(5_000)
    const out = await call
    expect(String(out.result)).toContain('https://docs.stripe.com/tax answered nothing')
  })
})

describe('registry', () => {
  test('refs lists the registered references of a category', async ($, on) => {
    world(on)
    await $.session.start(START)
    const out = await $.tool.call({ tool: 'mcp__research__refs', category: 'subscription-billing' })
    expect(String(out.result)).toContain('stripe  Stripe  product  -  subscription-billing')
  })

  test('propose_candidate queues a product the registry does not know', async ($, on) => {
    const files = world(on, { 'https://flexprice.io': '<h1>Open-source usage-based billing</h1>' })
    await $.session.start(START)
    const input = {
      tool: 'mcp__research__propose_candidate',
      id: 'flexprice',
      name: 'Flexprice',
      domains: ['flexprice.io'],
      categories: ['subscription-billing'],
      found_by: ['github'],
      evidence: [{ kind: 'docs', url: 'https://flexprice.io', quote: 'Open-source usage-based billing' }],
    }
    expect(String((await $.tool.call(input)).result)).toBe('proposed flexprice (found by github)')
    expect(files.get(`${ROOT}/research/registry/candidates.yaml`)).toContain('id: flexprice')
    const again = await $.tool.call({ ...input, found_by: ['launches'] })
    expect(String(again.result)).toBe('merged into candidate flexprice (found by github, launches)')
    const known = await $.tool.call({ ...input, id: 'stripe-billing', name: 'Stripe', domains: ['stripe.com'] })
    expect(String(known.result)).toContain('already registered as stripe')
  })
})
