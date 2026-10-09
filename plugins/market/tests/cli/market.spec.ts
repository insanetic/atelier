import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toYaml } from '../../../research/core/index.ts'
import { fakeIo } from '../../../research/tests/core/fake-io.ts'
import type { FakeIo } from '../../../research/tests/core/fake-io.ts'
import { main } from '../../cli/market.ts'
import { marketFiles } from '../../core/paths.ts'
import { CFG, TODAY, seedMarket } from '../core/fixtures.ts'

const env = (io: FakeIo) => ({ cwd: '/repo', home: '/home/u', today: TODAY, io })
const candidate = (id: string, name: string, domain: string) => ({
  id,
  name,
  domains: [domain],
  categories: ['usage-billing'],
  found_by: ['github-topics'],
  evidence: [{ kind: 'docs', url: `https://${domain}`, quote: 'usage-based billing', retrieved: TODAY }],
  proposed_at: TODAY,
})

test('no command prints usage; unknown commands exit 2', async () => {
  assert.match((await main([], env(fakeIo()))).output, /^usage: market <command>/)
  assert.equal((await main(['frobnicate'], env(fakeIo()))).code, 2)
})

test('refs lists tracked references by category', async () => {
  const io = fakeIo()
  seedMarket(io)
  const out = await main(['refs', '--category', 'usage-billing'], env(io))
  assert.match(out.output, /^lago {2}Lago {2}product {2}tier 1 {2}usage-billing,subscription-billing$/m)
})

test('candidates, approve and reject work the queue', async () => {
  const io = fakeIo()
  seedMarket(io)
  assert.deepEqual(await main(['candidates'], env(io)), { code: 0, output: 'no candidates' })
  io.files.set(marketFiles.candidates(CFG), toYaml([candidate('flexprice', 'Flexprice', 'flexprice.io'), candidate('meterflow', 'MeterFlow', 'meterflow.dev')]))
  assert.match((await main(['candidates'], env(io))).output, /^flexprice {2}Flexprice {2}flexprice\.io {2}usage-billing {2}found by github-topics$/m)
  assert.deepEqual(await main(['approve', 'flexprice'], env(io)), { code: 0, output: 'approved flexprice: added to research/references.yaml and the market registry' })
  assert.equal((await main(['reject', 'meterflow'], env(io))).code, 2)
  assert.deepEqual(await main(['reject', 'meterflow', '--reason', 'a hobby project'], env(io)), { code: 0, output: 'rejected meterflow: a hobby project' })
  assert.deepEqual(await main(['candidates'], env(io)), { code: 0, output: 'no candidates' })
})

test('landscape syncs the capability study and check validates the market files', async () => {
  const io = fakeIo()
  seedMarket(io)
  assert.deepEqual(await main(['landscape'], env(io)), { code: 0, output: 'landscape: 2 capabilities, 3 references' })
  assert.deepEqual(await main(['check'], env(io)), { code: 0, output: 'market check: no issues' })
  io.files.set(marketFiles.registry(CFG), toYaml({ orb: { status: 'active' } }))
  assert.equal((await main(['check'], env(io))).code, 1)
})
