import { test } from 'node:test'
import assert from 'node:assert/strict'
import { files, join, parseRepoUrl, resolvePath, treeDir } from '../../core/paths.ts'
import { CFG } from './fixtures.ts'

test('join collapses dot segments and duplicate slashes', () => {
  assert.equal(join('/a/b', '../c', './d//e'), '/a/c/d/e')
  assert.equal(join('a', '..'), '.')
  assert.equal(join('/work/subneo-web', '../subneo/research'), '/work/subneo/research')
})

test('resolvePath expands home and keeps absolute paths', () => {
  assert.equal(resolvePath('/repo', '~/.cache/research', '/home/u'), '/home/u/.cache/research')
  assert.equal(resolvePath('/repo', '/abs/dir', '/home/u'), '/abs/dir')
  assert.equal(resolvePath('/work/subneo-web', '../subneo/research', '/home/u'), '/work/subneo/research')
})

test('parseRepoUrl accepts https urls with or without .git', () => {
  assert.deepEqual(parseRepoUrl('https://github.com/getlago/lago-api'), { host: 'github.com', owner: 'getlago', name: 'lago-api' })
  assert.deepEqual(parseRepoUrl('https://github.com/getlago/lago-api.git'), { host: 'github.com', owner: 'getlago', name: 'lago-api' })
})

test('parseRepoUrl rejects ssh urls', () => {
  assert.throws(() => parseRepoUrl('git@github.com:getlago/lago-api.git'), /unsupported repository url/)
})

test('treeDir places one checkout per sha under the cache', () => {
  assert.equal(treeDir(CFG, 'https://github.com/getlago/lago-api', 'abc'), '/home/u/.cache/research/repos/github.com/getlago/lago-api/abc')
})

test('files names every study file under the research dir', () => {
  assert.equal(files.findings(CFG, 'tax'), '/repo/research/studies/tax/findings.yaml')
  assert.equal(files.notes(CFG, 'tax'), '/repo/research/studies/tax/study.md')
  assert.equal(files.references(CFG), '/repo/research/references.yaml')
})
