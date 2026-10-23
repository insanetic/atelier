# Tone

Copy to `~/.claude/rules/tone.md` (every project) or `.claude/rules/tone.md` (one project). Claude Code loads
it in every session. Keep TONE-100; change or drop the rest. Where a project's tone rules and these differ, the
project's win.

### TONE-100 [MUST] Text for other people is written with the tone:write skill

Text that someone other than me will read (issues, comments, replies, changelog lines, emails) is always
written with the tone:write skill: load it before drafting, in any language.

- Bad: a Linear comment drafted and posted without loading the skill.
- Checked by: review

### TONE-101 [MUST] German text for customers uses Sie unless the thread already uses du

- Good: "Bitte exportieren Sie die Rechnungen erneut."
- Bad: "Bitte exportier die Rechnungen erneut." in a new customer thread.
- Checked by: review

### TONE-102 [SHOULD] Comments on team-only projects may be up to 100 words

Engineers want the full status in one comment. Outweighed when the comment is visible to a customer.

- Bad: a status cut to 60 words that drops the retry behaviour.
- Checked by: review
