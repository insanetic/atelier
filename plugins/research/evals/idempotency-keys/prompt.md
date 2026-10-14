---
max_turns: 200
timeout_seconds: 3600
runs: 1
allowed_tools: [Read, Glob, Grep, Write, Edit, Bash, WebSearch, WebFetch, Agent, Skill, mcp__research__add_finding, mcp__research__verify_finding, mcp__research__query, mcp__research__matrix, mcp__research__clone, mcp__research__set_score]
tags: [research, brief]
---

Our payments API has idempotency keys (see `src/idempotency.ts`). How do others do idempotency keys, and is ours any good? I want to know what to change before we put more clients on it. Don't ask me anything. Put the whole result in your final reply, with sources, not just a pointer to a file.
