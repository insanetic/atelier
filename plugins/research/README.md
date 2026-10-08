# research

Evidence-anchored technical prior-art studies for Claude Code. Before building, ask how other products, open-source projects and standards solve the problem; record every answer with a verbatim quote, verify it independently, put our own design in the same matrix, and decide.

## When

- Before building something others have solved (tax, plan changes, proration, idempotency, audit logs).
- To judge a design we already have, or to choose between approaches.
- For frontend patterns (list filtering, command palette, editors).
- Quick mode (about 10 minutes, unverified) to see what is out there; full mode for decisions that last (data models, API shapes).

## How

`/study <topic> [--quick]` starts or reopens a study and opens the matrix pane; asking "how do others do X?" starts the `research:study` skill too. The skill walks the steps: frame, map (you approve the comparison questions and references), collect (one researcher per reference, in parallel), verify, synthesize, evaluate (you confirm scores), ideate, decide (`research decide`).

Studies live in the product repo under `research/` (or where `.research.yaml` `dir:` points, e.g. `dir: ../subneo/research` in a sibling repo) and are committed with the code.

- Agents: `research:scout`, `research:researcher`, `research:verifier`, `research:analyst`, `research:critic`
- Tools: `mcp__research__add_finding`, `verify_finding`, `set_score`, `clone`, `query`, `matrix`
- Command (on PATH in sessions): `research init | check | stale | query | matrix | decide | reverify [--due] | clone | repin`

Researchers read cloned repositories under `~/.cache/research`; add it to `permissions.additionalDirectories` in `~/.claude/settings.json` to avoid prompts.

## Develop

```
npm install
npm test && npm run typecheck
npm run build                               # dist/ is committed: rebuild after changing core/ or cli/
claude plugin validate . && claude plugin test .
claude --plugin-dir .                       # try it live
```
