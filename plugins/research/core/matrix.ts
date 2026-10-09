import type { Answer, Dimension, Evidence, Finding, Study } from './types.ts'
import { stateOf } from './fresh.ts'
import type { CellState } from './fresh.ts'

export type MatrixItem = { id: string; answer: Answer; state: CellState; at?: string }
export type MatrixCell = { ref: string; findings: MatrixItem[] }
export type MatrixRow = { dimension: Dimension; cells: MatrixCell[] }
export type Matrix = { topic: string; refs: string[]; rows: MatrixRow[]; counts: Record<CellState | 'missing', number> }

const MARK: Record<CellState, string> = {
  verified: 'ok',
  unverified: '?',
  stale: 'stale',
  drifted: 'drift',
  disputed: 'disputed',
  unknown: 'unknown',
}

export function buildMatrix(study: Study, findings: readonly Finding[], today: string): Matrix {
  const refs = Object.keys(study.references)
  const counts = { missing: 0, verified: 0, unverified: 0, stale: 0, drifted: 0, disputed: 0, unknown: 0 }
  const rows = study.dimensions.map(dimension => ({
    dimension,
    cells: refs.map(ref => {
      const items = findings
        .filter(finding => finding.ref === ref && finding.dimension === dimension.id && finding.kind === 'answer' && finding.status !== 'superseded')
        .map((finding): MatrixItem => {
          const state = stateOf(finding, dimension, today)
          counts[state]++
          const item: MatrixItem = { id: finding.id, answer: finding.answer, state }
          if (finding.verified !== undefined) item.at = finding.verified.at
          return item
        })
      if (items.length === 0) counts.missing++
      return { ref, findings: items }
    }),
  }))
  return { topic: study.topic, refs, rows, counts }
}

export function cellText(cell: MatrixCell): string {
  if (cell.findings.length === 0) return '-'
  return cell.findings
    .map(item => (item.state === 'unknown' ? 'unknown' : `${String(item.answer)} [${MARK[item.state]}${item.at === undefined ? '' : ` ${item.at}`}]`))
    .join(' / ')
}

export function statusLine(matrix: Matrix): string {
  const c = matrix.counts
  return `study ${matrix.topic}: ${c.verified} ok · ${c.unverified} unverified · ${c.stale} stale · ${c.drifted} drifted · ${c.disputed} disputed · ${c.missing} missing`
}

export function renderMatrix(matrix: Matrix): string {
  const header = `| dimension | ${matrix.refs.join(' | ')} |`
  const divider = `|${' --- |'.repeat(matrix.refs.length + 1)}`
  const rows = matrix.rows.map(row => `| ${row.dimension.id} | ${row.cells.map(cell => cellText(cell).replace(/\|/g, '\\|')).join(' | ')} |`)
  return [header, divider, ...rows, '', statusLine(matrix)].join('\n')
}

function sourceOf(item: Evidence): string {
  if (item.url !== undefined) return item.url
  if (item.artifact !== undefined) return item.artifact
  return `${item.repo}@${(item.sha ?? '').slice(0, 12)}:${item.path}#L${item.lines}`
}

export function describeFinding(finding: Finding): string[] {
  const verified = finding.verified === undefined ? '' : `, verified ${finding.verified.at} via ${finding.verified.via}`
  const clip = (quote: string) => (quote.length > 160 ? `${quote.slice(0, 157)}...` : quote)
  return [
    `${finding.id}: ${String(finding.answer)} [${finding.confidence}, ${finding.status}${verified}]`,
    ...(finding.detail === undefined ? [] : [finding.detail]),
    ...(finding.reuse === undefined ? [] : [`reuse: ${finding.reuse.type} ${finding.reuse.url} (${finding.reuse.license})`]),
    ...(finding.note === undefined ? [] : [`note: ${finding.note}`]),
    ...finding.evidence.map(item => `- ${item.kind} ${sourceOf(item)}: "${clip(item.quote)}"`),
  ]
}
