# Conventional Issues 0.2.0

A convention for issues and tasks: what an issue, a comment, a handoff and a close look like, in any
tracker. It does not care whether the tracker is Linear, Jira, GitHub, Trello or a spreadsheet. Every rule
has an ID that tools and reviews cite.

Why: an issue is read by people who were not there: the team, the product owner, whoever picks the work up
months later, and often customers, because trackers push issues to customer platforms and changelogs on
their own. A fixed shape makes every issue readable at a glance, safe to show, and usable as a changelog
line.

---

## 1. Audience and exposure

### CI-001 Write as if a customer reads it

Every issue and comment is written for an external reader, unless the user says it is internal or a rule
marks the team or project as internal-only.

### CI-002 Never written, anywhere

- Secrets: tokens, keys, passwords, connection strings, signed links.
- Personal data the reader does not need: emails, phone numbers, addresses.
- Other customers: names, accounts, data, unless the issue is about that customer and is internal.
- Blame: who caused it. Describe what happened.
- How the work or the text was made: AI, agents, sessions, prompts, tools.
- Open security weaknesses in detail. Describe the effect only.
- Internal commercial matters: prices, deals, contract terms, unless internal and about them.

### CI-003 Never written for an external reader

Code, file paths, function names, branches, commits, stack traces, log lines, internal hosts, links to
internal tools. Pull requests and commits go into the tracker's link or attachment field when it has one,
never into the text. Internal text keeps only the identifiers the next person needs to act: one
identifier, not a paste.

## 2. Facts

### CI-004 Only what is known

Only what the user, the conversation or the work itself shows. No guessed cause, reproduction, impact,
priority, date, version or person, and no hedges ("probably", "should now work", "vermutlich").

### CI-005 Ask or leave out

A missing fact the shape requires is asked. A missing optional fact means the section is left out. Never
"unknown", "TBD" or a placeholder.

## 3. Kinds

### CI-006 Exactly one kind per issue

| Kind | When |
|---|---|
| `bug` | something behaves differently from what is intended |
| `feature` | a capability that does not exist yet |
| `improvement` | something that exists and works, but should work better |
| `task` | work that changes no behaviour for users: maintenance, docs, refactoring, and non-software work (contracts, bookkeeping, hiring) |

Two kinds fit honestly: ask. Two pieces of work: two issues. A `task` may carry a finer label the workspace
has (chore, tech debt, docs) when one fits by meaning.

### CI-007 Every issue has a priority, and the reason is known

Priority is set on every new issue, from the signals in what was said or shown, by this scale:

| Priority | When |
|---|---|
| urgent | an active outage, data loss or wrong data reaching customers, many customers blocked, or a hard deadline within days |
| high | a customer or a deal is affected or waiting, an important flow is broken for some, or a deadline this cycle |
| medium | planned work with a clear benefit; no urgency signal (the default) |
| low | nice to have, cosmetic, or no one is waiting |

The strongest signal wins. With no signal the priority is `medium`, and it is said to be the default. The
priority is shown with its reason before it is set, so it can be changed.

## 4. Title

### CI-010 Short

At most 70 characters, sentence case, no trailing period.

### CI-011 No prefix

No type, scope or ID prefix: not `[Bug]`, `Bug:`, `fix:`, `feat(export):`, `IND-12`. The kind is a label.

### CI-012 States the outcome

The title names the outcome or the desired state, so it can go into a changelog as is. A bug's title names
the correct behaviour, not the symptom.

- English: imperative verb. "Keep line breaks in exported invoice notes"
- German: noun phrase or infinitive. "Zeilenumbrüche im Rechnungsexport erhalten"

## 5. Body

### CI-020 Short

At most 120 words, not counting checklist lines.

### CI-021 One shape per kind

Only these sections, in this order, as `##` headings in the issue's language. Required sections are always
there; optional ones are left out when empty. Nothing else.

| Kind | Required | Optional |
|---|---|---|
| `bug` | Problem, Expected | Steps, Done when |
| `feature` | Need, Done when | Not included |
| `improvement` | Today, Better | Done when |
| `task` | What, Done when | Why |

Order:

- `bug` Problem, Expected, Steps, Done when.
- `feature` Need, Done when, Not included.
- `improvement` Today, Better, Done when.
- `task` What, Why, Done when.

| English | German |
|---|---|
| Problem | Problem |
| Expected | Erwartet |
| Steps | Schritte |
| Done when | Fertig, wenn |
| Need | Bedarf |
| Not included | Nicht enthalten |
| Today | Heute |
| Better | Besser |
| What | Was |
| Why | Warum |

### CI-022 What goes in each section

- **Problem:** what happens, where, since when, who is affected.
- **Expected:** what should happen instead.
- **Steps:** a numbered list that reproduces it.
- **Need:** who needs what, for what.
- **Today / Better:** how it works now; how it should work.
- **What / Why:** the work; one line on why now.
- **Done when:** a checklist (`- [ ]`) of observable results, each one line.
- **Not included:** what the issue explicitly does not cover.

### CI-023 Durable truth lives in the description

When scope or acceptance criteria change, the description is updated; a comment says only what changed.

## 6. Comments

### CI-030 Short, one purpose

At most 60 words and one purpose per comment, named by its first words, in the comment's language. A
second purpose is a second comment.

| Purpose | English | German | Says |
|---|---|---|---|
| progress | `Status:` | `Stand:` | what changed since the last comment, and the next step |
| decision | `Decision:` | `Entscheidung:` | what was chosen, and why |
| question | `Question for <person>:` | `Frage an <person>:` | exactly what is needed, and by when if it matters |
| blocker | `Blocked:` | `Blockiert:` | by what, and what or whom it needs |

No greetings, sign-offs, thanks or apologies.

## 7. Handoff

### CI-040 Handing over is not closing, and always says where things stand

Moving an issue to review or to another person always gets one comment, at most 60 words, in up to three
labeled lines in this order. The first is required; the others are left out only when empty.

| Line | English | German |
|---|---|---|
| what is done | `Ready for review:` or `Handed to <person>:` | `Bereit zur Prüfung:` or `Übergabe an <person>:` |
| what to check | `To check:` | `Zu prüfen:` |
| what is open | `Open:` | `Offen:` |

```
Ready for review: exported invoices keep line breaks in notes.
To check: export an invoice with multi-line notes created after Oct 20.
Open: none.
```

## 8. Close

### CI-050 One result, one short closing comment

Every close has one result and one comment of at most two sentences, starting with the result's lead.

| Result | English | German | Says |
|---|---|---|---|
| `done` | `Done:` | `Erledigt:` | what changed for the reader; follow-ups by ID |
| `wont-do` | `Not doing:` | `Nicht umgesetzt:` | the reason |
| `works-as-intended` | `Works as intended:` | `Funktioniert wie vorgesehen:` | why, and what to do instead |
| `duplicate` | `Duplicate of` | `Duplikat von` | the other issue |
| `cant-reproduce` | `Not reproducible:` | `Nicht reproduzierbar:` | what was tried; what would reopen it |
| `obsolete` | `No longer relevant:` | `Nicht mehr relevant:` | why |

### CI-051 Checklists tell the truth

A `Done when` item is ticked only when it is met. A dropped item is said in the closing comment.

## 9. Links

### CI-060 Link, do not stretch

Follow-up work is a new, linked issue, not a longer comment or a reopened scope. A duplicate is linked to
the issue it duplicates. Related work is linked, not retold.

---

## Mapping onto a tracker

The kinds, purposes and results above are fixed. Their counterparts in a tracker (labels, statuses, link
types) are found by meaning in each workspace. Typical:

| Convention | Typical counterpart |
|---|---|
| kind | a type label (`Bug`, `Feature`, `Improvement`; `Chore`, `Tech debt` or `Docs` for a task) |
| priority | the tracker's priority field, or a priority label if it has no field |
| `done` | the completed status |
| `wont-do` | the canceled status, with a won't-fix label if one exists |
| `works-as-intended` | the canceled status, with a user-error or not-a-bug label if one exists |
| `duplicate` | the duplicate status or link |
| `cant-reproduce`, `obsolete` | the canceled status |
| handoff to review | the review status if one exists, otherwise the assignee only |
