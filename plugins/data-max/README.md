# data-max

A [Claude Code](https://claude.com/claude-code) **plugin** for **working with data end to end**. Three [Agent Skills](https://code.claude.com/docs/en/skills) cover the lifecycle of a messy data file:

- **data-review**: cleanse and pare down. Inspect a raw export and produce a tiered report on how to clean it for a warehouse.
- **data-transform**: execute that review. Turn the file into clean, warehouse-ready table(s) with a rerunnable script.
- **metric-creator**: build DSL-compatible metric (data cube) and dimension definitions on top of clean data.

Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install data-max@atelier
```

---

## The skills

| Skill | Invoke | Size¹ | What it does |
|---|---|---|---|
| **data-review** | `/data-max:data-review` | 3,226 | Reviews a data file (CSV/TSV/JSON/XML/Excel) for how cleanly it will land in a warehouse (BigQuery/Snowflake/ClickHouse/Postgres) and produces a tiered cleansing report, explaining every recommendation. *Reviews only; doesn't touch the data.* |
| **data-transform** | `/data-max:data-transform` | 1,653 | Consumes that review and produces the cleaned, warehouse-ready CSV(s), including splitting one file into several by grain, with a rerunnable script under `tools/`. Requires a review first. |
| **metric-creator** | `/data-max:metric-creator` | 4,937 | Authors declarative, DSL-compatible metric (data cube) and dimension definitions as versioned, copy-pasteable JSON, driven by a DDL schema you provide. Produces `<source>/<metric>.vX.Y.json` files and a `dimensions.md`. |

¹ Tokens the `SKILL.md` body adds **when the skill activates** (at rest only the one-line description is loaded); `references/` load on demand on top of this. Measured with [tiktoken](https://github.com/openai/tiktoken) (`o200k_base`) as a portable proxy; Claude's own tokenizer differs slightly.

**data-review → data-transform is a deliberate two-step pipeline:** the review produces the spec (the `<filename>-review.md` report) that the transform consumes. They are not interchangeable. **metric-creator** stands on its own: point it at a clean schema once the data is loaded. All three emit **artifacts** (reports, scripts, JSON/Markdown definitions) and deliberately refuse to write application code.

---

## Other agents

The Agent Skills format is an open spec, so the three folders under `skills/` work outside Claude Code too: they're plain `SKILL.md` directories with no Claude-Code-only syntax. Copy or symlink a folder into the agent's skills directory:

| Agent | Skills directory |
|-------|------------------|
| Codex CLI | `~/.codex/skills/` |
| Gemini CLI | `~/.gemini/skills/` |
| GitHub Copilot CLI | `~/.copilot/skills/` |
| Cursor | project `.cursor/rules/` (as rules) |

```bash
# example: make data-review available to Codex
ln -s "$(pwd)/skills/data-review" ~/.codex/skills/data-review
```

Tool names in the skill bodies (Read, Grep, Bash…) follow Claude Code conventions; other agents map them to their own equivalents.

---

## Layout

```text
.claude-plugin/plugin.json       # the data-max plugin manifest
skills/<skill>/SKILL.md          # the skill itself (auto-discovered, no manifest edit needed)
skills/<skill>/references/       # progressive-disclosure docs, loaded on demand
```

There is no build step, test runner or runtime: shipping means editing a `SKILL.md` or its references and keeping the manifest valid.

---

## Maintaining the skills

- **`name`** must equal the skill's directory name, or the skill won't resolve; it is also the `/data-max:<name>` invocation token. When renaming, change the directory, the `name:` **and every cross-reference** (data-review and data-transform reference each other by name in their bodies and descriptions) together. The `data-` prefix on the pair is deliberate: it keeps them in the data file / data model context and avoids a bare `review`, which could read as reviewing a metric.
- **`description`** is the only thing Claude sees when deciding whether to auto-invoke a skill. It must carry both what the skill does and the trigger phrases that should fire it; front-load concrete user utterances ("clean this export", "get this ready for the warehouse"). Treat it as a retrieval target, not a summary.
- Keep the `SKILL.md` body lean; depth lives in `references/*.md`.
- Frontmatter is the same in all three skills: `name`, `description`, then `user-invocable: true`, `license: MIT`, and a `metadata:` block carrying `author` and `version`. Don't revert to top-level `author`/`version`.
