---
name: discover
description: Find competitors and comparable products the research registry is missing, so no study forgets one (weak-SEO vendors included). Use when the user runs /discover, asks "who else does X", "are we missing competitors", "find alternatives to X", or before a study in a category that has not been swept recently.
---

# Discover

The registry (`research/registry/`) is the list of every known competitor, benchmark product and standard. Discovery proposes additions; a human approves them.

| File | Holds |
|---|---|
| `taxonomy.yaml` | Categories (kebab-case) and capabilities (snake_case), each with a definition |
| `references.yaml` | Facts per reference (kind, categories, source model, status, owner, domains, aliases) and our dated `stance` (tier, overlap per category). No stance = not a competitor |
| `candidates.yaml` | Discovered, waiting for approval (written only by `propose_candidate`) |
| `rejected.yaml` | Turned down, with the reason, so they are never proposed again |

## Run

`/discover <category> [<category> …]`. The categories must exist in `taxonomy.yaml`; propose a new one to the user (id + one-line definition) if needed.

1. Run `research refs --category <c>` for each category: that is what is known.
2. Dispatch `research:discoverer` agents in ONE message, one per channel and category: `alternatives`, `github`, `launches`, `marketplaces`. Give each the category id, its definition and the channel.
3. Snowball: when round 1 proposed new candidates, run one more `alternatives` round seeded with their names. Repeat until a round proposes nothing new (at most 3 rounds).
4. Report:
   - every candidate (`research candidates`): id, name, domain, the channels that found it;
   - per channel: proposed, merged, rediscovered known references;
   - whether discovery saturated (the last round added nothing).
5. The user decides each candidate: `research approve <id>` or `research reject <id> --reason "…"`. For approved ones, ask for the facts the agents could not settle (kind, source model, owner) and our stance (tier 1, 2 or watch; overlap direct or adjacent per category), and edit `references.yaml`. Then run `research check`.
6. Run `research landscape` so the landscape study gains the new references.

Never move a candidate into the registry without the user's approval.
