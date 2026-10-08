import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, ToolSpec } from 'claude-code'
import * as core from '../dist/core.js'

const USER_AGENT = 'research-kit/0.1 (+https://github.com/insanetic/research-kit)'
// $.http.fetch takes no timeout and the hook budget stands still while it waits:
// a source that never answers would hold the tool, so the clock bounds it.
const FETCH_TIMEOUT_MS = 15_000

/** core's Io over the engine: every byte goes through $, the mod has no Node. */
function modIo($: EngineInterface): core.Io {
  return {
    async readText(path) {
      return (await $.fs.exists(path)) ? String(await $.fs.read(path)) : undefined
    },
    writeText: (path, text) => $.fs.write(path, text),
    exists: path => $.fs.exists(path),
    async listDirs(path) {
      if (!(await $.fs.exists(path))) return []
      return (await $.fs.list(path)).filter(entry => entry.kind === 'dir').map(entry => entry.name)
    },
    async size(path) {
      return (await $.fs.exists(path)) ? (await $.fs.stat(path)).size : undefined
    },
    async fetchText(url) {
      const page = $.http.fetch(url, { headers: { 'user-agent': USER_AGENT } }).then(
        answer => ({ status: answer.status, text: answer.text }),
        () => ({ status: 0, text: '' }),
      )
      const timeout = $.clock.sleep(FETCH_TIMEOUT_MS).then(() => ({ status: 0, text: '' }))
      return Promise.race([page, timeout])
    },
    async run(argv, cwd) {
      const init = cwd === undefined ? { timeoutMs: 120_000 } : { cwd, timeoutMs: 120_000 }
      const done = await $.process.run(argv, init)
      return { exitCode: done.exitCode, stdout: done.stdout, stderr: done.stderr }
    },
  }
}

type ActiveStudy = { topic: string; matrix: core.Matrix; findings: core.Finding[] }

const PLUGIN = 'research-kit'
const PANE = 'research-study'
const DENY = `${PLUGIN}: findings.yaml and assessment.yaml are written only through the add_finding, verify_finding and set_score tools`
const GUARDED_FILE = /(^|\/)studies\/[^/]+\/(findings|assessment)\.yaml$/
const GUARDED_BASH =
  /(?:>>?|\btee\b(?:\s+-a)?)\s*\S*(?:findings|assessment)\.yaml|\b(?:sed\s+-i|perl\s+-p?i|mv|cp|rm)\b[^|;&]*(?:findings|assessment)\.yaml/

const active = atom({ plugin: 'research-kit', key: 'active' } as const, null)
const selected = atom({ plugin: 'research-kit', key: 'selected' } as const, null)
const studyLock = new core.KeyedLock()

const EVIDENCE = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: [...core.EVIDENCE_KINDS] },
    quote: { type: 'string', description: 'Verbatim excerpt: at most 300 characters for web sources, at most 15 lines for code.' },
    repo: { type: 'string', description: 'code, api_spec, spec: the repository URL as in references.yaml, or "self" for our own repo.' },
    sha: { type: 'string', description: 'code, api_spec, spec: the full 40-character commit sha (the pinned one).' },
    path: { type: 'string' },
    lines: { type: 'string', description: 'code, api_spec, spec: "40-58" or "40", 1-based.' },
    url: { type: 'string', description: 'docs, blog, issue, marketing: the page URL.' },
    archive: { type: 'string' },
    artifact: { type: 'string', description: 'tested: a path under the study directory starting with artifacts/.' },
  },
  required: ['kind', 'quote'],
}

const TOOLS: ToolSpec[] = [
  {
    name: 'add_finding',
    isDeferred: false,
    description:
      "Record one finding of a research study: a reference's answer to one dimension (kind answer) or a documented pain with an approach (kind pain), with verbatim evidence. Validates the record, checks every quote against its source (code at the pinned sha, or the fetched page) and writes findings.yaml. The answer must be one of the dimension's options, or \"unknown\" together with searched. Recording the same ref and dimension again replaces the earlier answer.",
    inputSchema: {
      type: 'object',
      properties: {
        study: { type: 'string' },
        ref: { type: 'string' },
        dimension: { type: 'string' },
        kind: { type: 'string', enum: ['answer', 'pain'] },
        answer: { type: ['string', 'number', 'boolean'] },
        detail: { type: 'string', description: 'Nuance in one or two sentences. Every number in it must appear in a quote.' },
        searched: { type: 'array', items: { type: 'string' }, description: 'Required when the answer is unknown: what you looked at.' },
        evidence: { type: 'array', items: EVIDENCE },
        id: { type: 'string', description: 'Only to replace one specific finding.' },
      },
      required: ['study', 'ref', 'dimension', 'answer', 'evidence'],
    },
  },
  {
    name: 'verify_finding',
    isDeferred: false,
    description:
      'Verifier only. Re-checks a finding\'s evidence and records whether the quotes support the answer: confirmed (primary evidence that supports it), likely (secondary or partial support), disputed (it does not support it; give a note). When the raw fetch cannot see a quote (a JavaScript-rendered page) and you confirmed it in a browser, pass browser_confirmed.',
    inputSchema: {
      type: 'object',
      properties: {
        study: { type: 'string' },
        id: { type: 'string' },
        outcome: { type: 'string', enum: ['confirmed', 'likely', 'disputed'] },
        browser_confirmed: { type: 'boolean' },
        note: { type: 'string' },
      },
      required: ['study', 'id', 'outcome'],
    },
  },
  {
    name: 'set_score',
    isDeferred: false,
    description:
      'Score one reference on one study criterion: 1-5 against the written levels, or unknown when no finding supports a level. Cite the finding ids that justify it. Pass confirmed_by "human" only after the user confirmed the score.',
    inputSchema: {
      type: 'object',
      properties: {
        study: { type: 'string' },
        ref: { type: 'string' },
        criterion: { type: 'string' },
        level: { type: ['integer', 'string'] },
        because: { type: 'array', items: { type: 'string' } },
        agent: { type: 'string' },
        confirmed_by: { type: 'string' },
      },
      required: ['study', 'ref', 'criterion', 'level', 'because'],
    },
  },
  {
    name: 'clone',
    isDeferred: false,
    description: "Check out a reference's repositories at their pinned sha into the local cache. Returns the directories: read them with Read, Grep and Glob and cite that sha.",
    inputSchema: { type: 'object', properties: { ref: { type: 'string' } }, required: ['ref'] },
  },
  {
    name: 'query',
    isDeferred: false,
    description: 'Search findings across studies by reference, dimension, study, state (verified, unverified, stale, drifted, disputed, unknown) or text.',
    inputSchema: {
      type: 'object',
      properties: {
        ref: { type: 'string' },
        dimension: { type: 'string' },
        study: { type: 'string' },
        state: { type: 'string' },
        text: { type: 'string' },
        id: { type: 'string', description: 'One finding; its evidence (URL or repo@sha:path#lines and quote) is printed.' },
        kind: { type: 'string', enum: ['answer', 'pain'] },
      },
    },
  },
  {
    name: 'matrix',
    isDeferred: false,
    description: "Show a study's comparison matrix (dimensions by references, each cell with its answer and state) and make it the active study in the pane.",
    inputSchema: { type: 'object', properties: { study: { type: 'string' } }, required: ['study'] },
  },
]

function argsOf(e: unknown): Record<string, unknown> {
  const { tool: _tool, tool_use_id: _id, consent: _consent, ...args } = e as Record<string, unknown>
  return args
}

const failure = (problem: unknown) => ({ result: `${PLUGIN}: ${(problem as Error).message}` })

async function contextOf($: EngineInterface): Promise<core.Ctx> {
  const io = modIo($)
  const root = await $.session.root()
  const home = (await $.env.get('HOME')) ?? root
  return { io, cfg: await core.loadConfig(io, root, home), today: core.todayFromMs(await $.clock.now()) }
}

/** Makes a study the active one: its matrix goes to the pane, its counts to the status line. */
async function showStudy($: EngineInterface, ctx: core.Ctx, topic: string): Promise<core.OpResult<core.Matrix>> {
  const loaded = await core.loadValidStudy(ctx, topic)
  if (!loaded.ok) return loaded
  const findings = await core.loadFindings(ctx.io, ctx.cfg, topic)
  const matrix = core.buildMatrix(loaded.value, findings, ctx.today)
  await update($, active, () => ({ topic, matrix, findings }))
  $.ui.status(core.statusLine(matrix))
  return core.ok(matrix)
}

async function activeStudy($: EngineInterface): Promise<ActiveStudy | null> {
  return (await read($, active)) as ActiveStudy | null
}

async function refreshIfActive($: EngineInterface, ctx: core.Ctx, topic: unknown): Promise<void> {
  const current = await activeStudy($)
  if (current !== null && current.topic === topic) await showStudy($, ctx, current.topic)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    for (const tool of TOOLS) await $.tool.register(tool)
    await $.command.register({
      name: 'study',
      description: 'Start or reopen a research study; without a topic, open the matrix pane',
      argumentHint: '<topic> [--quick]',
    })
    return next(e)
  })

  on('tool.call', { tool: 'Edit' }, ($, e, next) => (GUARDED_FILE.test(e.file_path) ? { deny: DENY } : next(e)))
  on('tool.call', { tool: 'Write' }, ($, e, next) => (GUARDED_FILE.test(e.file_path) ? { deny: DENY } : next(e)))
  on('tool.call', { tool: 'Bash' }, ($, e, next) => (GUARDED_BASH.test(e.command) ? { deny: DENY } : next(e)))

  on('tool.call', { tool: 'mcp__research-kit__add_finding' }, async ($, e) => {
    try {
      const input = argsOf(e) as unknown as core.AddFindingInput
      const ctx = await contextOf($)
      const out = await core.addFinding(ctx, input, studyLock)
      await refreshIfActive($, ctx, input.study)
      return { result: core.renderOp(out, out.ok ? `recorded ${out.value.id} (${out.value.method}, unverified)` : '') }
    } catch (problem) {
      return failure(problem)
    }
  })

  on('tool.call', { tool: 'mcp__research-kit__verify_finding' }, async ($, e) => {
    try {
      const input = argsOf(e) as unknown as core.VerifyInput
      const ctx = await contextOf($)
      const out = await core.verifyFinding(ctx, input, studyLock)
      await refreshIfActive($, ctx, input.study)
      const verdict = out.ok ? (out.value.status === 'disputed' ? 'disputed' : `${out.value.confidence} via ${out.value.verified?.via}`) : ''
      return { result: core.renderOp(out, out.ok ? `${out.value.id}: ${verdict}` : '') }
    } catch (problem) {
      return failure(problem)
    }
  })

  on('tool.call', { tool: 'mcp__research-kit__set_score' }, async ($, e) => {
    try {
      const args = argsOf(e)
      const input = { ...args, agent: typeof args.agent === 'string' ? args.agent : 'analyst' } as unknown as core.SetScoreInput
      const ctx = await contextOf($)
      const out = await core.setScore(ctx, input, studyLock)
      return { result: core.renderOp(out, out.ok ? `scored ${out.value.ref}/${out.value.criterion}: ${out.value.level}` : '') }
    } catch (problem) {
      return failure(problem)
    }
  })

  on('tool.call', { tool: 'mcp__research-kit__clone' }, async ($, e) => {
    try {
      const out = await core.cloneRef(await contextOf($), String(argsOf(e).ref))
      return { result: out.ok ? out.value.join('\n') : core.renderOp(out, '') }
    } catch (problem) {
      return failure(problem)
    }
  })

  on('tool.call', { tool: 'mcp__research-kit__query' }, async ($, e) => {
    try {
      const hits = await core.query(await contextOf($), argsOf(e) as core.QueryInput)
      return { result: core.renderHits(hits) }
    } catch (problem) {
      return failure(problem)
    }
  })

  on('tool.call', { tool: 'mcp__research-kit__matrix' }, async ($, e) => {
    try {
      const topic = String(argsOf(e).study)
      const shown = await showStudy($, await contextOf($), topic)
      return { result: shown.ok ? core.renderMatrix(shown.value) : shown.errors.join('\n') }
    } catch (problem) {
      return failure(problem)
    }
  })

  on('command.run', { command: 'study' }, async ($, e) => {
    try {
      const [topic, ...flags] = e.args.trim().split(/\s+/).filter(word => word !== '')
      if (topic === undefined) {
        const current = await activeStudy($)
        if (current === null) return { text: 'No active study. Run /study <topic> to start one.' }
        await $.ui.open({ id: PANE, title: `Study ${current.topic}` })
        return { text: `Matrix of ${current.topic} opened.` }
      }
      const ctx = await contextOf($)
      const made = await core.createStudy(ctx, topic, flags.includes('--quick') ? 'quick' : 'full')
      if (!made.ok) return { text: made.errors.join('\n') }
      await showStudy($, ctx, topic)
      await $.ui.open({ id: PANE, title: `Study ${topic}` })
      const dir = core.files.studyDir(ctx.cfg, topic)
      const { mode } = made.value.study
      return {
        text: `Study ${topic} ${made.value.created ? 'created' : 'reopened'} (${mode} mode) at ${dir}.`,
        context: [`The user ran /study ${e.args.trim()}. Run the research-kit study skill for the study "${topic}" in ${mode} mode; its files are in ${dir}.`],
      }
    } catch (problem) {
      return { text: `${PLUGIN}: ${(problem as Error).message}` }
    }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const current = await activeStudy($)
    if (current === null) return <Text dimColor>{'No active study. Run /study <topic>.'}</Text>
    const chosenId = await read($, selected)
    const chosen = current.findings.find(finding => finding.id === chosenId)
    return (
      <Box flexDirection="column">
        <Text bold>{`Study ${current.topic}`}</Text>
        {current.matrix.rows.map(row => (
          <Box flexDirection="column">
            <Text>{row.dimension.id}</Text>
            {row.cells.map(cell =>
              cell.findings.length === 0 ? (
                <Text dimColor>{`  ${cell.ref}: -`}</Text>
              ) : (
                cell.findings.map(item => (
                  <Button
                    plain
                    key={item.id}
                    dimColor={item.state !== 'verified'}
                    label={`  ${cell.ref}: ${core.cellText({ ref: cell.ref, findings: [item] })}`}
                    onPress={() => update($, selected, () => item.id)}
                  />
                ))
              ),
            )}
          </Box>
        ))}
        <Text dimColor>{core.statusLine(current.matrix)}</Text>
        {chosen !== undefined && (
          <Box flexDirection="column">
            {core.describeFinding(chosen).map(line => (
              <Text>{line}</Text>
            ))}
          </Box>
        )}
      </Box>
    )
  })
}
