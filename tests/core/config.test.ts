import { test } from 'node:test'
import assert from 'node:assert/strict'
import { loadConfig } from '../../core/config.ts'
import { fakeIo } from './fake-io.ts'

test('defaults to ./research and ~/.cache/research', async () => {
  const cfg = await loadConfig(fakeIo(), '/work/subneo', '/home/u')
  assert.deepEqual(cfg, { root: '/work/subneo', dir: '/work/subneo/research', cache: '/home/u/.cache/research' })
})

test('.research.yaml points a sibling repo at the product research dir', async () => {
  const io = fakeIo({ '/work/subneo-web/.research.yaml': 'dir: ../subneo/research\ncache: /tmp/rk\n' })
  const cfg = await loadConfig(io, '/work/subneo-web', '/home/u')
  assert.equal(cfg.dir, '/work/subneo/research')
  assert.equal(cfg.cache, '/tmp/rk')
})
