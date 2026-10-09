import type { StudyMode } from './types.ts'

/** The sections of a brief, in order; research finish holds study.md to them. */
export const BRIEF_SECTIONS = ['Answer', 'Who solved it', 'Approaches', 'What to reuse', 'Pitfalls', 'Ours against theirs', 'Recommendation', 'Open questions'] as const
/** Replaces "Ours against theirs" when nothing of ours exists yet. */
export const GREENFIELD_SECTION = 'Greenfield'
export const DEEP_SECTIONS = ['Question and decision', 'Paradigms found', 'Trade-offs', 'Pain', 'Where ours stands', 'Candidates', 'Decision'] as const
/** Brief sections that may stand without a citation: they summarize or ask, they claim nothing new. */
export const UNCITED_SECTIONS: readonly string[] = ['Answer', 'Who solved it', 'Open questions', GREENFIELD_SECTION]

export function notesTemplate(topic: string, mode: StudyMode): string {
  const sections: readonly string[] = mode === 'deep' ? DEEP_SECTIONS : BRIEF_SECTIONS
  return `# ${topic}\n\n${sections.map(section => `## ${section}\n`).join('\n')}`
}
