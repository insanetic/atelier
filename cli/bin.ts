import { homedir } from 'node:os'
import { main } from './research.ts'
import { nodeIo } from './node-io.ts'

try {
  const today = new Date().toISOString().slice(0, 10)
  const result = await main(process.argv.slice(2), { cwd: process.cwd(), home: homedir(), today, io: nodeIo() })
  if (result.output !== '') console.log(result.output)
  process.exitCode = result.code
} catch (problem) {
  console.error(`research: ${(problem as Error).message}`)
  process.exitCode = 1
}
