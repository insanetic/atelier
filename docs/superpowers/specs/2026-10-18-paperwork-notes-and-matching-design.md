# paperwork 0.3.0: document notes and list matching

## Intent

Two small additions to paperwork:

1. **Notes.** One markdown file per document, generated from the records, so the archive opens
   in Obsidian and atlas can link to a document. A person can add notes to it, and these are kept.
2. **List matching.** You get a list from your accountant, a bank or a card statement, or anywhere
   else. Each line has a date and an amount, and sometimes a vendor. paperwork tells you, line by
   line, which invoice covers it, which several invoices cover it together, or that nothing does.
   For a missing line it shows the invoices worth checking.

The use case is the accountant closing a month or a year and asking for the missing invoices.

## Naming

The files are called **notes**. That is Obsidian's word ("Obsidian stores your notes as
Markdown-formatted plain text files in a vault", obsidian.md/help/data-storage), and the atlas
plugin's word (`notes/`, "one folder of markdown notes"). "Card" came from Zettelkasten index cards.
Neither tool uses it, so it was the wrong word. "Sidecar" is the technical term for a metadata file
that sits next to its source file. These notes live in their own folder, so that word doesn't fit
either.

## Goals

- `paperwork notes [--rebuild]` writes `notes/<YYYY>/<id8>.md` for every document with read data.
  It writes only files whose content changed, the output is deterministic, and `export` runs it too.
  `--rebuild` rewrites every note.
- Each note has flat frontmatter: id, title, date, entity, counterparty, class, number, gross,
  currency, status and file (an archive-relative link to the PDF). Every scalar is a quoted string,
  because DuckDB's YAML reader turns an unquoted `NO` into false and drops leading zeros. The body
  holds the main fields and a `## Notes` section. Everything below `## Notes` is the person's and
  survives a rebuild.
- A note whose document no longer exists is removed, unless someone wrote below `## Notes`. Then it
  is kept and reported.
- `paperwork match <items.json> [--from DATE --to DATE] [--entity E]` checks every line and writes
  `exports/matches/<name>.csv`, plus a short summary for the chat.
- The `match` skill: Claude reads whatever file you give it (PDF, CSV, XML, a scan, an email text)
  into `_paperwork/lists/<name>.json`. Each item is `{date, amount, vendor?, text}` and carries the
  evidence it was read from. The engine checks that evidence against the file's text, as it does for
  invoices. Then it runs `match`. Running it again after new invoices arrive re-checks the same
  list.

## Matching

Amounts compare as the absolute gross, to the cent. Dates use a window of 30 days before the line's
date to 7 days after it. Both window values can be changed with `--before` and `--after`. With
`--from/--to`, only documents in that range count. When the line names a vendor, only that vendor's
documents count. The vendor is compared through the existing vendor aliases.

Each line gets one result:

| Result | When |
|---|---|
| `found` | exactly one document in the window has the amount |
| `combined` | no single document has it, but 2 to 6 documents from one vendor, issued within 3 days of each other, add up to it exactly. This is the Amazon case. |
| `unsure` | more than one document or more than one combination fits. All of them are listed, and you pick. |
| `missing` | nothing fits. Up to 5 suggestions follow: documents from that vendor between 90 days before and 30 days after the date, closest amount first. Without a vendor, documents within 3% of the amount. |

One document covers at most one line per list. When two lines want the same document, both become
`unsure`. The CSV has: line, date, amount, vendor, result, documents (archive paths), suggestions.

## Non-goals

- Bank formats, bank accounts, IBAN matching, or importing payments.
- A stored confirmation state for matches. The person decides in the conversation, and the CSV is
  regenerated each run.
- Hub notes per company or counterparty, list notes, Excel input (save it as CSV), copying the
  found invoices into a folder, a watcher, DuckDB and the UI.

## Anti-goals

- A wrong `found`. When in doubt the result is `unsure`.
- Losing a person's notes.
- Notes becoming a second source of truth. The records stay the truth, and notes are output.

## Builder's freedom

Note body layout, the CSV column order beyond the list above, the subset search algorithm (search
at most 20 candidates per line), and the skill's wording.
