# market

A [Claude Code](https://claude.com/claude-code) plugin for **competitor tracking**. It keeps:
- a registry of every known competitor, benchmark product and standard in your market;
- discovery that keeps the registry complete;
- a landscape of who has which capability.

It works on top of [research](../research), which it depends on. Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install research@atelier
/plugin install market@atelier
```

Then run `/discover usage-billing`.

---

## What it keeps

All of it lives in `research/market/`, beside research's studies:

- **`taxonomy.yaml`:** categories (`usage-billing`, `entitlements`, …) and capabilities (`public_api`, …), each with a definition, plus scope rules that say what belongs in the registry at all.
- **`registry.yaml`:** per reference, the market facts (domains, categories, source model, owner, status) and our dated stance (tier 1, 2 or watch; overlap direct or adjacent per category). The reference's own facts stay in research's `references.yaml`.
- **`candidates.yaml` and `rejected.yaml`:** the discovery queue, and what was turned down and why.

---

## Discovery

`/discover <category>` sends one discoverer per channel:
- alternatives pages;
- GitHub topics and awesome lists;
- launches such as Show HN;
- marketplaces.

It repeats until a round finds nothing new. Approve finds with `market approve <id>`, and turn them down with `market reject <id> --reason …`.

`market landscape` keeps a standing research study with one yes/no question per capability. `market refs --capability public_api` then lists everyone verified to have one, which is useful for `/study api-model --against …`.

`research` never reads `research/market/`. Uninstalling market leaves every study intact.

---

## What's inside

| Component | Name | What it does |
|---|---|---|
| Skill | `/discover` (`/market:discover`) | Finds missing competitors through several channels |
| Agent | `market:discoverer` | Searches one channel and proposes candidates with evidence |
| Tools | `refs`, `propose_candidate` | The registry, and the validated discovery queue |
| Command | `market` (on PATH in sessions) | `refs`, `candidates`, `approve`, `reject`, `landscape`, `check` |

---

## Develop

```bash
npm install                            # also run npm install in ../research: market's core imports research's
npm test && npm run typecheck
npm run build                          # dist/ is committed
claude plugin validate . && claude plugin test .
```
