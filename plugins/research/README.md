# research

A [Claude Code](https://claude.com/claude-code) **plugin** for **technical prior-art studies**. Before you build something, it finds out how other products, open-source projects and standards solve it, verifies every claim against its source, puts our own design in the same comparison, and helps you decide. Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install research@atelier
```

Then run `/study tax`, or just ask "how do others do tax?".

---

## When to use it

- Before building something others have already solved: tax, plan changes, proration, idempotency, audit logs.
- To judge a design we already have, or to choose between approaches.
- For frontend patterns: list filtering, a command palette, an editor.
- Not for small choices, things a standard already settles, or market and sales questions.

**Quick mode** (`/study <topic> --quick`, about 10 minutes, unverified) shows what is out there. **Full mode** (`/study <topic>`) is for decisions that last, like a data model or an API shape.

---

## The list of everyone we compare against

`research/registry/` keeps every known competitor, benchmark product and standard, so no study depends on someone remembering a vendor or on a vendor ranking well in search.

- `taxonomy.yaml`: categories (`usage-billing`, `entitlements`, …) and capabilities (`public_api`, …), each with a definition.
- `references.yaml`: facts per product (kind, categories, open source or not, status, owner, domains, aliases) and our dated stance (tier 1, 2 or watch; overlap direct or adjacent per category). Being a competitor, being open source and being a benchmark are separate: the first is our stance, the second a fact, the third a role inside one study.
- `/discover <category>` sends one discoverer per channel (alternatives pages, GitHub topics and awesome lists, launches such as Show HN, marketplaces) and repeats until a round finds nothing new. Finds land in `candidates.yaml`; you approve them with `research approve <id>` or turn them down with `research reject <id> --reason …` (kept in `rejected.yaml`, so they are never proposed again).
- Every study names its categories; `research check` warns when a registered competitor overlapping them is neither included nor excluded with a reason.

**Benchmarks** are studies of one thing we have: `/study api-model --against stripe,lago`, or against everyone with a capability (`research refs --capability public_api`, read from the standing landscape study that `research landscape` keeps in step with the registry).

---

## How a study runs

1. **Frame:** the question and the decision it feeds.
2. **Map:** a scout proposes the comparison questions and the references. **You approve them.**
3. **Collect:** one researcher per reference, in parallel. Every finding carries a verbatim quote from code at a pinned commit, an API spec, the docs or an issue tracker.
4. **Verify:** an independent verifier re-checks every quote.
5. **Synthesize:** the comparison matrix, the main approaches, their trade-offs and pain.
6. **Evaluate:** our design is scored next to the others. **You confirm the scores.**
7. **Ideate:** at least three candidate designs, each attacked by a critic.
8. **Decide:** **you decide**, and `research decide` records it with a snapshot of the evidence.

Studies are plain files in the product repo under `research/studies/<topic>/`, committed with the code. A sibling repo of the same product (a frontend, say) points at them with `.research.yaml`:

```yaml
dir: ../subneo/research
```

---

## Install

```bash
/plugin marketplace add insanetic/atelier     # from GitHub
/plugin install research@atelier
# or, from a local clone:
/plugin marketplace add ./path/to/atelier
```

For a whole project, run `claude plugin marketplace add insanetic/atelier --scope project` and `claude plugin install research@atelier --scope project` in its root, then commit `.claude/settings.json`.

Researchers read cloned reference repositories under `~/.cache/research`. To skip the permission prompts, add that directory to `permissions.additionalDirectories` in `~/.claude/settings.json`.

Update later with `/plugin marketplace update atelier`.

**Other agents:** the `study` skill depends on this plugin's tools and agents, so it only works inside Claude Code.

---

## What's inside

| Component | Name | On invoke¹ | What it does |
|---|---|---|---|
| Skill | `/study` (`/research:study`) | ~2.4k | The method: drives the eight steps |
| Skill | `/discover` (`/research:discover`) | small | Finds missing competitors through several channels |
| Agent | `research:scout` | ~530 | Proposes comparison questions, criteria and references |
| Agent | `research:researcher` | ~510 | Researches one reference and records its findings |
| Agent | `research:verifier` | ~400 | Re-checks quotes and judges support, independently |
| Agent | `research:analyst` | ~200 | Proposes scores against the written criteria |
| Agent | `research:critic` | ~170 | Attacks candidate designs with the recorded pain |
| Agent | `research:discoverer` | small | Searches one discovery channel and proposes candidates with evidence |
| Tools | `add_finding`, `verify_finding`, `set_score`, `clone`, `query`, `matrix`, `refs`, `propose_candidate` | n/a | Validated writes, quote checks, search, the registry, the comparison pane |
| Command | `research` (on PATH in sessions) | n/a | `init`, `check`, `stale`, `query`, `matrix`, `decide`, `reverify`, `clone`, `repin`, `refs`, `candidates`, `approve`, `reject`, `landscape` |

¹ Tokens from `claude plugin details research@atelier`. The always-on cost is about 415 tokens for the skill and agent descriptions, plus the six tool schemas (about 1.2k tokens, estimated from their size).

`findings.yaml` and `assessment.yaml` are written only through the tools; a guard blocks hand edits.

---

## Repository layout

```text
plugins/research/
├── .claude-plugin/plugin.json    # plugin manifest
├── skills/study/SKILL.md         # the method
├── agents/                       # scout, researcher, verifier, analyst, critic
├── hooks/                        # the mod: tools, guard, pane, status line
├── core/                         # shared logic without I/O: records, validation, quote checks
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
