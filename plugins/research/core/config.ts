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
