import { test } from 'node:test'
import assert from 'node:assert/strict'
import { main } from '../../cli/rulebook.ts'
import type { CliIo, Env } from '../../cli/rulebook.ts'

const ROOT = '/repo'
const ENTRY = '### HTTP-001 [MUST] HTTP is called only from services\n\n- Bad: a component that injects the client.\n- Checked by: review\n'
const SCOPED = `---\npaths:\n  - 'src/**/*.ts'\n---\n${ENTRY}`

/** An in-memory repository; `git` answers from the table, and fails for a command it does not hold. */
function env(seed: Record<string, string>, git: Record<string, string> = {}, cwd = ROOT): Env {
  const files = new Map(Object.entries(seed).map(([path, text]) => [`${ROOT}/${path}`, text]))
  const childrenOf = (path: string) => [...new Set([...files.keys()].filter(key => key.startsWith(`${path}/`)).map(key => key.slice(path.length + 1).split('/')[0] ?? ''))]
  const io: CliIo = {
    readText: async path => files.get(path),
    list: async path => childrenOf(path).map(name => ({ name, isDir: !files.has(`${path}/${name}`) })),
    exists: async path => files.has(path) || childrenOf(path).length > 0,
    run: async argv => {
      const out = git[argv.slice(1).join(' ')]
      return out === undefined ? { exitCode: 1, stdout: '' } : { exitCode: 0, stdout: out }
    },
  }
  return { cwd, io }
}

const GIT = {
  'diff --name-only --relative HEAD': 'src/b.ts\n',
  'symbolic-ref --quiet --short refs/remotes/origin/HEAD': 'origin/main\n',
  'diff --name-only --relative origin/main...HEAD': 'src/a.ts\nsrc/b.ts\n',
  'ls-files --others --exclude-standard': 'docs/new.md\n',
}

test('no command prints usage; an unknown one and a repository without a catalog exit 2', async () => {
  assert.match((await main([], env({}))).output, /^usage: rulebook <command>/)
  assert.equal((await main(['frobnicate'], env({ '.claude/rules/http.md': ENTRY }))).code, 2)
  assert.deepEqual(await main(['check'], env({ 'README.md': '' })), { code: 2, output: 'rulebook: no catalog; .claude/rules at /repo holds no entries' })
})

test('check passes a sound catalog and exits 1 with the faults of a broken one', async () => {
  assert.deepEqual(await main(['check'], env({ '.claude/rules/http.md': ENTRY })), { code: 0, output: 'rulebook check: 1 entries in 1 files, no issues' })
  const broken = await main(['check'], env({ '.claude/rules/http.md': ENTRY.replace('review', 'spec `src/gone.spec.ts`'), 'CLAUDE.md': 'See HTTP-002.' }))
  assert.equal(broken.code, 1)
  assert.match(broken.output, /^\.claude\/rules\/http\.md:1 HTTP-001: `Checked by:` names src\/gone\.spec\.ts, which does not exist/m)
  assert.match(broken.output, /^CLAUDE\.md:1 cites HTTP-002, which is no entry/m)
  assert.match(broken.output, /rulebook check: 2 to fix$/)
})

test('changed joins the branch, the working tree and the untracked files', async () => {
  assert.deepEqual(await main(['changed'], env({}, GIT)), { code: 0, output: 'docs/new.md\nsrc/a.ts\nsrc/b.ts' })
  assert.equal((await main(['changed'], env({}))).code, 2)
})

test('for selects by the named files, or by the changed ones, from any folder of the repository', async () => {
  const seed = { '.claude/rules/http.md': SCOPED, '.claude/rules/arch.md': ENTRY.replace('HTTP-001', 'ARCH-001') }
  const named = await main(['for', '--ids', 'README.md'], env(seed))
  assert.match(named.output, /Rule files that apply \(1\):\n- \.claude\/rules\/arch\.md \(always\)/)
  const changed = await main(['for', '--ids'], env(seed, GIT))
  assert.match(changed.output, /^- \.claude\/rules\/http\.md \(src\/\*\*\/\*\.ts matches src\/a\.ts\)$/m)
  assert.match(changed.output, /^- HTTP-001 \[MUST\] HTTP is called only from services \(\.claude\/rules\/http\.md:5\)$/m)
  const below = await main(['for', '--ids', 'a.ts'], env(seed, {}, `${ROOT}/src`))
  assert.match(below.output, /^- src\/a\.ts$/m)
  assert.match(below.output, /http\.md \(src/)
})

test('next and show answer from the catalog', async () => {
  const seed = { '.claude/rules/http.md': ENTRY }
  assert.deepEqual(await main(['next', 'HTTP'], env(seed)), { code: 0, output: 'HTTP-002' })
  assert.equal((await main(['next', 'http'], env(seed))).code, 2)
  assert.match((await main(['show', 'HTTP-001'], env(seed))).output, /^<!-- \.claude\/rules\/http\.md:1 -->\n### HTTP-001 \[MUST\]/)
  assert.equal((await main(['show', 'HTTP-009'], env(seed))).code, 2)
})
