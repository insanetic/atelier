import type { Config } from './types.ts'

export function join(...parts: string[]): string {
  const raw = parts.filter(part => part !== '').join('/')
  const isAbsolute = raw.startsWith('/')
  const out: string[] = []
  for (const segment of raw.split('/')) {
    if (segment === '' || segment === '.') continue
    if (segment === '..' && out.length > 0 && out[out.length - 1] !== '..') {
      out.pop()
      continue
    }
    out.push(segment)
  }
  const body = out.join('/')
  if (isAbsolute) return `/${body}`
  return body === '' ? '.' : body
}

export function resolvePath(base: string, path: string, home: string): string {
  if (path === '~') return join(home)
  if (path.startsWith('~/')) return join(home, path.slice(2))
  if (path.startsWith('/')) return join(path)
  return join(base, path)
}

export function parseRepoUrl(url: string): { host: string; owner: string; name: string } {
  const match = /^https?:\/\/([^/]+)\/([^/]+)\/([^/#?]+?)(?:\.git)?\/?$/.exec(url)
  if (!match) throw new Error(`unsupported repository url ${url}; expected https://<host>/<owner>/<repo>`)
  const [, host = '', owner = '', name = ''] = match
  return { host, owner, name }
}

export function treeDir(cfg: Config, repoUrl: string, sha: string): string {
  const { host, owner, name } = parseRepoUrl(repoUrl)
  return join(cfg.cache, 'repos', host, owner, name, sha)
}

export const files = {
  references: (cfg: Config) => join(cfg.dir, 'references.yaml'),
  studies: (cfg: Config) => join(cfg.dir, 'studies'),
  studyDir: (cfg: Config, topic: string) => join(cfg.dir, 'studies', topic),
  study: (cfg: Config, topic: string) => join(cfg.dir, 'studies', topic, 'study.yaml'),
  findings: (cfg: Config, topic: string) => join(cfg.dir, 'studies', topic, 'findings.yaml'),
  assessment: (cfg: Config, topic: string) => join(cfg.dir, 'studies', topic, 'assessment.yaml'),
  notes: (cfg: Config, topic: string) => join(cfg.dir, 'studies', topic, 'study.md'),
}
