# rulebook

A [Claude Code](https://claude.com/claude-code) **plugin** for a **numbered convention catalog**: the rules coding agents must follow in a repository, each written as one checkable entry with a stable ID, checked by a machine wherever a machine can decide, and reviewed by an agent only where it cannot. Any stack. Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install rulebook@atelier
```

Then ask "add a rule that HTTP is called only from services", or run `/rulebook:review add the invoice export endpoint` before a commit.

---

## The catalog

Rules live in `.claude/rules/*.md`. Every entry has the same shape:

```markdown
### HTTP-001 [MUST] HTTP is called only from services

Components, directives and pipes call a method on an injectable service that owns the endpoint and its types.

- Bad: `inject(HttpClient)` in a `*.component.ts`.
- Checked by: eslint `no-restricted-imports`; review (a wrapper around the client)
```

- **One ID, cited everywhere.** Skills, docs, check messages and review findings name `HTTP-001` and restate nothing.
- **`Checked by:` is required.** It names the lint rule, test or hook that enforces the entry, or `review` when only judgment can.
- **MUST or SHOULD.** A MUST bends only through the waiver its entry names; a SHOULD says what outweighs it.
- **Core and product.** `<area>.md` files are identical across the repositories of a family; `<product>-<area>.md` files hold one product's additions. A single repository needs only the first kind.

The plugin holds the method and the tooling, not the rules: each repository keeps its own catalog and its own checks.

---

## What a machine decides

Everything about the catalog that needs no judgment is the `rulebook` command's, not the model's. It is on the `PATH` while the plugin is enabled, has no dependencies, and runs the same in a terminal, a git hook or CI.

| Command | Gives |
|---|---|
| `rulebook check` | Every fault of the catalog, each with its place and its fix; exit 1 when there is one |
| `rulebook for [--ids] [<file>...]` | The rule files that govern the files (the changed ones when none are named) and, in full, the entries review checks |
| `rulebook changed [--base <ref>]` | The changed files: the branch against its base, the working tree, the untracked |
| `rulebook next <AREA>` | The next free ID of a prefix |
| `rulebook show <ID>...` | The entries as written, with file and line |

`rulebook check` decides:

- the heading grammar, `### <AREA>-<nnn> [MUST|SHOULD|RETIRED] <rule>`, and that no ID is used twice
- a live entry without `Checked by:`, and a review-only entry without a `Good:` or a `Bad:`
- the line order Good, Bad, Checked by, Waiver, Why
- a SHOULD that does not say what outweighs it
- a `Checked by:` that names a file which does not exist
- a citation of an unknown or retired ID, in the catalog, `.claude/skills/`, `CLAUDE.md` and `AGENTS.md`
- frontmatter that is unclosed, empty, or holds a key other than `paths:`

The plugin also runs the check **after every edit of a rules file** and puts what it finds beside the edit's result, so a broken entry is fixed in the turn that wrote it. The edit itself is never blocked.

Whether a rule is true, clear or a duplicate in meaning stays a judgment, and the skills say so.

---

## The skills

- **`/rulebook:write`**: adding, changing, retiring or reviewing a convention, in `.claude/rules/`, `CLAUDE.md`, `AGENTS.md`, Cursor or Copilot instructions, or when someone asks that Claude "always" or "never" do something in a project. It first decides whether the convention belongs in the catalog at all (a check, an entry, a skill, or nowhere), takes the ID from `rulebook next`, and finishes on a clean `rulebook check`.
- **`/rulebook:review`**: before a commit or merge, or when asked whether a change follows the catalog or built what was requested. Not a bug or security review; it runs next to them.

A repository's own authoring file (often `.claude/rules/authoring.md`) wins where it is more specific: its ID prefixes, its file names, its kinds of check.

### How a review runs

The review runs forked, as the read-only `reviewer` agent: it sees none of the conversation, only its arguments, and has no tool that edits. An approval that is not passed does not exist for it.

```text
/rulebook:review <the ask> | deviations: <approved departures> | files: <paths, optional>
```

1. **The ask:** the requirements, from the arguments, the commit messages or the linked issue.
2. **The change:** the named files, or `rulebook changed`.
3. **The gate:** the command the repository names for checking a change. A failure is a finding as it stands.
4. **The entries:** `rulebook for` selects them. The reviewer reads only the entries review checks, for the rule files whose `paths:` match; nothing is selected by eye.
5. **The report:** a verdict, what was reviewed, the requirements traced both ways, blockers and should-fixes by entry ID with `file:line`, requested deviations, and catalog gaps as proposals.

No entry, no finding: a pattern the catalog lacks is reported as a gap, never as a violation.

---

## Install

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install rulebook@atelier
# or, from a local clone:
/plugin marketplace add ./path/to/atelier
```

For a whole project, run `claude plugin marketplace add insanetic/atelier --scope project` and `claude plugin install rulebook@atelier --scope project` in its root, then commit `.claude/settings.json`.

Update later with `/plugin marketplace update atelier`.

**Requirements:** Node 24 or later for the `rulebook` command. Claude Code on claude.ai and Cowork does not install a plugin that ships a `bin/` directory.

**In CI or a git hook:** run the bundled file directly, `node <atelier>/plugins/rulebook/dist/cli.js check`.

---

## What's inside

| Component | Name | What it does |
|---|---|---|
| Skill | `/rulebook:write` | Where a convention goes, the entry grammar, changing and retiring an entry, starting a catalog |
| Skill | `/rulebook:review` | The forked review: the ask, the gate, the selected entries, the report |
| Agent | `rulebook:reviewer` | The read-only agent the review runs as: Read, Grep, Glob, Bash |
| CLI | `rulebook` | `check`, `for`, `changed`, `next`, `show` |
| Hook | `tool.call` on Edit and Write | Runs the catalog check after an edit of a rules file |

---

## Repository layout

```text
plugins/rulebook/
├── .claude-plugin/plugin.json    # plugin manifest
├── skills/
│   ├── write/                    # the method, with references/catalog.md and references/tools.md
│   └── review/SKILL.md           # the review
├── agents/reviewer.md            # the read-only reviewer
├── core/                         # parser, checks, glob matching, selection: pure, no Node
├── cli/                          # the rulebook command over core
├── hooks/                        # the mod: the check after an edit, over the same core
├── bin/rulebook                  # the launcher on the PATH
├── dist/                         # the bundled core and CLI, committed
└── tests/                        # core and cli (node --test), mod (claude plugin test)
```

---

## Develop

```bash
npm install
npm run build                         # bundles core and the CLI into dist/; commit the result
npm test && npm run typecheck
claude plugin test .                  # the hook, against the engine
claude plugin validate --strict .
claude --plugin-dir .                 # try it live
```
