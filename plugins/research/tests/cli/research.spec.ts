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

const candidate = (id: string, name: string, domain: string) => ({
  id,
  name,
  domains: [domain],
  categories: ['usage-billing'],
  found_by: ['github-topics'],
  evidence: [{ kind: 'docs', url: `https://${domain}`, quote: 'usage-based billing', retrieved: TODAY }],
  proposed_at: TODAY,
})

test('refs lists registered references by category', async () => {
  const io = fakeIo()
  seedStudy(io)
  const out = await main(['refs', '--category', 'usage-billing'], env(io))
  assert.equal(out.code, 0)
  assert.match(out.output, /^lago {2}Lago {2}product {2}tier 1 {2}usage-billing,subscription-billing$/m)
})

test('candidates lists the queue with the channels that found each one', async () => {
  const io = fakeIo()
  seedStudy(io)
  assert.deepEqual(await main(['candidates'], env(io)), { code: 0, output: 'no candidates' })
  io.files.set(files.candidates(CFG), toYaml([candidate('flexprice', 'Flexprice', 'flexprice.io')]))
  assert.deepEqual(await main(['candidates'], env(io)), { code: 0, output: 'flexprice  Flexprice  flexprice.io  usage-billing  found by github-topics' })
})

test('approve and reject take candidates out of the queue', async () => {
  const io = fakeIo()
  seedStudy(io)
  io.files.set(files.candidates(CFG), toYaml([candidate('flexprice', 'Flexprice', 'flexprice.io'), candidate('meterflow', 'MeterFlow', 'meterflow.dev')]))
  assert.deepEqual(await main(['approve', 'flexprice'], env(io)), { code: 0, output: 'approved flexprice: added to the registry' })
  assert.equal((await main(['reject', 'meterflow'], env(io))).code, 2)
  assert.deepEqual(await main(['reject', 'meterflow', '--reason', 'a hobby project'], env(io)), { code: 0, output: 'rejected meterflow: a hobby project' })
  assert.deepEqual(await main(['candidates'], env(io)), { code: 0, output: 'no candidates' })
})

test('landscape syncs the capability study with the registry', async () => {
  const io = fakeIo()
  seedStudy(io)
  assert.deepEqual(await main(['landscape'], env(io)), { code: 0, output: 'landscape: 2 capabilities, 3 references' })
})
