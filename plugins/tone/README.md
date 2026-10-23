# tone

A [Claude Code](https://claude.com/claude-code) **plugin** for text that other people read: issues, comments,
changelog lines. It keeps that text short, specific and safe for its reader, in German or English. Part of the
[atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install tone@atelier
```

Call it with `/tone:write <draft, notes or file> [issue|comment|changelog] [internal|external]`, or let it
run every time (below).

### Turning it on for every text

Claude does not reliably pick this skill on its own: asked to "write a comment", it writes one itself. In
tests the skill fired in none of the runs without a rule and in every run with this line in
`~/.claude/rules/tone.md` (or a project's `.claude/rules/`). [`examples/tone.md`](examples/tone.md) is the
ready-to-copy rules file: this line plus two sample overrides, in a format `rulebook check` accepts.

```bash
cp plugins/tone/examples/tone.md ~/.claude/rules/tone.md
```

The line itself:

```markdown
Text that someone other than me will read (issues, comments, replies, changelog lines, emails) is always
written with the tone:write skill: load it before drafting, in any language.
```

The line is yours, not the plugin's: the plugin installs nothing and names no other plugin.

---

## What it does

- **Profiles** say who reads a kind of text and what fits: `issue`, `comment`, `changelog`. Adding a kind,
  such as `email`, is one more file in `skills/write/references/profiles/`.
- **The base** applies to every profile: only known facts, nothing that must never be written, one language,
  one form of address, no filler and no AI tells. Every rule has an ID (`TONE-001` …) that findings cite.
- **`tone check`** decides what a machine can, the same way every time.
- **The skill** judges the rest and returns the revised text, ready to paste. It never posts anything.

| | `issue` | `comment` | `changelog` |
|---|---|---|---|
| Reader | team, product owner, maybe a customer | same as the issue | customers, always |
| Length | title ≤ 70 characters, body ≤ 120 words (checklists not counted) | ≤ 60 words, ≤ 3 sentences or ≤ 4 bullets | one line, ≤ 100 characters |
| Format | `##` headings, short bullets, ≤ 1 bold | no headings, tables or bold | plain line, no issue IDs |

### Never written

In any text: secrets, personal data the reader does not need, other customers, blame, how the text or the
work was made (AI, agents, tools), open security weaknesses, internal commercial detail.

For an external reader also: code, paths, function names, branches, commits, stack traces, log lines, hosts
and IPs. An internal reader gets only the identifiers needed to act.

The audience is `external` unless the caller says otherwise or the context makes it plain.

### Language and address

The reply follows the language of the thread; new text follows the request. `du` or `Sie` comes from the
thread, how the reporter wrote, or what you said; when nothing tells, `Sie` for external readers and `du`
for internal ones. A text never mixes them.

---

## `tone check`

On the `PATH` while the plugin is enabled. Python 3.9+, no dependencies, no network.

```bash
tone check --profile comment [--audience internal|external] [--lang de|en] [--json] <file|->
tone profiles
```

Exit 0 when there is no error (notes may remain), 1 with errors, 2 on a usage error. It reports; it never
rewrites. It decides lengths and formatting from the profile, filler, hedges and AI tells from the phrase
lists in `base.md` (German and English), secret and token shapes, emails and phone numbers, technical
internals and links in external text, and mixed `du` and `Sie`.

A link to an obviously internal host (localhost, an IP, `.internal`, `.corp` …) is an error. Any other link is
a note: the check cannot know which domains are public, so the review decides.

---

## Your own rules

The plugin ships defaults and installs nothing. To change them, write a rules file: `~/.claude/rules/tone.md`
for every project, `.claude/rules/tone.md` for one. Claude Code loads both in every session; the review ranks
them above the profile and the base. Claude Code does not rank a global rule against a project rule, so say
in the global file that a project's tone rules win.

The entry format below is the [rulebook](../rulebook) one, so `rulebook check` accepts it; `TONE-1xx` is
free for your rules.

```markdown
### TONE-102 [SHOULD] Comments on team-only projects may be up to 100 words

Engineers want the full status in one comment. Outweighed when the comment is visible to a customer.

- Bad: a status cut to 60 words that drops the retry behaviour.
- Checked by: review
```

The check never reads rules files, so its output stays the same; the review lists any finding it set aside
under **Dismissed**, with the rule that allowed it.

---

## Using it from other plugins

Nothing names this plugin and this plugin names nothing. A skill that writes text for others says, in
general terms, "if a writing-style review is available, run the draft through it before posting". With
`tone` installed, Claude combines them; without it, nothing breaks.

---

## Layout

```text
plugins/tone/
├── .claude-plugin/plugin.json
├── bin/tone                       # runs lib/tone.py
├── lib/tone.py                    # the check
├── skills/write/
│   ├── SKILL.md
│   └── references/
│       ├── base.md                # TONE-0xx rules and the phrase lists
│       └── profiles/              # issue.md, comment.md, changelog.md
├── examples/tone.md               # rules file to copy into ~/.claude/rules/
├── tests/test_tone.py
└── evals/                         # one case per scenario, graded with and without the plugin
```

## Develop

```bash
python3 -m unittest discover -s plugins/tone/tests
claude plugin validate --strict plugins/tone
claude plugin eval plugins/tone --runs 2 --judge-model sonnet
```
