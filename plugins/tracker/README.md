# tracker

A [Claude Code](https://claude.com/claude-code) **plugin** for issues and tasks in any tracker: **Conventional
Issues**, one short, fixed shape for issues, comments, handoffs and closes, like Conventional Commits for
commit messages, and the skills that keep every write to it. Part of the [atelier](../../README.md)
marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install tracker@atelier
```

It uses whatever tracker tool is connected (the Linear MCP, a Jira or GitHub tool, a CLI). With none, every
result comes back ready to copy and paste.

---

## The convention

[`CONVENTION.md`](CONVENTION.md) is the whole of it, readable without the plugin. In short:

- **Written for customers by default.** Trackers push issues to customer platforms and changelogs on their
  own, so nothing internal goes in unless the issue is internal: no code, paths, commits, stack traces,
  secrets, personal data, other customers, blame, or how the work was made.
- **Nothing guessed.** A missing fact is asked or its section is left out.
- **One kind:** `bug`, `feature`, `improvement`, `task` (also non-software work).
- **Always a priority**, inferred on a fixed scale (urgent, high, medium, low) from who is affected and what
  is waiting; `medium` when nothing says otherwise, shown with its reason before it is set.
- **The title is the outcome**, at most 70 characters, no prefix, so it can go into a changelog as is.
- **One body shape per kind**, at most 120 words without checklists:

  | Kind | Sections |
  |---|---|
  | `bug` | Problem, Expected, *Steps*, *Done when* |
  | `feature` | Need, Done when, *Not included* |
  | `improvement` | Today, Better, *Done when* |
  | `task` | What, *Why*, Done when |

- **Comments** have one purpose, at most 60 words, and start with it: `Status:`, `Decision:`, `Question for
  <person>:`, `Blocked:` (German: `Stand:`, `Entscheidung:`, `Frage an <person>:`, `Blockiert:`).
- **Handoff is not closing.** Moving to review or to someone always leaves three lines: `Ready for review:`,
  `To check:`, `Open:`.
- **Close** with one result and at most two sentences: `Done:`, `Not doing:`, `Works as intended:`,
  `Duplicate of`, `Not reproducible:`, `No longer relevant:`.

German and English section names and leads are both defined; the text follows the language of the thread.

---

## The skills

| Skill | Use it to |
|---|---|
| `/tracker:issue` | create a new issue from a report, request or a bug found while working |
| `/tracker:retro` | turn work already done (this session, this branch, or what you describe) into one or several issues, written as if reported first, then hand them over or close them |
| `/tracker:comment` | add a progress, decision, question or blocker comment |
| `/tracker:handoff` | move an issue to review or another person, with the three-line comment |
| `/tracker:close` | close one or several issues with a result and a closing comment |
| `/tracker:check` | check a draft or an existing issue against the convention |

Every skill follows [`PROCEDURE.md`](PROCEDURE.md): find the tracker, resolve the exact target (your rule,
what you said, the related issue, the repository matched against project names, the project of similar
issues; asking only when several fit), look up its
labels and statuses live and map the convention onto them, draft, check, **show you everything it will write
and wait for your yes**, then write and report the ID and link. It never invents labels, statuses or people
and never creates a label without asking.

Typical chains: work done → `retro` → `handoff` (testing) or `close` (done). Retro reuses the `issue`,
`handoff` and `close` steps, so a backfilled issue looks exactly as if it had been filed first. A bug found on the way → `issue`,
linked to the one in progress.

### Turning it on

Claude may answer "create a ticket" with the tracker's tools directly. To make it use these skills every
time, copy [`examples/tracker.md`](examples/tracker.md) to `~/.claude/rules/tracker.md`:

```bash
cp plugins/tracker/examples/tracker.md ~/.claude/rules/tracker.md
```

It also shows how to fix routing (this repository goes to team X, project Y), mark teams or projects as
internal-only, set the default language and address, and waive confirmation for one kind of write. The file
is yours; the plugin installs nothing. The entries use the [rulebook](../rulebook) format; `CI-1xx` is free
for your rules.

---

## `tracker check`

On the `PATH` while the plugin is enabled. Python 3.9+, no dependencies, no network, no tracker.

```bash
tracker check [--json] <file|->
```

The draft carries a small frontmatter (`type`, `kind`, `purpose`, `result`, `audience`); see
[`PROCEDURE.md`](PROCEDURE.md). It decides title length and prefix, the sections and their order per kind,
required sections, checklists and numbered steps, placeholders, word and sentence limits, comment leads,
handoff and close shape, secrets and personal data, and technical internals in customer-visible text. Exit
0 when there is no error, 1 with errors, 2 on a usage error. It reports; it never rewrites.

A writing-style plugin, if you have one, polishes the wording inside this shape; `tracker check` runs last.

---

## Layout

```text
plugins/tracker/
├── .claude-plugin/plugin.json
├── CONVENTION.md                  # Conventional Issues, CI-0xx
├── PROCEDURE.md                   # how every skill reads, maps, confirms and writes
├── bin/tracker                    # runs lib/tracker.py
├── lib/tracker.py                 # the check
├── skills/{issue,retro,comment,handoff,close,check}/SKILL.md
├── examples/tracker.md            # rules file to copy into ~/.claude/rules/
├── tests/test_tracker.py          # also checks the script's tables against CONVENTION.md
└── evals/                         # one case per scenario, dry and without a tracker
```

## Develop

```bash
python3 -m unittest discover -s plugins/tracker/tests
claude plugin validate --strict plugins/tracker
claude plugin eval plugins/tracker --runs 2 --judge-model sonnet
```
