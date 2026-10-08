import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cloneRef, ensureTree } from '../../core/clone.ts'
import { treeDir } from '../../core/paths.ts'
import { fakeIo } from './fake-io.ts'
import { gitFake } from './git-fake.ts'
import { CFG, LAGO_URL, SHA, TODAY, seedStudy } from './fixtures.ts'

test('ensureTree initialises, fetches and checks out the pinned sha once', async () => {
  const io = fakeIo()
  gitFake(io)
  const ctx = { io, cfg: CFG, today: TODAY }
  const dir = treeDir(CFG, LAGO_URL, SHA)
  assert.deepEqual(await ensureTree(ctx, LAGO_URL, SHA), { ok: true, value: dir, warnings: [] })
  assert.deepEqual(io.runs, [
    ['git', '-C', dir, 'rev-parse', 'HEAD'],
    ['git', 'init', '-q', dir],
    ['git', '-C', dir, 'remote', 'add', 'origin', LAGO_URL],
    ['git', '-C', dir, 'fetch', '-q', '--depth', '1', 'origin', SHA],
    ['git', '-C', dir, '-c', 'advice.detachedHead=false', 'checkout', '-q', '--detach', 'FETCH_HEAD'],
    ['git', '-C', dir, 'rev-parse', 'HEAD'],
  ])
  await ensureTree(ctx, LAGO_URL, SHA)
  assert.equal(io.runs.length, 7)
})

test('a failing fetch is reported with git stderr', async () => {
  const io = fakeIo()
  io.onRun = argv =>
    argv.includes('fetch')
      ? { exitCode: 128, stdout: '', stderr: 'fatal: remote error: upload-pack: not our ref' }
      : { exitCode: argv.includes('rev-parse') ? 128 : 0, stdout: '', stderr: '' }
  const out = await ensureTree({ io, cfg: CFG, today: TODAY }, LAGO_URL, SHA)
  assert.match(out.ok ? '' : out.errors[0], /not our ref/)
})

test('cloneRef checks out every pinned repository of a reference', async () => {
  const io = fakeIo()
  seedStudy(io)
  gitFake(io)
  const ctx = { io, cfg: CFG, today: TODAY }
  assert.deepEqual(await cloneRef(ctx, 'lago'), { ok: true, value: [treeDir(CFG, LAGO_URL, SHA)], warnings: [] })
  const stripe = await cloneRef(ctx, 'stripe')
  assert.match(stripe.ok ? '' : stripe.errors[0], /has no repositories to clone/)
})
