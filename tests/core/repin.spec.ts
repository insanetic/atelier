import { test } from 'node:test'
import assert from 'node:assert/strict'
import { repin } from '../../core/repin.ts'
import { loadFindings, loadReferences } from '../../core/store.ts'
import { fakeIo } from './fake-io.ts'
import { gitFake } from './git-fake.ts'
import { CFG, LAGO_FILE, LAGO_URL, NEW_SHA, SHA, TODAY, codeFinding, lagoFilePath, seedStudy } from './fixtures.ts'

test('repin moves code findings whose quote survives and drifts the rest', async () => {
  const moved = '# moved down a line\nclass Taxes\n  def total\n    round(total_tax)\n  end\nend\n'
  const io = fakeIo({ [lagoFilePath()]: LAGO_FILE, [lagoFilePath(NEW_SHA)]: moved })
  const rates = codeFinding({
    id: 'lago.max_rates',
    dimension: 'max_rates',
    answer: 3,
    evidence: [{ kind: 'code', repo: LAGO_URL, sha: SHA, path: 'app/services/rates.rb', lines: '1', quote: 'MAX_RATES = 3' }],
  })
  seedStudy(io, { findings: [codeFinding(), rates] })
  gitFake(io)
  const out = await repin({ io, cfg: CFG, today: TODAY }, 'lago')
  assert.deepEqual(out.ok && out.value, { pins: [{ url: LAGO_URL, sha: NEW_SHA }], moved: ['tax/lago.rounding'], drifted: ['tax/lago.max_rates'] })
  const [rounding, maxRates] = await loadFindings(io, CFG, 'tax')
  assert.deepEqual(rounding.evidence[0], { ...codeFinding().evidence[0], sha: NEW_SHA, lines: '4' })
  assert.equal(maxRates.status, 'drifted')
  const [lago] = await loadReferences(io, CFG)
  assert.deepEqual(lago.repos, [{ url: LAGO_URL, pin: NEW_SHA, pinned_at: TODAY }])
})

test('repin --to needs a full sha', async () => {
  const io = fakeIo()
  seedStudy(io)
  const out = await repin({ io, cfg: CFG, today: TODAY }, 'lago', 'abc')
  assert.match(out.ok ? '' : out.errors[0], /full 40-character sha/)
})

test('repin refuses a repository url git could read as an option, before running git', async () => {
  const io = fakeIo()
  seedStudy(io, { references: [{ id: 'lago', name: 'Lago', repos: [{ url: '--upload-pack=touch /tmp/pwned', pin: SHA, pinned_at: '2026-10-01' }] }] })
  gitFake(io)
  const out = await repin({ io, cfg: CFG, today: TODAY }, 'lago')
  assert.match(out.ok ? '' : out.errors[0], /unsupported repository url/)
  assert.deepEqual(io.runs, [])
})
