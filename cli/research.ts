import type { Io } from '../core/io.ts'
import { CELL_STATES } from '../core/fresh.ts'
import type { CellState } from '../core/fresh.ts'
import {
  buildMatrix,
  cloneRef,
  createStudy,
  files,
  loadConfig,
  loadFindings,
  loadStudy,
  query,
  renderHits,
  renderIssues,
  renderMatrix,
  renderReport,
  repin,
  resolvePath,
  reverify,
  runCheck,
} from '../core/index.ts'

export type CliEnv = { cwd: string; home: string; today: string; io: Io }
export type CliResult = { code: number; output: string }

export const USAGE = `usage: research <command>

  init <topic> [--quick]     create a study skeleton
  check                      validate every record; exit 1 on errors
  stale                      list stale, drifted and pin-stale findings
  query [--ref R] [--dimension D] [--study S] [--state X] [--text T]
                             search findings across studies
  matrix <topic>             print a study's comparison matrix
  reverify [--due] [--report FILE]
                             re-check evidence (--due: only findings past their TTL)
  clone <ref>                check out a reference's pinned repositories
  repin <ref> [--to SHA]     move a reference to a new commit and re-anchor its code findings`

const VALUED = new Set(['ref', 'dimension', 'study', 'state', 'text', 'report', 'to'])

export function parseArgs(args: readonly string[]): { positional: string[]; flags: Map<string, string | true> } {
  const positional: string[] = []
  const flags = new Map<string, string | true>()
  for (let i = 0; i < args.length; i++) {
    const arg = args[i]
    if (!arg.startsWith('--')) {
      positional.push(arg)
      continue
    }
    const name = arg.slice(2)
    const value = args[i + 1]
    if (VALUED.has(name) && value !== undefined && !value.startsWith('--')) {
      flags.set(name, value)
      i++
    } else flags.set(name, true)
  }
  return { positional, flags }
}

const usageError = (message: string): CliResult => ({ code: 2, output: `${message}\n\n${USAGE}` })

export async function main(argv: readonly string[], env: CliEnv): Promise<CliResult> {
  const [command, ...rest] = argv
  if (command === undefined || command === 'help' || command === '--help' || command === '-h') return { code: 0, output: USAGE }
  const { positional, flags } = parseArgs(rest)
  const valueOf = (name: string) => {
    const value = flags.get(name)
    return typeof value === 'string' ? value : undefined
  }
  const cfg = await loadConfig(env.io, env.cwd, env.home)
  const ctx = { io: env.io, cfg, today: env.today }
  switch (command) {
    case 'init': {
      const topic = positional[0]
      if (topic === undefined) return usageError('init needs a topic')
      const made = await createStudy(ctx, topic, flags.has('quick') ? 'quick' : 'full')
      if (!made.ok) return { code: 1, output: made.errors.join('\n') }
      return { code: 0, output: `${made.value.created ? 'created' : 'exists'} ${files.studyDir(cfg, topic)}` }
    }
    case 'check': {
      const issues = await runCheck(ctx)
      return { code: issues.some(issue => issue.level === 'error') ? 1 : 0, output: renderIssues(issues) }
    }
    case 'stale': {
      const issues = (await runCheck(ctx)).filter(issue => issue.kind === 'freshness')
      return { code: 0, output: issues.length === 0 ? 'nothing is stale' : renderIssues(issues) }
    }
    case 'query': {
      const state = valueOf('state')
      if (state !== undefined && !(CELL_STATES as readonly string[]).includes(state)) return usageError(`--state must be one of ${CELL_STATES.join(', ')}`)
      const hits = await query(ctx, {
        ref: valueOf('ref'),
        dimension: valueOf('dimension'),
        study: valueOf('study'),
        state: state as CellState | undefined,
        text: valueOf('text'),
      })
      return { code: 0, output: renderHits(hits) }
    }
    case 'matrix': {
      const topic = positional[0]
      if (topic === undefined) return usageError('matrix needs a topic')
      const study = await loadStudy(env.io, cfg, topic)
      if (study === undefined) return { code: 1, output: `study ${topic} does not exist` }
      return { code: 0, output: renderMatrix(buildMatrix(study, await loadFindings(env.io, cfg, topic), env.today)) }
    }
    case 'reverify': {
      const output = renderReport(await reverify(ctx, { dueOnly: flags.has('due') }))
      const report = valueOf('report')
      if (report !== undefined) await env.io.writeText(resolvePath(env.cwd, report, env.home), `${output}\n`)
      return { code: 0, output }
    }
    case 'clone': {
      const ref = positional[0]
      if (ref === undefined) return usageError('clone needs a reference id')
      const out = await cloneRef(ctx, ref)
      return out.ok ? { code: 0, output: out.value.join('\n') } : { code: 1, output: out.errors.join('\n') }
    }
    case 'repin': {
      const ref = positional[0]
      if (ref === undefined) return usageError('repin needs a reference id')
      const out = await repin(ctx, ref, valueOf('to'))
      if (!out.ok) return { code: 1, output: out.errors.join('\n') }
      const { pins, moved, drifted } = out.value
      const lines = [...pins.map(pin => `pinned ${pin.url} at ${pin.sha}`), `moved: ${moved.join(', ') || 'none'}`, `drifted: ${drifted.join(', ') || 'none'}`]
      return { code: 0, output: lines.join('\n') }
    }
    default:
      return usageError(`unknown command ${command}`)
  }
}
