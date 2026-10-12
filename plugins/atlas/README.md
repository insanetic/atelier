# atlas

A [Claude Code](https://claude.com/claude-code) **plugin** for a **personal brain**: one folder of markdown notes in your home directory that holds what is worth knowing beyond a single task. It is the same in every project, it is consulted only when you ask, and it opens in Obsidian. Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install atlas@atelier
```

Then run `atlas init` once in a terminal, and ask "what do I know about Acme?" or "remember that Jane moved to the platform team".

---

## What it holds

People, organisations, decisions, concepts and sources: knowledge that outlives the task it came from. Work with a deadline belongs in a task manager, not here.

```text
~/atlas/                  # $ATLAS_HOME overrides the location
├── atlas.json            # the catalog: note types, their fields, review ages
├── notes/                # every active note, flat, one idea per file
├── inbox/                # quick captures that are not notes yet
└── archive/              # superseded and archived notes
```

A note is a markdown file. Its file name is its title, and its frontmatter is flat:

```markdown
---
id: 20261012T143055
type: person
description: Head of data at Acme; contact for the warehouse migration
aliases:
  - J. Doe
status: active
created: 2026-10-12
verified: 2026-10-12
valid_from: 2025-03-01
org: "[[Acme GmbH]]"
role: Head of data
---
Runs the data team at [[Acme GmbH]]. Decided [[Use DuckDB for the warehouse]].
```

- **Types** come from `atlas.json`: `note`, `person`, `organisation`, `decision`, `source`, `hub`. Add your own there.
- **Links** are plain wikilinks. Backlinks are computed, never stored.
- **Facts carry time:** `valid_from` and `valid_to` say when something is true, and `verified` says when it was last confirmed.
- **A fact that changed is superseded, not overwritten.** The old note moves to `archive/` with a link to its replacement.

The folder is a git repository, and every change the command makes is its own commit.

---

## In a session

Nothing from the brain is in a session until you ask. The only standing cost is the description of one skill.

| You say | What happens |
|---|---|
| "What do I know about the warehouse migration?" | The `atlas` skill searches, opens the few notes that matter, and answers from them |
| "Remember that we chose DuckDB because of cost" | It checks for an existing note, then writes or extends one |
| `/atlas:drain` | Walks the lint with you: re-verify, supersede, archive, merge or fix, one finding at a time |

The drain never runs on its own, and it never decides for you whether something is still true.

---

## The command

`atlas` is on the PATH while the plugin is enabled. It needs Python 3.9 or later and nothing else. There is no index: each call reads the files, so an edit in Obsidian is seen at once.

```bash
atlas find --text "acme warehouse"                  # every word must appear; title matches first
atlas find --type person --where "org=Acme" --valid-on today
atlas find --type decision --verified-before 2026-04-01
atlas find --links-to "Jane Doe"
atlas get "Jane Doe"                                # the note, and what links to it
atlas new "Jane Doe" --type person -d "Head of data at Acme" --set "org=[[Acme GmbH]]"
atlas supersede "Pricing 2025" --by "Pricing 2026"
atlas rename "Acme" "Acme GmbH"                     # rewrites every link
atlas check                                         # the lint
```

`find` prints one line per note (path, type, description), so the agent picks what to open without opening it.

| Command | What it does |
|---|---|
| `init` | Creates the brain |
| `types` | Prints the catalog |
| `find`, `get`, `links` | Search, read, follow links |
| `new`, `capture`, `inbox` | Write a note, drop a line into the inbox, list the inbox |
| `set`, `verify` | Change fields, mark as confirmed today |
| `supersede`, `archive`, `restore` | Close a note in favour of a newer one, shelve it, bring it back |
| `rename`, `merge` | Rename with relinking, fold a duplicate into another note |
| `check` | Report what needs attention; exits 1 on an error |

`atlas <command> --help` lists the options.

### What the lint finds

| Finding | Level | Meaning |
|---|---|---|
| `schema` | error | Missing required field, unknown type, a date that is not a date |
| `broken-link` | error | A link to a note that does not exist |
| `duplicate` | error | Two notes share a title or an alias |
| `supersede` | error | Superseded without a replacement, or the replacement is missing |
| `expired` | warning | `valid_to` has passed and the note is still active |
| `overdue` | warning | Not verified within the age its type sets |
| `orphan` | warning | Nothing links to it and it is not a hub |
| `misplaced` | warning | Status and folder disagree |
| `inbox` | warning | A capture older than the inbox age |

---

## Obsidian

Open the brain's folder as a vault. Notes, links, backlinks, the graph and properties work as they are. Edit freely: the command reads the files on every call. Rename notes inside Obsidian (it updates the links) or with `atlas rename`, not in a file manager.

Keep frontmatter flat: `key: value` or a list. The lint reports lines it cannot read.

---

## Install

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install atlas@atelier                 # user scope: every project on this machine
atlas init                                    # once, in a terminal
```

`atlas init` prints two entries for `~/.claude/settings.json`: the brain under `permissions.additionalDirectories`, and allow rules for the command and for edits in the brain. Add them to reach the brain from any project without prompts.

Update later with `/plugin marketplace update atelier`.

---

## What's inside

| Component | Name | What it does |
|---|---|---|
| Skill | `/atlas` (`/atlas:atlas`) | Recall and remember: when to consult the brain and how to call the command |
| Skill | `/atlas:drain` | Works through the lint with you; runs only when you call it |
| Command | `atlas` | Everything that needs no judgment: search, write, lifecycle, lint |

No hook, no MCP server, nothing added to CLAUDE.md.

---

## Repository layout

```text
plugins/atlas/
├── .claude-plugin/plugin.json    # plugin manifest
├── DESIGN.md                     # the design and what is left for later
├── bin/atlas                     # the command on the PATH
├── lib/atlas.py                  # its implementation, standard library only
├── skills/atlas/SKILL.md         # recall and remember
├── skills/drain/SKILL.md         # work through the lint
└── tests/test_atlas.py
```

---

## Develop

```bash
python3 -m unittest discover -s tests
claude plugin validate --strict .
claude --plugin-dir .                 # try it live
```

The design, and the triggers for what is deliberately left out (a cache, semantic search, automatic capture, sharing), are in [DESIGN.md](DESIGN.md).
