import { check, checkFiles, loadCatalog } from './check.ts'
import type { Catalog } from './check.ts'
import type { Issue, SourceFile } from './types.ts'

export const RULES_DIR = '.claude/rules'
const SKILLS_DIR = '.claude/skills'
/** The instruction files that cite entries beside the catalog and the skills. */
const CITING_FILES = ['CLAUDE.md', 'AGENTS.md', '.claude/CLAUDE.md']

/** What the catalog code needs from its host: the CLI gives Node's, the mod the engine's. Paths are absolute. */
export interface Io {
  readText(path: string): Promise<string | undefined>
  list(path: string): Promise<readonly { readonly name: string; readonly isDir: boolean }[]>
  exists(path: string): Promise<boolean>
}

async function markdownUnder(io: Io, root: string, dir: string): Promise<SourceFile[]> {
  const found: SourceFile[] = []
  for (const item of await io.list(`${root}/${dir}`)) {
    const path = `${dir}/${item.name}`
    if (item.isDir) found.push(...(await markdownUnder(io, root, path)))
    else if (item.name.endsWith('.md')) found.push({ path, text: (await io.readText(`${root}/${path}`)) ?? '' })
  }
  return found.sort((a, b) => a.path.localeCompare(b.path))
}

export interface Workspace {
  readonly rules: readonly SourceFile[]
  readonly catalog: Catalog
  issues(): Promise<Issue[]>
}

/** The catalog of the repository at `root`, read once. */
export async function openWorkspace(io: Io, root: string): Promise<Workspace> {
  const rules = await markdownUnder(io, root, RULES_DIR)
  const catalog = loadCatalog(rules)
  return {
    rules,
    catalog,
    async issues() {
      const citing = await markdownUnder(io, root, SKILLS_DIR)
      for (const path of CITING_FILES) {
        const text = await io.readText(`${root}/${path}`)
        if (text !== undefined) citing.push({ path, text })
      }
      const missing = new Set<string>()
      for (const path of checkFiles(catalog)) if (!(await io.exists(`${root}/${path}`))) missing.add(path)
      return check(rules, citing, missing)
    },
  }
}
