# research-kit

Evidence-anchored technical prior-art studies for Claude Code. Before building, ask how other products, open-source projects and standards solve the problem. Record every answer with a verbatim quote, verify it independently, put your own design in the same matrix, and decide.

## Install (per user)

```
/plugin install research-kit --marketplace insanetic/research-kit
```

Let researchers read the clone cache without prompts by adding this to `~/.claude/settings.json`:

```json
{ "permissions": { "additionalDirectories": ["~/.cache/research"] } }
```

## Enable in a project

Commit this to `.claude/settings.json`, so a fresh clone offers the plugin:

```json
{
  "extraKnownMarketplaces": { "research-kit": { "source": { "source": "github", "repo": "insanetic/research-kit" } } },
  "enabledPlugins": { "research-kit@research-kit": true }
}
```

Knowledge lives per product in `research/` at the product's main repo. A sibling repo of the same product points at it with `.research.yaml`:

```yaml
dir: ../subneo/research
```

It also adds that directory to `permissions.additionalDirectories`.

## Use

- `/study <topic> [--quick]` starts or reopens a study and opens the matrix pane; `/study` alone reopens the pane.
- The `research-kit:study` skill drives the method.
- Agents: `research-kit:scout`, `researcher`, `verifier`, `analyst`, `critic`.
- Tools: `mcp__research-kit__add_finding`, `verify_finding`, `set_score`, `clone`, `query`, `matrix`.

## CLI (git hooks, CI, terminal)

```
npx --yes --package=github:insanetic/research-kit#v0.1.0 research check
```

Commands: `init`, `check`, `stale`, `query`, `matrix`, `decide`, `reverify [--due] [--report FILE]`, `clone`, `repin`.

## Develop

```
npm install
npm test && npm run typecheck
npm run build        # dist/ is committed; CI fails when it is stale
npx --yes @anthropic-ai/claude-code plugin validate .
npx --yes @anthropic-ai/claude-code plugin test .
claude --plugin-dir .   # try it live
```
