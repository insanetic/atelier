# research

A [Claude Code](https://claude.com/claude-code) plugin for **prior art before you build**. Ask how others solved a task, and you get a brief:
- who solved it, and how;
- what to reuse;
- the pitfalls they hit;
- how ours compares.

Every claim is checked against a quote from its source. Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install research@atelier
```

Then run `/study tax`, or just ask "how do others do tax?".

---

## When to use it

- Before building something others may already have solved: tax, plan changes, proration, idempotency keys, audit logs, a command palette.
- To check whether our existing design holds up, and what to change in it.
- Not for small choices, or for things a standard already settles.

## Three depths

| Command | Takes | You get |
|---|---|---|
| `/study <task> --quick` | ~5 min | Has anyone done this? References and first answers, with sources, unchecked |
| `/study <task>` | ~20–30 min, no questions asked | **The brief**: every claim cites a verified finding |
| `/study <task> --deep`, or "go deeper" | your time | Scores against written criteria, three or more designs attacked by a critic, and a recorded decision |

A brief has eight sections:
1. Answer
2. Who solved it
3. Approaches
4. What to reuse
5. Pitfalls
6. Ours against theirs (Greenfield when nothing of ours exists yet)
7. Recommendation
8. Open questions

Reply "add Chargebee", "drop Y" or "go deeper", and it extends the same study.

To benchmark something we have against named references: `/study api-model --against stripe,lago`.

---

## How a brief is made

1. **Frame:** the task becomes a question, and the plugin looks for our implementation in the repo.
2. **Map:** a scout picks 4–8 references for being best at the problem (products, open-source code, libraries, standards, write-ups), plus 4–8 points to compare them on.
3. **Collect:** one researcher per reference, in parallel. Each records:
   - answers;
   - pitfalls from issue trackers and postmortems;
   - things worth reusing, with their licence.

   Ours is read from our own code.
4. **Verify:** each quote is re-checked against code at a pinned commit or against the fetched page, and an independent verifier judges whether it supports the claim.
5. **Write and finish:** `research finish` refuses a brief with a missing section, or with a citation that is unverified, disputed or out of date.

---

## Files

Plain files in the repo you work in, committed with the code. There is nothing to set up: the first `/study` creates `research/`.

```text
research/
├── references.yaml            # facts about everything studied: kind, docs, repositories pinned to a commit, licence
└── studies/<topic>/
    ├── study.yaml             # question, mode, references and their roles, comparison points
    ├── findings.yaml          # evidence, written only through the tools
    ├── assessment.yaml        # scores (deep)
    └── study.md               # the brief
```

A sibling repo of the same product can share one research directory through `.research.yaml` (`dir: ../product/research`).

Findings age:
- prices and limits after 90 days;
- features after 180 days;
- architecture after 365 days.

`research reverify --due` re-checks old findings without the model, and `research stale` lists what needs work.

---

## Competitor tracking

Who exists in your market, tiers, and discovery live in the separate [market](../market) plugin. Studies never need it.

---

## Install

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install research@atelier
# or, from a local clone:
/plugin marketplace add ./path/to/atelier
```

For a whole project, run these in its root, then commit `.claude/settings.json`:

```bash
claude plugin marketplace add insanetic/atelier --scope project
claude plugin install research@atelier --scope project
```

Researchers read cloned reference repositories under `~/.cache/research`. To skip the permission prompts, add that directory to `permissions.additionalDirectories` in `~/.claude/settings.json`.

Update later with `/plugin marketplace update atelier`.

**Other agents:** the `study` skill depends on this plugin's tools and agents, so it only works inside Claude Code.

---

## What's inside

| Component | Name | On invoke¹ | What it does |
|---|---|---|---|
| Skill | `/study` (`/research:study`) | ~2,570 | The method: quick, brief and deep |
| Agent | `research:scout` | ~590 | Picks the references best at the task, and the comparison points |
| Agent | `research:researcher` | ~660 | Researches one reference: answers, pitfalls, things to reuse |
| Agent | `research:verifier` | ~390 | Re-checks quotes and judges support, independently |
| Agent | `research:analyst` | ~220 | Proposes scores against the written criteria (deep) |
| Agent | `research:critic` | ~190 | Attacks candidate designs with the recorded pitfalls (deep) |
| Tools | `add_finding`, `verify_finding`, `set_score`, `clone`, `query`, `matrix` | n/a | Validated writes, quote and licence checks, search, the comparison pane |
| Command | `research` (on PATH in sessions) | n/a | `init`, `check`, `stale`, `query`, `matrix`, `finish`, `drop`, `decide`, `reverify`, `clone`, `repin` |

¹ Tokens, estimated as file size / 4.

`findings.yaml` and `assessment.yaml` are written only through the tools; a guard blocks hand edits.

---

## Repository layout

```text
plugins/research/
├── .claude-plugin/plugin.json    # plugin manifest
├── skills/study/SKILL.md         # the method
├── agents/                       # scout, researcher, verifier, analyst, critic
├── hooks/                        # the mod: tools, guard, pane, status line
├── core/                         # shared logic without I/O: records, validation, quote and licence checks
├── cli/, bin/research            # the research command
├── dist/                         # committed bundles: core for the mod, cli for Node
└── tests/                        # node:test suites (*.spec.ts) and mod tests (tests/mod)
```

---

## Develop

```bash
npm install
npm test && npm run typecheck
npm run build                         # dist/ is committed: rebuild after changing core/ or cli/
claude plugin validate . && claude plugin test .
claude --plugin-dir .                 # try it live
```
