import { execFile } from 'node:child_process'
import { access, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import type { Io, RunResult } from '../core/io.ts'

const USER_AGENT = 'research/0.2 (+https://github.com/insanetic/atelier)'
const FETCH_TIMEOUT_MS = 30_000

const isMissing = (problem: unknown) => (problem as NodeJS.ErrnoException).code === 'ENOENT'

export function nodeIo(): Io {
  return {
    async readText(path) {
      try {
        return await readFile(path, 'utf8')
      } catch (problem) {
        if (isMissing(problem)) return undefined
        throw problem
      }
    },
    async writeText(path, text) {
      await mkdir(dirname(path), { recursive: true })
      await writeFile(path, text)
    },
    async exists(path) {
      try {
        await access(path)
        return true
      } catch {
        return false
      }
    },
    async listDirs(path) {
      try {
        return (await readdir(path, { withFileTypes: true })).filter(entry => entry.isDirectory()).map(entry => entry.name)
      } catch (problem) {
        if (isMissing(problem)) return []
        throw problem
      }
    },
    async size(path) {
      try {
        return (await stat(path)).size
      } catch {
        return undefined
      }
    },
    async fetchText(url) {
      try {
        const response = await fetch(url, { redirect: 'follow', headers: { 'user-agent': USER_AGENT }, signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) })
        return { status: response.status, text: await response.text() }
      } catch {
        return { status: 0, text: '' }
      }
    },
    run(argv, cwd) {
      return new Promise<RunResult>(resolve => {
        execFile(argv[0], argv.slice(1), { cwd, maxBuffer: 64 * 1024 * 1024 }, (problem, stdout, stderr) => {
          const exitCode = problem === null ? 0 : typeof problem.code === 'number' ? problem.code : 1
          resolve({ exitCode, stdout: String(stdout), stderr: String(stderr) })
        })
      })
    },
  }
}
