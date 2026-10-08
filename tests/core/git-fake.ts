import type { RunResult } from '../../core/io.ts'
import type { FakeIo } from './fake-io.ts'
import { NEW_SHA } from './fixtures.ts'

const done = (stdout = ''): RunResult => ({ exitCode: 0, stdout, stderr: '' })

/** git as the cache uses it; a checkout dir ends in its sha, so rev-parse answers that. */
export function gitFake(io: FakeIo, remoteHead = NEW_SHA): void {
  const checkedOut = new Set<string>()
  io.onRun = argv => {
    if (argv[1] === 'ls-remote') return done(`${remoteHead}\tHEAD\n`)
    if (argv[1] === 'init') {
      io.files.set(`${argv[3]}/.git/HEAD`, 'ref: refs/heads/main\n')
      return done()
    }
    const dir = argv[2]
    if (argv[3] === 'rev-parse') {
      return checkedOut.has(dir) ? done(`${dir.split('/').pop()}\n`) : { exitCode: 128, stdout: '', stderr: 'fatal: not a git repository' }
    }
    if (argv.includes('checkout')) checkedOut.add(dir)
    return done()
  }
}
