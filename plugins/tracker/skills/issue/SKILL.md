---
name: issue
description: >-
  Use whenever something not yet done should be tracked as a new issue or task: the user asks to create,
  open, file, log or add an issue, ticket, task, card, bug report or feature request ("leg ein Ticket an",
  "leg dafür ein Ticket an", "mach daraus ein Issue", "track this", "add it to the backlog", "a customer
  asked for…"), or a bug or follow-up turns up while working. Not for work that is already done or being
  tested: that is retro. Any tracker (Linear, Jira, GitHub, Trello…), or none: then the issue comes back
  ready to copy and paste. Writes it in the Conventional Issues shape: one kind, an outcome title, a fixed
  short body, nothing guessed, nothing internal for customers to see.
argument-hint: "<what should be tracked>"
---

# A new issue

Read [CONVENTION.md](../../CONVENTION.md) (audience, facts, kinds, title, body, links) and
[PROCEDURE.md](../../PROCEDURE.md), and follow the procedure around these steps.

```
$ARGUMENTS
```

1. **Facts.** Gather them from the request and the conversation. Keep only what is stated or shown.
2. **Already tracked?** Search the target for an open issue about the same thing (title words, the
   symptom, the customer's wording). If one fits, propose a comment or a link there instead, and stop
   unless the user still wants a new one.
3. **Kind** (CI-006). Pick from what the work is, not from the words used: wrong behaviour is a `bug`, a
   missing capability a `feature`, a working thing made better an `improvement`, everything else a
   `task`. Two fit honestly: ask. Two pieces of work: offer two issues.
4. **Ask once** for what the kind's required sections need and the context lacks: for a `bug` what
   happens and what is expected; for a `feature` who needs it and when it is done; for a `task` what
   done looks like. Never ask for what you can read from the context. Priority, assignee, project and
   due date are set only when the user or a rule gives them; ask for priority only when the tracker
   requires it.
5. **Title** (CI-010 to CI-012): the outcome, so it reads as a changelog line. A bug's title is the correct
   behaviour.
6. **Body** (CI-020 to CI-022): only the kind's sections, in order; optional sections left out when empty.
7. **Draft, check, confirm, write, report** as the procedure says. A bug found while working on another
   issue is linked to it (CI-060).
