import { mock } from 'claude-code/testing'
import type { On } from 'claude-code'

export const ROOT = '/work/product'

const SEED: Record<string, string> = {
  [`${ROOT}/research/references.yaml`]: '- id: stripe\n  name: Stripe\n  kind: product\n',
  [`${ROOT}/research/market/taxonomy.yaml`]: 'categories:\n  subscription-billing: Recurring plans and invoices\ncapabilities: {}\n',
  [`${ROOT}/research/market/registry.yaml`]: 'stripe:\n  domains: [stripe.com]\n  categories: [subscription-billing]\n',
}

/** The world beneath the plugin: an in-memory file system, fixed pages, no processes. */
export function world(on: On, pages: Record<string, string> = {}): Map<string, string> {
  const files = new Map(Object.entries(SEED))
  const childrenOf = (path: string) => [
    ...new Set([...files.keys()].filter(key => key.startsWith(`${path}/`)).map(key => key.slice(path.length + 1).split('/')[0])),
  ]
  mock.env(on, { HOME: '/home/u' })
  mock.clock(on, { now: Date.UTC(2026, 9, 8) })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.root', () => ({ value: ROOT }))
  on('tool.register', ($, e) => ({ value: { tool: `mcp__market__${e.name}` } }))
  on('fs.exists', ($, e) => ({ value: files.has(e.path) || childrenOf(e.path).length > 0 }))
  on('fs.read', ($, e) => {
    const text = files.get(e.path)
    return text === undefined ? { deny: `ENOENT: ${e.path}` } : { value: text }
  })
  on('fs.write', ($, e) => {
    files.set(e.path, e.text)
    return { value: undefined }
  })
  on('fs.list', ($, e) => ({
    value: childrenOf(e.path).map(name => ({ name, kind: files.has(`${e.path}/${name}`) ? ('file' as const) : ('dir' as const), size: 0, mtimeMs: 0, isLink: false })),
  }))
  on('fs.stat', ($, e) => ({ value: { kind: files.has(e.path) ? ('file' as const) : ('dir' as const), size: files.get(e.path)?.length ?? 0, mtimeMs: 0, isLink: false } }))
  on('http.fetch', ($, e) => {
    const text = pages[e.url]
    return { value: { status: text === undefined ? 404 : 200, ok: text !== undefined, headers: {}, text: text ?? '' } }
  })
  on('process.run', () => ({ value: { exitCode: 1, stdout: '', stderr: 'no processes in tests', isStdoutTruncated: false, isStderrTruncated: false } }))
  return files
}
