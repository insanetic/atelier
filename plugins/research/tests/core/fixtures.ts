import type { Config, Finding, Reference, Score, Study } from '../../core/types.ts'
import { files, treeDir } from '../../core/paths.ts'
import { toYaml } from '../../core/yaml.ts'
import type { FakeIo } from './fake-io.ts'

export const CFG: Config = { root: '/repo', dir: '/repo/research', cache: '/home/u/.cache/research' }
export const TODAY = '2026-10-08'
export const SHA = 'a'.repeat(40)
export const NEW_SHA = 'b'.repeat(40)
export const LAGO_URL = 'https://github.com/getlago/lago-api'
export const STRIPE_TAX_URL = 'https://docs.stripe.com/tax'

export const REFERENCES: Reference[] = [
  { id: 'lago', name: 'Lago', kind: 'product', repos: [{ url: LAGO_URL, pin: SHA, pinned_at: '2026-10-01' }], license: 'AGPL-3.0' },
  { id: 'stripe', name: 'Stripe', kind: 'product', docs: 'https://docs.stripe.com' },
  { id: 'subneo', name: 'Subneo', kind: 'ours', repos: [{ url: 'self' }] },
]

export function study(over: Partial<Study> = {}): Study {
  return {
    topic: 'tax',
    question: 'How should Subneo compute tax?',
    decision_needed: 'in-house vs engine',
    status: 'draft',
    mode: 'full',
    references: { lago: ['competitor', 'code-read'], stripe: 'competitor', subneo: 'ours' },
    dimensions: [
      { id: 'rounding', ask: 'Where is tax rounded?', type: 'enum', options: ['per_line', 'per_invoice'], volatility: 'slow' },
      { id: 'max_rates', ask: 'How many tax rates per line?', type: 'number', volatility: 'medium' },
    ],
    criteria: [{ id: 'edge_cases', ask: 'How complete is edge-case handling?', levels: { '1': 'single rate', '3': 'exemptions', '5': 'everything' } }],
    ...over,
  }
}

export function docsFinding(over: Partial<Finding> = {}): Finding {
  return {
    id: 'stripe.rounding',
    ref: 'stripe',
    dimension: 'rounding',
    kind: 'answer',
    answer: 'per_line',
    evidence: [{ kind: 'docs', url: STRIPE_TAX_URL, quote: 'Tax is rounded per line item.', retrieved: TODAY }],
    method: 'docs',
    confidence: 'unverified',
    status: 'current',
    ...over,
  }
}

export function codeFinding(over: Partial<Finding> = {}): Finding {
  return {
    id: 'lago.rounding',
    ref: 'lago',
    dimension: 'rounding',
    kind: 'answer',
    answer: 'per_invoice',
    evidence: [{ kind: 'code', repo: LAGO_URL, sha: SHA, path: 'app/services/taxes.rb', lines: '2-3', quote: 'round(total_tax)' }],
    method: 'source',
    confidence: 'unverified',
    status: 'current',
    ...over,
  }
}

export const LAGO_FILE = 'class Taxes\n  def total\n    round(total_tax)\n  end\nend\n'

export function lagoFilePath(sha = SHA): string {
  return `${treeDir(CFG, LAGO_URL, sha)}/app/services/taxes.rb`
}

export function seedStudy(io: FakeIo, options: { study?: Study; findings?: Finding[]; scores?: Score[]; notes?: string; references?: Reference[] } = {}): void {
  const s = options.study ?? study()
  io.files.set(files.references(CFG), toYaml(options.references ?? REFERENCES))
  io.files.set(files.study(CFG, s.topic), toYaml(s))
  io.files.set(files.findings(CFG, s.topic), toYaml(options.findings ?? []))
  io.files.set(files.assessment(CFG, s.topic), toYaml(options.scores ?? []))
  if (options.notes !== undefined) io.files.set(files.notes(CFG, s.topic), options.notes)
}
