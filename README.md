# atelier

A [Claude Code](https://claude.com/claude-code) **plugin marketplace**: insanetic's agent tooling (plugins, skills and mods) shared across every project and machine, and installed the same way everywhere.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install research@atelier
```

---

## Plugins

| Plugin | Invoke | What it does |
|---|---|---|
| [research](plugins/research) | `/study <topic>` | Technical prior-art studies: how other products, open-source projects and standards solve a problem, verified quote by quote and compared with our own design. |

---

## Install

**For yourself** (every project on this machine):

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install research@atelier
# or, from a local clone:
/plugin marketplace add ./path/to/atelier
```

The same from a terminal: `claude plugin marketplace add insanetic/atelier && claude plugin install research@atelier`.

**For a project** (everyone who opens it is offered the plugin). Run this in the project root and commit `.claude/settings.json`:

```bash
claude plugin marketplace add insanetic/atelier --scope project
claude plugin install research@atelier --scope project
```

Update later with `/plugin marketplace update atelier`; enable or disable with `/plugin`.

---

## Repository layout

```text
.
├── .claude-plugin/
│   └── marketplace.json          # the atelier marketplace: one entry per plugin
└── plugins/
    └── research/                 # self-contained plugin: manifest, skill, agents, hooks, CLI, tests
```

Each plugin lives in `plugins/<name>/` with its own `.claude-plugin/plugin.json` and has one entry in `.claude-plugin/marketplace.json`.
