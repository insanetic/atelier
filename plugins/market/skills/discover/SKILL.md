---
name: discover
description: Find competitors and comparable products the market registry is missing, so no one is forgotten (weak-SEO vendors included). Use when the user runs /discover, asks "who else does X", "are we missing competitors", "find alternatives to X", or before reviewing a category that has not been swept recently.
---

# Discover

The market registry lists every known competitor, benchmark product and standard in this product's market. Discovery proposes additions; a human approves them.

| File | Holds |
|---|---|
| `research/references.yaml` | Facts per reference (name, kind, docs, repositories, licence), shared with the research plugin's studies |
| `research/market/registry.yaml` | Per reference id:<br>- market facts: vendor, owner, successor, aliases, domains, categories, source model, delivery, status;<br>- our dated `stance`: tier, and overlap per category.<br>No stance means not a competitor |
| `research/market/taxonomy.yaml` | `scope` (include and exclude rules), categories (kebab-case) and capabilities (snake_case), each with a definition |
| `research/market/candidates.yaml` | Discovered products waiting for approval (written only by `propose_candidate`) |
| `research/market/rejected.yaml` | Products turned down, with the reason, so they are never proposed again |

## Run

`/discover <category> [<category> …]`. The categories must exist in `taxonomy.yaml`. If one is missing, propose it to the user: an id and a one-line definition.

1. **Load what is known.** Read `research/market/taxonomy.yaml`, and run `market refs --category <c>` for each category: that is the scope and what is already known.
   - If `scope` is missing, write it with the user first:
     - a short list of include rules: who the product is for, and what its core is;
     - a short list of exclude rules: the neighbouring markets that look alike.

     Without a scope, discovery floods the queue.
2. **Dispatch.** Send `market:discoverer` agents in ONE message, one per channel and category. The channels are `alternatives`, `github`, `launches` and `marketplaces`. Give each agent:
   - the category id and its definition;
   - its channel;
   - the scope rules, verbatim.
3. **Snowball.** When round 1 proposed new candidates, run one more `alternatives` round seeded with their names. Repeat until a round proposes nothing new, for at most 3 rounds.
4. **Report:**
   - every candidate (`market candidates`): id, name, domain, and the channels that found it;
   - per channel: what it proposed, what it merged, and which known references it rediscovered;
   - whether discovery saturated, meaning the last round added nothing.
5. **Decide.** The user decides on each candidate: `market approve <id>` or `market reject <id> --reason "…"`.
   - For each approved one, ask for the facts the agents could not settle:
     - the kind, in `research/references.yaml`;
     - the source model and owner, in `research/market/registry.yaml`.
   - Ask for our stance too, also in `research/market/registry.yaml`: tier 1, 2 or watch, and overlap direct or adjacent per category.
   - Then run `market check`.
6. **Update the landscape.** Run `market landscape`, so the landscape study gains the new references.

Never move a candidate into the registry without the user's approval.

**Benchmarks against everyone with a capability:** `market refs --capability public_api` lists the references whose landscape finding is verified. Pass their ids to `/study <topic> --against <ids>` (research plugin).

Headless runs (`claude -p`) stop background agents after 10 minutes. Set `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` so every round finishes.
