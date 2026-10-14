---
type: llm
weight: 3
---

The response identifies, as specific causes tied to this plan (not generic risks), ALL THREE of:
1. The rollback doesn't work: the previous release needs `users.email`, which the migration dropped, so redeploying it cannot restore service (the drop is irreversible without a backup/restore).
2. The migration on 41M rows during peak traffic: long-running INSERT/ALTER, locks or timeouts, unlike the 3 seconds on 2,000 staging rows.
3. The password-reset service owned by another team breaks when `users.email` disappears.

Pass only if all three appear. Partial credit is not allowed.
