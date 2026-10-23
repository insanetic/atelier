# tracker 0.1.0: a convention for issues, and the skills that keep it

## Intent

Conventional Commits made commit messages predictable without caring whether the code lives on GitHub or
GitLab. `tracker` does the same for issues and tasks. It is a short, versioned **convention**: what an
issue, a comment, a handoff and a close look like. A set of **skills** writes and changes issues so that
every result follows it, through whatever tracker tool is connected.

Why: issues and comments today are too long, vague, inconsistent and say things they should not. Readers
are the team, the product owner, teammates who pick the work up later, and possibly customers, because
trackers push issues to customer platforms on their own. Titles and closing lines feed changelogs. The old
`linear` skill (one 240-line file, Linear- and workspace-specific) did not fix that.

## Goals

- **The convention** (`CONVENTION.md`, versioned): issue kinds, title rules, a fixed body shape per kind,
  a fixed shape per comment purpose, handoff, close results, what is never written, how facts are handled.
  No tool names, no company names. Readable by people without the plugin.
- **Six skills**, each carrying the convention parts it needs, so each produces conforming output alone:
  `issue`, `retro`, `comment`, `handoff`, `close`, and `check` (review a draft or an existing issue).
- **`tracker check`**: a deterministic lint of a draft against the convention, like commitlint. No
  network, no tracker.
- **Tool agnostic.** The skills use whatever tracker tool is connected (an MCP server, a CLI). They
  discover teams, projects, labels, statuses and users live and map the convention onto them.
- **Works for non-software work** (contracts, bookkeeping, HR) through the `task` kind.
- Language agnostic: German most of the time, English sometimes.

## Replaces

The personal `linear` skill (`~/.claude/skills/linear` and copies in project `.claude/skills/`) is removed
once `tracker` is built and verified. Nothing of it stays installed.

## Non-goals

- Shipping or configuring a tracker connection. The user installs the MCP or CLI.
- Workspace administration: creating projects, teams, label groups, workflows. A missing label is proposed
  and created only after the user says yes.
- Project updates, cycles, roadmaps, changelog generation (0.1.0).
- Pushing issues to customer platforms. The tracker does that on its own; we only make every text safe for
  it.

## Anti-goals

- A skill, the convention or the README names a specific tracker, company, team or label as required.
  Examples may use one, marked as an example.
- `tracker` requires, names or detects another plugin (including `tone`). Combination happens in context:
  the skills say generically "if a writing-style skill is available, apply it to the text before posting".
- Anything is written to the tracker that the user has not seen and confirmed in this session (see
  **Confirmation**).
- A fact, cause, reproduction, priority, date or person that nobody stated.
- Text longer than the convention allows, or a second topic in one comment.

## The convention (content of `CONVENTION.md`)

Every rule has an ID (`CI-001` …) that findings and skills cite.

### Audience

- Every issue and comment is written as if a customer may read it, unless the user says it is internal,
  or a rules file marks the team or project as internal-only. Internal-only text may hold the technical
  identifiers the next person needs to act (one identifier, not a paste).

### What is never written

Secrets; personal data the reader does not need; other customers; blame or who caused it; how the work or
text was made (AI, agents, sessions, tools); open security weaknesses in detail; internal commercial
matters. In customer-visible text also: code, file paths, function names, branches, commits, stack traces,
log lines, internal hosts and links to internal tools. Links to pull requests and commits go into the
tracker's link or attachment field when it has one, never into the prose.

### Facts

- Only what the user, the conversation or the work itself shows. No guessed cause, reproduction, impact,
  priority, date, version or person.
- Missing and needed: ask. Missing and optional: leave the section out. Never fill it with "unknown" or a
  placeholder.

### Kinds

Exactly one per issue.

| Kind | When | Maps to (example) |
|---|---|---|
| `bug` | something behaves differently from intended | label `Bug` |
| `feature` | a capability that does not exist yet | label `Feature` |
| `improvement` | something that exists works, but should work better | label `Improvement` |
| `task` | work with no behaviour change for users: maintenance, docs, refactors, and non-software work | `Chore`, `Tech debt`, `Docs` or none, whichever label fits by meaning |

Two kinds fit honestly: ask. Two pieces of work: two issues.

### Title (CI-010 …)

- At most 70 characters, sentence case, no trailing period, no prefix (`[Bug]`, `fix:`, issue IDs).
- States the outcome or the desired state, so it can go into a changelog as is. For a bug, the correct
  behaviour, not the symptom ("Keep line breaks in exported invoice notes").
- English: imperative verb. German: noun phrase or infinitive ("Zeilenumbrüche im Rechnungsexport
  erhalten").

### Body shapes (CI-020 …)

At most 120 words, not counting checklist lines. `##` headings in the issue's language; the English names
are canonical, the skills translate them. Only these sections, in this order; optional ones are left out
when empty.

| Kind | Sections |
|---|---|
| `bug` | **Problem** (what happens, where, since when, who is affected; required) · **Expected** (required) · **Steps** (optional, numbered) · **Done when** (optional checklist) |
| `feature` | **Need** (who needs what, for what; required) · **Done when** (required checklist) · **Not included** (optional) |
| `improvement` | **Today** (required) · **Better** (required) · **Done when** (optional checklist) |
| `task` | **What** (required) · **Why** (optional, one line) · **Done when** (required checklist) |

### Comments (CI-030 …)

At most 60 words. One purpose, named by the first word(s), in the comment's language:

| Purpose | Shape (English / German lead) |
|---|---|
| progress | `Status:` / `Stand:` what changed since the last comment, and the next step |
| decision | `Decision:` / `Entscheidung:` what was chosen, because why |
| question | `Question for @person:` / `Frage an @person:` exactly what is needed, and by when if it matters |
| blocker | `Blocked:` / `Blockiert:` by what, and what or whom it needs |
| handoff | see Handoff |
| close | see Close |

A change of scope or acceptance criteria goes into the description; the comment then says only what
changed.

### Handoff (CI-040 …)

Moving an issue to review or to another person is not closing it. It always gets one comment, at most 60
words, in three labeled lines, each left out only when empty:

```
Ready for review: <what is done, as outcome>
To check: <what and where or how>
Open: <what is unclear or not done, or "none">
```

German: `Bereit zur Prüfung:` / `Übergabe an @person:` · `Zu prüfen:` · `Offen:`.

### Close (CI-050 …)

One result, one closing comment of at most 2 sentences, leading with the result word:

| Result | Lead (en / de) | Says | Maps to (example) |
|---|---|---|---|
| done | `Done:` / `Erledigt:` | what changed for the reader; follow-ups by ID | status `Done` |
| won't do | `Not doing:` / `Nicht umgesetzt:` | the reason | `Canceled` + `Wontfix` |
| works as intended | `Works as intended:` / `Funktioniert wie vorgesehen:` | why, and what to do instead | `Canceled` + `User error` |
| duplicate | `Duplicate of` / `Duplikat von` | the other issue | `Duplicate`, linked |
| can't reproduce | `Not reproducible:` / `Nicht reproduzierbar:` | what was tried; what would reopen it | `Canceled` |
| obsolete | `No longer relevant:` / `Nicht mehr relevant:` | why | `Canceled` |

Checked acceptance criteria are ticked only when actually met; a dropped one is said in the closing comment.

### Links (CI-060)

Follow-up work is a new linked issue, not a longer comment. Duplicates are linked. Related work found while
doing an issue is linked, not described.

## The skills

All skills share: **resolve the target** (team/board and project/list from context and rules files; ask
when ambiguous; never a default remembered from earlier), **check before writing** (the exact issue by ID,
labels and statuses as they exist), **confirmation**, and **report back** (ID, link, where it went, what was
set).

### Confirmation

Every write is shown first, in one message, exactly as it will be posted (title, body, kind label, status,
assignee, target; or the comment), and is written after the user confirms. Several writes in one flow are
confirmed together. A rules file may relax this per action (for example "comments on my own issues need no
confirmation"); the plugin never relaxes it on its own.

### `issue`: a new issue from a report, request or finding

1. Gather the facts from the request and the conversation.
2. Search the tracker for an existing issue on the same thing; if one fits, propose commenting or linking
   there instead.
3. Pick the kind; ask if two fit.
4. Ask, in one batched question, only for what the shape requires and the context lacks.
5. Draft, run `tracker check`, confirm, create, report.

A bug found while working on another issue is created linked to it.

### `retro`: issues for work already done

1. **Sources:** the current session (conversation, changed files, commits on the branch against its base),
   or what the user tells, or both. Gaps or contradictions are asked, not filled.
2. **Search** for existing issues that cover the work; matched work gets a comment or close there instead
   of a new issue.
3. **Split by outcome**, not by file. When the work could be one issue or several, ask once, showing both
   options with their titles and kinds, and recommend one with a one-line reason. Example:
   - One issue: "Rechnungsexport überarbeiten" (improvement)
   - Three issues (recommended, three separate outcomes a reader would look for): "Zeilenumbrüche im
     Rechnungsexport erhalten" (bug), "Export nach Buchungskanal filtern" (feature), "Export-Wiederholungen
     konfigurierbar machen" (improvement)
4. **Write each as if reported or requested first**: a bug states the symptom someone saw and the expected
   behaviour; a feature states the need. Nothing about the work having been done already in the body; that
   goes into the closing comment. Created by and created at stay what the tracker records; nothing is
   backdated or attributed to someone else.
5. **Assign** to the user unless they say otherwise.
6. **Ask the state** in the same confirmation: still in progress, being tested (handoff to review), or done.
   Done hands over to `close` with result `done` implied; testing hands over to `handoff`.
7. Confirm all issues, their states and closing comments together, then write.

### `comment`

Picks the purpose from the request; one purpose per comment; ask if the request mixes two (offer two
comments). Never changes status, assignee or fields. Updates the description instead when scope changed,
and says so in a one-line comment.

### `handoff`

Sets the new status and/or assignee and posts the handoff comment. Asks for the receiver or status when not
clear. Discovers whether the workspace has a review status; if not, uses assignee only.

### `close`

Picks the result from the request or the flow (`retro` implies `done`); asks with a recommendation when
unclear. Ticks met acceptance criteria, posts the closing comment, sets the mapped status and label, links
the duplicate or follow-ups. Several issues are closed in one confirmed batch.

### `check`

Reviews a draft or an existing issue (by ID) against the convention: runs `tracker check`, judges what the
script cannot (facts, audience, one topic), returns findings with rule IDs and a corrected version. Writes
nothing unless asked to apply the correction (which then goes through confirmation).

## Mapping onto a tracker

- The convention's kinds, results and purposes are fixed. Their counterparts in a workspace are found live
  each time (list labels, statuses, users, projects) and matched by meaning and name, in the workspace's
  spelling.
- No match for a kind or result label: proceed without it and say so, or offer to create it (only after a
  yes). No match for a required status (done, canceled, duplicate): ask.
- A rules file may fix mappings ("result won't do maps to label Wontfix"), routing ("this repository goes to
  team IND, project Mews") and internal-only teams or projects.
- Tool calls are whatever the connected tool offers. The skills name operations generically (find issues,
  create issue, update issue, add comment, link issues, list labels or statuses); no tool names in skills.
- **No tracker tool connected:** the skill still produces the conforming draft (checked) and hands it over
  ready to copy and paste by hand: title, body and the fields to set (kind label, status, assignee) in
  separate code blocks, then says that nothing was written. **More than one:** a rules-file routing decides; otherwise ask which one.

## Next to a writing-style plugin

The convention wins on structure: kinds, sections, lead words, results, limits. A writing-style skill, when
one is available, only polishes wording inside that structure. Order: draft, writing-style pass, then
`tracker check` last, so the posted text always conforms. Rules files may raise or lower the convention's
limits; `tracker check` enforces the convention only, and the skill lists any finding it set aside because a
rule allows it under **Dismissed** (same as `tone`).

## `tracker check`

`tracker check [--json] <file|->`. The draft is markdown with a small frontmatter:

```
---
type: issue | comment
kind: bug | feature | improvement | task        # issue
purpose: progress | decision | question | blocker | handoff | close   # comment
result: done | wont-do | works-as-intended | duplicate | cant-reproduce | obsolete   # close
lang: de | en                                   # optional, detected otherwise
---
# <title>             (issue)
<body>
```

Decides: title length, prefix, period; the sections and their order per kind, required ones present, no
others; body and comment word limits, checklists not counted; comment lead word per purpose and language;
handoff and close shape; checklists under Done when; code spans, paths, stack-trace shapes and token shapes
anywhere unless `audience: internal` is set. Exit 0 clean, 1 findings, 2 usage. Never rewrites.

## Rules files (user-owned, example shipped)

`examples/tracker.md`, copy-paste ready, in rulebook entry format (`CI-1xx` free for users):

- a line that makes Claude use the tracker skills for every tracker write (as with `tone`, skills may not
  trigger on their own; verify in evals);
- routing per repository;
- internal-only teams or projects;
- default language and address;
- relaxing confirmation for an action, as an example.

## Evals (at least)

- `issue` from a thin bug report: asks for the expected behaviour, invents no cause or steps.
- `issue` that already exists: proposes linking or commenting instead.
- `retro` from a session with three separate outcomes: offers one versus three with a recommendation, titles
  as outcomes, written as if reported.
- `retro` from the user's description only, with a gap: asks.
- `close` without a result: asks with recommendation; with "rejected because X": `Not doing:` comment, no
  question.
- `handoff`: three labeled lines, no closing.
- `comment` mixing a decision and a question: two comments or asks.
- A non-software `task` (contract renewal) in German.
- A customer-visible issue: no paths, commits or names of other customers; PR link only as an attachment.
- Trigger: "leg dafür ein Ticket an" fires `issue`; a plain chat question fires nothing.

Evals run dry and without a tracker: the prompt pastes the existing issues, labels and statuses the case
needs, and the graders read the confirmation message. The plugin's no-tracker path (draft only) is what
runs.

## Layout

```
plugins/tracker/
  .claude-plugin/plugin.json
  README.md
  CONVENTION.md
  bin/tracker  lib/tracker.py          # Python 3.9+, stdlib only, like tone
  skills/{issue,retro,comment,handoff,close,check}/SKILL.md
  examples/tracker.md
  tests/test_tracker.py
  evals/<case>/prompt.md, graders/*.md
```

Registered in the marketplace, the root README and the pre-commit test hook.

## Decisions made by me (check these)

- Four kinds: bug, feature, improvement, task. Chore, tech debt and docs are labels a `task` may carry.
- Bug titles state the correct behaviour, not the symptom, so they read as changelog lines.
- Every write needs confirmation in the session; rules files may relax it.
- Comments at most 60 words; issue bodies at most 120; closing comments at most 2 sentences.
- Retro assigns to the user and never backdates or fakes the reporter.
- PR and commit links go to the tracker's link field, never into prose.
- Skills read the one `CONVENTION.md` at the plugin root (independence is between plugins, not between
  skills of one plugin); no copies.
- No setup skill; discovery is live and preferences live in the user's rules file.
- No tracker connected: draft only. Several: rules routing, else ask.
- Writing-style pass before `tracker check`, never after; the convention wins on structure.
- `tracker check` enforces the convention only; overrides are applied and shown by the skill.
- Evals paste the workspace state into the prompt; no mock server.

## Left to the builder

- The lint's exact heuristics, sharing nothing with `tone` at runtime (copying code is fine).
- Wording of skills and README, following the convention itself.
