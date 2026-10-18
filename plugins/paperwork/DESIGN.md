# paperwork: design

Version 0.3.

## What it is

An archive for business documents (invoices, credit notes, receipts and what looks like them) for one or more
legal entities. Files are dropped into an inbox in any format, any language (German and English first), for any
entity. They are read, checked, named by one convention, filed into one folder structure and indexed into CSV.
Nothing is ever deleted.

## Goals

- **Deterministic where it can be.** One tested engine does every file operation, check and export. The same
  archive gives byte-identical exports.
- **Frozen extraction.** Reading a scan is the one step that is not deterministic. Its result is checked, stored
  with evidence and never recomputed unless asked, so a rerun changes nothing.
- **More deterministic over time.** E-invoices are parsed from their XML. A vendor seen once and confirmed gets a
  template, and its next documents are extracted by the engine alone.
- **Nothing lost.** No delete path exists. Every move is journaled and can be undone. Originals are never
  modified.
- **Checked, not trusted.** A document is filed only when its numbers reconcile and its entity is known;
  everything else waits in review.

## Not in this version

- Bank import and a paid / open status. A list is matched on demand, nothing is stored.
- A DATEV export (decided once we know whether the accountant uses DATEV).
- A pane or band in Claude Code.
- Background watching of the inbox; it is processed when the skill runs.
- Mail import.

## The archive

```text
<root>/                                   # e.g. OneDrive/Belege; $PAPERWORK_HOME overrides
├── _inbox/                               # drop anything here
├── _review/                              # failed a check, or entity/type unclear
├── _duplicates/                          # linked to their original, never deleted
├── _paperwork/
│   ├── config.json                       # entities, classes (fields, required, checks, name and folder templates), categories, tolerances
│   ├── rules.json                        # archive rules; rules/<user>.json holds one person's
│   ├── vendors.json                      # counterparties: aliases, VAT IDs, IBANs, templates
│   ├── docs/<sha256>.json                # one record per document: the source of truth
│   ├── derived/<sha256>/                 # text layer, OCR text, embedded XML, page renders
│   ├── journal.jsonl                     # every move, append-only
│   └── lock                              # one writer at a time
├── <entity-slug>/<YYYY>/in/              # received (Eingangsrechnungen)
├── <entity-slug>/<YYYY>/out/             # issued (Ausgangsrechnungen)
└── exports/
    ├── all/*.csv
    └── <entity-slug>/*.csv
```

- **Entity, then year, then direction.** Books, VAT returns and the accountant work per entity and fiscal year;
  in versus out decides the booking.
- **Type lives in the file name, not in a folder.** Folders stay shallow; one folder holds a whole period.
- **No dot folders.** OneDrive and Windows handle `_paperwork` reliably; `.paperwork` is hidden and easy to break.

## The file name

```text
{issue_date}_{type}_{counterparty}_{number}_{gross}{currency}_{id}.{ext}

2026-03-14_inv_telekom_R-88231_49.99EUR_a1b2c3d4.pdf
2026-03-20_cn_amazon-eu_DE-5521-07_-12.50EUR_9f3e0c11.pdf
2026-04-02_inv_mueller-baustoffe_2026-0412_1190.00EUR_04be77d2.xml
```

| Part | Rule |
|---|---|
| `issue_date` | ISO 8601 issue date (Rechnungsdatum) |
| `type` | `inv`, `cn` (credit note, Storno), `rcpt`, `rem` (reminder), `notice` (Bescheid), `oc` (order confirmation), `quote`, `contract`, `other` |
| `counterparty` | Slug from `vendors.json`: the seller for `in/`, the buyer for `out/` |
| `number` | Document number made safe: `/ \ : * ? " < > \|` and spaces become `-`; `-` when there is none |
| `gross` | Gross amount, dot decimal, two places, negative for credit notes |
| `currency` | ISO 4217 code |
| `id` | First 8 hex characters of the file's SHA-256 |

- ASCII only, lowercase slugs: `ä ö ü ß` become `ae oe ue ss`, so macOS (NFD) and Windows (NFC) agree and
  OneDrive makes no conflict copies.
- The `id` makes clashes impossible and ties a file found anywhere back to its record.
- The full path stays under 250 characters; a long number or slug is cut, never the date, amount or id.
- The name is a function of the record. Changing a confirmed field plans a rename; nothing else does.

## A document record

`_paperwork/docs/<sha256>.json`. The SHA-256 of the file's bytes is the document's identity; a rename or move
never changes it.

```json
{
  "id": "a1b2c3d4…",
  "status": "filed",
  "path": "acme-gmbh/2026/in/2026-03-14_inv_telekom_R-88231_49.99EUR_a1b2c3d4.pdf",
  "original_name": "Rechnung_März.pdf",
  "first_seen": "_inbox/Rechnung_März.pdf",
  "media": "pdf-text",
  "entity": "acme-gmbh",
  "direction": "in",
  "doc_type": "inv",
  "fields": {
    "issue_date":     {"value": "2026-03-14", "source": "template:telekom", "evidence": {"page": 1, "text": "Rechnungsdatum 14.03.2026"}},
    "seller":         {"value": "telekom", "source": "template:telekom"},
    "invoice_number": {"value": "R-88231", "source": "template:telekom"},
    "net":            {"value": "41.92", "source": "template:telekom"},
    "gross":          {"value": "49.99", "source": "template:telekom"}
  },
  "tax": [{"rate": "19", "net": "41.92", "tax": "7.97"}],
  "lines": [],
  "lines_status": "none",
  "checks": [{"id": "net_plus_tax_is_gross", "result": "pass"}],
  "duplicate_of": null,
  "related": [],
  "tools": {"engine": "0.3.0", "pdftotext": "24.08.0"}
}
```

### Fields

| Field | Required for `inv`/`cn` | Notes |
|---|---|---|
| `issue_date` | yes | |
| `service_period` | no | Leistungszeitraum: start and end, or one date |
| `due_date` | no | |
| `seller` | yes | Vendor slug, plus the name, address, VAT ID and tax number as printed |
| `buyer` | yes | As printed; resolves to `entity` for `in` |
| `billing_address` | yes | As printed, plus parsed street, postcode, city, country |
| `invoice_number` | yes | As printed |
| `currency` | yes | |
| `net`, `tax[]`, `gross` | yes | Exact decimals as strings; `tax[]` per rate |
| `reverse_charge` | no | §13b / intra-EU, from the text or the XML |
| `iban`, `payment_method` | no | |
| `category`, `tags` | no | From `config.json`; can be defaulted per vendor |
| `lines[]` | no | Description, quantity, unit, unit price, net, tax rate |
| `lines_status` | — | `complete` (lines sum to net), `partial`, `none` |
| `related` | — | E.g. a reminder points to its invoice, a credit note to what it corrects |

Every field has a `source`: `xml`, `template:<vendor>`, `claude`, or `user`. Fields from `claude` carry evidence
(page and the printed text), and the engine checks that the text appears in the document's derived text.

### Statuses

`new` → `extracted` → `ok`, `unconfirmed` or `review` → `filed`. Also `duplicate` and `missing` (the file is gone
from where the record says; the record stays).

## Classes and rules

A **class** is the one place that decides a document type's fields, checks, file name and folder. The
built-ins (`inv cn rcpt rem notice oc quote contract other`) reproduce the 0.1.0 names and folders;
`classes` in `config.json` is shallow-merged over them. A proposal's `doc_type` must be a class key.
Every rendered path is checked before a move, live and never from stored checks: `path:folder` (an empty
segment, or one starting with `_` or `.`), `path:name` (an empty name, a leading `.`, or a slash) and
`path:length`. They send the document to review and `accept` refuses them. `apply` also refuses a plan
whose target lies outside the archive or in an engine folder other than `_review/` and `_duplicates/`.

**Rules** set values on documents that match (`when`: counterparty, VAT ID, text, regex, doc type,
entity). There are two layers: `_paperwork/rules.json` for the archive and `_paperwork/rules/<user>.json`
for one person (`PAPERWORK_USER`).

- The archive layer is applied first; the user layer only fills what is still open.
- The most specific rule (most `when` keys) wins. A tie with different values is `rule:conflict` and the
  document goes to review.
- A person's edit (`paperwork set`) beats a rule and clears a conflict on that field.
- Rules are applied when fields are set (extract, record, set) and saved with a log. Only
  `paperwork rules apply` re-applies them to documents already recorded. `rules test` previews
  without writing; its `--file` stands in for `rules.json`. Keep that draft outside
  `_paperwork/rules/`, since a file there becomes a user layer.
- A rule that sets `fields.<name>` names its class with `set.doc_type` or `when.doc_type`. A rule
  the document's data cannot take (a class without the proposal's fields) is a `rule:conflict`.

A document ends in one of three outcomes:

| Outcome | Meaning |
|---|---|
| `ok` / `filed` | No check failed (warnings do not block) and a rule, a template, XML or a person decided the class |
| `unconfirmed` | Filed, but Claude recorded it and classified it alone or introduced a new counterparty. `paperwork confirm` settles it |
| `review` | A check failed or a rule conflicts. Held back until a person decides |

## Reading a document

The engine tries the most deterministic route first and records which one it used:

1. **E-invoice XML.** XRechnung (UBL or CII) as an `.xml` file, or ZUGFeRD/Factur-X embedded in a PDF
   (extracted with `pdfdetach`). Parsed by the engine. For an e-invoice the XML is the legal original.
2. **Vendor template** on the PDF's text layer (`pdftotext -layout`), when the counterparty is recognised.
3. **Claude** reads the text layer, or the OCR text plus page images for scans and photos (`tesseract -l deu+eng`),
   and writes its proposal to a JSON file; `paperwork record` checks and stores it.

OCR text, page renders and extracted XML are stored under `derived/` and reused, so a new tesseract version
cannot change an archived document.

## Checks

Money is exact decimal throughout; the rounding tolerance is in `config.json` (default 0.01 per tax rate).

- Net + tax = gross, per rate and in total.
- Tax = net × rate, within the tolerance.
- Lines sum to net, when lines are given (sets `lines_status`).
- Credit notes are negative; invoices are not.
- The issue date is a real date, not in the future, not before the configured start year.
- VAT ID format per country, with the German check digit; IBAN mod-97; ISO currency code.
- The entity is exactly one: the buyer (for `in`) or the seller (for `out`) matches exactly one entity by VAT ID,
  tax number, name variant or address. None or two goes to review.
- Every quoted piece of evidence appears in the document's text.
- **§14 UStG mandatory content** (Pflichtangaben) for `in` invoices: missing items are reported in `issues.csv`,
  because they put the input tax deduction at risk. This is a warning, not a block.

A failed check sends the document to `_review/`. Warnings are filed with the document and listed in `issues.csv`.

## Duplicates

| Kind | Rule | Result |
|---|---|---|
| Exact | Same SHA-256 | Second copy to `_duplicates/`, `duplicate_of` set |
| Same document | Same entity, counterparty, type and normalised number, same gross | To `_duplicates/`, `duplicate_of` set; the better source wins (XML > text PDF > scan) |
| Suspected | Same counterparty, issue date and gross, no number on one side | To review; never decided automatically |

OneDrive conflict copies (`name-MacBook.pdf`) fall out as exact duplicates.

## Moves, the journal and undo

- Every change of location is a **plan** first (`plan.json`: from, to, sha256), shown before it is applied.
- `apply` re-hashes each source, refuses if a target exists, moves, and appends to `journal.jsonl`.
- `undo <journal id>` moves files back, checking each hash.
- A move to another volume copies, verifies the hash and leaves the source in place, reported as `copied`.
- Moves happen only inside the archive root, or from an adopted folder into it.
- There is no code that deletes or overwrites a file. Bytes of an original are never written.
- A lock file stops a second writer, e.g. the engine running on two machines over OneDrive.

## Vendors and templates

`vendors.json` holds each counterparty: slug, name variants, VAT IDs, IBANs, default category, and optionally a
template.

A template is a set of anchored patterns on the text layer, one per field, with a parser (`date_de`, `date_en`,
`amount_de`, `amount_en`, …). Claude writes it after a vendor's first document is confirmed. The engine saves it only
when `paperwork template test <vendor>` reproduces the confirmed values of every confirmed document of that vendor
exactly. A template that fails on a new document sends it to Claude extraction, not to review, and the failure is
reported so the template can be fixed.

## CSV exports

Always regenerated from the records, in stable sort order (entity, issue date, id), so the same archive gives
byte-identical files.

| File | One row per |
|---|---|
| `documents.csv` | document: every field above, path, status, sources |
| `lines.csv` | line item, keyed by document id |
| `vat_summary.csv` | entity × month × direction × tax rate: net, tax, gross |
| `vendors.csv` | counterparty: totals per entity and year |
| `issues.csv` | open problem: review reasons, warnings, missing files, suspected duplicates |
| `class-<key>.csv` | document of a class that declares fields: id, entity, counterparty, issue date, status, confirmed, path, then the fields |

Two dialects: canonical (UTF-8, `,`, dot decimal, ISO dates) and `--dialect de` (UTF-8 with BOM, `;`, decimal
comma) for German Excel.

## The engine: `paperwork`

Python standard library, run inside a Docker image (`docker/Dockerfile`: the base image pinned by digest, plus
poppler and tesseract with `deu` and `eng`). Nothing is installed on the host. `bin/paperwork` builds the image once,
then runs each command with `--network none`, the caller's uid, the engine mounted read-only and only the archive
root mounted, at the same path. So the engine can only see and change the archive, and documents never leave the
machine from inside it. Every record stores the engine, poppler and tesseract versions it was read with.

Because only the root is mounted, everything the engine touches is inside it: proposals and templates are written
to `_paperwork/`, and existing folders are brought in by making them the root or copying them into `_inbox/`.

```bash
paperwork init <root>                    # layout and config
paperwork doctor                         # tools, config, lock
paperwork ingest [--adopt <folder>]      # hash, register, exact duplicates, text/OCR/XML, templates
paperwork pending                        # what needs Claude: documents without fields, with their derived text
paperwork schema                         # the proposal format
paperwork record <id> fields.json        # check a proposal, store it as ok or review
paperwork set <id> field=value ...       # a user's correction, recorded in the record's edits
paperwork confirm <id> [<id>...]         # confirm what Claude classified alone
paperwork rules test [--file f]          # preview rules (f stands in for rules.json), writes nothing
paperwork rules apply                    # re-apply rules to documents a person did not set
paperwork accept <id> <check> --reason   # waive one check, recorded with its reason
paperwork reextract <id>                 # drop the fields so it is read again (kept in history)
paperwork list [--status s] | show <id> | status
paperwork plan [--out plan.json]         # renames and moves for every ok document
paperwork apply plan.json                # move, journal
paperwork undo <journal-id>
paperwork template test|set <vendor> [template.json]
paperwork vendors | vendor <slug> merge|rename|category|alias <value>
paperwork export [--dialect de]
paperwork verify                         # every file present, every hash matches, records consistent
```

Exit codes: 0 ok, 1 a check failed, 2 usage, 3 needs review, 4 locked, 5 Docker or tools missing.

`ingest` also retries the XML and template routes for registered documents that are still unread, so a template
saved now reads the vendor's pending documents on the next `ingest`. Duplicates are not a command of their own:
they are recomputed with every change and show as status `duplicate` or a `duplicate:*` check.

## Skills

| Skill | Job |
|---|---|
| **setup** | Asks for the entities (names, VAT IDs, tax numbers, addresses), categories and start year; writes `config.json` |
| **inbox** | The main loop: `ingest` → extract what the engine could not → `record` → `dupes` → show the plan → `apply` → `export`. Reports filed, in review and duplicates |
| **review** | Works through `_review/` with the user; offers a template for each vendor confirmed |
| **catalog** | Brings existing folders in: adopt in place (index only), or reorganise into the structure, always as a plan |
| **ask** | Answers questions from the CSVs ("Telekom 2025 per entity", "input tax Q3"), with DuckDB when installed |
| **match** | Reads a list of payments, writes the list JSON with its evidence, runs `match`, presents missing, unsure, combined and found |

## Notes

`notes/<YYYY>/<id8>.md` (`notes/undated/` without a date) is a view of the record for Obsidian. The frontmatter
and table are rebuilt from the record; everything below `## Notes` belongs to the person and is carried across
rebuilds and moves. The `id` is `pw:<id8>`, which is how a note finds its document after a move. A file is the
engine's only at `notes/(<YYYY>|undated)/<id8>.md`, as UTF-8, with the same id on an `id:` line in its leading
`---` frontmatter. Line ends may be CRLF. Every other file under `notes/` is never written over or removed, and
only empty `<YYYY>` and `undated` folders are removed. These are left alone and reported in `kept`: a file at a
note's path that is not ours or not UTF-8, a note without a `## Notes` line, an orphan with text, and a note
whose target already holds a file the scan did not see (a linked folder, or a name differing only in case). The guard
lets Claude write under `notes/`, and the entity slugs `notes` and `matches` are reserved.

## List matching

`match` takes a list in `_lists/` and a JSON Claude wrote from it in `_paperwork/lists/`. Claude reads, the engine
decides. Each item carries the evidence as printed, and the engine checks it against the source's text like a
document proposal: absent text is fatal, except on OCR sources where it is a warning, and evidence that does not
read as the value is always fatal. Date and amount evidence must not touch a digit on either side, checked on the
text with whitespace collapsed; whitespace may differ where a number meets a letter or symbol, never inside a
number. An amount starting or ending in a three-digit group must not continue a number through `.`, `,` or `'`. Matching is by amount, vendor (whole words of the company name, one vendor only)
and a date window (30 days before, 7 after), then combinations of 2 to 6 documents of one vendor and one sign
within 3 days. Results are `found`, `combined`, `unsure` and
`missing`, with up to 5 suggestions. The output is `exports/matches/<name>.csv`. Choices are not stored: the engine
holds no paid or open state.

## The hook

A PreToolUse hook on Bash, Write, Edit, MultiEdit and NotebookEdit (`hooks/guard.py`, host `python3`, standard
library) refuses `rm`, `mv`, overwriting `cp`, `trash`, `unlink`, redirects, in-place edits, `find -delete` and
`git clean` that touch an archive, and edits of anything there except `_paperwork/config.json`,
`_paperwork/rules.json`, `_paperwork/rules/`, `_paperwork/proposals/`, `_paperwork/templates/`,
`_paperwork/lists/` and `notes/`. `paperwork` itself is allowed, and so is `cp -n` into `_inbox/` and `_lists/`. It makes "never delete"
enforced, not promised, for the shell commands it can parse.

## Testing

- Engine unit tests on synthetic fixtures (`bin/paperwork __test`, inside the image): text PDFs, scans, a ZUGFeRD PDF and an XRechnung, credit notes,
  several tax rates, reverse charge, German and English layouts, exact and same-document duplicates, a OneDrive
  conflict copy.
- Real invoices never enter git. A local run against them reads `$PAPERWORK_PRIVATE_FIXTURES`, outside the repo.

## Open

- Does the accountant use DATEV? Decides the DATEV export.
- Evals in `evals/` like data-max (an inbox run, a review, a template).
