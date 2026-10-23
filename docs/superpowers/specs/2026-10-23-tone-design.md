# tone 0.1.0: how text for other people reads

## Intent

Agents write text that other people read: issues, comments, changelog lines, later emails. Today
that text is too long, vague, inconsistent in format, and says things it should not (internal
details, guesses, plumbing). The readers are mixed: the team, the product owner, teammates who pick
the work up later, and sometimes customers, because issues can surface on the customer platform and
feed the changelog.

`tone` is a standalone plugin that makes such text short, specific, consistent and safe for its
reader. It owns **how text reads and what may never appear in it**. It does not own what a text is
about or where it is posted; other plugins (the planned `tracker`, a later email plugin) own that.

## Goals

- One fixed, predictable procedure: the same draft, profile and audience give the same findings.
- **Profiles**, one file each, for the kinds of text. 0.1.0 ships `issue`, `comment`, `changelog`.
  Adding a kind (for example `email`) is adding one file, no code.
- A shared **base** every profile builds on: facts, exposure, style, language, formality.
- A `review` skill: draft + profile + audience in, findings + revised text out. Usable on its own
  ("check this comment") and by any other skill that writes text.
- A deterministic **check** command for everything a machine can decide; the skill judges the rest.
- Language agnostic. Mostly German, sometimes English, rules written once for both.

## Non-goals

- Posting anything anywhere. `tone` never calls a tracker, mail or chat tool.
- Deciding content or structure of an issue (sections, type, labels). That is `tracker`'s.
- Installing or managing rules files. The user writes their own if they want overrides.
- Changing how Claude talks to the user in chat. Only text written for other people.

## Anti-goals (a failure even if it works)

- `tone` names, requires or detects another plugin, or another plugin names `tone`. They combine
  only through context: a writing skill elsewhere says, generically, "if a writing-style review is
  available, run the draft through it before posting".
- The review invents facts to make a text complete or "nicer". It may cut, shorten, reorder and
  rephrase. It never adds a claim that is not in the draft or the given context; a gap becomes a
  question back to the caller.
- The revised text is longer than the draft, unless the draft broke a rule that needed words (for
  example a missing reason on a rejection).
- It reads like AI wrote it.

## How it fits with other plugins and with rules files

- **Independent.** No `dependencies` in `plugin.json`, no mention of other plugins in skills or
  docs.
- **Overrides belong to the user, in Claude Code rules files.** `~/.claude/rules/*.md` loads in
  every session, `.claude/rules/*.md` per project, with no skill referring to them. Claude Code
  does not rank the two when they conflict, so a user who wants a project to win writes that into
  the global file. The plugin ships no rules file and no setup for one. The README shows one short
  example, in the rulebook entry format (`### TONE-101 [MUST] ...`) so it passes `rulebook check` in
  repos that use rulebook.
- **Precedence inside a review** (fixed): explicit instruction in the request > rules files in
  context > the profile > the base.
- **Overrides and the check.** `tone check` knows only the plugin's profiles and base, so its
  output never changes with rules files. The review skill may dismiss a check finding only when a
  higher source allows it, and then lists it under **Dismissed** with the source (for example
  "TONE-012 dismissed: project rule TONE-101 allows 100 words"). Same input, same check output;
  overrides stay visible.

## When it runs

**Built:** the skill is named `write`, not `review`: it is used while drafting, and the name decides
whether Claude reaches for it. Live runs showed Claude does not pick it on its own for "write a
comment" requests (0 of 8 runs, with two description rewrites). With one line in the user's own rules
file naming the skill, it fired in every run. The README gives that line; the plugin still installs
nothing. The notes below describe the intent.

- The skill description is broad: it triggers whenever Claude drafts text that someone other than
  the user will read (an issue, a comment, a changelog line, an email), whether a skill asked for it
  or not, and when the user asks to check such a text. It stays quiet for chat replies to the user,
  code, commit messages and docs in the repo.
- No hooks in 0.1.0.
- Only `tone check` is repeatable byte for byte. The review follows a fixed, ordered checklist
  (exposure, facts, audience, language and formality, length, style), so results are stable, but
  evals grade outcomes, not exact text.

## The base (applies to every profile)

Each rule has a stable ID (`TONE-001` …) that findings cite. Groups:

**Facts**
- Only what the draft or the given context states. No guesses written as facts, no "probably",
  "should now work", "seems to". Unknown means left out or asked.
- No promises of dates, releases or behaviour the context does not contain.

**Exposure: never written, in any profile**
- Secrets: tokens, keys, passwords, connection strings, signed URLs.
- Personal data beyond what the reader already has: emails, phone numbers, addresses of people.
- Other customers: names, tenants, accounts, data, unless the text is about that customer and the
  reader is internal.
- Blame or naming who caused a problem.
- How the text was made: no mention of AI, agents, Claude, sessions, prompts or tools used.
- Security weaknesses in detail before they are fixed.
- Internal commercial matters: prices, deals, contract terms, unless the profile's audience is
  internal and the context is about them.

**Exposure: only when the audience is internal**
- Code, file paths, function names, branches, commits, PR links, stack traces, log lines, internal
  hostnames, IPs, service and repository names, database tables.
- Even then: only what the reader needs to act. One identifier beats a paste; a link beats a log.

**Audience**
- `external` or `internal`, passed by the caller. If not passed and not clear from context,
  `external`. Defaulting to the safe side is the point.

**Style**
- Lead with the outcome. One topic per text.
- Plain words; the correct technical term only where the reader knows it.
- No filler, hedging, greetings, sign-offs, apologies, thanks-for-reporting boilerplate, or
  restating the title.
- No AI tells: long dashes, "not just X but Y", lists of three for rhythm, "delve", "seamless",
  "robust", "leverage", bold scattered through prose, emoji. German equivalents included
  ("grundsätzlich", "im Prinzip", "nahtlos", "umfassend", "spannend").
- Consistent formatting per profile (below); nothing outside it.

**Language**
- Reply in the language the thread or issue is already in. New text: the language the caller
  passes, else the language of the user's request.
- Never mix languages in one text, except fixed product and technical terms.

**Formality (German, and any language with a formal and informal you)**
- Inferred from context: the thread's existing address, how the reporter wrote, what the user said.
- Not inferable and not told: `Sie` for external, `du` for internal.
- One form throughout a text.

## Profiles 0.1.0

A profile is one markdown file: frontmatter with the machine-checkable limits, body with the
judgement rules and two short good and bad examples (one German, one English).

| | `issue` | `comment` | `changelog` |
|---|---|---|---|
| Reader | team, product owner, maybe a customer | same as the issue | customers |
| Default audience | external | external | external (never internal) |
| Title | ≤ 70 characters, states the outcome, no type prefix (`[Bug]`, `fix:`), no trailing period. German: noun phrase or infinitive ("Export großer Rechnungen beschleunigen") | n/a | n/a |
| Body | ≤ 120 words, excluding checklists. `##` headings only, short bullets, no tables unless the content is tabular | ≤ 60 words, at most 3 sentences or 4 bullets, no headings | one line, ≤ 100 characters, what changed for the user |
| Never | anything from the base | a second topic; repeating the issue | issue IDs, internal names, anything only the team understands |

The sections inside an issue body are not `tone`'s business. The limits apply to whatever sections
the caller uses.

## The review skill

`/tone:write <draft, notes or file> [profile] [audience] [language]`

1. Pick the profile (given, or inferred from the text's shape; ask if it is honestly two).
2. Run `tone check` on the draft.
3. Judge what the script cannot: facts versus guesses, exposure in meaning (a customer named
   indirectly), tone, clarity, one topic, formality.
4. Return, always in this shape:
   - **Verdict:** `ok`, `fixed` or `needs input`.
   - **Findings:** at most 7, each `TONE-id · the quoted phrase · the fix`. Most severe first;
     exposure before style.
   - **Revised text,** ready to paste, or nothing when the verdict is `ok`.
   - **Questions,** only for `needs input`: a fact the text needs that the context does not have.
   - **Dismissed,** only when a check finding was overruled, each with its source.
5. Never posts, never writes files except when asked to fix a file in place.

**Input.** The draft is markdown. For the `issue` profile the first line `# <title>` is the title
and the rest is the body; without that line the whole draft is body and the title is not checked.
Context (the existing thread, the report, the facts the text may use) comes from the conversation,
or from a file named in the request. The check never needs context.

## The check command

`tone check --profile <name> [--audience internal|external] [--lang de|en] [--json] <file|->`

Deterministic, no network, no model. Exit 0 clean, 1 findings, 2 usage error. Decides:

- length limits from the profile frontmatter (characters, words, sentences, bullets)
- banned characters and phrases from the base and the profile, per language
- type prefixes in titles, trailing periods, heading levels, tables, emoji
- for `external`: paths, IPs, stack-trace and log-line shapes, branch and commit shapes, code spans,
  and URLs. A URL to an obviously internal host (localhost, bare IP, single-label host, `.local`,
  `.internal`, `.lan`, `.corp`) is an error; any other URL is a note the review judges, because the
  check cannot know which domains are public without setup.
- for every audience: token, key and password shapes; email addresses and phone numbers
- mixed `du` and `Sie` in German text

It reports; it never rewrites.

## Layout

```
plugins/tone/
  .claude-plugin/plugin.json
  README.md
  bin/tone                                   # runs lib/tone.py
  lib/tone.py                                # the check, Python 3.9+, stdlib only
  skills/write/SKILL.md
  skills/write/references/base.md           # the TONE-0xx rules and the phrase lists
  skills/write/references/profiles/issue.md
  skills/write/references/profiles/comment.md
  skills/write/references/profiles/changelog.md
  tests/test_tone.py
  evals/<case>/prompt.md, evals/<case>/graders/*.md
```

Registered in `.claude-plugin/marketplace.json` and the root README table.

## Evals (at least)

- German comment on a bug that pastes a stack trace and a file path, audience external.
- English issue with filler, a `[Bug]` prefix and a guessed cause.
- A changelog line that names another customer and an internal service.
- An internal comment where a commit hash and a function name are fine and must survive.
- A German thread already in `du`, reply must stay `du` although audience is external.
- An `ok` draft that must come back unchanged (no over-editing).
- Fires: Claude drafts a Linear comment for a teammate. Stays quiet: a plain chat answer to the user.
- A rules file in context raises the comment limit; the finding shows under Dismissed.

## Decisions made by me (check these)

- Length limits: title 70 chars, issue body 120 words, comment 60 words, changelog 100 chars.
- Default audience is `external` when unknown.
- Precedence: request > rules files > profile > base.
- Findings capped at 7 per review.
- Rule IDs `TONE-0xx` in the plugin; `TONE-1xx` left free for users' own rules files.
- Profiles live only in the plugin in 0.1.0; a user adjusts them through rules files, not by
  replacing profile files.
- The review may overrule a check finding only with a named higher source, shown under Dismissed.
- The skill fires on its own whenever Claude drafts text for someone other than the user; no hooks.
- External URLs: internal-looking hosts are errors, other URLs are left to the review's judgement.
- Issue title is the first `# ` line of the draft.
- Only the check is byte-repeatable; the review is a fixed ordered checklist, graded on outcomes.

## Left to the builder

- Script language: no runtime dependencies; node like `rulebook` or Python stdlib like
  `paperwork`, whichever keeps tests simplest.
- The exact phrase lists, as long as they cover German and English and stay in the profile and base
  files, not in code.
- Wording of the skill and README, following the rules it enforces.
