import type { Dimension, Finding, Reference, Volatility } from './types.ts'

export const TTL_DAYS: Record<Volatility, number> = { fast: 90, medium: 180, slow: 365 }

/** A finding that belongs to no dimension (a pain or reuse finding) ages like a feature. */
export function volatilityOf(dimension: Dimension | undefined): Volatility {
  return dimension?.volatility ?? 'medium'
}
export const PIN_MAX_DAYS = 180
const DAY_MS = 86_400_000

export const isDate = (value: unknown): value is string =>
  typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`))

export function addDays(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10)
}

export function todayFromMs(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

export const CELL_STATES = ['verified', 'unverified', 'stale', 'drifted', 'disputed', 'unknown'] as const
export type CellState = (typeof CELL_STATES)[number]

export function isStale(finding: Finding, dimension: Dimension | undefined, asOf: string): boolean {
  if (finding.verified === undefined || !isDate(finding.verified.at)) return false
  return addDays(finding.verified.at, TTL_DAYS[volatilityOf(dimension)]) < asOf
}

export function stateOf(finding: Finding, dimension: Dimension | undefined, today: string): CellState {
  if (finding.status === 'disputed') return 'disputed'
  if (finding.status === 'drifted') return 'drifted'
  if (finding.answer === 'unknown') return 'unknown'
  if (finding.verified === undefined) return 'unverified'
  return isStale(finding, dimension, today) ? 'stale' : 'verified'
}

export type StalePin = { ref: string; url: string; pinned_at: string }

export function stalePins(references: readonly Reference[], today: string): StalePin[] {
  return references.flatMap(ref =>
    (Array.isArray(ref.repos) ? ref.repos : []).flatMap(repo =>
      repo.pin !== undefined && isDate(repo.pinned_at) && addDays(repo.pinned_at, PIN_MAX_DAYS) < today
        ? [{ ref: ref.id, url: repo.url, pinned_at: repo.pinned_at }]
        : [],
    ),
  )
}

/** Why a finding cannot carry a claim today, or undefined when it can. */
export function citableProblem(id: string, finding: Finding | undefined, dimension: Dimension | undefined, today: string): string | undefined {
  if (finding === undefined) return `${id} does not exist`
  if (finding.status === 'disputed') return `${id} is disputed`
  if (finding.status === 'drifted') return `${id} has drifted; re-research it first`
  if (finding.status !== 'current') return `${id} is ${finding.status}`
  if (finding.verified === undefined || finding.confidence === 'unverified') return `${id} is not verified`
  if (isStale(finding, dimension, today)) return `${id} is past its ${volatilityOf(dimension)} TTL; re-verify it first`
  return undefined
}
