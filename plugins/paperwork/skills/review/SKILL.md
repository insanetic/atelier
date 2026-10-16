---
name: review
description: >-
  Use when documents in the paperwork archive need a decision - "what's in
  review", "fix the invoices that failed", "this invoice belongs to the other
  company", "that's not a duplicate", "the total is wrong", "check the
  issues", or to teach the archive a vendor's layout with a template so its
  invoices are read without Claude. Works through _review and issues.csv with
  the user; every fix is recorded, nothing is deleted.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 0.1.0
---

# Review

`paperwork list --status review` and `exports/all/issues.csv` hold everything open. Each problem
has a check id; `paperwork show <id>` prints the record, the derived text and the page images.

## Workflow

1. Group the open problems by kind and work through them with the user in batches
   (AskUserQuestion, recommended answer first). Look at the document yourself before asking.
2. Settle each one with the engine, never by editing files:

   | Problem | Fix |
   |---|---|
   | `entity`: no or several entities | Ask which entity; `paperwork set <id> entity=<slug>`. If it is a new company, add it with the `setup` skill. |
   | `evidence:*`, `sum:*`, `tax:*` | Read the document again (page images for scans). A misreading: `paperwork set <id> gross=36.98 ...` (dotted keys for nested fields, JSON for lists). The document is wrong: `paperwork accept <id> <check> --reason "..."`. |
   | `duplicate:suspected` | Same counterparty, date and total, no number. Ask; a separate document: `accept <id> duplicate:suspected --reason`. |
   | `duplicate:conflict` | Same number, different totals: usually a corrected invoice. Set `doc_type`/`refers_to`, or accept. |
   | `unsupported` | A HEIC photo, a broken file: ask the user for a PDF or JPEG and drop that into `_inbox`. The original stays in `_review`. |
   | Warnings (`ustg14`, `tax:zero`, `entity:shared-address`) | Explain what is at stake (e.g. input tax deduction needs the §14 UStG items); accept only with a reason. |

   A waived check stays in the record with its reason. `paperwork reextract <id>` drops the fields so
   the document is read again (the old fields stay in its history).
3. `paperwork plan`, `paperwork apply <plan>`, `paperwork export`.

## Vendors

`paperwork vendors` lists counterparties. The same company under two slugs (e.g. a new VAT ID):
`paperwork vendor <slug> merge <into>`. Default category: `paperwork vendor <slug> category hosting`.

## Templates

For a vendor with recurring documents of one layout, write `_paperwork/templates/<slug>.json` and
run `paperwork template set <slug> <file>`. The engine saves it only when it reproduces every
confirmed document of that vendor exactly (doc type, date, number, currency, net, gross, tax,
reverse charge, entity). From then on `paperwork ingest` extracts that vendor's documents itself.

```json
{
  "match": ["Hetzner Online GmbH", "DE812871812"],
  "fixed": {"doc_type": "inv", "currency": "EUR",
            "seller": {"name": "Hetzner Online GmbH", "address": ["Industriestr. 25", "91710 Gunzenhausen"],
                       "vat_id": "DE812871812", "country": "DE"}},
  "fields": {
    "invoice_number": {"pattern": "Rechnungsnummer:\\s*(\\d+)"},
    "issue_date": {"pattern": "Rechnungsdatum:\\s*(\\d{2}\\.\\d{2}\\.\\d{4})", "type": "date"},
    "buyer.name": {"pattern": "^\\s*(\\S.*?)\\s{2,}Tel\\.:"},
    "net": {"pattern": "^\\s*Summe\\s+([\\d.,]+ €)", "type": "amount", "decimal": ","},
    "gross": {"pattern": "^\\s*Summe\\s+[\\d.,]+ €\\s+[\\d.,]+ €\\s+([\\d.,]+ €)", "type": "amount", "decimal": ","},
    "tax": {"pattern": "^\\s*(\\d+) %\\s+([\\d.,]+) €\\s+([\\d.,]+) €", "repeat": true, "type": "amount",
            "decimal": ",", "groups": {"rate": 1, "net": 2, "tax": 3}}
  }
}
```

- Patterns run on `_paperwork/derived/<id>/text.txt` (the layout text) in multiline mode; group 1
  unless `group` is given. `type`: `text`, `date`, `amount` (`decimal` "," or "."), `lines`.
- `repeat` with `groups` builds lists (`tax`, `lines`); `types` sets a type per group.
- `match` strings must identify the vendor: a name plus its VAT ID.
- A template that stops matching a new layout sends that document to Claude, and `ingest` reports
  `template_failed`; fix the template, test it, then `paperwork reextract` and `ingest` again.
