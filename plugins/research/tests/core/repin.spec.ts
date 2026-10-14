import { test } from 'node:test'
import assert from 'node:assert/strict'
import { repin } from '../../core/repin.ts'
import { loadFindings, loadReferences } from '../../core/store.ts'
import { files } from '../../core/paths.ts'
import { fakeIo } from './fake-io.ts'
import { gitFake } from './git-fake.ts'
import { CFG, LAGO_FILE, LAGO_URL, NEW_SHA, SHA, TODAY, codeFinding, lagoFilePath, seedStudy, study } from './fixtures.ts'

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

test('repin keeps the comments and layout of a hand-edited references.yaml', async () => {
  const io = fakeIo({ [lagoFilePath()]: LAGO_FILE, [lagoFilePath(NEW_SHA)]: LAGO_FILE })
  seedStudy(io)
  const text = `# facts only\n- id: lago # open source, AGPL\n  name: Lago\n  repos:\n    - url: ${LAGO_URL}\n      pin: ${SHA}\n      pinned_at: 2026-10-01\n# --- standards ---\n- id: stripe\n  name: Stripe\n- id: subneo\n  name: Subneo\n`
  io.files.set(files.references(CFG), text)
  gitFake(io)
  assert.equal((await repin({ io, cfg: CFG, today: TODAY }, 'lago')).ok, true)
  const after = io.files.get(files.references(CFG)) ?? ''
  assert.equal(after, text.replace(SHA, NEW_SHA).replace('2026-10-01', TODAY))
})

test('repin writes nothing when one of the repositories fails', async () => {
  const second = 'https://github.com/getlago/lago-front'
  const io = fakeIo({ [lagoFilePath()]: LAGO_FILE, [lagoFilePath(NEW_SHA)]: '' })
  const references = [{ id: 'lago', name: 'Lago', kind: 'product' as const, repos: [{ url: LAGO_URL, pin: SHA, pinned_at: '2026-10-01' }, { url: second, pin: SHA, pinned_at: '2026-10-01' }] }]
  seedStudy(io, { references, study: study({ references: { lago: 'competitor' } }), findings: [codeFinding()] })
  gitFake(io)
  const failing = io.onRun
  io.onRun = (argv, cwd) => (argv.includes('ls-remote') && argv.includes(second) ? { exitCode: 128, stdout: '', stderr: 'not found' } : failing(argv, cwd))
  const findingsBefore = io.files.get(files.findings(CFG, 'tax'))
  const out = await repin({ io, cfg: CFG, today: TODAY }, 'lago')
  assert.match(out.ok ? '' : out.errors[0], /cannot resolve HEAD of .*lago-front/)
  assert.equal(io.files.get(files.findings(CFG, 'tax')), findingsBefore)
  assert.equal((await loadReferences(io, CFG))[0]?.repos?.[0]?.pin, SHA)
})

test('repin leaves a disputed finding disputed when its quote is gone', async () => {
  const io = fakeIo({ [lagoFilePath()]: LAGO_FILE, [lagoFilePath(NEW_SHA)]: 'class Taxes\nend\n' })
  seedStudy(io, { findings: [codeFinding({ status: 'disputed', note: 'the code rounds per line' })] })
  gitFake(io)
  const out = await repin({ io, cfg: CFG, today: TODAY }, 'lago')
  assert.deepEqual(out.ok && out.value.drifted, ['tax/lago.rounding'])
  assert.equal((await loadFindings(io, CFG, 'tax'))[0]?.status, 'disputed')
})
