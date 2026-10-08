import type { Config } from './types.ts'

export type FetchResult = { status: number; text: string }
export type RunResult = { exitCode: number; stdout: string; stderr: string }

/**
 * Everything core needs from the outside world. Implementations never throw for
 * expected failures: a missing file reads as undefined, a failed fetch answers
 * status 0.
 */
export interface Io {
  readText(path: string): Promise<string | undefined>
  writeText(path: string, text: string): Promise<void>
  exists(path: string): Promise<boolean>
  listDirs(path: string): Promise<string[]>
  size(path: string): Promise<number | undefined>
  fetchText(url: string): Promise<FetchResult>
  run(argv: readonly string[], cwd?: string): Promise<RunResult>
}

export type Ctx = { io: Io; cfg: Config; today: string }
