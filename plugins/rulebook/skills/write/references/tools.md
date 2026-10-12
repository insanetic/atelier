# Rule files per tool

The entry grammar is the same everywhere; only the file location and the scoping frontmatter differ.

| Tool              | Location                                         | Scope by path                                  | Always on                         |
| ----------------- | ------------------------------------------------ | ---------------------------------------------- | --------------------------------- |
| Claude Code       | `.claude/rules/**/*.md`                          | `paths:` list of globs; the only key read      | no frontmatter                    |
| Cursor            | `.cursor/rules/*.mdc` (a plain `.md` is ignored) | `globs: src/**/*.ts` and `alwaysApply: false`  | `alwaysApply: true`               |
| GitHub Copilot    | `.github/instructions/*.instructions.md`         | `applyTo: "src/**/*.ts"`                       | `.github/copilot-instructions.md` |
| Windsurf          | `.windsurf/rules/*.md`; `.devin/` wins if present | `trigger: glob` and `globs:`                   | `trigger: always_on`              |
| AGENTS.md readers | `AGENTS.md`, nearest file wins                   | a nested `AGENTS.md` in the directory          | root `AGENTS.md`                  |

- Claude Code reads AGENTS.md only when there is no CLAUDE.md; to serve both, CLAUDE.md imports it with `@AGENTS.md`.
- Claude Code loads a `paths:` file when a matching file is read, written or edited, not when it is only searched.
- Claude Code treats a rules file symlinked from outside the repository as an external import: it loads only after
  the user approves external imports for the project, and then only if it has no `paths:`. To share scoped core files
  across repositories, copy them in; keep the copies identical.
- Cursor, GitHub Copilot and Windsurf also read `AGENTS.md`, so it is the one file every tool sees.
- A Windsurf rules file is limited to 12,000 characters.
