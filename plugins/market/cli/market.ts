import { loadConfig } from '../../research/core/index.ts'
import type { Io } from '../../research/core/index.ts'
import { approveCandidate, listReferences, rejectCandidate, renderReferences, syncLandscape } from '../core/registry.ts'
import { loadCandidates } from '../core/store.ts'
import { renderMarketIssues, runMarketCheck } from '../core/check.ts'

export type CliEnv = { cwd: string; home: string; today: string; io: Io }
export type CliResult = { code: number; output: string }

export const USAGE = `usage: market <command>

  refs [--category C] [--tier 1|2|watch] [--capability X] [--kind K]
                             list tracked references; --capability reads the verified landscape study
  candidates                 list discovered products waiting for approval
  approve <id>               add a candidate to research/references.yaml and research/market/registry.yaml
  reject <id> --reason R     record why a candidate is out, so it is not proposed again
  landscape                  sync the landscape study: one question per capability, every active tracked reference
  check                      validate research/market/; exit 1 on errors`

const VALUED = new Set(['category', 'tier', 'capability', 'kind', 'reason'])

function parseArgs(args: readonly string[]): { positional: string[]; flags: Map<string, string | true> } {
  const positional: string[] = []
  const flags = new Map<string, string | true>()
  for (let i = 0; i < args.length; i++) {
    const arg = args[i] ?? ''
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
    case 'refs': {
      const filter = { category: valueOf('category'), tier: valueOf('tier'), capability: valueOf('capability'), kind: valueOf('kind') }
      return { code: 0, output: renderReferences(await listReferences(ctx, filter)) }
    }
    case 'candidates': {
      const candidates = await loadCandidates(env.io, cfg)
      if (candidates.length === 0) return { code: 0, output: 'no candidates' }
      const lines = candidates.map(item => [item.id, item.name, item.domains.join(','), item.categories.join(',') || '-', `found by ${item.found_by.join(', ')}`].join('  '))
      return { code: 0, output: lines.join('\n') }
    }
    case 'approve': {
      const id = positional[0]
      if (id === undefined) return usageError('approve needs a candidate id')
      const out = await approveCandidate(ctx, id)
      return out.ok ? { code: 0, output: `approved ${id}: added to research/references.yaml and the market registry` } : { code: 1, output: out.errors.join('\n') }
    }
    case 'reject': {
      const id = positional[0]
      const reason = valueOf('reason')
      if (id === undefined || reason === undefined) return usageError('reject needs a candidate id and --reason')
      const out = await rejectCandidate(ctx, id, reason)
      return out.ok ? { code: 0, output: `rejected ${id}: ${reason}` } : { code: 1, output: out.errors.join('\n') }
    }
    case 'landscape': {
      const out = await syncLandscape(ctx)
      if (!out.ok) return { code: 1, output: out.errors.join('\n') }
      return { code: 0, output: `landscape: ${out.value.dimensions} capabilities, ${out.value.references} references` }
    }
    case 'check': {
      const issues = await runMarketCheck(ctx)
      return { code: issues.some(issue => issue.level === 'error') ? 1 : 0, output: renderMarketIssues(issues) }
    }
    default:
      return usageError(`unknown command ${command}`)
  }
}
