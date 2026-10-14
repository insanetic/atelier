---
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
tags: [premortem, software]
---

We're shipping this Friday and I'm pretty confident — it tested well on staging. Can you premortem it quickly?

Plan: move user emails from `users.email` into a new `contacts` table.

1. Friday 18:00 (our traffic peak is 17:00–21:00): deploy the new code, which reads and writes only `contacts`.
2. Same deploy runs the migration: `INSERT INTO contacts SELECT id, email FROM users; ALTER TABLE users DROP COLUMN email;`
3. Staging has 2,000 users; production has 41 million. The migration ran in 3 seconds on staging.
4. The password-reset service (owned by another team) still queries `users.email` directly; they said they'll "update soon".
5. If anything goes wrong we redeploy the previous release.
