# Conventional Issues 0.6.0

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

### CI-008 Stands on its own

Someone who was not there can pick the issue up and finish it from the issue alone, without the
conversation it came from. Every issue answers:

| Question | Where it goes |
|---|---|
| what should be true afterwards | the title and the TL;DR |
| why, and for whom | Problem, Goal, Current state or Why |
| how to tell it is done | Acceptance criteria |
| who asked, when it was not the one filing it, and who answers questions | the tracker's people fields (subscriber, mention, customer or requester link) |
| what the work needs: documents, files, accounts, the original request, related or blocking issues | the tracker's attachments and links |
| by when, if a date was given | the due date |

A fact the work needs that was said only in the conversation goes into the issue; one that is missing is
asked (CI-005). Text holds only what its reader may see (CI-002, CI-003). Context only the team may see
goes into an internal comment if the tracker has them, otherwise a linked issue in an internal-only team or
project.

## 3. Kinds

### CI-006 Exactly one kind per issue

| Kind | When | Changelog group |
|---|---|---|
| `bug` | something behaves differently from what is intended | Fixed |
| `feature` | a capability that does not exist yet | Added |
| `improvement` | something that exists and works, but should work better | Changed |
| `task` | work that changes no behaviour for users: maintenance, docs, refactoring, and non-software work (contracts, bookkeeping, hiring) | none |

The changelog groups are those of Keep a Changelog, so an outcome title goes into a changelog as is.

Two kinds fit honestly: ask. Two pieces of work: two issues. A `task` may carry a finer label the workspace
has (chore, tech debt, docs) when one fits by meaning.

### CI-007 Priority comes from a signal, never from a default

Priority is worked out for every new issue from the signals in what was said or shown, by this scale:

| Priority | When |
|---|---|
| urgent | an active outage, data loss or wrong data reaching customers, many customers blocked, or a hard deadline within days |
| high | a customer or a deal is affected or waiting, an important flow is broken for some, or a deadline this cycle |
| medium | planned work with a clear benefit; no urgency signal (the default) |
| low | nice to have, cosmetic, or no one is waiting |
| none | no signal at all: the tracker's "no priority", or the field left empty |

The strongest signal wins. With no signal the priority is `none`, so a priority in the tracker always
means someone judged it; a default `medium` would look judged when it was not. The priority is shown with its
reason before it is set, so it can be changed.

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
| `bug` | Problem, Expected behaviour, Acceptance criteria | Steps to reproduce |
| `feature` | Goal, Acceptance criteria | Out of scope |
| `improvement` | Current state, Goal, Acceptance criteria | — |
| `task` | Task, Why, Acceptance criteria | — |

Order:

- `bug` Problem, Expected behaviour, Steps to reproduce, Acceptance criteria.
- `feature` Goal, Acceptance criteria, Out of scope.
- `improvement` Current state, Goal, Acceptance criteria.
- `task` Task, Why, Acceptance criteria.

| English | German |
|---|---|
| Problem | Problem |
| Expected behaviour | Erwartetes Verhalten |
| Steps to reproduce | Schritte zum Nachstellen |
| Goal | Ziel |
| Current state | Ist-Zustand |
| Task | Aufgabe |
| Why | Warum |
| Acceptance criteria | Akzeptanzkriterien |
| Out of scope | Nicht im Umfang |

### CI-022 What goes in each section

- **Problem:** what happens, where, since when, who is affected and how.
- **Expected behaviour:** what should happen instead.
- **Steps to reproduce:** a numbered list that reproduces it.
- **Goal:** for a feature, who needs what, for what; for an improvement, how it should work.
- **Current state:** how it works now, and what that costs whom.
- **Task / Why:** the work; one line on why it is needed, and why now.
- **Acceptance criteria:** a checklist (`- [ ]`) of observable results, each one line.
- **Out of scope:** what the issue explicitly does not cover.

### CI-023 Durable truth lives in the description

When scope or acceptance criteria change, the description is updated; a comment says only what changed.

### CI-024 Starts with a TL;DR

The body's first line comes before the first section: one sentence of
at most 25 words, led by `TL;DR:` in every language, saying what the matter is and for whom or why. It
adds to the title instead of repeating it. For a bug it names what people see, in their words, so search
and duplicate checks still find it while the title names the correct behaviour. It counts toward the 120
words.

- "TL;DR: Multi-line notes in exported invoices end up on one line; customers send them to their guests."
- "TL;DR: Der Mietvertrag für das Büro Leipzig läuft am 31.12. aus und soll um zwei Jahre verlängert werden."

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

### CI-031 Mention only someone who must act

A mention notifies, so it is a request for action, not a way to inform.

- **When:** in a comment that needs one person to act: the person in `Question for`, the person a `Blocked:`
  comment needs, the receiver in `Handed to`, a reviewer in `Ready for review:`. Normally one person; two
  only when both must act.
- **Not:** in a description (people go into the assignee and subscriber fields, CI-008); in a status,
  decision or closing comment (whoever should follow is a subscriber); to say thanks or "fyi"; the author
  themself; a group or team handle (`@team`, `@channel`, `@here`, `@all`); the person already assigned, for
  routine progress.
- **Who:** only a person found in the workspace, with the tracker's own mention, never a guessed handle. No
  account: the name without `@`, and ask whether someone else should be mentioned. Customers and other
  external people are mentioned only in their own issue, and only when they must answer (CI-002).
- **Shown first:** the confirmation lists everyone a write will notify.

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
Where the tracker has a resolution field or a close reason, the result is set there too, so it can be
filtered; the comment still starts with the lead.

| Result | English | German | Says |
|---|---|---|---|
| `done` | `Done:` | `Erledigt:` | what changed for the reader; follow-ups by ID |
| `wont-do` | `Won't do:` | `Nicht umgesetzt:` | the reason |
| `works-as-intended` | `Works as intended:` | `Funktioniert wie vorgesehen:` | why, and what to do instead |
| `duplicate` | `Duplicate of` | `Duplikat von` | the other issue |
| `cant-reproduce` | `Not reproducible:` | `Nicht reproduzierbar:` | what was tried; what would reopen it |
| `obsolete` | `No longer relevant:` | `Nicht mehr relevant:` | why |

### CI-051 Checklists tell the truth

An acceptance criterion is ticked only when it is met. A dropped item is said in the closing comment.

## 9. Links

### CI-060 Link, do not stretch

Follow-up work is a new, linked issue, not a longer comment or a reopened scope. A duplicate is linked to
the issue it duplicates. Related work is linked, not retold.

## 10. Terms

### CI-070 The same words, every time

Every fixed term is written exactly as the tables above spell it, in the text's language: section headings
(CI-021), comment leads (CI-030), handoff lines (CI-040) and close leads (CI-050). `TL;DR:` is the same in
every language (CI-024). So a reader, a search and a script can rely on them.

- **Exactly:** same spelling, case and punctuation. `Ist-Zustand`, not `Ist Zustand`; `Acceptance
  criteria`, not `Acceptance Criteria:`; `Expected behaviour`, not `Expected behavior`.
- **No synonyms:** not `Soll-Zustand`, `Aktuell`, `Definition of done`, `Hintergrund`, `Background`,
  `Update:`, `Zwischenstand:`. The table's term, or nothing.
- **What Claude writes:** the rule holds for every new issue and comment Claude writes. Existing issues
  and text people write themselves are left as they are; `check` cleans one up when asked.
- **One language per text:** the language of the text decides the column (PROCEDURE.md, step 4). A German
  issue has German headings and leads, an English one English; never mixed, also not when the thread mixes.
- **Other languages:** a language with a column in the tables uses its own terms. A language without one
  uses the English terms until a column is added: one more entry per term, here and in `lib/tracker.py`,
  never translated ad hoc in a single issue.

---

## Mapping onto a tracker

The kinds, purposes and results above are fixed. Their counterparts in a tracker (labels, statuses, link
types) are found by meaning in each workspace. Typical:

| Convention | Typical counterpart |
|---|---|
| kind | the tracker's issue type field when it has one (GitHub issue types, Jira work types); otherwise a type label (`Bug`, `Feature`, `Improvement`; `Chore`, `Tech debt` or `Docs` for a task) |
| priority | the tracker's priority field, or a priority label if it has no field; `none` is "no priority" or empty |
| who asked, who answers | subscribers or mentions; the customer or requester link if the tracker has one |
| what the work needs | attachments and links (the original request, related, blocked by) |
| by when | the due date |
| `done` | the completed status; resolution Done; close reason completed |
| `wont-do` | the canceled status; resolution Won't do; close reason not planned; a won't-fix label if one exists |
| `works-as-intended` | the canceled status; a matching resolution if one exists; close reason not planned; a user-error or not-a-bug label if one exists |
| `duplicate` | the duplicate status or link; resolution Duplicate; close reason duplicate |
| `cant-reproduce` | the canceled status; resolution Cannot reproduce; close reason not planned |
| `obsolete` | the canceled status; a matching resolution if one exists; close reason not planned |
| handoff to review | the review status if one exists, otherwise the assignee only |
