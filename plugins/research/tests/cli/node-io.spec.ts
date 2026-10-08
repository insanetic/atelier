import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { nodeIo } from '../../cli/node-io.ts'

test('nodeIo reads, writes, lists and sizes real files', async () => {
  const root = await mkdtemp(join(tmpdir(), 'research-'))
  const io = nodeIo()
  await io.writeText(`${root}/a/b/file.txt`, 'hello')
  assert.equal(await io.readText(`${root}/a/b/file.txt`), 'hello')
  assert.equal(await io.readText(`${root}/missing.txt`), undefined)
  assert.deepEqual(await io.listDirs(`${root}/a`), ['b'])
  assert.deepEqual(await io.listDirs(`${root}/none`), [])
  assert.equal(await io.size(`${root}/a/b/file.txt`), 5)
  assert.equal(await io.exists(`${root}/a`), true)
  await rm(root, { recursive: true })
})

test('nodeIo runs commands and reports their exit codes', async () => {
  const io = nodeIo()
  const version = await io.run(['git', '--version'])
  assert.equal(version.exitCode, 0)
  assert.match(version.stdout, /git version/)
  assert.notEqual((await io.run(['git', 'no-such-subcommand'])).exitCode, 0)
})
