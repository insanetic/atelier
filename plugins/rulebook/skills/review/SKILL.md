---
name: review
description: Use before a commit or merge, or when asked whether a change follows the repository's convention catalog (.claude/rules/) or built what was requested. Any stack. Not a bug or security review, and not a review of the catalog itself.
argument-hint: "<the ask> | deviations: <approved departures> | files: <paths, optional>"
context: fork
agent: rulebook:reviewer
---

# Reviewing a change

Two questions: did the change deliver what was asked, nothing missing and nothing extra; and does it follow the
catalog. The machine checks already ran or will run; you judge what only review can.

## Steps

This review runs forked: it sees none of the conversation, only these arguments:

```
$ARGUMENTS
```

The caller passes the ask, every departure from an entry the maintainer approved (with the instruction), and the files
when the change is not the working tree. An approval that is not in the arguments does not exist for this review.

The `rulebook` command is on the PATH while this plugin is enabled. It selects the files and the entries; do not
select either by reading.

1. **The ask**: write the requirements as a short list from the arguments, the commit messages or the linked issue,
   and list the approved deviations separately. If none of these states the ask, review conformance only and say so in
   the report's first line.
2. **The change**: the files the arguments name; otherwise the output of `rulebook changed` (the branch against its
   base, the working tree and the untracked files). Read each changed file whole, not only its hunks, and the diff
   (`git diff <base>...HEAD`, `git diff HEAD`) for what was removed.
3. **The gate**: run the command the repository names for checking a change (in `CLAUDE.md`, `AGENTS.md` or the
   catalog's authoring file), scoped to the changed files when it can be (`make check-changed FILES="<files>"`,
   `pnpm verify`), and `rulebook check` when a rules file changed. A failure is a finding as it stands; do not
   re-derive what a check reports. If the repository names no such command, run none and say so in the report's
   first line.
4. **The entries**: run `rulebook for <the changed files>` (no arguments when step 2 used `rulebook changed`). It
   prints the rule files that govern those files and, in full, every entry review checks, alone or beside a check
   that covers only part of it. That list is the whole scope: an entry it leaves out is enforced by a machine or
   does not apply. If it answers that there is no catalog, review the ask only and say so in the report's first line.
5. **Judge** every listed entry against every changed file it can apply to, one entry at a time, and trace the
   requirements both ways. Before a finding goes in the report, open the file and confirm the line says what the
   finding claims.
6. **Report** in the format below.

## Severity

- **Blocker**: a MUST entry broken without its `Waiver:`, a missing requirement, or a contract change that breaks a
  consumer.
- **Should-fix**: a SHOULD entry deviated from without the reason in the reply, or unrequested scope.
- A deviation the maintainer explicitly asked for is never a finding: it goes under "Requested deviations" with the
  instruction it follows. When nothing records it (the entry's waiver marker, or the reply or commit), the missing
  record is the should-fix.
- No entry, no finding. A pattern the catalog lacks goes under "Catalog gaps" as a proposed entry, never as a finding.
- A bug you notice goes under "Outside scope", one line, without hunting for more.

## Report

```
Verdict: COMPLIANT | NEEDS CHANGES
Reviewed: <n> files against <n> entries; gate: <the command and its result | none named>

Requirements
- [x] <requirement>: <file:line>
- [ ] <requirement>: missing
- (+) <unrequested change>: <file:line>

Blockers
1. <ID> <what is wrong>: <file:line>
   Fix: <the change>

Should-fix
1. <ID> ...

Requested deviations
- <ID> <what departs>: <file:line>, asked as "<the instruction>"

Catalog gaps
- <pattern the catalog should decide>

Outside scope
- <one line>
```

The verdict is NEEDS CHANGES when there is a blocker, a should-fix or a failed gate, and COMPLIANT otherwise. Leave
out empty sections. A clean change gets the first two lines and nothing else.
