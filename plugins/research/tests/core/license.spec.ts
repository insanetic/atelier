import { test } from 'node:test'
import assert from 'node:assert/strict'
import { licenseGuard } from '../../core/license.ts'
import type { Evidence } from '../../core/types.ts'
import { LAGO_URL, SHA } from './fixtures.ts'

const quoted = (quote: string): Evidence[] => [{ kind: 'code', repo: LAGO_URL, sha: SHA, path: 'LICENSE', lines: '1-2', quote }]

test('a licence is found by its SPDX id or by the full name its own text uses', () => {
  assert.equal(licenseGuard('AGPL-3.0', quoted('GNU AFFERO GENERAL PUBLIC LICENSE\n                       Version 3, 19 November 2007')), undefined)
  assert.equal(licenseGuard('MIT', quoted('"license": "MIT"')), undefined)
  assert.equal(licenseGuard('Apache-2.0', quoted('Apache License\n                           Version 2.0, January 2004')), undefined)
  assert.equal(licenseGuard('BUSL-1.1', quoted('License: BUSL-1.1')), undefined)
  assert.equal(licenseGuard('unknown', []), undefined)
})

test('a licence name inside another word or licence does not count', () => {
  assert.match(licenseGuard('MIT', quoted('Submit a pull request')) ?? '', /license MIT is not in any quote; quote the licence file or the package page, or use unknown/)
  assert.match(licenseGuard('GPL-3.0', quoted('GNU AFFERO GENERAL PUBLIC LICENSE Version 3')) ?? '', /license GPL-3.0 is not in any quote/)
  assert.match(licenseGuard('GPL-3.0', quoted('SPDX-License-Identifier: AGPL-3.0')) ?? '', /not in any quote/)
})
