import type { Io } from './io.ts'
import type { Config } from './types.ts'
import { join, resolvePath } from './paths.ts'
import { parseYaml } from './yaml.ts'

export const CONFIG_FILE = '.research.yaml'

export async function loadConfig(io: Io, root: string, home: string): Promise<Config> {
  const text = await io.readText(join(root, CONFIG_FILE))
  const raw = text === undefined ? null : parseYaml(text)
  const data = raw !== null && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
  const dir = typeof data.dir === 'string' ? data.dir : 'research'
  const cache = typeof data.cache === 'string' ? data.cache : '~/.cache/research'
  return { root: join(root), dir: resolvePath(root, dir, home), cache: resolvePath(root, cache, home) }
}

/**
 * Where a command run from cwd finds research/: the nearest folder up to the
 * repository root that holds a .research.yaml, else the repository root, else
 * cwd itself outside a repository. The mod uses the session root, so a command
 * from a subfolder lands on the same directory.
 */
export async function findRoot(io: Io, cwd: string): Promise<string> {
  for (let dir = join(cwd); ; dir = join(dir, '..')) {
    if ((await io.exists(join(dir, CONFIG_FILE))) || (await io.exists(join(dir, '.git')))) return dir
    if (dir === '/' || !dir.startsWith('/')) return join(cwd)
  }
}
