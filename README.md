# atelier

A [Claude Code](https://claude.com/claude-code) **plugin marketplace**: insanetic's agent tooling (plugins, skills and mods) shared across every project and machine, and installed the same way everywhere.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install research@atelier
/plugin install market@atelier
/plugin install premortem@atelier
/plugin install rulebook@atelier
/plugin install atlas@atelier
/plugin install data-max@atelier
/plugin install tone@atelier
```

---

## Plugins

| Plugin | Invoke | What it does |
|---|---|---|
| [research](plugins/research) | `/study <task>` | Prior art before you build: how others solved a task, what to reuse, the pitfalls, and how ours compares, every claim verified quote by quote. |
| [market](plugins/market) | `/discover <category>` | Competitor tracking on top of research: the registry of every known competitor, discovery that keeps it complete, and the capability landscape. |
| [premortem](plugins/premortem) | `/premortem <plan>`, `/premortem:dystopia <product>`, `/premortem:oppenheimer <capability>` | A premortem before anything costly or hard to reverse: assume it already failed, work backward to the causes from every lens, rank them on evidence, and change the plan before going ahead. Dystopia assumes it succeeded at scale and traces who paid for that success; oppenheimer assumes a dual-use capability got out and was used, and sets the red lines while they can still be set. |
| [rulebook](plugins/rulebook) | `/rulebook:write <convention>`, `/rulebook:review <the ask>` | A numbered convention catalog in `.claude/rules/` for any stack: each rule one checkable entry with a stable ID, a CLI that checks the catalog and selects the entries a change falls under, and a forked, read-only review of a change against them and the ask. |
| [atlas](plugins/atlas) | `/atlas <question or fact>`, `/atlas:drain` | A personal brain: one folder of markdown notes in your home directory, the same in every project, consulted when a question is about something you recorded, with your standing preferences shown at session start. Typed notes with validity dates, a command that searches and maintains them with no index, a lint that finds what went stale, and it opens in Obsidian. |
| [data-max](plugins/data-max) | `/data-max:inspect`, `/data-max:clean`, `/data-max:check`, `/data-max:model` | Raw exports to warehouse, deterministically: profile a CSV/Excel/JSON/XML export and settle its decisions in a declarative spec, clean it into typed, reconciled tables (CSV/Parquet, DDL, MERGE), check each new export for drift before loading, and model staging, facts, dimensions and history on top in dbt, SQLMesh or SQL. |
| [paperwork](plugins/paperwork) | `/paperwork:setup`, `/paperwork:inbox`, `/paperwork:review`, `/paperwork:catalog`, `/paperwork:ask`, `/paperwork:match` | A company's or a person's paperwork in one folder that never deletes: drop anything into an inbox and it is read (XRechnung/ZUGFeRD XML, text layer, OCR, all inside Docker), checked against its own text and arithmetic, classified, assigned to one of your entities, renamed, filed, deduplicated and indexed into CSV. Your own document classes (contracts, payslips) decide fields, names and folders; rules and vendor templates make recurring documents deterministic, and what Claude decided alone waits for your confirmation. Every document also gets a markdown note (open the archive in Obsidian), and a bank statement or any list of payments can be matched against the archive to find the missing invoices. |
| [tone](plugins/tone) | `/tone:write <draft>` | Text written for other people, short and safe: issues, comments and changelog lines checked against a profile for their reader. A deterministic `tone check` catches length, filler, AI tells, secrets, personal data and technical internals in customer-visible text; the review judges the rest (guesses stated as facts, other customers, blame, du or Sie) and returns a revised text. German and English. Your own `.claude/rules/` files override its defaults. |

---

## Install

**For yourself** (every project on this machine):

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install research@atelier
/plugin install market@atelier
/plugin install premortem@atelier
/plugin install rulebook@atelier
/plugin install atlas@atelier
/plugin install data-max@atelier
/plugin install tone@atelier
# or, from a local clone:
/plugin marketplace add ./path/to/atelier
```

The same from a terminal: `claude plugin marketplace add insanetic/atelier && claude plugin install <plugin>@atelier`.

**For a project** (everyone who opens it is offered the plugins). Run this in the project root and commit `.claude/settings.json`:

```bash
claude plugin marketplace add insanetic/atelier --scope project
claude plugin install research@atelier --scope project
claude plugin install market@atelier --scope project
claude plugin install premortem@atelier --scope project
claude plugin install rulebook@atelier --scope project
claude plugin install data-max@atelier --scope project
claude plugin install tone@atelier --scope project
```

Update later with `/plugin marketplace update atelier`; enable or disable with `/plugin`.

---

## Repository layout

```text
.
├── .claude-plugin/
│   └── marketplace.json          # the atelier marketplace: one entry per plugin
└── plugins/
    ├── research/                 # self-contained plugin: manifest, skill, agents, hooks, CLI, tests
    ├── market/                   # competitor tracking: registry, discovery, landscape (depends on research)
    ├── premortem/                # skill-only plugin: premortem, dystopia and oppenheimer skills, evals
    ├── rulebook/                 # convention catalog: two skills, a reviewer agent, the rulebook CLI, an edit hook
    ├── atlas/                    # personal brain: two skills and the atlas CLI (Python, no dependencies)
    ├── data-max/                 # raw exports to warehouse: four skills and the data-max engine (Python, no dependencies)
    ├── paperwork/                # document archive: six skills, the paperwork engine (Python in Docker), a guard hook
    └── tone/                     # text for other people: one write skill, profiles and the tone check (Python, no dependencies)
```

Each plugin lives in `plugins/<name>/` with its own `.claude-plugin/plugin.json` and has one entry in `.claude-plugin/marketplace.json`.

---

## Contributing

Turn on the git hooks once per clone:

```bash
git config core.hooksPath .githooks
```

- **`commit-msg`** requires [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `type(scope): subject`, with the plugin as scope, as in `feat(atlas): restore a note from the archive`.
- **`pre-commit`** checks that staged manifests are valid JSON and runs a plugin's tests when it has a fast, dependency-free suite (atlas, tone).

Research results under `research/` are local and not committed.
