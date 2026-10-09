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

export type Citation = { topic: string; id: string; raw: string }

/** Every [f:<id>] and [f:<topic>/<id>] in a text; a bare id belongs to `topic`. */
export function citationsOf(text: string, topic: string): Citation[] {
  return [...text.matchAll(/\[f:(?:([a-z0-9-]+)\/)?([^\]\s]+)\]/g)].map(match => ({ topic: match[1] ?? topic, id: match[2] ?? '', raw: match[0] }))
}

export type Section = { title: string; body: string }

/** The level-two sections of a study.md, in order. Text above the first one is not a section; headings inside code fences do not count. */
export function sectionsOf(notes: string): Section[] {
  const sections: Section[] = []
  let isFenced = false
  for (const line of notes.split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) isFenced = !isFenced
    const heading = isFenced ? null : /^## (.*\S)\s*$/.exec(line)
    const last = sections.at(-1)
    if (heading !== null) sections.push({ title: heading[1] ?? '', body: '' })
    else if (last !== undefined) last.body += `${line}\n`
  }
  return sections
}
