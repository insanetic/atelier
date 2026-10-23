---
audience_default: external
title_max_chars: 70
body_max_words: 120
heading_levels: [2]
tables: false
bold_max: 1
---

# Profile: issue

**Reader:** the team, the product owner, a teammate who picks it up months later, and maybe a
customer on the customer platform. Titles end up in changelogs.

**Shape:** a draft starts with `# <title>`; everything after it is the body. The sections inside the
body are the caller's choice, not this profile's.

## Title (TONE-060 to TONE-062, check)

- At most 70 characters. States the outcome or the desired state, specific enough to stand alone in
  a list.
- No type prefix: no `[Bug]`, `Bug:`, `fix:`, `feat(x):`. Labels carry the type.
- Sentence case, no trailing period.
- English: imperative verb ("Keep line breaks in exported invoice notes").
- German: noun phrase or infinitive ("Zeilenumbrüche im Rechnungsexport erhalten").

## Body (TONE-063, TONE-043, check)

- At most 120 words, not counting checklist lines (`- [ ]`, `- [x]`).
- `##` headings only. Short bullets. No tables unless the content is a table. At most one bold span.
- Plain facts the reader needs to act. No history of how it was found, no conversation transcript.

## Examples

Bad:

```
# [Bug] Export kaputt – wahrscheinlich wegen dem neuen Parser in src/export/pdf.ts
```

Good:

```
# Zeilenumbrüche im Rechnungsexport erhalten

## Problem
Mehrzeilige Notizen erscheinen im PDF-Export in einer Zeile.
```

Bad:

```
# Fix: the dashboard is not working seamlessly for Acme anymore
```

Good:

```
# Show revenue widgets for accounts without a currency
```
