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

export function normalizeText(text: string): string {
  return text
    .normalize('NFKC')
    .replace(/[‘’‚‛′]/g, "'")
    .replace(/[“”„‟″]/g, '"')
    .replace(/[‐-―−]/g, '-')
    .replace(/[`*]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

export function containsQuote(haystack: string, quote: string): boolean {
  const needle = normalizeText(quote)
  return needle !== '' && normalizeText(haystack).includes(needle)
}

export function locateQuote(text: string, quote: string, maxSpan = 30): { start: number; end: number } | undefined {
  const needle = normalizeText(quote)
  if (needle === '') return undefined
  const lines = text.split('\n')
  const normalized = lines.map(normalizeText)
  const firstWord = needle.split(' ')[0] ?? needle
  for (let start = 0; start < lines.length; start++) {
    if (!normalized.slice(start, start + maxSpan).join(' ').includes(firstWord)) continue
    for (let end = start; end < Math.min(lines.length, start + maxSpan); end++) {
      if (!normalized.slice(start, end + 1).join(' ').includes(needle)) continue
      let first = start
      while (first < end && normalized.slice(first + 1, end + 1).join(' ').includes(needle)) first++
      return { start: first + 1, end: end + 1 }
    }
  }
  return undefined
}

export function numbersIn(text: string): string[] {
  return (text.match(/\d+(?:[.,]\d+)*/g) ?? []).map(number => number.replace(/,(?=\d{3}(?!\d))/g, ''))
}
