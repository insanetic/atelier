const SPECIAL = /[.+^$()|\\]/

/** A `paths:` glob as a pattern over a root-relative path: `**` crosses folders, `*` and `?` stay inside one. */
export function globToRegExp(glob: string): RegExp {
  const pattern = glob.replace(/^\.\//, '')
  let out = ''
  let depth = 0
  for (let at = 0; at < pattern.length; at++) {
    const char = pattern[at] ?? ''
    if (char === '*' && pattern[at + 1] === '*') {
      const isSegment = (at === 0 || pattern[at - 1] === '/') && pattern[at + 2] === '/'
      out += isSegment ? '(?:.*/)?' : '.*'
      at += isSegment ? 2 : 1
    } else if (char === '*') out += '[^/]*'
    else if (char === '?') out += '[^/]'
    else if (char === '{') {
      depth++
      out += '(?:'
    } else if (char === '}' && depth > 0) {
      depth--
      out += ')'
    } else if (char === ',' && depth > 0) out += '|'
    else if (char === '[') {
      const end = pattern.indexOf(']', at + 1)
      if (end === -1) out += '\\['
      else {
        out += `[${pattern.slice(at + 1, end).replace(/^!/, '^').replace(/\\/g, '\\\\')}]`
        at = end
      }
    } else out += SPECIAL.test(char) ? `\\${char}` : char
  }
  return new RegExp(`^${out}$`)
}

export function matchesGlob(path: string, glob: string): boolean {
  return globToRegExp(glob).test(path.replace(/^\.\//, ''))
}
