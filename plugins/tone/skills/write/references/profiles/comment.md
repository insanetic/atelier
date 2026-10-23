---
audience_default: external
body_max_words: 60
max_sentences: 3
max_bullets: 4
heading_levels: []
tables: false
bold_max: 0
---

# Profile: comment

**Reader:** whoever reads the issue it sits on, which may include a customer.

## Rules (TONE-063 to TONE-065, TONE-043, check)

- At most 60 words: at most 3 sentences, or a lead sentence and at most 4 bullets.
- One purpose: progress, decision, question, blocker or outcome. A second topic is a second comment,
  or a new issue.
- No headings, no tables, no bold.
- Does not repeat the issue's title or description; it adds what is new.
- A question names who must answer and what exactly is needed.

## Examples

Bad:

```
Hallo zusammen, kurzes Update: Ich habe mir das angeschaut und grundsätzlich scheint das Problem
im Cache zu liegen (siehe `CacheService.invalidate()`). Ich denke, das sollte jetzt behoben sein.
Viele Grüße
```

Good:

```
Behoben: Der Export enthält neue Rechnungen jetzt sofort, nicht erst nach einer Stunde.
```

Bad:

```
Thanks for reporting! We looked into this and it's worth noting that the sync is not just slow but
also fails sometimes. We'll probably ship a fix soon.
```

Good:

```
Decision: we keep the hourly sync and add a manual "Sync now" button. Hourly is enough for the
reports; the button covers urgent cases.
```
