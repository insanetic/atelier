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

1. **Facts.** Gather them from the request and the conversation. Keep only what is stated or shown. If the
   work is already done, fixed or being tested, this is a backfill: follow [retro](../retro/SKILL.md)
   instead, which reuses these steps and adds the handoff or close.
2. **Already tracked?** Search the target for an open issue about the same thing (title words, the
   symptom, the customer's wording). If one fits, propose a comment or a link there instead, and stop
   unless the user still wants a new one.
3. **Kind** (CI-006). Pick from what the work is, not from the words used: wrong behaviour is a `bug`, a
   missing capability a `feature`, a working thing made better an `improvement`, everything else a
   `task`. Two fit honestly: ask. Two pieces of work: offer two issues.
4. **Ask once** for what the kind's required sections and CI-008 need and the context lacks: for a `bug`
   what happens, who is affected and what is expected; for a `feature` who needs it, for what, and when it
   is done; for an `improvement` what today costs and when it is better; for a `task` why and what done
   looks like; for every kind, who to ask and what the work needs, when that is not plain. Never ask for
   what you can read from the context. Assignee and due date are set only when the user or a rule gives
   them.
5. **Title** (CI-010 to CI-012): the outcome, so it reads as a changelog line. A bug's title is the correct
   behaviour.
6. **Body** (CI-020 to CI-024): the `TL;DR:` line (in every language), then only the kind's sections, in
   order, with the headings spelled exactly as the convention's table has them in the issue's language
   (CI-070); optional sections left out when empty.
7. **Fields** (CI-008): who asked and who answers questions, documents and files, the original request,
   related or blocking issues, a given date: each into its field as the procedure's step 5 says, not
   into the text. Read the issue as someone who was not in the conversation: whatever they would still
   have to ask is asked now.
8. **Target and priority:** the team and project by the procedure's ladder (its step 2), the priority by
   CI-007 (its step 6), each shown with its reason in the confirmation.
9. **Draft, check, confirm, write, report** as the procedure says. A bug found while working on another
   issue is linked to it (CI-060).
