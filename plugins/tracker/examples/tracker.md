# Tracker

Copy to `~/.claude/rules/tracker.md` (every project) or `.claude/rules/tracker.md` (one project). Claude Code
loads it in every session. Keep CI-100; change or drop the rest, and replace the example names with yours.
Where a project's tracker rules and these differ, the project's win.

### CI-100 [MUST] Tracker writes go through the tracker skills

Every issue, comment, handoff or close written to an issue tracker (or drafted for one) uses the matching
tracker skill: tracker:issue, tracker:retro, tracker:comment, tracker:handoff, tracker:close. Load it before
drafting.

- Bad: an issue created straight through the tracker's tools without loading tracker:issue.
- Checked by: review

### CI-101 [MUST] Issues from this repository go to one place

Example: issues from this repository go to team "Indicate Data", project "Mews", unless the user names
another.

- Bad: asking for the team every time although this rule names it.
- Checked by: review

### CI-102 [MUST] These are internal-only

Example: team "Backoffice" and project "Platform Ops" are internal-only: technical identifiers the next
person needs may appear there. Everything else is written for customers.

- Bad: a commit hash in an issue of any other project.
- Checked by: review

### CI-103 [MUST] German first

New issues are written in German; replies follow the thread's language. Address: Sie for customers, du in
the team, unless the thread says otherwise.

- Good: "Bitte exportieren Sie die Rechnungen erneut."
- Checked by: review

### CI-104 [SHOULD] Comments on my own issues need no confirmation

Progress comments (`Stand:`) on issues assigned to me are posted without asking first. Outweighed when the
issue is visible to a customer.

- Bad: asking to confirm a one-line status on my own internal issue.
- Checked by: review
