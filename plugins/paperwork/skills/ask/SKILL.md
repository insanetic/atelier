---
name: ask
description: >-
  Use when the user asks a question about their invoices, receipts, vendors or
  spending in the paperwork archive - "what did we pay Hetzner in 2025",
  "input tax for Q2", "all invoices of Acme GmbH last year", "which invoices
  are in USD", "show credit notes", "what is still in review", "find the
  invoice for the coffee machine". Answers from the CSV index, with the file
  paths, without changing anything.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 0.3.0
---

# Ask

Answer from `exports/` (run `paperwork export` first if the archive changed). Read-only.

| File | Holds |
|---|---|
| `documents.csv` | One row per document: entity, direction, type, dates, counterparty, parties, billing address, number, currency, net, tax, gross, rates, reverse charge, category, status, confirmed, path, warnings |
| `lines.csv` | Line items, keyed by document `id` |
| `vat_summary.csv` | Entity × month × direction × currency × tax rate (ok, filed and unconfirmed invoices, receipts, credit notes) |
| `class-<key>.csv` | Documents of a class that declares fields (`exports/<scope>/`): id, entity, counterparty, issue date, status, confirmed, path, then the class's fields |
| `vendors.csv` | Entity × year × counterparty totals |
| `issues.csv` | Open problems and warnings |

Every document also has a note, `notes/<YYYY>/<id8>.md`, with the user's own text below `## Notes`. Search the notes when the question is about what the user wrote.

`exports/all/` covers every entity; `exports/<entity>/` one. Use DuckDB if it is installed
(`duckdb -c "select ... from read_csv('exports/all/documents.csv')"`), otherwise Python's `csv`.

- Money is exact decimal text; sum with `DECIMAL`, never floats. Never add currencies together:
  group by `currency`.
- Exclude `status` `duplicate` and `review` from totals unless asked; say how many were left out.
  `unconfirmed` documents are filed and count; mention them when their class or counterparty matters.
- Credit notes are negative, so a plain sum is the net spend.
- Give the `path` of every document you cite so the user can open it.
- If the answer needs a field the index does not have, say so instead of guessing from file names.
