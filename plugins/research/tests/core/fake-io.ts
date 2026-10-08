import type { FetchResult, Io, RunResult } from '../../core/io.ts'

export type FakeIo = Io & {
  files: Map<string, string>
  pages: Map<string, FetchResult>
  fetched: string[]
  runs: string[][]
  onRun: (argv: readonly string[], cwd?: string) => RunResult
}

export function fakeIo(seed: Record<string, string> = {}): FakeIo {
  const files = new Map(Object.entries(seed))
  const pages = new Map<string, FetchResult>()
  const fetched: string[] = []
  const runs: string[][] = []
  const io: FakeIo = {
    files,
    pages,
    fetched,
    runs,
    onRun: () => ({ exitCode: 1, stdout: '', stderr: 'no command in this fake' }),
    async readText(path) {
      return files.get(path)
    },
    async writeText(path, text) {
      files.set(path, text)
    },
    async exists(path) {
      return files.has(path) || [...files.keys()].some(key => key.startsWith(`${path}/`))
    },
    async listDirs(path) {
      const names = new Set<string>()
      for (const key of files.keys()) {
        if (!key.startsWith(`${path}/`)) continue
        const rest = key.slice(path.length + 1)
        const cut = rest.indexOf('/')
        if (cut > 0) names.add(rest.slice(0, cut))
      }
      return [...names].sort()
    },
    async size(path) {
      return files.get(path)?.length
    },
    async fetchText(url) {
      fetched.push(url)
      return pages.get(url) ?? { status: 404, text: '' }
    },
    async run(argv, cwd) {
      runs.push([...argv])
      return io.onRun(argv, cwd)
    },
  }
  return io
}
