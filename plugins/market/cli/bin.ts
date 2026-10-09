import { homedir } from 'node:os'
import { main } from './market.ts'
import { nodeIo } from '../../research/cli/node-io.ts'

try {
  const today = new Date().toISOString().slice(0, 10)
  const result = await main(process.argv.slice(2), { cwd: process.cwd(), home: homedir(), today, io: nodeIo() })
  if (result.output !== '') console.log(result.output)
  process.exitCode = result.code
} catch (problem) {
  console.error(`market: ${(problem as Error).message}`)
  process.exitCode = 1
}
