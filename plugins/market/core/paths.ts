import { join } from '../../research/core/index.ts'
import type { Config } from '../../research/core/index.ts'

/** market's files live inside the research dir it tracks, under market/. */
export const marketFiles = {
  dir: (cfg: Config) => join(cfg.dir, 'market'),
  taxonomy: (cfg: Config) => join(cfg.dir, 'market', 'taxonomy.yaml'),
  registry: (cfg: Config) => join(cfg.dir, 'market', 'registry.yaml'),
  candidates: (cfg: Config) => join(cfg.dir, 'market', 'candidates.yaml'),
  rejected: (cfg: Config) => join(cfg.dir, 'market', 'rejected.yaml'),
}
