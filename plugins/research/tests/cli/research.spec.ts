import { test } from 'node:test'
import assert from 'node:assert/strict'
import { main } from '../../cli/research.ts'
import { files } from '../../core/paths.ts'
import { fakeIo } from '../core/fake-io.ts'
import type { FakeIo } from '../core/fake-io.ts'
import { toYaml } from '../../core/yaml.ts'
import { CFG, TODAY, codeFinding, docsFinding, seedStudy, study } from '../core/fixtures.ts'

const env = (io: FakeIo) => ({ cwd: '/repo', home: '/home/u', today: TODAY, io })

test('no command prints usage', async () => {
  const out = await main([], env(fakeIo()))
  assert.equal(out.code, 0)
  assert.match(out.output, /^usage: research <command>/)
})

test('unknown commands exit 2 with usage', async () => {
  const out = await main(['frobnicate'], env(fakeIo()))
  assert.equal(out.code, 2)
  assert.match(out.output, /unknown command frobnicate/)
})

test('init creates a study under the configured dir', async () => {
  const io = fakeIo()
  const out = await main(['init', 'tax', '--quick'], env(io))
  assert.deepEqual(out, { code: 0, output: 'created /repo/research/studies/tax' })
  assert.ok(io.files.has(files.study(CFG, 'tax')))
})

test('check exits 1 on errors and 0 when clean', async () => {
  const clean = fakeIo()
  seedStudy(clean, { findings: [docsFinding()] })
  assert.deepEqual(await main(['check'], env(clean)), { code: 0, output: 'research check: no issues' })
  const broken = fakeIo()
  seedStudy(broken, { findings: [docsFinding({ answer: 'per_order' })] })
  assert.equal((await main(['check'], env(broken))).code, 1)
})

test('stale lists only freshness issues', async () => {
  const io = fakeIo()
  seedStudy(io, { findings: [codeFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: '2024-01-01', via: 'git' } })] })
  const out = await main(['stale'], env(io))
  assert.equal(out.code, 0)
  assert.match(out.output, /^warn .*lago.rounding: verified 2024-01-01/)
})

test('matrix prints the table and fails for a missing study', async () => {
  const io = fakeIo()
  seedStudy(io, { findings: [codeFinding()] })
  assert.match((await main(['matrix', 'tax'], env(io))).output, /\| rounding \| per_invoice \[\?\] \| - \| - \|/)
  assert.deepEqual(await main(['matrix', 'billing'], env(io)), { code: 1, output: 'study billing does not exist' })
})

test('query passes filters through and rejects unknown states', async () => {
  const io = fakeIo()
  seedStudy(io, { findings: [docsFinding(), codeFinding()] })
  assert.match((await main(['query', '--ref', 'lago'], env(io))).output, /^tax\/lago.rounding /)
  assert.equal((await main(['query', '--state', 'fresh'], env(io))).code, 2)
})

test('reverify prints what changed', async () => {
  const io = fakeIo()
  seedStudy(io)
  const out = await main(['reverify', '--due'], env(io))
  assert.deepEqual(out, { code: 0, output: 'research reverify: nothing changed' })
})

test('clone reports a reference without repositories', async () => {
  const io = fakeIo()
  seedStudy(io)
  assert.deepEqual(await main(['clone', 'stripe'], env(io)), { code: 1, output: 'reference stripe has no repositories to clone' })
})

test('matrix of a study whose dimensions key is empty reports the study errors', async () => {
  const io = fakeIo()
  seedStudy(io)
  io.files.set(files.study(CFG, 'tax'), toYaml(study()).replace(/dimensions:[\s\S]*?criteria:/, 'dimensions:\ncriteria:'))
  const out = await main(['matrix', 'tax'], env(io))
  assert.equal(out.code, 1)
  assert.match(out.output, /study tax has errors: dimensions must be a list/)
})

test('decide records a decision from the command line', async () => {
  const io = fakeIo()
  seedStudy(io, { findings: [docsFinding({ confidence: 'confirmed', verified: { by: 'verifier', at: TODAY, via: 'fetch' } })] })
  const out = await main(['decide', 'tax', '--chosen', 'engine', '--cites', 'stripe.rounding', '--revisit', 'Stripe changes rounding'], env(io))
  assert.deepEqual(out, { code: 0, output: 'decided tax: engine (cites stripe.rounding)' })
})

test('the registry commands are gone; they live in the market plugin', async () => {
  for (const command of ['refs', 'candidates', 'approve', 'reject', 'landscape']) {
    const out = await main([command], env(fakeIo()))
    assert.equal(out.code, 2)
    assert.match(out.output, new RegExp(`unknown command ${command}`))
  }
})

test('init makes a brief by default and takes --quick or --deep', async () => {
  const io = fakeIo()
  await main(['init', 'tax'], env(io))
  assert.match(io.files.get(files.study(CFG, 'tax')) ?? '', /mode: brief/)
  await main(['init', 'plan-change', '--deep'], env(io))
  assert.match(io.files.get(files.study(CFG, 'plan-change')) ?? '', /mode: deep/)
})
