import { describe, expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const ROOT = '/work/product'
const START = { cwd: ROOT, surface: 'terminal' as const, isInteractive: true }
const GOOD = '### HTTP-001 [MUST] HTTP is called only from services\n\n- Bad: a component that injects the client.\n- Checked by: review\n'

/** The world beneath the plugin: an in-memory file system, and an Edit and a Write that store what they are given. */
function world(on: On, seed: Record<string, string>): Map<string, string> {
  const files = new Map(Object.entries(seed).map(([path, text]) => [`${ROOT}/${path}`, text]))
  const childrenOf = (path: string) => [...new Set([...files.keys()].filter(key => key.startsWith(`${path}/`)).map(key => key.slice(path.length + 1).split('/')[0] ?? ''))]
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.root', () => ({ value: ROOT }))
  on('fs.exists', ($, e) => ({ value: files.has(e.path) || childrenOf(e.path).length > 0 }))
  on('fs.read', ($, e) => {
    const text = files.get(e.path)
    return text === undefined ? { deny: `ENOENT: ${e.path}` } : { value: text }
  })
  on('fs.list', ($, e) => ({
    value: childrenOf(e.path).map(name => ({ name, kind: files.has(`${e.path}/${name}`) ? ('file' as const) : ('dir' as const), size: 0, mtimeMs: 0, isLink: false })),
  }))
  on('tool.call', { tool: 'Write' }, ($, e) => {
    files.set(e.file_path, e.content)
    return { result: { type: 'create', filePath: e.file_path, content: e.content, structuredPatch: [], originalFile: null } as never }
  })
  return files
}

describe('the catalog check after an edit', () => {
  test('a rules file left with a fault reports it beside the result', async ($, on) => {
    world(on, { '.claude/rules/http.md': GOOD })
    await $.session.start(START)
    const out = await $.tool.call({ tool: 'Write', file_path: `${ROOT}/.claude/rules/api.md`, content: `${GOOD}\n### HTTP-002 [MUST] Errors carry a code\n` })
    const said = (out.context ?? []).join('\n')
    expect(said).toContain('rulebook check: 2 to fix')
    expect(said).toContain('.claude/rules/http.md:1 HTTP-001: the ID is already used at .claude/rules/api.md:1')
    expect(said).toContain('.claude/rules/api.md:6 HTTP-002: add a `- Checked by:` line')
  })

  test('a clean catalog and a file outside it add nothing', async ($, on) => {
    world(on, { '.claude/rules/http.md': GOOD })
    await $.session.start(START)
    const clean = await $.tool.call({ tool: 'Write', file_path: `${ROOT}/.claude/rules/api.md`, content: GOOD.replace('HTTP-001', 'API-001') })
    expect(clean.context).toBe(undefined)
    const outside = await $.tool.call({ tool: 'Write', file_path: `${ROOT}/src/a.md`, content: '### HTTP-001 [MUST] Again\n' })
    expect(outside.context).toBe(undefined)
  })
})
