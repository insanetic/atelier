import type { EngineInterface, Register } from 'claude-code'
import * as core from '../dist/core.js'

const MAX_ISSUES = 20

/** core's Io over the engine: the mod has no Node, every read goes through $. */
function modIo($: EngineInterface): core.Io {
  return {
    async readText(path) {
      return (await $.fs.exists(path)) ? String(await $.fs.read(path)) : undefined
    },
    async list(path) {
      if (!(await $.fs.exists(path))) return []
      return (await $.fs.list(path)).map(entry => ({ name: entry.name, isDir: entry.kind === 'dir' }))
    },
    exists: path => $.fs.exists(path),
  }
}

/** What the catalog check says after an edit of a rules file, for the model to read beside the edit's result. */
async function report($: EngineInterface, filePath: string): Promise<string | undefined> {
  const root = await $.session.root()
  if (!filePath.startsWith(`${root}/${core.RULES_DIR}/`) || !filePath.endsWith('.md')) return undefined
  const issues = await (await core.openWorkspace(modIo($), root)).issues()
  if (issues.length === 0) return undefined
  const more = issues.length > MAX_ISSUES ? `\n… and ${issues.length - MAX_ISSUES} more: run \`rulebook check\`` : ''
  return `rulebook check: ${issues.length} to fix in the catalog. Fix each before you go on.\n${core.renderIssues(issues.slice(0, MAX_ISSUES))}${more}`
}

export const register: Register = on => {
  for (const tool of ['Edit', 'Write'] as const) {
    on('tool.call', { tool }, async ($, e, next) => {
      const ran = await next(e)
      if (ran.deny !== undefined || ran.isError === true) return ran
      const text = await report($, e.file_path)
      return text === undefined ? ran : { ...ran, context: [...(ran.context ?? []), text] }
    }).catch(($, e, next) => next(e)) // the check never stands in the way of the edit
  }
}
