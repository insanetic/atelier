import { test } from 'node:test'
import assert from 'node:assert/strict'
import { drop } from '../../core/drop.ts'
import { renderIssues, runCheck } from '../../core/check.ts'
import { files } from '../../core/paths.ts'
import { loadAssessment, loadFindings, loadStudy } from '../../core/store.ts'
import { fakeIo } from './fake-io.ts'
import { CFG, TODAY, codeFinding, docsFinding, seedStudy } from './fixtures.ts'

test('drop removes a reference with its findings and scores and keeps comments', async () => {
  const io = fakeIo()
  const score = { ref: 'stripe', criterion: 'edge_cases', level: 3, because: ['stripe.rounding'], by: { agent: 'analyst', at: TODAY } }
  seedStudy(io, { findings: [docsFinding(), codeFinding()], scores: [score], notes: '# tax\nSee [f:stripe.rounding].\n' })
  io.files.set(files.study(CFG, 'tax'), `# kept\n${io.files.get(files.study(CFG, 'tax'))}`)
  const ctx = { io, cfg: CFG, today: TODAY }
  const out = await drop(ctx, 'tax', 'stripe')
  assert.deepEqual(out.ok ? out.value : out.errors, { findings: ['stripe.rounding'], scores: 1 })
  assert.match(io.files.get(files.study(CFG, 'tax')) ?? '', /^# kept\n/)
  assert.deepEqual(Object.keys((await loadStudy(io, CFG, 'tax'))?.references ?? {}), ['lago', 'subneo'])
  assert.deepEqual((await loadFindings(io, CFG, 'tax')).map(finding => finding.id), ['lago.rounding'])
  assert.deepEqual(await loadAssessment(io, CFG, 'tax'), [])
  assert.match(renderIssues(await runCheck(ctx)), /citation \[f:stripe\.rounding\] does not resolve/)
})

test('drop refuses a reference the study does not have', async () => {
  const io = fakeIo()
  seedStudy(io)
  const out = await drop({ io, cfg: CFG, today: TODAY }, 'tax', 'avalara')
  assert.match(out.ok ? '' : out.errors.join('\n'), /avalara is not a reference of study tax/)
})
