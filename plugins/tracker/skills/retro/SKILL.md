---
name: retro
description: >-
  Use when issues or tickets should be created for work that is already done or being tested: "mach mir
  nachträglich die Tickets", "leg Tickets für das an, was ich gemacht habe", "das ist schon fertig, mach ein
  Issue dafür", "create issues for what I did", "backfill the tickets for this branch", "track what we did
  today". Takes the work from this session, the branch, or the user's description; checks for existing
  issues; asks whether it becomes one issue or several, with a recommendation; writes each as if it had
  been reported or requested first; then hands over to review or closes as done. Any tracker, or none: then
  everything comes back to copy and paste.
argument-hint: "[what was done, if not this session]"
---

# Issues for work already done

Read [CONVENTION.md](../../CONVENTION.md) (audience, facts, kinds, title, body, close) and
[PROCEDURE.md](../../PROCEDURE.md), and follow the procedure around these steps.

```
$ARGUMENTS
```

1. **What was done.** From the user's words, this conversation, and the work itself: changed files and
   commits on the current branch against its base (`git log` and `git diff <base>...HEAD`), when there is a
   repository. Each source may be missing; use what exists. Where they disagree or something needed is
   missing, ask; never fill a gap (CI-004). The user's picture of the work may be incomplete or partly
   wrong: say what the work shows when it differs.
2. **Outcomes, not files.** List the separate outcomes a reader would look for: a fixed behaviour, a new
   capability, an improvement, a piece of maintenance. Refactoring and tests that serve an outcome belong
   to it.
3. **Already tracked?** Search the target for issues that cover each outcome. A match gets a comment,
   handoff or close there instead of a new issue.
4. **One or several.** When the outcomes could be one issue or several, ask once with both options as
   their titles and kinds, and recommend one with a one-line reason. Example:
   - One issue: "Rechnungsexport überarbeiten" (improvement)
   - Three issues (recommended: three outcomes someone would look for separately):
     "Zeilenumbrüche im Rechnungsexport erhalten" (bug), "Export nach Buchungskanal filtern" (feature),
     "Export-Wiederholungen konfigurierbar machen" (improvement)
   The user may also merge or split differently.
5. **Written as if reported or requested first.** A bug states what someone saw and what should happen; a
   feature states the need; nothing in the body says the work is already done or how it was done. That goes
   into the closing or handoff comment. The tracker keeps its own creator and creation date; never
   backdate, and never name someone else as reporter.
6. **Assignee:** the user, unless they say otherwise.
7. **State, in the same question as step 4 when possible:** still in progress, being tested, or done.
   - in progress: create only;
   - being tested: hand over as **handoff** does (review status, `Ready for review:` comment);
   - done: close as **close** does, with result `done` implied; ask for a different result only if the
     work says so.
   `Done when` items are ticked only for what the work shows is met (CI-051).
8. **Confirm everything at once:** every issue, its fields, and its handoff or closing comment, as the
   procedure says. Then write, issue by issue, and report.
