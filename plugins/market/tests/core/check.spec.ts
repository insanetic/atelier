import { test } from 'node:test'
import assert from 'node:assert/strict'
import { runCheck, toYaml } from '../../../research/core/index.ts'
import { fakeIo } from '../../../research/tests/core/fake-io.ts'
import { renderMarketIssues, runMarketCheck } from '../../core/check.ts'
import { marketFiles } from '../../core/paths.ts'
import { CFG, REGISTRY, TODAY, seedMarket } from './fixtures.ts'

const ctxOf = (io: ReturnType<typeof fakeIo>) => ({ io, cfg: CFG, today: TODAY })

test('a clean market has no issues', async () => {
  const io = fakeIo()
  seedMarket(io)
  assert.deepEqual(await runMarketCheck(ctxOf(io)), [])
  assert.equal(renderMarketIssues([]), 'market check: no issues')
})

test('check reports candidates that collide with the registry and entries research does not know', async () => {
  const io = fakeIo()
  seedMarket(io)
  const lago2 = { id: 'lago2', name: 'Lago 2', domains: ['getlago.com'], categories: [], found_by: ['x'], evidence: [{ kind: 'docs', url: 'https://getlago.com', quote: 'billing', retrieved: TODAY }], proposed_at: TODAY }
  io.files.set(marketFiles.candidates(CFG), toYaml([lago2]))
  io.files.set(marketFiles.registry(CFG), toYaml({ ...REGISTRY, orb: { status: 'acquired' } }))
  const rendered = renderMarketIssues(await runMarketCheck(ctxOf(io)))
  assert.match(rendered, /candidate lago2: domain getlago\.com is already registered as lago/)
  assert.match(rendered, /orb is not in research\/references\.yaml/)
})

test('research check never reads research/market/: a broken market leaves it clean', async () => {
  const io = fakeIo()
  seedMarket(io)
  io.files.set(marketFiles.registry(CFG), 'lago: [unclosed')
  assert.deepEqual(await runCheck(ctxOf(io)), [])
  assert.match(renderMarketIssues(await runMarketCheck(ctxOf(io))), /registry\.yaml/)
})
