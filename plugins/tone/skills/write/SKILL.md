---
name: write
description: >-
  Use whenever you write, draft, formulate, answer or check text that someone other than the user will
  read: an issue or ticket, a comment or reply on one, a changelog or release-note line, a status update,
  an email or a message to a customer or teammate. German requests count too ("schreib einen
  Kommentar", "formulier eine Antwort", "Ticket", "Changelog-Eintrag", "kann das so raus?"). Load it
  before you write the text, not after. It sets the length and format per kind of text, cuts filler,
  greetings, sign-offs and AI tells, keeps out what must never be written (secrets, personal data, other
  customers, blame, code and internals for external readers, guesses stated as facts) and keeps one form
  of address (du or Sie). Not for chat replies to the user, code, commit messages or repository docs.
argument-hint: "<draft or file> [profile: issue|comment|changelog] [audience: internal|external] [language]"
---

# Writing text for other people

The draft is read by someone who was not in this conversation: a teammate, the product owner, maybe a
customer, maybe a changelog. Make it short, specific, consistent and safe for that reader. Cut, reorder
and rephrase; never add a claim that is not in the draft or the context.

## Inputs

```
$ARGUMENTS
```

- **Draft:** the text in the arguments, a file they name, or the text you were about to post. For the
  `issue` profile, a first line `# <title>` is the title and the rest is the body.
- **Profile:** given, or from the text's shape: a title and a body is `issue`, a reply on an issue is
  `comment`, one line about a change for users is `changelog`. If it is honestly two, ask.
  `tone profiles` lists what exists.
- **Audience:** given, or clear from context (a team-only project, an internal note, a customer
  thread). Otherwise `external`.
- **Language:** the language the thread or issue already uses; else the one given; else the language
  of the user's request.
- **Context:** the facts the text may use, and the thread it joins. From the conversation, or a file
  named in the arguments.

Read [references/base.md](references/base.md) and the profile in `references/profiles/<name>.md` before
judging. Rules files in context (`~/.claude/rules/`, `.claude/rules/`) that speak about tone, length,
address or exposure apply too.

**Precedence**, highest first: an explicit instruction in the request, rules files in context, the
profile, the base.

## Steps

1. **Check.** Write the draft to a file in the scratchpad (or use the given file) and run
   `tone check --profile <name> --audience <audience> --lang <de|en> --json <file>`. The `tone` command
   is on the PATH while this plugin is enabled. Every `error` is a finding unless step 3 dismisses it.
   A `note` is for you to judge.
2. **Judge** what the check cannot, in this order, citing the base rule:
   1. Exposure in meaning: another customer named indirectly, blame, an open security weakness,
      commercial detail, an internal tool behind a public-looking link (TONE-012 to TONE-016, TONE-022).
   2. Facts: every claim is backed by the draft or the context; no guess, no promise (TONE-001, 002).
   3. Audience: nothing an external reader cannot use (TONE-020, TONE-044).
   4. Language and address: one language; du or Sie inferred from the thread, how the reporter wrote,
      or what the user said; if none of these tells, `Sie` external, `du` internal (TONE-050, 051).
   5. Shape: outcome first, one topic, no restated title (TONE-040).
   6. Style: plain words, nothing that reads as generated (TONE-041 to TONE-044).
3. **Dismiss** a check finding only when a higher source allows it (a rules file, the request) or when
   the match is plainly not what the rule is about (a company hotline is not personal data, a public
   docs link is fine). Every dismissal is listed with its reason.
4. **Revise.** Fix every finding. The revision is never longer than the draft unless a rule needed
   words, and it never contains a fact the context does not hold. A missing fact becomes a question,
   not a filler sentence.
5. **Re-check** the revised text with `tone check` until it has no error left that you did not dismiss.

## Report

Always this shape, nothing around it:

```
**Verdict:** ok | fixed | needs input
**Findings:**
- TONE-0xx · "quoted phrase" · the fix
**Revised text:**
<the text, ready to paste>
**Questions:**
- <a fact the text needs that the context does not have>
**Dismissed:**
- TONE-0xx · "quoted phrase" · the reason or the rule that allows it
```

- `ok`: no finding; leave out Findings and Revised text. Do not touch a text that is already fine.
- `fixed`: the revised text resolves everything.
- `needs input`: a fact is missing; the revised text holds what is known, the questions hold the rest.
- At most 7 findings, most severe first: exposure, facts, audience, language, shape, style.
- Leave out Questions and Dismissed when they are empty.

When another skill called this review before posting, hand back the revised text and post only that.
When the verdict is `needs input`, ask the user before anything is posted. Never post or send anything
from this skill, and never write files except when asked to fix a file in place.
