/** The tool-owned files of a study: only add_finding, verify_finding and set_score write them. */
export const GUARDED_FILE = /(^|\/)studies\/[^/]+\/(findings|assessment)\.yaml$/

const NAMED = /(?:findings|assessment)\.yaml\b/
const REDIRECT = />\|?>?\s*['"]?[^\s'"]*(?:findings|assessment)\.yaml/
const IN_PLACE_TOOL = /\b(?:sed|perl|ruby|yq)\b/
const IN_PLACE_FLAG = /\s(?:-[a-zA-Z]*i[a-zA-Z.]*|--in-?place\S*)(?=\s|$)/
const REMOVES = /\b(?:rm|mv|truncate|shred|unlink)\b/
const COPIES_ONTO = /\b(?:cp|install|ln|rsync)\b/
const GIT_REWRITES = /\bgit\s+(?:checkout|restore|reset|stash|apply|am|mv|rm)\b/
const DD_ONTO = /\bdd\b.*\bof=\S*(?:findings|assessment)\.yaml/
const SCRIPT = /\b(?:python3?|node|deno|bun|ruby)\b/
const SCRIPT_WRITE = /\b(?:open|writeFile\w*|write_text|write_bytes|dump)\s*\(/
const READ_ONLY_OPEN = /\bopen\s*\([^)]*\)\s*\)/

const lastWord = (segment: string) => (segment.trim().split(/\s+/).at(-1) ?? '').replace(/^['"]|['"]$/g, '')

/** A script that opens the file for writing: open(..., 'w'), writeFileSync, write_text, dump into an open handle. */
function scriptWrites(segment: string): boolean {
  if (!SCRIPT.test(segment) || !SCRIPT_WRITE.test(segment)) return false
  if (/\bopen\s*\([^)]*,\s*['"][wa+]/.test(segment) || /\b(?:writeFile\w*|write_text|write_bytes)\s*\(/.test(segment)) return true
  return /\bdump\s*\(/.test(segment) && !READ_ONLY_OPEN.test(segment)
}

/**
 * Whether a shell command would write a study's findings.yaml or
 * assessment.yaml. Each command of a pipeline or list is judged on its own, so
 * reading, grepping or copying the files elsewhere stays allowed.
 */
export function isGuardedWrite(command: string): boolean {
  if (!NAMED.test(command)) return false
  // An inline script keeps its own ; and | inside quotes: it is judged whole.
  if (scriptWrites(command)) return true
  return command.split(/&&|\|\||[;|\n]/).some(segment => {
    if (!NAMED.test(segment)) return false
    if (REDIRECT.test(segment) || /\btee\b/.test(segment)) return true
    if (IN_PLACE_TOOL.test(segment) && IN_PLACE_FLAG.test(segment)) return true
    if (REMOVES.test(segment) || GIT_REWRITES.test(segment) || DD_ONTO.test(segment)) return true
    return COPIES_ONTO.test(segment) && NAMED.test(lastWord(segment))
  })
}
