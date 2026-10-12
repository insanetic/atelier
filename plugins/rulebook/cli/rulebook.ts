import { RULES_DIR, entryText, nextId, openWorkspace, renderIssues, renderSelection, rulesFor } from '../core/index.ts'
import type { Io } from '../core/index.ts'

export interface RunResult {
  readonly exitCode: number
  readonly stdout: string
}

export interface CliIo extends Io {
  run(argv: readonly string[], cwd: string): Promise<RunResult>
}

export interface Env {
  readonly cwd: string
  readonly io: CliIo
}

export interface Result {
  readonly code: number
  readonly output: string
}

const USAGE = `usage: rulebook <command>

  check                        every machine-decidable fault of the catalog in ${RULES_DIR}; exit 1 when there is one
  for [--ids] [--base <ref>] [<file>...]
                               the rule files that govern the files, and their entries for review, in full
                               (--ids: one line each); without files: the changed files
  changed [--base <ref>]       the changed files: the branch against its base, the working tree, the untracked
  next <PREFIX>                the next free ID of a prefix
  show <ID>...                 the entries as written`

const fail = (output: string): Result => ({ code: 2, output })

/** The nearest folder at or above `cwd` that holds a catalog; `cwd` when none does. */
async function findRoot(io: Io, cwd: string): Promise<string> {
  for (let dir = cwd; dir !== ''; dir = dir.slice(0, dir.lastIndexOf('/'))) if (await io.exists(`${dir}/${RULES_DIR}`)) return dir
  return cwd
}

async function git(env: Env, root: string, ...args: string[]): Promise<string[] | undefined> {
  const done = await env.io.run(['git', ...args], root)
  return done.exitCode === 0 ? done.stdout.split('\n').filter(line => line !== '') : undefined
}

/** The branch the work started from: the remote's default, else `main` or `master`. */
async function baseOf(env: Env, root: string): Promise<string | undefined> {
  const remote = await git(env, root, 'symbolic-ref', '--quiet', '--short', 'refs/remotes/origin/HEAD')
  if (remote?.[0] !== undefined) return remote[0]
  for (const branch of ['main', 'master']) if ((await git(env, root, 'rev-parse', '--verify', '--quiet', branch)) !== undefined) return branch
  return undefined
}

export async function changedFiles(env: Env, root: string, base?: string): Promise<string[] | undefined> {
  const tree = await git(env, root, 'diff', '--name-only', '--relative', 'HEAD')
  if (tree === undefined) return undefined
  const from = base ?? (await baseOf(env, root))
  const branch = from === undefined ? [] : ((await git(env, root, 'diff', '--name-only', '--relative', `${from}...HEAD`)) ?? [])
  const untracked = (await git(env, root, 'ls-files', '--others', '--exclude-standard')) ?? []
  return [...new Set([...branch, ...tree, ...untracked])].sort()
}

function flag(args: string[], name: string): string | undefined {
  const at = args.indexOf(name)
  return at === -1 ? undefined : args.splice(at, 2)[1]
}

function toggle(args: string[], name: string): boolean {
  const at = args.indexOf(name)
  if (at !== -1) args.splice(at, 1)
  return at !== -1
}

export async function main(argv: readonly string[], env: Env): Promise<Result> {
  const [command, ...args] = argv
  if (command === undefined || command === 'help' || command === '--help') return { code: 0, output: USAGE }
  const root = await findRoot(env.io, env.cwd)

  if (command === 'changed') {
    const files = await changedFiles(env, root, flag(args, '--base'))
    return files === undefined ? fail('rulebook: not a git repository; name the files') : { code: 0, output: files.join('\n') }
  }

  const workspace = await openWorkspace(env.io, root)
  const { catalog } = workspace
  if (catalog.entries.length === 0) return fail(`rulebook: no catalog; ${RULES_DIR} at ${root} holds no entries`)

  if (command === 'check') {
    const issues = await workspace.issues()
    if (issues.length > 0) return { code: 1, output: `${renderIssues(issues)}\n\nrulebook check: ${issues.length} to fix` }
    return { code: 0, output: `rulebook check: ${catalog.entries.length} entries in ${catalog.files.length} files, no issues` }
  }

  if (command === 'for') {
    const isIdsOnly = toggle(args, '--ids')
    const base = flag(args, '--base')
    const below = root === env.cwd ? '' : `${env.cwd.slice(root.length + 1)}/`
    const named = args.map(path => (path.startsWith(`${root}/`) ? path.slice(root.length + 1) : `${below}${path.replace(/^\.\//, '')}`))
    const files = named.length > 0 ? named : await changedFiles(env, root, base)
    if (files === undefined) return fail('rulebook: not a git repository; name the files')
    if (files.length === 0) return { code: 0, output: 'rulebook: no changed files' }
    return { code: 0, output: `Files (${files.length}):\n${files.map(path => `- ${path}`).join('\n')}\n\n${renderSelection(rulesFor(catalog, files), isIdsOnly)}` }
  }

  if (command === 'next') {
    const prefix = args[0]
    if (prefix === undefined || !/^[A-Z][A-Z0-9]*$/.test(prefix)) return fail('usage: rulebook next <PREFIX>, the prefix in capitals (HTTP)')
    return { code: 0, output: nextId(catalog, prefix) }
  }

  if (command === 'show') {
    if (args.length === 0) return fail('usage: rulebook show <ID>...')
    const unknown = args.filter(id => !catalog.entries.some(entry => entry.id === id))
    if (unknown.length > 0) return fail(`rulebook: no entry ${unknown.join(', ')}`)
    const shown = catalog.entries.filter(entry => args.includes(entry.id))
    return { code: 0, output: shown.map(entry => `<!-- ${entry.file}:${entry.line} -->\n${entryText(entry)}`).join('\n\n') }
  }

  return fail(`rulebook: unknown command ${command}\n\n${USAGE}`)
}
