import { execFile } from 'node:child_process'
import { access, readFile, readdir } from 'node:fs/promises'
import { main } from './rulebook.ts'
import type { CliIo } from './rulebook.ts'

const isMissing = (problem: unknown) => ['ENOENT', 'ENOTDIR'].includes((problem as NodeJS.ErrnoException).code ?? '')

const io: CliIo = {
  async readText(path) {
    try {
      return await readFile(path, 'utf8')
    } catch (problem) {
      if (isMissing(problem)) return undefined
      throw problem
    }
  },
  async list(path) {
    try {
      return (await readdir(path, { withFileTypes: true })).map(entry => ({ name: entry.name, isDir: entry.isDirectory() }))
    } catch (problem) {
      if (isMissing(problem)) return []
      throw problem
    }
  },
  async exists(path) {
    try {
      await access(path)
      return true
    } catch {
      return false
    }
  },
  run: (argv, cwd) =>
    new Promise(resolve => {
      execFile(argv[0] ?? '', argv.slice(1), { cwd, maxBuffer: 64 * 1024 * 1024 }, (problem, stdout) => {
        resolve({ exitCode: problem === null ? 0 : 1, stdout })
      })
    }),
}

try {
  const result = await main(process.argv.slice(2), { cwd: process.cwd(), io })
  if (result.output !== '') console.log(result.output)
  process.exitCode = result.code
} catch (problem) {
  console.error(`rulebook: ${(problem as Error).message}`)
  process.exitCode = 1
}
