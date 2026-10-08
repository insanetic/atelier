# premortem

A [Claude Code](https://claude.com/claude-code) **plugin** for **premortems**. Before you ship, merge, launch or lock in a plan, it assumes the thing has already failed and works backward to why, while there is still time to change the plan. Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install premortem@atelier
```

Then run `/premortem the billing migration`, or just ask "what could go wrong with this?".

---

## When to use it

- Before anything costly or hard to reverse: a release, a merge, a migration, a launch, an architecture or refactor plan.
- When confidence is high and nobody has pushed back: "tested well", "should be fine", "just a sanity check".
- For code and systems, web and UX, and any other plan (marketing, design, ops).
- Not for a postmortem of an incident that really happened, and not a replacement for code or security review. It runs next to them.

The skill also fires on its own when you say "premortem", "what could go wrong", "poke holes", "red team this", "is this actually ready" and the like.

---

## How a pass runs

1. **Name it:** what is shipping, and what success had to look like.
2. **Jump to the failure:** a concrete moment ("three weeks after launch") and the failure stated as fact.
3. **Work backward:** 8 to 12 causes, each from a separate vantage point (load, the rollback, the confused first-timer, the 3am on-call, the assumption nobody checked, …), with no filtering for likelihood.
4. **Make each cause real:** the mechanism, the false assumption behind it, the earliest signal.
5. **Rank:** likelihood and impact, and only now.
6. **Change the plan:** for each top cause, the guardrail, test, flag or redesign to add before going ahead.

Causes are written in the past tense with no hedging. Asking "what went wrong?" instead of "what could go wrong?" surfaces more real causes, and a "might" or "probably" lets the optimism back in. The result is still reported plainly as risks and fixes, never as incidents that happened.

Depth follows the stakes. A small, reversible change gets a 30-second pass; a one-way decision gets the full one. For the highest stakes it sends parallel agents, one per vantage point, so no cause anchors the others (through [superpowers](https://github.com/obra/superpowers)' `dispatching-parallel-agents` skill when it is installed).

---

## Install

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install premortem@atelier
# or, from a local clone:
/plugin marketplace add ./path/to/atelier
```

For a whole project, run `claude plugin marketplace add insanetic/atelier --scope project` and `claude plugin install premortem@atelier --scope project` in its root, then commit `.claude/settings.json`.

Update later with `/plugin marketplace update atelier`.

**Other agents:** the skill is a plain `SKILL.md` with no tools, hooks or agents, so any agent that reads Agent Skills can use `skills/premortem/` as is.

---

## What's inside

| Component | Name | On invoke¹ | What it does |
|---|---|---|---|
| Skill | `/premortem` (`/premortem:premortem`) | ~1.6k | The method: holds the failure frame, walks the vantage points, ranks, changes the plan |

¹ Tokens from `claude plugin details premortem@atelier`. The always-on cost is about 240 tokens for the skill description.

---

## Repository layout

```text
plugins/premortem/
├── .claude-plugin/plugin.json    # plugin manifest
└── skills/premortem/SKILL.md     # the method
```

---

## Develop

```bash
claude plugin validate --strict .
claude --plugin-dir .                 # try it live
```
