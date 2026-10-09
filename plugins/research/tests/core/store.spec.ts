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
  const second = await createStudy(ctx, 'tax', 'deep')
  assert.equal(second.ok && second.value.created, false)
})

test('createStudy rejects topics that are not kebab-case', async () => {
  const out = await createStudy({ io: fakeIo(), cfg: CFG, today: TODAY }, 'Tax Study', 'deep')
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

test('createStudy refuses to rebuild a study whose study.yaml is empty', async () => {
  const io = fakeIo()
  seedStudy(io, { findings: [docsFinding()], notes: '# tax\nhand-written synthesis\n' })
  io.files.set(files.study(CFG, 'tax'), '# rewriting the frame\n')
  const out = await createStudy({ io, cfg: CFG, today: TODAY }, 'tax', 'deep')
  assert.match(out.ok ? '' : out.errors[0], /study\.yaml is empty or not a mapping/)
  assert.deepEqual(await loadFindings(io, CFG, 'tax'), [docsFinding()])
  assert.equal(io.files.get(files.notes(CFG, 'tax')), '# tax\nhand-written synthesis\n')
})

test('createStudy creates only the files that are missing', async () => {
  const io = fakeIo({ [files.notes(CFG, 'tax')]: '# tax\nnotes first\n' })
  const out = await createStudy({ io, cfg: CFG, today: TODAY }, 'tax', 'deep')
  assert.equal(out.ok && out.value.created, true)
  assert.equal(io.files.get(files.notes(CFG, 'tax')), '# tax\nnotes first\n')
})

test('references.yaml sits at the top of the research dir and no registry is created', async () => {
  const io = fakeIo()
  await createStudy({ io, cfg: CFG, today: TODAY }, 'tax', 'quick')
  assert.equal(files.references(CFG), '/repo/research/references.yaml')
  assert.equal(io.files.get('/repo/research/references.yaml'), '[]\n')
  assert.deepEqual([...io.files.keys()].filter(path => path.includes('/registry/')), [])
})

test('a brief skeleton has no decision fields and gets the brief headings; a deep one gets the deep headings', async () => {
  const io = fakeIo()
  const ctx = { io, cfg: CFG, today: TODAY }
  await createStudy(ctx, 'tax', 'brief')
  const saved = await loadStudy(io, CFG, 'tax')
  assert.equal(saved?.mode, 'brief')
  assert.equal(saved?.decision_needed, undefined)
  assert.equal(saved?.criteria, undefined)
  assert.match(io.files.get(files.notes(CFG, 'tax')) ?? '', /^# tax\n\n## Answer\n\n## Who solved it\n[\s\S]*## Ours against theirs\n[\s\S]*## Open questions\n$/)
  await createStudy(ctx, 'plan-change', 'deep')
  assert.equal((await loadStudy(io, CFG, 'plan-change'))?.decision_needed, '')
  assert.match(io.files.get(files.notes(CFG, 'plan-change')) ?? '', /## Candidates\n/)
})
