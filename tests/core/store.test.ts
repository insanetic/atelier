import { test } from 'node:test'
import assert from 'node:assert/strict'
import { files } from '../../core/paths.ts'
import { createStudy, listTopics, loadFindings, loadStudy } from '../../core/store.ts'
import { fakeIo } from './fake-io.ts'
import { CFG, TODAY, docsFinding, seedStudy } from './fixtures.ts'

test('createStudy writes a draft skeleton once', async () => {
  const io = fakeIo()
  const ctx = { io, cfg: CFG, today: TODAY }
  const first = await createStudy(ctx, 'tax', 'quick')
  assert.equal(first.ok && first.value.created, true)
  assert.match(io.files.get(files.study(CFG, 'tax')) ?? '', /status: draft\nmode: quick/)
  assert.equal(io.files.get(files.findings(CFG, 'tax')), '[]\n')
  assert.equal(io.files.get(files.assessment(CFG, 'tax')), '[]\n')
  assert.equal(io.files.get(files.references(CFG)), '[]\n')
  assert.match(io.files.get(files.notes(CFG, 'tax')) ?? '', /^# tax\n/)
  const second = await createStudy(ctx, 'tax', 'full')
  assert.equal(second.ok && second.value.created, false)
})

test('createStudy rejects topics that are not kebab-case', async () => {
  const out = await createStudy({ io: fakeIo(), cfg: CFG, today: TODAY }, 'Tax Study', 'full')
  assert.equal(out.ok, false)
})

test('loaders read what was written', async () => {
  const io = fakeIo()
  seedStudy(io, { findings: [docsFinding()] })
  assert.deepEqual(await listTopics(io, CFG), ['tax'])
  assert.equal((await loadStudy(io, CFG, 'tax'))?.topic, 'tax')
  assert.deepEqual(await loadFindings(io, CFG, 'tax'), [docsFinding()])
})

test('unparsable YAML is reported with its path', async () => {
  const io = fakeIo({ [files.study(CFG, 'tax')]: 'topic: [unclosed' })
  await assert.rejects(loadStudy(io, CFG, 'tax'), /study\.yaml/)
})
