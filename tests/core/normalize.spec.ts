import { test } from 'node:test'
import assert from 'node:assert/strict'
import { containsQuote, htmlToText, locateQuote, normalizeText, numbersIn } from '../../core/normalize.ts'

test('normalizeText folds quotes, dashes, whitespace, case and markdown marks', () => {
  assert.equal(normalizeText('  “Tax” is — `rounded`\n per **line**  '), '"tax" is - rounded per line')
})

test('htmlToText drops scripts and styles and decodes entities', () => {
  const text = htmlToText('<style>p{}</style><script>var x = "<p>"</script><p>A&amp;B&#39;s &#x2014; ok</p>')
  assert.equal(normalizeText(text), "a&b's - ok")
})

test('containsQuote across markup and ligatures', () => {
  const page = '<p>Tax is <b>round</b>ed&nbsp;per line item. Proﬁles apply.</p>'
  assert.equal(containsQuote(htmlToText(page), 'Tax is rounded per line item.'), true)
  assert.equal(containsQuote(htmlToText(page), 'Profiles apply'), true)
  assert.equal(containsQuote(htmlToText(page), 'per invoice'), false)
})

test('an empty quote never matches', () => {
  assert.equal(containsQuote('anything', '   '), false)
})

test('locateQuote returns the tight 1-based line range', () => {
  const text = 'a\nb\n  round(\n    total_tax)\nc\n'
  assert.deepEqual(locateQuote(text, 'round( total_tax)'), { start: 3, end: 4 })
  assert.equal(locateQuote(text, 'missing'), undefined)
})

test('locateQuote stays fast on a 5,000-line file', () => {
  const lines = Array.from({ length: 5000 }, (_, i) => `line ${i} of filler text`)
  lines[4990] = 'the needle is here'
  const started = Date.now()
  assert.deepEqual(locateQuote(lines.join('\n'), 'the needle is here'), { start: 4991, end: 4991 })
  assert.ok(Date.now() - started < 2000, 'locateQuote took longer than 2s')
})

test('numbersIn drops thousands separators and keeps decimals', () => {
  assert.deepEqual(numbersIn('1,000,000 calls, 2.5% and 24 h'), ['1000000', '2.5', '24'])
})

test('locateQuote finds a quote that spans a blank line', () => {
  const text = 'def total\n  sum = a + b\n\n  round(sum)\nend\n'
  assert.deepEqual(locateQuote(text, 'sum = a + b\n\n  round(sum)'), { start: 2, end: 4 })
})

test('locateQuote stays fast on long lines whose words are all common', () => {
  const lines = Array.from({ length: 5000 }, () => 'the '.repeat(1000).trim())
  lines[4990] = 'the needle is here'
  const started = Date.now()
  assert.deepEqual(locateQuote(lines.join('\n'), 'the needle is here'), { start: 4991, end: 4991 })
  assert.ok(Date.now() - started < 2000, `locateQuote took ${Date.now() - started}ms`)
})
