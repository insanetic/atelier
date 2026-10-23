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
- **Stands on its own.** Someone who was not there can finish the issue from it alone: why, done when, who
  to ask and what the work needs. People, documents, the original request and related issues go into the
  tracker's fields, not the text.
- **One kind:** `bug`, `feature`, `improvement`, `task` (also non-software work).
- **Priority from a signal**, on a fixed scale (urgent, high, medium, low) from who is affected and what is
  waiting; `none` when nothing says so, never a default that looks judged. Shown with its reason first.
- **Changelog-ready.** Each kind has a Keep a Changelog group (bug Fixed, feature Added, improvement
  Changed), and a bug's TL;DR keeps the symptom so it stays findable.
- **The title is the outcome**, at most 70 characters, no prefix, so it can go into a changelog as is.
- **One body shape per kind**, at most 120 words without checklists, after a one-sentence `TL;DR:` line
  (in every language):

  | Kind | Sections |
  |---|---|
  | `bug` | Problem, Expected, *Steps*, Done when |
  | `feature` | Need, Done when, *Not included* |
  | `improvement` | Today, Better, Done when |
  | `task` | What, Why, Done when |

- **Comments** have one purpose, at most 60 words, and start with it: `Status:`, `Decision:`, `Question for
  <person>:`, `Blocked:` (German: `Stand:`, `Entscheidung:`, `Frage an <person>:`, `Blockiert:`).
- **Mention only who must act**: the person asked, the one a blocker needs, the receiver of a handoff;
  never in descriptions, status or close comments, never `@team`.
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
| `/tracker:retro` | turn work already done (this session, this branch, or what you describe) into one or several issues, written as if reported first, then hand them over or close them; suggests open issues for what was found but not done (bugs, gaps, postponed work, TODOs), created only if you pick them |
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
[`PROCEDURE.md`](PROCEDURE.md). It decides title length and prefix, the TL;DR line, the sections and their order per kind,
required sections, checklists and numbered steps, placeholders, word and sentence limits, comment leads,
handoff and close shape, mentions, secrets and personal data, and technical internals in customer-visible text. Exit
0 when there is no error, 1 with errors, 2 on a usage error. It reports; it never rewrites.

A writing-style plugin, if you have one, polishes the wording inside this shape; `tracker check` runs last.

---

## Nothing is written without your yes

The skills show every write and wait for your answer. A model can still skip that step, for example when
you ask "close IND-12" and it takes the request as the yes. So the plugin also ships a hook: before any write
to a tracker (an MCP tool of Linear, Jira, GitHub issues and similar, or `gh issue`, `gh api …/issues`,
`glab issue`, `acli jira`, `jira`), Claude Code itself asks you and shows what will be sent. Reads are not
affected. To switch the hook off, for example when a rule of yours waives confirmation, set
`TRACKER_CONFIRM_WRITES=0` under `env` in your settings.

---

## Layout

```text
plugins/tracker/
├── .claude-plugin/plugin.json
├── CONVENTION.md                  # Conventional Issues, CI-0xx
├── PROCEDURE.md                   # how every skill reads, maps, confirms and writes
├── bin/tracker                    # runs lib/tracker.py
├── hooks/confirm.py               # asks before every tracker write (PreToolUse)
├── lib/tracker.py                 # the check
├── skills/{issue,retro,comment,handoff,close,check}/SKILL.md
├── examples/tracker.md            # rules file to copy into ~/.claude/rules/
├── tests/test_tracker.py          # also checks the script's tables against CONVENTION.md
├── tests/test_confirm.py          # which tool calls count as tracker writes
└── evals/                         # one case per scenario, dry and without a tracker
```

## Develop

```bash
python3 -m unittest discover -s plugins/tracker/tests
claude plugin validate --strict plugins/tracker
claude plugin eval plugins/tracker --runs 2 --judge-model sonnet
```
