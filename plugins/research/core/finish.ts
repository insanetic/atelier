import type { Ctx } from './io.ts'
import type { Finding, Finished, Study } from './types.ts'
import { files } from './paths.ts'
import { citableProblem } from './fresh.ts'
import { listTopics, loadFindings, loadNotes, loadStudy, loadValidStudy } from './store.ts'
import { BRIEF_SECTIONS, GREENFIELD_SECTION, UNCITED_SECTIONS, citationsOf, sectionsOf } from './notes.ts'
import { setInYaml } from './yaml.ts'
import { fail, ok } from './result.ts'
import type { OpResult } from './result.ts'

type Owned = { study: Study | undefined; findings: Map<string, Finding> }

/**
 * The gate of a brief, as research decide is the gate of a decision: study.md
 * has every section in order, each section that makes a claim cites a finding,
 * and every citation is current, verified and within its TTL. Passing records
 * finished and status: brief, keeping study.yaml's comments.
 */
export async function finish(ctx: Ctx, topic: string): Promise<OpResult<Finished>> {
  const loaded = await loadValidStudy(ctx, topic)
  if (!loaded.ok) return loaded
  const study = loaded.value
  if (study.mode !== 'brief') return fail(`study ${topic} is mode ${study.mode}; finish closes a brief`)
  const expected = BRIEF_SECTIONS.map(title => (title === 'Ours against theirs' && study.greenfield === true ? GREENFIELD_SECTION : title))
  const sections = sectionsOf(await loadNotes(ctx.io, ctx.cfg, topic))
  const titles = sections.map(section => section.title)
  const problems: string[] = []
  if (titles.join('\n') !== expected.join('\n')) {
    problems.push(`study.md needs exactly these sections, in order: ${expected.join(', ')}; it has ${titles.join(', ') || 'none'}`)
  }
  const topics = new Set(await listTopics(ctx.io, ctx.cfg))
  const owners = new Map<string, Owned>()
  const ownerOf = async (owner: string): Promise<Owned> => {
    const known = owners.get(owner)
    if (known !== undefined) return known
    const found: Owned = topics.has(owner)
      ? {
          study: owner === topic ? study : await loadStudy(ctx.io, ctx.cfg, owner),
          findings: new Map((await loadFindings(ctx.io, ctx.cfg, owner)).map(finding => [finding.id, finding])),
        }
      : { study: undefined, findings: new Map() }
    owners.set(owner, found)
    return found
  }
  const cited = new Set<string>()
  for (const section of sections) {
    const cites = citationsOf(section.body, topic)
    if (cites.length === 0 && !UNCITED_SECTIONS.includes(section.title)) problems.push(`section ${section.title} cites no finding`)
    for (const cite of cites) {
      const key = cite.topic === topic ? cite.id : `${cite.topic}/${cite.id}`
      if (cited.has(key)) continue
      cited.add(key)
      const owned = await ownerOf(cite.topic)
      const finding = owned.findings.get(cite.id)
      const dimension = owned.study?.dimensions.find(dim => dim.id === finding?.dimension)
      const problem = citableProblem(key, finding, dimension, ctx.today)
      if (problem !== undefined) problems.push(problem)
    }
  }
  if (problems.length > 0) return fail(...problems)
  const finished: Finished = { at: ctx.today, cites: cited.size }
  const path = files.study(ctx.cfg, topic)
  await ctx.io.writeText(path, setInYaml((await ctx.io.readText(path)) ?? '', { status: 'brief', finished }))
  return ok(finished)
}
