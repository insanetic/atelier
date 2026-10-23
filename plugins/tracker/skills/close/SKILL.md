---
name: close
description: >-
  Use when an issue or task is finished or should be closed for any reason: done, rejected, won't do,
  duplicate, not reproducible, works as intended, no longer relevant ("schließ das Ticket", "mach IND-12
  zu", "close it as done", "reject this", "das ist ein Duplikat", "erledigt"). Picks the result (asks with a
  recommendation when unclear), ticks met acceptance criteria, posts one short closing comment that starts
  with the result (Done / Not doing / Duplicate of …; German: Erledigt / Nicht umgesetzt / Duplikat von …),
  and sets the matching status and label. Several issues in one go. Any tracker, or none: then it comes back
  to copy and paste.
argument-hint: "<issue ID(s)> [result] [reason]"
---

# Closing

Read [CONVENTION.md](../../CONVENTION.md) (audience, facts, close, links, mapping) and
[PROCEDURE.md](../../PROCEDURE.md), and follow the procedure around these steps.

```
$ARGUMENTS
```

1. **The issues.** Fetch each one, its `Done when` list and recent comments.
2. **Result** (CI-050): `done`, `wont-do`, `works-as-intended`, `duplicate`, `cant-reproduce` or
   `obsolete`. From the request or the flow (after retro the work implies `done`). Not clear: ask, with the
   likely result first and why. For `duplicate`, find the issue it duplicates and confirm it.
3. **The closing comment**, at most two sentences, starting with the result's lead:
   - `done`: what changed for the reader, as an outcome; follow-ups by ID;
   - `wont-do`, `obsolete`: the reason;
   - `works-as-intended`: why, and what to do instead;
   - `cant-reproduce`: what was tried, and what would reopen it;
   - `duplicate`: the other issue.
   No technical detail for an external reader; links to pull requests go into the link field (CI-003).
4. **Checklist** (CI-051): tick met `Done when` items; an item dropped or not met is said in the comment.
5. **Follow-ups** (CI-060): work that remains becomes a new linked issue (as **issue** does), confirmed
   together with the close.
6. **Status, resolution or close reason, and label** from the convention's mapping, found live. Several
   issues: one confirmation for all.
7. **Draft, check, confirm, write, report** as the procedure says. A direct "close it" is the request, not
   the yes: show the result, the comment and the status first, even when the result was named.
