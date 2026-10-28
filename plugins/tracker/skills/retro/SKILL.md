---
name: retro
description: >-
  Use when one or more issues or tickets should be created for work that is already done, fixed or being
  tested: "mach mir nachträglich ein Ticket", "mach mir nachträglich die Tickets", "ist gefixt, leg ein
  Ticket dafür an", "leg Tickets für das an, was ich gemacht habe", "das ist schon fertig, mach ein
  Issue dafür", "create issues for what I did", "backfill the tickets for this branch", "track what we did
  today". Takes the work from this session, the branch, or the user's description; checks for existing
  issues; asks whether it becomes one issue or several, with a recommendation; writes each as if it had
  been reported or requested first; then hands over to review or closes as done. Also suggests open issues
  for what the session found but did not do (bugs, gaps, postponed work, TODOs), created only if picked. Any tracker, or none: then
  everything comes back to copy and paste.
argument-hint: "[what was done, if not this session]"
---

# Issues for work already done

Retro turns back time: each piece of work gets the issue it would have had if it had been filed first, then
the handoff or close it would have had afterwards. So it reuses those skills' steps, not its own version of
them. Read [CONVENTION.md](../../CONVENTION.md), [PROCEDURE.md](../../PROCEDURE.md), and the steps of
[issue](../issue/SKILL.md), [handoff](../handoff/SKILL.md) and [close](../close/SKILL.md).

```
$ARGUMENTS
```

Retro's own part is finding and splitting the work:

1. **What was done.** From the user's words, this conversation, and the work itself: changed files and
   commits on the current branch against its base (`git log` and `git diff <base>...HEAD`), when there is a
   repository. Each source may be missing; use what exists. Where they disagree or something needed is
   missing, ask; never fill a gap (CI-004). The user's picture of the work may be incomplete or partly
   wrong: say what the work shows when it differs.
2. **Outcomes, not files.** List the separate outcomes a reader would look for: a fixed behaviour, a new
   capability, an improvement, a piece of maintenance. Refactoring and tests that serve an outcome belong
   to it.
3. **Open findings.** Collect what the session found but did not do: a bug or gap someone noticed, work
   put off ("later", "out of scope", "separate issue"), a known limitation, a review point left unfixed,
   and `TODO`/`FIXME` lines the changes add (`git diff <base>...HEAD | grep '^+.*\(TODO\|FIXME\)'`). Only
   what was actually said or shown; leave out what is trivial, and what is already tracked gets a link
   instead (search first, as `issue` does).
4. **One or several.** When the outcomes could be one issue or several, ask once with both options as their
   titles and kinds, and recommend one with a one-line reason. Example:
   - One issue: "Rechnungsexport überarbeiten" (improvement)
   - Three issues (recommended: three outcomes someone would look for separately):
     "Zeilenumbrüche im Rechnungsexport erhalten" (bug), "Export nach Buchungskanal filtern" (feature),
     "Export-Wiederholungen konfigurierbar machen" (improvement)
   The user may also merge or split differently. In the same question, ask the state (step 6) and offer the
   open findings as a separate list of suggested open issues, each with title, kind, priority and a one-line
   reason; the user picks which to create, none are preselected unless the user asked for all.

Then, for each issue, exactly what the other skills do:

5. **The issue, as `issue` does it** (its steps 2 to 8), with the work as the facts and as if it were being
   filed before the work started:
   - already tracked? A match gets its handoff or close there instead of a new issue;
   - kind, outcome title, TL;DR and body: a bug states what someone saw and what should happen, a feature
     the need; nothing in the body says the work is done or how;
   - fields as `issue` sets them (CI-008): who asked, the original request, documents, related issues;
   - team and project by the procedure's ladder; the changed files and the repository are strong signals;
   - priority by CI-007 as it would have been when reported (a customer-visible bug is not `low` because it
     is fixed now);
   - assignee: the user, unless they say otherwise.
   The tracker keeps its own creator and creation date; never backdate, never name someone else as reporter.
6. **The state:** still in progress, being tested, or done.
   - in progress: the issue only, status in progress;
   - being tested: then as `handoff` does it (its steps 2 to 4): review status or receiver, the three-line
     comment;
   - done: then as `close` does it (its steps 2 to 6) with result `done` implied: ticked acceptance criteria
     the work shows are met (CI-051), the `Done:` comment, follow-ups as new linked issues.
7. **Picked findings, as `issue` does them** (its steps 2 to 8): new open issues in the backlog status,
   priority by CI-007, no assignee unless the user names one, each linked to the issue it came from (CI-060). The issue that found them says so
   only through the link, not in its closing comment.
8. **Confirm everything at once**, as the procedure says: every issue with its target, kind, priority and
   their reasons, its handoff or closing comment, and the picked open issues with their links. Then write issue by issue, in the order issue, fields,
   comment, status, and report.
