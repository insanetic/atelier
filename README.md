# atelier

A [Claude Code](https://claude.com/claude-code) **plugin marketplace**: insanetic's agent tooling (plugins, skills and mods) shared across every project and machine, and installed the same way everywhere.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install research@atelier
/plugin install market@atelier
/plugin install premortem@atelier
```

---

## Plugins

| Plugin | Invoke | What it does |
|---|---|---|
| [research](plugins/research) | `/study <task>` | Prior art before you build: how others solved a task, what to reuse, the pitfalls, and how ours compares, every claim verified quote by quote. |
| [market](plugins/market) | `/discover <category>` | Competitor tracking on top of research: the registry of every known competitor, discovery that keeps it complete, and the capability landscape. |
| [premortem](plugins/premortem) | `/premortem <plan>` | A premortem before anything costly or hard to reverse: assume it already failed, work backward to the causes from every vantage point, rank them, and change the plan before going ahead. |

---

## Install

**For yourself** (every project on this machine):

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install research@atelier
/plugin install market@atelier
/plugin install premortem@atelier
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
    └── premortem/                # skill-only plugin: manifest and the premortem skill
```

Each plugin lives in `plugins/<name>/` with its own `.claude-plugin/plugin.json` and has one entry in `.claude-plugin/marketplace.json`.
