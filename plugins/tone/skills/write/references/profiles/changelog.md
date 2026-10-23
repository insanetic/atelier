---
audience_default: external
audience_fixed: external
single_line: true
max_chars: 100
heading_levels: []
tables: false
bold_max: 0
no_issue_ids: true
---

# Profile: changelog

**Reader:** customers. Always external, whatever the caller passes.

## Rules (TONE-066 to TONE-069, check)

- One line, at most 100 characters.
- What changed for the user, in their words. Not how, not why internally.
- No issue IDs (`ABC-123`, `#42`), no internal project, service or team names.
- Past tense or present state, the same choice across one release.
  - English: "Exported invoices keep line breaks in notes."
  - German: "Exportierte Rechnungen behalten Zeilenumbrüche in Notizen."

## Examples

Bad: `Fixed IND-412: refactored the PDF renderer in export-service so newlines aren't stripped`

Good: `Exported invoices keep line breaks in notes.`

Bad: `Nahtlose Synchronisierung für Acme und alle anderen Kunden – jetzt noch schneller!`

Good: `Die Synchronisierung läuft jetzt alle 15 Minuten statt stündlich.`
