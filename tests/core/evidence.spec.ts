import { test } from 'node:test'
import assert from 'node:assert/strict'
import type { Evidence } from '../../core/types.ts'
import type { Io } from '../../core/io.ts'
import { cachedIo, checkEvidence, findArchive } from '../../core/evidence.ts'
import { files } from '../../core/paths.ts'
import { fakeIo } from './fake-io.ts'
import type { FakeIo } from './fake-io.ts'
import { CFG, LAGO_FILE, SHA, STRIPE_TAX_URL, TODAY, codeFinding, docsFinding, lagoFilePath } from './fixtures.ts'

const ctxOf = (io: FakeIo) => ({ io, cfg: CFG, today: TODAY })
const STUDY_DIR = files.studyDir(CFG, 'tax')
const code = codeFinding().evidence[0]
const docs = docsFinding().evidence[0]

test('code evidence passes when the cited lines hold the quote', async () => {
  const io = fakeIo({ [lagoFilePath()]: LAGO_FILE })
  assert.deepEqual(await checkEvidence(ctxOf(io), STUDY_DIR, code), { ok: true, via: 'git' })
})

test('code evidence names the right lines when the citation is off', async () => {
  const io = fakeIo({ [lagoFilePath()]: LAGO_FILE })
  assert.deepEqual(await checkEvidence(ctxOf(io), STUDY_DIR, { ...code, lines: '4-5' }), {
    ok: false,
    reason: 'the quote is at lines 3, not 4-5',
    needsBrowser: false,
  })
})

test('code evidence without a checkout asks for a clone', async () => {
  const outcome = await checkEvidence(ctxOf(fakeIo()), STUDY_DIR, code)
  assert.equal(outcome.ok, false)
  assert.match(outcome.ok ? '' : outcome.reason, /clone the reference first/)
})

test('self evidence reads through git show at the sha', async () => {
  const io = fakeIo()
  io.onRun = argv =>
    argv[1] === 'show' && argv[2] === `${SHA}:internal/tax.go`
      ? { exitCode: 0, stdout: 'package app\n\nfunc roundTax() {}\n', stderr: '' }
      : { exitCode: 128, stdout: '', stderr: 'bad object' }
  const self: Evidence = { kind: 'code', repo: 'self', sha: SHA, path: 'internal/tax.go', lines: '3', quote: 'func roundTax()' }
  assert.deepEqual(await checkEvidence(ctxOf(io), STUDY_DIR, self), { ok: true, via: 'git' })
  assert.deepEqual(io.runs[0], ['git', 'show', `${SHA}:internal/tax.go`])
})

test('web evidence passes when the fetched page holds the quote', async () => {
  const io = fakeIo()
  io.pages.set(STRIPE_TAX_URL, { status: 200, text: '<p>Tax is <em>rounded</em> per line item.</p>' })
  assert.deepEqual(await checkEvidence(ctxOf(io), STUDY_DIR, docs), { ok: true, via: 'fetch' })
})

test('a reachable page without the quote needs a browser', async () => {
  const io = fakeIo()
  io.pages.set(STRIPE_TAX_URL, { status: 200, text: '<div id="root"></div>' })
  assert.deepEqual(await checkEvidence(ctxOf(io), STUDY_DIR, docs), {
    ok: false,
    reason: `the quote is not in the fetched page of ${STRIPE_TAX_URL}`,
    needsBrowser: true,
  })
})

test('a dead page falls back to its archive copy', async () => {
  const io = fakeIo()
  const archive = 'https://web.archive.org/web/20261001/https://docs.stripe.com/tax'
  io.pages.set(archive, { status: 200, text: '<p>Tax is rounded per line item.</p>' })
  assert.deepEqual(await checkEvidence(ctxOf(io), STUDY_DIR, { ...docs, archive }), { ok: true, via: 'archive' })
})

test('a source that answers nothing is rejected with its url', async () => {
  const io = fakeIo()
  io.pages.set(STRIPE_TAX_URL, { status: 0, text: '' })
  assert.deepEqual(await checkEvidence(ctxOf(io), STUDY_DIR, docs), {
    ok: false,
    reason: `${STRIPE_TAX_URL} answered nothing`,
    needsBrowser: false,
  })
})

test('artifacts must exist and stay under the size cap', async () => {
  const io = fakeIo({ [`${STUDY_DIR}/artifacts/small.png`]: 'x'.repeat(10), [`${STUDY_DIR}/artifacts/big.png`]: 'x'.repeat(300 * 1024 + 1) })
  const tested = (artifact: string): Evidence => ({ kind: 'tested', artifact, quote: 'the filter applies on every keystroke' })
  assert.deepEqual(await checkEvidence(ctxOf(io), STUDY_DIR, tested('artifacts/small.png')), { ok: true, via: 'file' })
  const big = await checkEvidence(ctxOf(io), STUDY_DIR, tested('artifacts/big.png'))
  assert.match(big.ok ? '' : big.reason, /the cap is 307200/)
  const missing = await checkEvidence(ctxOf(io), STUDY_DIR, tested('artifacts/none.png'))
  assert.match(missing.ok ? '' : missing.reason, /does not exist/)
})

test('findArchive returns the closest snapshot over https', async () => {
  const io = fakeIo()
  io.pages.set(`https://archive.org/wayback/available?url=${encodeURIComponent(STRIPE_TAX_URL)}`, {
    status: 200,
    text: JSON.stringify({ archived_snapshots: { closest: { available: true, url: 'http://web.archive.org/web/20261001/https://docs.stripe.com/tax' } } }),
  })
  assert.equal(await findArchive(io, STRIPE_TAX_URL), 'https://web.archive.org/web/20261001/https://docs.stripe.com/tax')
  assert.equal(await findArchive(fakeIo(), STRIPE_TAX_URL), undefined)
})

test('cachedIo fetches each url once', async () => {
  const seen: string[] = []
  const counting: Io = { ...fakeIo(), async fetchText(url) { seen.push(url); return { status: 200, text: 'x' } } }
  const cached = cachedIo(counting)
  await cached.fetchText('https://a.dev')
  await cached.fetchText('https://a.dev')
  assert.deepEqual(seen, ['https://a.dev'])
})

test('self evidence with a sha git could read as an option never reaches git', async () => {
  const io = fakeIo()
  const evil: Evidence = { kind: 'code', repo: 'self', sha: '--output=/tmp/pwned', path: 'x', lines: '1', quote: 'x' }
  const outcome = await checkEvidence(ctxOf(io), STUDY_DIR, evil)
  assert.equal(outcome.ok, false)
  assert.deepEqual(io.runs, [])
})

test('code evidence with an unsupported repo url is a miss, not a crash', async () => {
  const outcome = await checkEvidence(ctxOf(fakeIo()), STUDY_DIR, { ...code, repo: 'git@github.com:getlago/lago-api.git' })
  assert.equal(outcome.ok, false)
})
