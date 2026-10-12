---
name: write
description: Use when adding, changing, retiring or reviewing a convention that coding agents must follow in a repository - a file under .claude/rules/, CLAUDE.md or AGENTS.md guidance, Cursor or Copilot instructions - or when someone asks that Claude "always" or "never" do something in this project. Any stack. Not for the content of a skill (a procedure).
argument-hint: "[the convention to add, change or retire]"
---

# Writing rules

A rule is one checkable statement with a stable ID, in a fixed grammar, in a catalog every repository reads the same
way. If the repository already has an authoring file for its catalog (often `.claude/rules/authoring.md`), it wins
where it is more specific: its ID prefixes, its file names, its kinds of check. Everything else here applies.

The `rulebook` command decides everything about the catalog a machine can; it is on the PATH while this plugin is
enabled. Use it instead of reading or counting by hand:

| Command                 | Gives                                                                    |
| ----------------------- | ------------------------------------------------------------------------ |
| `rulebook next <AREA>`  | the next free ID of a prefix                                             |
| `rulebook show <ID>...` | the entries as written, with their file and line                         |
| `rulebook check`        | every fault of the grammar below, with its place and its fix; exit 0 clean |

## 1. Decide where it goes

Take the first line that fits:

| The convention                                                         | Home                                                  |
| ---------------------------------------------------------------------- | ----------------------------------------------------- |
| Follows from the code, the language's defaults or the framework's docs | Nowhere. Write nothing                                |
| A machine can decide it (linter rule, test, hook)                      | The check, plus an entry whose `Checked by:` names it |
| Needs judgment                                                         | An entry with `Checked by: review`                    |
| An ordered procedure (how to add an endpoint, a migration, an email)   | A skill that cites entry IDs and restates none        |
| A one-off instruction for this task                                    | Nowhere. Do it                                        |

A check's failure message starts with the entry ID and says the fix. Fix or waive every existing violation in the
same change, so the check starts green.

Before writing, search the catalog for the subject (`grep -rn '<subject>' .claude/rules`): an entry that already says
it is edited, and one that says the opposite is the conflict to raise, not a second entry to add.

## 2. Pick the file

- `.claude/rules/<area>.md` is the core: shared by every repository of the family, generic examples (Order,
  Customer, Invoice), no product names, so the file stays identical everywhere.
- `.claude/rules/<product>-<area>.md` holds one product's additions and its pointers to real code. A product entry
  adds to the core and never contradicts it. A repository that shares its catalog with no other needs no product
  files: every entry lives in `<area>.md`.
- Frontmatter: `paths:` with a YAML list of globs scopes a file to the code it governs; it is the only key Claude Code
  reads. A file without `paths:` loads in every session, so only the contract and the cross-cutting entries live
  there. Invalid YAML loads the file everywhere: keep the frontmatter to `paths:` alone.
- Other tools: [references/tools.md](references/tools.md).

A new catalog starts with the contract, once, in its always-loaded file: [references/catalog.md](references/catalog.md).

## 3. Write the entry

```markdown
### <ID> [MUST|SHOULD] <what must be true, as a checkable sentence>

What it means, in one to three lines. For a SHOULD: `Outweighed when <what can outweigh it>.`

- Good: <a minimal correct example>
- Bad: <the mistake it prevents>
- Checked by: <tool> `<rule>`, `<rule>`; <path of a test or hook>; review (<the part only review covers>)
- Waiver: <the exact marker that allows a local exception>
- Why: <one sentence>
```

- **ID**: `<AREA>-<nnn>`, three digits, from `rulebook next <AREA>`; product entries use the product's prefix. A
  number is never reused.
- **Title**: one observable behaviour a reviewer can answer yes or no to; two independent rules are two entries. A
  prohibition names the behaviour and the alternative in the same line ("HTTP is called only from services", not
  "don't use HttpClient").
- **MUST** allows a deviation only through its `Waiver:`. **SHOULD** says what outweighs it, in a sentence that
  starts with `Outweighed`. An exception is a `Waiver:` marker or its own entry, never a clause in the title or body.
- **Lines** come in the order Good, Bad, Checked by, Waiver, Why. `Checked by:` is required; an entry checked only by
  review has a `Good:` or a `Bad:`. `Waiver:` only when the entry allows one. `Why:` gives the reason and adds no rule.
- **Checked by** lists its checks separated by `;`. Each is a tool followed by the backticked names of its rules
  (``eslint `no-restricted-imports` ``), the path of the test, hook or workflow that enforces the entry
  (`internal/guard_test.go`), or `review`. A note goes in parentheses after the check it belongs to. A path named
  here must exist.
- **Tone**: plain sentences. No capitals for emphasis, no IMPORTANT or CRITICAL.

## 4. Change or retire

Read the entry first with `rulebook show <ID>`.

| Change                  | Do                                                                           |
| ----------------------- | ---------------------------------------------------------------------------- |
| Wording, same meaning   | Edit in place, same ID                                                       |
| New meaning             | New ID. The old entry becomes `### <old ID> [RETIRED] Replaced by <new ID>.` |
| Dropped                 | `### <ID> [RETIRED] <one-line reason>.`                                      |
| Ignored twice in review | Make it a check, or delete it                                                |

While a catalog is still being designed and used by one repository, delete the old entry instead of retiring it.
Either way, every citation of the old ID changes in the same change: `rulebook check` lists the ones left behind in
the catalog, the skills, `CLAUDE.md` and `AGENTS.md`; `grep -rn '<old ID>'` finds those in code and check messages.

## 5. Verify

1. `rulebook check` exits 0. It decides: the heading grammar, duplicate IDs, a missing `Checked by:`, a review-only
   entry without an example, the line order, a SHOULD without `Outweighed`, a `Checked by:` path that does not exist,
   a citation of an unknown or retired ID, and frontmatter that is unclosed or holds a key other than `paths:`. The
   plugin also runs it after every edit of a rules file and reports what it finds beside the edit.
2. A new check fails on a known violation, and its message starts with the entry ID.
3. No other entry says the same or the opposite (the search of step 1).

## 6. Reply

List the entries added, changed or retired by ID, with their homes, and the last line of `rulebook check`. A
convention you think is missing goes in the reply as a proposal, not into the catalog: write only what was asked.
