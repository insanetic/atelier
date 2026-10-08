# atelier

insanetic's agent tooling for Claude Code: one marketplace, shared by every project.

| Plugin | What it does |
|---|---|
| [research](plugins/research) | Evidence-anchored prior-art studies: how others solve a problem, verified quote by quote, compared with our own design |

## Use in a project

Commit this to the project's `.claude/settings.json`; a fresh clone then offers the plugins:

```json
{
  "extraKnownMarketplaces": { "atelier": { "source": { "source": "github", "repo": "insanetic/atelier" } } },
  "enabledPlugins": { "research@atelier": true }
}
```

Or install by hand: `/plugin install research@atelier` after `/plugin marketplace add insanetic/atelier`.

## Layout

Each plugin is self-contained under `plugins/<name>/` (its own `package.json`, tests and `.claude-plugin/plugin.json`) and is listed in `.claude-plugin/marketplace.json`.
