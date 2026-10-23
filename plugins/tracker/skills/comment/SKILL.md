---
name: comment
description: >-
  Use when the user wants to add a comment, update, note, decision, question or blocker to an existing
  issue or task ("kommentier das im Ticket", "schreib ins Issue, dass…", "post an update on IND-12", "ask
  the reporter for…", "note that we decided…"). One purpose per comment in the Conventional Issues shape,
  at most 60 words, starting with Status, Decision, Question for, or Blocked (German: Stand, Entscheidung,
  Frage an, Blockiert). Never changes status or assignee: moving to review or to someone is handoff,
  finishing is close. Any tracker, or none: then the comment comes back to copy and paste.
argument-hint: "<issue ID> <what to say>"
---

# A comment

Read [CONVENTION.md](../../CONVENTION.md) (audience, facts, comments, links) and
[PROCEDURE.md](../../PROCEDURE.md), and follow the procedure around these steps.

```
$ARGUMENTS
```

1. **The issue.** Fetch it and its recent comments: the language and address to keep, and what was already
   said, so the comment adds only what is new.
2. **Purpose** (CI-030): progress, decision, question or blocker. The request mixes two: offer two comments.
   It is really a handoff or a close: say so and do that instead (handoff, close).
3. **Write it**: the lead, then only what that purpose says. A question names the person and exactly what is
   needed. At most 60 words, no greeting, no sign-off.
4. **Scope or acceptance criteria changed?** Update the description (CI-023) and keep the comment to what
   changed; both go into the same confirmation.
5. **Draft, check, confirm, write, report** as the procedure says. Nothing but the comment (and a
   description update) is changed.
