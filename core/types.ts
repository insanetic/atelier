export const ROLES = ['competitor', 'specialist', 'oss', 'standard', 'alternative', 'anti', 'ours'] as const
export type Role = (typeof ROLES)[number]
export const VOLATILITIES = ['fast', 'medium', 'slow'] as const
export type Volatility = (typeof VOLATILITIES)[number]
export const DIMENSION_TYPES = ['enum', 'number', 'duration', 'bool', 'text'] as const
export type DimensionType = (typeof DIMENSION_TYPES)[number]
export const STUDY_STATUSES = ['quick', 'draft', 'decided', 'superseded'] as const
export type StudyStatus = (typeof STUDY_STATUSES)[number]
export const STUDY_MODES = ['quick', 'full'] as const
export type StudyMode = (typeof STUDY_MODES)[number]
export const EVIDENCE_KINDS = ['code', 'api_spec', 'spec', 'docs', 'tested', 'blog', 'issue', 'marketing'] as const
export type EvidenceKind = (typeof EVIDENCE_KINDS)[number]
/** Strongest first. */
export const METHODS = ['tested', 'source', 'docs', 'third_party', 'claimed'] as const
export type Method = (typeof METHODS)[number]
export const CONFIDENCES = ['confirmed', 'likely', 'unverified'] as const
export type Confidence = (typeof CONFIDENCES)[number]
export const FINDING_STATUSES = ['current', 'superseded', 'disputed', 'drifted'] as const
export type FindingStatus = (typeof FINDING_STATUSES)[number]
export const FINDING_KINDS = ['answer', 'pain'] as const
export type FindingKind = (typeof FINDING_KINDS)[number]
export const VIAS = ['fetch', 'git', 'archive', 'browser', 'file'] as const
export type Via = (typeof VIAS)[number]
export const KANO = ['must', 'performance', 'attractive'] as const
export type Kano = (typeof KANO)[number]
export const WARDLEY = ['genesis', 'custom', 'product', 'commodity'] as const
export type Wardley = (typeof WARDLEY)[number]

export type RepoRef = { url: string; pin?: string; pinned_at?: string }

export type Reference = {
  id: string
  name: string
  docs?: string
  api_spec?: string
  repos?: RepoRef[]
  license?: string
}

export type Dimension = {
  id: string
  ask: string
  type: DimensionType
  options?: string[]
  volatility: Volatility
  kano?: Kano
  wardley?: Wardley
}

export type Criterion = { id: string; ask: string; levels: Record<string, string> }

export type Decision = { chosen: string; decided_at: string; cites: string[]; revisit_when: string }

export type Study = {
  topic: string
  question: string
  decision_needed: string
  status: StudyStatus
  mode: StudyMode
  references: Record<string, Role | Role[]>
  dimensions: Dimension[]
  criteria: Criterion[]
  decision?: Decision
}

export type Evidence = {
  kind: EvidenceKind
  quote: string
  repo?: string
  sha?: string
  path?: string
  lines?: string
  url?: string
  retrieved?: string
  archive?: string
  artifact?: string
}

export type Answer = string | number | boolean

export type Verified = { by: string; at: string; via: Via }

export type Finding = {
  id: string
  ref: string
  dimension: string
  kind: FindingKind
  answer: Answer
  detail?: string
  searched?: string[]
  evidence: Evidence[]
  method: Method
  confidence: Confidence
  verified?: Verified
  status: FindingStatus
  note?: string
}

export type Score = {
  ref: string
  criterion: string
  level: number | 'unknown'
  because: string[]
  by: { agent: string; confirmed_by?: string; at: string }
}

/** Absolute paths: the repo root, the product research dir, the clone cache. */
export type Config = { root: string; dir: string; cache: string }

export type Issue = { level: 'error' | 'warn'; kind: 'schema' | 'freshness'; file: string; message: string }
