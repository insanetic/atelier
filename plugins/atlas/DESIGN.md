# atlas: design

Version 0.1.

## What it is

A personal brain: one folder of markdown notes in the home directory that holds what is worth knowing beyond
a single task (people, organisations, decisions, concepts, sources), reachable from every Claude Code session
and opened by Obsidian for reading and editing by hand.

## Goals

- **One brain per user**, not per project, the same in every session.
- **Used when the turn calls for it.** A session starts with a short hint and the standing preferences; nothing
  else is loaded until the skill or the command is called.
- **Files are the truth.** Plain markdown that Obsidian, an editor and git all understand.
- **No index.** Every query scans the files; nothing can go stale.
- **A lifecycle.** A note can be verified, superseded and archived, and a lint names what needs attention.

## Not in this version

- Sharing, sync between people, a server.
- Search by meaning (embeddings).
- Typed relations between notes.
- Automatic capture from sessions, and any background agent.
- Links to the task, mail and calendar plugins.

## The brain

```text
~/atlas/                  # $ATLAS_HOME overrides the location
├── atlas.json            # the catalog: note types, their fields, review ages
├── notes/                # every active note, flat, one idea per file
├── inbox/                # quick captures that are not notes yet
├── archive/              # superseded and archived notes
└── .gitignore            # Obsidian's workspace files
```

It is a git repository when git is available. Every command that changes a file commits exactly the files it
touched, and a PostToolUse hook commits each file Claude's edit tools change inside the brain, so each change by an
agent can be seen and undone. Edits the user makes in Obsidian are theirs to commit (`atlas commit`); the lint
reports what is left uncommitted.

## A note

```markdown
---
id: 20261012T143055
type: person
description: Head of data at Acme; our contact for the warehouse migration
aliases:
  - J. Doe
status: active
created: 2026-10-12
verified: 2026-10-12
valid_from: 2025-03-01
org: "[[Acme GmbH]]"
role: Head of data
sources:
  - "[[Kickoff call 2026-10-01]]"
---
Jane runs the data team at [[Acme GmbH]]. She decided on [[Use DuckDB for the warehouse]].
```

- **The file name is the title.** Obsidian resolves `[[Jane Doe]]` by file name, so links are written with the title.
- **`id` is the stable handle.** It survives a rename. It is the creation time to the second.
- **`description` is one line.** `atlas find` prints it, so the agent can choose what to open without opening it.
- **Frontmatter is flat:** `key: value`, or a list. Obsidian does not support nested properties, and a flat
  subset needs no YAML library.
- **A change touches only its fields.** Writing a note keeps the lines of the fields it did not change, comments
  and lines it cannot read exactly as they were.

### Fields of every note

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable identifier |
| `type` | yes | One of the types in `atlas.json` |
| `description` | yes | One line saying what the note holds |
| `status` | yes | `active`, `superseded` or `archived` |
| `created` | yes | Date the note was created |
| `aliases` | no | Other names for the same thing |
| `verified` | no | Date the content was last confirmed |
| `valid_from`, `valid_to` | no | When the content is true: from the first date up to, not including, the second |
| `superseded_by` | no | Link to the note that replaced this one |
| `sources` | no | Links or URLs the content came from |

Any other field is allowed and left alone.

### The catalog

`atlas.json` lists the types. Adding a type is an edit to this file, not to the code.

| Type | For | Own fields | Review after |
|---|---|---|---|
| `note` | A concept, fact or lesson (the default) | none | 365 days |
| `person` | Someone you deal with | `org`, `role` | 180 days |
| `organisation` | A company, team or vendor | none | 365 days |
| `decision` | Something decided, with the reason | `decided` (required) | never |
| `source` | An article, document or thread | `url`, `author` | never |
| `hub` | An entry point that links a topic's notes | none | never |
| `preference` | How the user wants Claude to work, in every project | none | 365 days |

A brain made before `preference` existed gets it by adding the type to its `atlas.json`.

### Links

- Plain wikilinks in the text: `[[Title]]`, `[[Title|shown text]]`, `[[Title#Heading]]`.
- Backlinks are computed by scanning, never stored.
- Relations are not typed. Two fields are links the tool acts on: `superseded_by` and `sources`.

## The command

`atlas` is on the PATH while the plugin is enabled. Python 3.9 or later, standard library only.

| Command | What it does |
|---|---|
| `atlas init` | Creates the brain, its catalog and a `Home` hub, and makes it a git repository |
| `atlas types` | Prints the catalog |
| `atlas hint` | Prints the session-start hint and the standing preferences; prints nothing without a brain |
| `atlas find [filters]` | Lists matching notes, one line each: path, type, description |
| `atlas get <ref>` | Prints one note and the notes that link to it |
| `atlas links <ref>` | Prints a note's outgoing links and backlinks |
| `atlas new --type T "Title"` | Creates a note; refuses when the title or an alias is taken; `--from <ref>` links it from a hub |
| `atlas link <from> <to> …` | Appends `- [[to]]` to a hub or note, unless it already links there |
| `atlas commit [ref …]` | Commits the named notes, or every changed file; `--hook` is what the edit hook runs |
| `atlas capture "text"` | Drops a line into the inbox; never overwrites an earlier capture |
| `atlas inbox` | Lists the inbox with ages |
| `atlas set <ref> key=value …` | Changes frontmatter fields; a repeated key makes a list, `key=` clears it |
| `atlas verify <ref>` | Sets `verified` to today |
| `atlas supersede <old> --by <new>` | Closes the old note and moves it to the archive |
| `atlas archive <ref>` | Moves a note to the archive |
| `atlas restore <ref>` | Brings an archived note back as active |
| `atlas rename <ref> "New title"` | Renames the file, rewrites every link, keeps the old title as an alias |
| `atlas merge <dup> --into <note>` | Points the duplicate's links and names at the survivor and archives it |
| `atlas check` | The lint |

`<ref>` is a title, an alias, an id or a path. An active note wins over an archived one, and a title over an alias.
An archived note keeps its title, but its aliases are free for the note that replaced it.

Field values are one line: whitespace and newlines in a value become one space.

### Filters of `find`

All are optional and combine.

| Filter | Keeps notes |
|---|---|
| `--type person` | Of that type (repeatable) |
| `--text "warehouse acme"` | Containing every word at the start of a word, ignoring case and accents, in the title, an alias, the description, another field's value or the text (never in field names or bookkeeping fields); ranked in that order |
| `--valid-on 2026-10-12` | Valid on that date |
| `--valid-from D`, `--valid-to D` | Whose validity overlaps that period |
| `--verified-before D` | Not verified since that date |
| `--status superseded` | With that status (default: `active`) |
| `--links-to <ref>`, `--linked-from <ref>` | Linked with that note |
| `--where key=value` | Whose field equals, or whose list contains, the value |
| `--all` | Also from the archive |
| `--limit N`, `--json`, `--paths` | Output control |

### The lint

`atlas check` reports, and exits 1 when there is an error:

| Finding | Level | Meaning |
|---|---|---|
| `schema` | error | Missing required field, unknown type, a date that is not a date |
| `broken-link` | error | A link to a note that does not exist |
| `duplicate` | error | Two active notes share a title or an alias, or an archived title is an active title |
| `supersede` | error | `superseded` without `superseded_by`, or its target is missing |
| `expired` | warning | `valid_to` has passed and the note is still active |
| `overdue` | warning | Not verified within the age its type sets |
| `orphan` | warning | Nothing links to it and it is not a hub or a preference |
| `misplaced` | warning | Status and folder disagree |
| `inbox` | warning | A capture older than the inbox age |
| `uncommitted` | warning | A file changed since the last commit |

## In a session

- **A SessionStart hook** runs `atlas hint`: one paragraph saying the brain exists and when to use the skill, then
  the active `preference` notes, one line each (at most 20). Without it the skill did not trigger on questions that
  did not name the brain (0 of 6 sessions), because Claude's own memory answered them first. The hint and the
  skill's name and description are the standing cost.
- **The skill `atlas`** says when to consult the brain and how to call the command. It runs when the user asks
  about something they may have recorded, asks to remember something, or types `/atlas`.
- **The skill `drain`** (`/atlas:drain`) walks the lint with the user: re-verify, supersede, archive, merge or fix,
  one finding at a time. It never runs on its own.
- **A PostToolUse hook** on Claude's edit tools commits a file it changed inside the brain. It is silent and does
  nothing for files elsewhere.
- **Two hooks, no MCP server, nothing in CLAUDE.md.**
- **Access from any project** needs two entries in the user's `~/.claude/settings.json`, which `atlas init`
  prints and the user adds: the brain under `permissions.additionalDirectories`, and an allow rule for the command.

## Rules the skills hold to

- **Look before writing.** `atlas find` first; extend an existing note before creating one.
- **One idea per note,** with a description that says what it holds.
- **Keep what was true before.** A note about something that lasts (person, organisation, topic) is edited in
  place and says what changed and when; a claim at a point in time (decision, price, plan) is superseded by a new
  note. A title like "Jane Doe" cannot be superseded by another "Jane Doe", and links to it must keep working.
- **Preferences that hold in every project go to the brain** as `preference` notes; preferences for one repository
  stay in that repository.
- **Say where it came from.** Fill `sources`; mark what the agent concluded itself as such in the text.
- **Open few notes.** Choose from the descriptions; read only what the question needs.

## Later, when a trigger is met

| Add | When |
|---|---|
| A cache of the scan | A scan takes more than about a second in real use |
| Ranked or semantic search | Queries need several tries to find a note that exists |
| Capture at the end of a session | Captures by hand are too few |
| Spaces and sharing | A second person needs part of it |
