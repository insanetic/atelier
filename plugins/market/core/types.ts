import type { Evidence } from '../../research/core/index.ts'

export const SOURCE_MODELS = ['open_source', 'source_available', 'proprietary'] as const
export type SourceModel = (typeof SOURCE_MODELS)[number]
export const DELIVERIES = ['saas', 'self_hosted', 'library'] as const
export type Delivery = (typeof DELIVERIES)[number]
export const STATUSES = ['active', 'acquired', 'sunset', 'dead'] as const
export type Status = (typeof STATUSES)[number]
export const OVERLAPS = ['direct', 'adjacent'] as const
export type Overlap = (typeof OVERLAPS)[number]

/** Our view of a reference, which is opinion: dated, and absent for anything that is not a competitor. */
export type Stance = { tier: 1 | 2 | 'watch'; overlap: Record<string, Overlap>; basis?: string; reviewed: string }

/** Market facts about one reference of research/references.yaml, and our stance on it. */
export type Entry = {
  vendor?: string
  owned_by?: string
  successor?: string
  aliases?: string[]
  domains?: string[]
  categories?: string[]
  source_model?: SourceModel
  delivery?: Delivery[]
  status?: Status
  stance?: Stance
}

/** registry.yaml: reference id -> its market entry. */
export type Registry = Record<string, Entry>

/** The controlled vocabulary: market categories (kebab-case) and capabilities (snake_case), each defined. */
export type Taxonomy = {
  categories: Record<string, string>
  capabilities: Record<string, string>
  /** What belongs in the registry at all: every discovery agent applies these rules before proposing. */
  scope?: { include?: string[]; exclude?: string[] }
}

export type Candidate = {
  id: string
  name: string
  domains: string[]
  categories: string[]
  found_by: string[]
  evidence: Evidence[]
  note?: string
  proposed_at: string
}

export type Rejection = { id: string; name: string; domains?: string[]; reason: string; rejected_at: string }
