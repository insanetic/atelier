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
```

---

## Plugins

| Plugin | Invoke | What it does |
|---|---|---|
| [research](plugins/research) | `/study <task>` | Prior art before you build: how others solved a task, what to reuse, the pitfalls, and how ours compares, every claim verified quote by quote. |
| [market](plugins/market) | `/discover <category>` | Competitor tracking on top of research: the registry of every known competitor, discovery that keeps it complete, and the capability landscape. |
| [premortem](plugins/premortem) | `/premortem <plan>` | A premortem before anything costly or hard to reverse: assume it already failed, work backward to the causes from every vantage point, rank them, and change the plan before going ahead. |
| [rulebook](plugins/rulebook) | `/rulebook:write <convention>`, `/rulebook:review <the ask>` | A numbered convention catalog in `.claude/rules/` for any stack: each rule one checkable entry with a stable ID, a CLI that checks the catalog and selects the entries a change falls under, and a forked, read-only review of a change against them and the ask. |
| [atlas](plugins/atlas) | `/atlas <question or fact>`, `/atlas:drain` | A personal brain: one folder of markdown notes in your home directory, the same in every project and consulted only when asked. Typed notes with validity dates, a command that searches and maintains them with no index, a lint that finds what went stale, and it opens in Obsidian. |

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
    ├── premortem/                # skill-only plugin: manifest and the premortem skill
    ├── rulebook/                 # convention catalog: two skills, a reviewer agent, the rulebook CLI, an edit hook
    └── atlas/                    # personal brain: two skills and the atlas CLI (Python, no dependencies)
```

Each plugin lives in `plugins/<name>/` with its own `.claude-plugin/plugin.json` and has one entry in `.claude-plugin/marketplace.json`.

---

## Contributing

Turn on the git hooks once per clone:

```bash
git config core.hooksPath .githooks
```

- **`commit-msg`** requires [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `type(scope): subject`, with the plugin as scope, as in `feat(atlas): restore a note from the archive`.
- **`pre-commit`** checks that staged manifests are valid JSON and runs a plugin's tests when it has a fast, dependency-free suite (atlas).

Research results under `research/` are local and not committed.
