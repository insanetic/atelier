import type { Dimension, Finding, Reference, Volatility } from './types.ts'

export const TTL_DAYS: Record<Volatility, number> = { fast: 90, medium: 180, slow: 365 }
export const PIN_MAX_DAYS = 180
const DAY_MS = 86_400_000

export function addDays(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10)
}

export function todayFromMs(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

export const CELL_STATES = ['verified', 'unverified', 'stale', 'drifted', 'disputed', 'unknown'] as const
export type CellState = (typeof CELL_STATES)[number]

export function isStale(finding: Finding, dimension: Dimension | undefined, asOf: string): boolean {
  if (finding.verified === undefined) return false
  return addDays(finding.verified.at, TTL_DAYS[dimension?.volatility ?? 'fast']) < asOf
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
    (ref.repos ?? []).flatMap(repo =>
      repo.pin !== undefined && repo.pinned_at !== undefined && addDays(repo.pinned_at, PIN_MAX_DAYS) < today
        ? [{ ref: ref.id, url: repo.url, pinned_at: repo.pinned_at }]
        : [],
    ),
  )
}
