---
name: handoff
description: >-
  Use when an issue or task moves to review, testing or another person without being finished: "move it to
  review", "gib das an Swen", "ready for QA", "assign to the product owner", "zur Abnahme". Sets the status
  and/or assignee and always leaves one comment so the next person knows exactly where things stand: what
  is done, what to check, what is open (Ready for review / To check / Open; German: Bereit zur Prüfung /
  Zu prüfen / Offen). Not for closing: that is close. Any tracker, or none: then it comes back to copy and
  paste.
argument-hint: "<issue ID> [to whom or which status]"
---

# A handoff

Read [CONVENTION.md](../../CONVENTION.md) (audience, facts, handoff) and [PROCEDURE.md](../../PROCEDURE.md),
and follow the procedure around these steps.

```
$ARGUMENTS
```

1. **The issue.** Fetch it, its acceptance criteria and recent comments.
2. **Where it goes.** The receiver and/or the status from the request or a rule. Look up whether the
   workspace has a review status; without one, the handoff is the assignee alone. Not clear: ask, with the
   likely receiver first.
3. **The comment** (CI-040), at most 60 words:
   - `Ready for review:` (or `Handed to <person>:`): what is done, as an outcome;
   - `To check:` what to look at, and where or how, concretely enough to start without asking;
   - `Open:` what is unclear or not done, or `none`.
   Only facts from the work and the conversation; what is not known goes under `Open:`.
4. **Tick** acceptance criteria that are met, and only those (CI-051).
5. **Mention** only the receiver or reviewer, found in the workspace (CI-031); nobody else.
6. **Draft, check, confirm, write, report** as the procedure says. Never sets a completed or canceled
   status.
