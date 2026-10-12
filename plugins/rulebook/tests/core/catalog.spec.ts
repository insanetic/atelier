import { test } from 'node:test'
import assert from 'node:assert/strict'
import { check, loadCatalog, matchesGlob, nextId, parseCheckedBy, parseFrontmatter, parseRulesFile, renderIssues, renderSelection, rulesFor } from '../../core/index.ts'

const RULES = [
  '---',
  'paths:',
  "  - 'src/**/*.ts'",
  '  - "*.config.mjs"',
  '---',
  '',
  '# Example',
  '',
  '```markdown',
  '### XY-999 [MUST] Inside a fence, never an entry',
  '```',
  '',
  '### XY-001 [MUST] One rule',
  '',
  'Meaning.',
  '',
  '- Checked by: eslint `a/b`, `c/*` (a note `x/y`); internal/guard_test.go; review',
  '',
  '### XY-002 [SHOULD] Another rule',
  '',
  'Outweighed when a public API already exposes the other form.',
  '',
  '- Good: something.',
  '- Checked by: eslint `@scope/one`,',
  '  `@scope/two`',
  '',
  '## Section',
  '',
  '### XY-003 [RETIRED] Replaced by XY-001.',
].join('\n')

const file = (path: string, text: string) => ({ path, text })
const messages = (...files: { path: string; text: string }[]) => renderIssues(check(files)).split('\n')

test('a Checked by line splits at semicolons, keeps backticked names and drops notes', () => {
  assert.deepEqual(parseCheckedBy('eslint `a`, `b` (see `c`); internal/guard_test.go; review (the rest)'), [
    { kind: 'eslint', names: ['a', 'b'] },
    { kind: 'internal/guard_test.go', names: [] },
    { kind: 'review', names: [] },
  ])
})

test('a rules file gives its entries, skips fenced examples and joins a wrapped Checked by', () => {
  const parsed = parseRulesFile(file('x.md', RULES))
  assert.deepEqual(parsed.entries.map(entry => [entry.id, entry.level, entry.line]), [['XY-001', 'MUST', 13], ['XY-002', 'SHOULD', 19], ['XY-003', 'RETIRED', 29]])
  assert.deepEqual(parsed.entries[1]?.checks, [{ kind: 'eslint', names: ['@scope/one', '@scope/two'] }])
  assert.deepEqual(parsed.frontmatter.paths, ['src/**/*.ts', '*.config.mjs'])
})

test('frontmatter reads paths as a list, an inline list or a comma string, and names every other key', () => {
  assert.deepEqual(parseFrontmatter('---\npaths: src/**/*.ts, "lib/**"\n---\n').paths, ['src/**/*.ts', 'lib/**'])
  assert.deepEqual(parseFrontmatter("---\npaths: ['a/**', b]\n---\n").paths, ['a/**', 'b'])
  assert.deepEqual(parseFrontmatter('---\ndescription: x\nglobs: y\n---\n').otherKeys, ['description', 'globs'])
  assert.equal(parseFrontmatter('# No frontmatter\n').paths, undefined)
  assert.equal(parseFrontmatter('---\npaths:\n  - a\n').isUnclosed, true)
})

test('a glob crosses folders only with a double star', () => {
  assert.equal(matchesGlob('src/app/a.ts', 'src/**/*.ts'), true)
  assert.equal(matchesGlob('src/a.ts', 'src/**/*.ts'), true)
  assert.equal(matchesGlob('src/app/a.ts', 'src/*.ts'), false)
  assert.equal(matchesGlob('src/app/+state/plan/plan.store.ts', 'src/app/+state/**'), true)
  assert.equal(matchesGlob('eslint.config.mjs', '*.config.mjs'), true)
  assert.equal(matchesGlob('tools/eslint.config.mjs', '*.config.mjs'), false)
  assert.equal(matchesGlob('src/a.html', 'src/**/*.{ts,html}'), true)
  assert.equal(matchesGlob('a.go', '**/*.go'), true)
})

test('a sound catalog has no issues', () => {
  assert.deepEqual(check([file('.claude/rules/x.md', RULES)]), [])
})

test('check names every fault with its place and its fix', () => {
  const text = [
    '---',
    'description: x',
    '---',
    '### AB-001 [MUST] No check at all',
    '',
    '### AB-001 [MUST] Review alone, no example',
    '- Checked by: review',
    '',
    '### AB-2 [MUST] A short number',
    '',
    '### AB-003 [MAY] An unknown level',
    '',
    '### AB-004 [MUST] Lines out of order, cites AB-009 and AB-005',
    '- Why: because.',
    '- Bad: the mistake.',
    '- Checked by: spec `src/gone.spec.ts`; review',
    '',
    '### AB-005 [RETIRED] Replaced by AB-004.',
    '',
    '### AB-006 [SHOULD] Says nothing of what outweighs it',
    '- Bad: the mistake.',
    '- Checked by: review',
  ].join('\n')
  const issues = check([file('.claude/rules/a.md', text)], [file('.claude/skills/s/SKILL.md', 'Follow AB-004, AB-005 and AB-777; ISO-639 is no entry.')], new Set(['src/gone.spec.ts']))
  assert.deepEqual(renderIssues(issues).split('\n'), [
    '.claude/rules/a.md:1 the frontmatter holds `description:`; only `paths:` is read, remove the rest',
    '.claude/rules/a.md:4 AB-001: add a `- Checked by:` line that names the check, or `review`',
    '.claude/rules/a.md:6 AB-001: the ID is already used at .claude/rules/a.md:4; take the next free number (`rulebook next AB`)',
    '.claude/rules/a.md:6 AB-001: an entry checked only by review needs a `- Good:` or a `- Bad:` line',
    '.claude/rules/a.md:9 an entry heading reads `### <AREA>-<nnn> [MUST|SHOULD|RETIRED] <rule>`, the number three digits',
    '.claude/rules/a.md:11 an entry heading reads `### <AREA>-<nnn> [MUST|SHOULD|RETIRED] <rule>`, the number three digits',
    '.claude/rules/a.md:13 AB-004: the lines come in the order Good, Bad, Checked by, Waiver, Why',
    '.claude/rules/a.md:13 AB-004: `Checked by:` names src/gone.spec.ts, which does not exist; name the check that enforces the entry, or `review`',
    '.claude/rules/a.md:13 cites AB-009, which is no entry; cite an existing ID',
    '.claude/rules/a.md:13 cites AB-005, which is retired (Replaced by AB-004.); cite its replacement or drop the citation',
    '.claude/rules/a.md:20 AB-006: a SHOULD says what can outweigh it, in a sentence that starts with `Outweighed`',
    '.claude/skills/s/SKILL.md:1 cites AB-005, which is retired (Replaced by AB-004.); cite its replacement or drop the citation',
    '.claude/skills/s/SKILL.md:1 cites AB-777, which is no entry; cite an existing ID',
  ])
})

test('an unclosed frontmatter and an empty paths list are faults', () => {
  assert.match(messages(file('a.md', '---\npaths:\n  - a\n### AB-001 [MUST] x\n- Bad: y\n- Checked by: review'))[0] ?? '', /no closing `---`/)
  assert.match(messages(file('a.md', '---\npaths:\n---\n### AB-001 [MUST] x\n- Bad: y\n- Checked by: review'))[0] ?? '', /`paths:` is empty/)
})

test('rulesFor takes the always-loaded files and those whose paths match, and keeps what review checks', () => {
  const catalog = loadCatalog([
    file('.claude/rules/arch.md', '### ARCH-001 [MUST] Layers\n- Checked by: eslint `boundaries`\n\n### ARCH-002 [MUST] Search first\n- Bad: a twin.\n- Checked by: review\n'),
    file('.claude/rules/x.md', RULES),
    file('.claude/rules/sql.md', "---\npaths:\n  - '**/*.sql'\n---\n### SQL-001 [MUST] x\n- Bad: y\n- Checked by: review\n"),
  ])
  const selection = rulesFor(catalog, ['src/app/a.ts', 'README.md'])
  assert.deepEqual(selection.applied, [
    { file: '.claude/rules/arch.md', because: 'always' },
    { file: '.claude/rules/x.md', because: 'src/**/*.ts matches src/app/a.ts' },
  ])
  assert.deepEqual(selection.review.map(entry => entry.id), ['ARCH-002', 'XY-001'])
  assert.equal(selection.machineOnly, 2)
  assert.match(renderSelection(selection, true), /^- XY-001 \[MUST\] One rule \(\.claude\/rules\/x\.md:13\)$/m)
  assert.match(renderSelection(selection, false), /<!-- \.claude\/rules\/x\.md:13 -->\n### XY-001 \[MUST\] One rule\n\nMeaning\.\n\n- Checked by: eslint/)
})

test('nextId is one past the highest number ever used, retired included', () => {
  const catalog = loadCatalog([file('x.md', RULES)])
  assert.equal(nextId(catalog, 'XY'), 'XY-004')
  assert.equal(nextId(catalog, 'NEW'), 'NEW-001')
})
