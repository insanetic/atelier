import { describe, expect, test } from 'claude-code/testing'
import { FINDINGS, ROOT, clocks, opened, registered, world } from './world.ts'

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

  test('add_finding records a reuse finding whose licence is quoted and refuses one whose licence is not', async ($, on) => {
    world(on, { 'https://github.com/stripe/openapi': '<p>OpenAPI specification for the Stripe API. License: MIT</p>' })
    await $.session.start(START)
    const reuse = {
      tool: 'mcp__research__add_finding',
      study: 'tax',
      ref: 'stripe',
      kind: 'reuse',
      answer: 'Stripe OpenAPI spec',
      detail: 'Machine-readable tax objects to follow',
      reuse: { type: 'spec', url: 'https://github.com/stripe/openapi', license: 'MIT' },
      evidence: [{ kind: 'docs', url: 'https://github.com/stripe/openapi', quote: 'OpenAPI specification for the Stripe API. License: MIT' }],
    }
    expect(String((await $.tool.call(reuse)).result)).toBe('recorded stripe.reuse.1 (docs, unverified)')
    const wrong = await $.tool.call({ ...reuse, reuse: { ...reuse.reuse, license: 'Apache-2.0' } })
    expect(String(wrong.result)).toContain('license Apache-2.0 is not in any quote')
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

describe('session', () => {
  test('registers the study tools and nothing of the registry', async ($, on) => {
    world(on)
    await $.session.start(START)
    expect(registered.join(',')).toBe('add_finding,verify_finding,set_score,clone,query,matrix')
  })
})
