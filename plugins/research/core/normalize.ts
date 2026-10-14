const NAMED: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: ' ',
  ndash: '-',
  mdash: '-',
  hellip: '...',
  lsquo: "'",
  rsquo: "'",
  ldquo: '"',
  rdquo: '"',
  laquo: '"',
  raquo: '"',
  copy: '©',
  reg: '®',
  trade: '™',
  times: '×',
  divide: '÷',
  rarr: '→',
  larr: '←',
  harr: '↔',
  bull: '•',
  middot: '·',
  shy: '',
  zwsp: '',
  zwj: '',
  zwnj: '',
}

const INLINE_TAG = /<\/?(?:a|abbr|b|code|em|i|kbd|mark|small|span|strong|sub|sup|var)\b[^>]*>/gi

export function decodeEntities(text: string): string {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, body: string) => {
    if (body.startsWith('#')) {
      const isHex = body[1] === 'x' || body[1] === 'X'
      const code = isHex ? parseInt(body.slice(2), 16) : parseInt(body.slice(1), 10)
      return Number.isFinite(code) && code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : whole
    }
    return NAMED[body.toLowerCase()] ?? whole
  })
}

/** Page text for quote matching: inline tags vanish, block tags become spaces. */
export function htmlToText(html: string): string {
  const stripped = html
    .replace(/<script\b[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[\s\S]*?<\/style>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(INLINE_TAG, '')
    .replace(/<[^>]+>/g, ' ')
  return decodeEntities(stripped)
}

const LOOKS_LIKE_HTML = /<(?:!doctype\s+html|html|head|body|div|p|span|a|h[1-6]|ul|ol|li|table|article|main|section|em|strong|code|pre|br)\b/i

/** A fetched page as text: HTML loses its markup, anything else (raw markdown, source, JSON) is kept as it is. */
export function pageText(page: string): string {
  return LOOKS_LIKE_HTML.test(page) ? htmlToText(page) : page
}

/**
 * Text for comparing quotes. Prose (markup: true) also drops backticks and
 * asterisks, which markdown and rendered pages disagree on; code keeps them, as
 * `a * b` and `a b` are different code.
 */
export function normalizeText(text: string, options: { markup?: boolean } = {}): string {
  const plain = text
    .normalize('NFKC')
    .replace(/[\u00ad\u200b-\u200d\u2060\ufeff]/g, '')
    .replace(/[‘’‚‛′]/g, "'")
    .replace(/[“”„‟″]/g, '"')
    .replace(/[‐-―−]/g, '-')
  return (options.markup === true ? plain.replace(/[`*]/g, '') : plain).replace(/\s+/g, ' ').trim().toLowerCase()
}

export function containsQuote(haystack: string, quote: string, options: { markup?: boolean } = {}): boolean {
  const needle = normalizeText(quote, options)
  return needle !== '' && normalizeText(haystack, options).includes(needle)
}

/**
 * Finds a quote's 1-based line range. Lines are normalized once and joined by a
 * single space (blank lines drop out), so one indexOf covers the whole file.
 */
export function locateQuote(text: string, quote: string): { start: number; end: number } | undefined {
  const needle = normalizeText(quote)
  if (needle === '') return undefined
  const offsets: number[] = []
  const lineNumbers: number[] = []
  let joined = ''
  text.split('\n').forEach((line, index) => {
    const normalized = normalizeText(line)
    if (normalized === '') return
    if (joined !== '') joined += ' '
    offsets.push(joined.length)
    lineNumbers.push(index + 1)
    joined += normalized
  })
  const at = joined.indexOf(needle)
  if (at === -1) return undefined
  const lineAt = (offset: number) => {
    let low = 0
    let high = offsets.length - 1
    while (low < high) {
      const mid = Math.ceil((low + high) / 2)
      if ((offsets[mid] ?? 0) <= offset) low = mid
      else high = mid - 1
    }
    return lineNumbers[low] ?? 1
  }
  return { start: lineAt(at), end: lineAt(at + needle.length - 1) }
}

export function numbersIn(text: string): string[] {
  return (text.match(/\d+(?:[.,]\d+)*/g) ?? []).map(number => number.replace(/,(?=\d{3}(?!\d))/g, ''))
}
