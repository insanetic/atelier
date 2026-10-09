import type { EngineInterface, Register, ToolSpec } from 'claude-code'
import * as core from '../dist/core.js'

const USER_AGENT = 'market/0.1 (+https://github.com/insanetic/atelier)'
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

const PLUGIN = 'market'
const registryLock = new core.KeyedLock()

const EVIDENCE = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: ['docs', 'blog', 'issue', 'marketing'] },
    quote: { type: 'string', description: 'Verbatim excerpt of at most 300 characters.' },
    url: { type: 'string' },
  },
  required: ['kind', 'quote', 'url'],
}

const TOOLS: ToolSpec[] = [
  {
    name: 'refs',
    isDeferred: false,
    description:
      'List the tracked references (research/market/registry.yaml with the facts of research/references.yaml): every known competitor, benchmark product and standard. Filter by taxonomy category, stance tier (1, 2, watch), kind, or a capability the landscape study verified. Start every discovery from this list.',
    inputSchema: {
      type: 'object',
      properties: { category: { type: 'string' }, tier: { type: 'string' }, capability: { type: 'string' }, kind: { type: 'string' } },
    },
  },
  {
    name: 'propose_candidate',
    isDeferred: false,
    description:
      'Discoverer only. Propose a product the market registry does not know yet, for a human to approve. Give its domains and a verbatim quote from its own site that says what it does; found_by names the discovery channel. Products already tracked or rejected are refused (by id, name, alias or domain); a product another channel already proposed is merged, adding the channel.',
    inputSchema: {
      type: 'object',
      properties: {
        id: { type: 'string', description: 'kebab-case, e.g. flexprice' },
        name: { type: 'string' },
        domains: { type: 'array', items: { type: 'string' } },
        categories: { type: 'array', items: { type: 'string' }, description: 'Taxonomy category ids only.' },
        found_by: { type: 'array', items: { type: 'string' } },
        evidence: { type: 'array', items: EVIDENCE },
        note: { type: 'string' },
      },
      required: ['id', 'name', 'domains', 'categories', 'found_by', 'evidence'],
    },
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

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    for (const tool of TOOLS) await $.tool.register(tool)
    return next(e)
  })

  on('tool.call', { tool: 'mcp__market__refs' }, async ($, e) => {
    try {
      const rows = await core.listReferences(await contextOf($), argsOf(e) as core.ReferenceFilter)
      return { result: core.renderReferences(rows) }
    } catch (problem) {
      return failure(problem)
    }
  })

  on('tool.call', { tool: 'mcp__market__propose_candidate' }, async ($, e) => {
    try {
      const out = await core.proposeCandidate(await contextOf($), argsOf(e) as unknown as core.CandidateInput, registryLock)
      if (!out.ok) return { result: core.renderOp(out, '') }
      const { candidate, merged } = out.value
      const channels = `(found by ${candidate.found_by.join(', ')})`
      return { result: core.renderOp(out, merged ? `merged into candidate ${candidate.id} ${channels}` : `proposed ${candidate.id} ${channels}`) }
    } catch (problem) {
      return failure(problem)
    }
  })
}
