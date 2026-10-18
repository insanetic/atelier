# paperwork

A [Claude Code](https://claude.com/claude-code) **plugin** that keeps a company's (or a person's)
paperwork in one folder. You drop documents into an inbox. They are read, checked, classified,
renamed, filed per entity, deduplicated and indexed into CSV. **Nothing is ever deleted**, and every
move can be undone.

Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install paperwork@atelier
```

Needs **Docker**. Nothing is installed on the machine: the engine runs in a pinned image with
Python, poppler and tesseract (German and English), with no network, and only the archive folder is
mounted. The guard hook runs on the host with the system `python3`.

---

## Getting started

**1. Point it at a folder.** Run `/paperwork:setup` and name the folder, for example
`~/OneDrive/Belege`, a SharePoint library synced to your disk, or Dropbox. It creates the layout
below, and asks once for your entities: each company and the private person, with the name
variants, VAT IDs, tax numbers and addresses that appear on documents. That is how a document finds
its owner later.

**2. Drop documents into `_inbox/`.** Anything: PDFs, scans, phone photos, XRechnung or ZUGFeRD
files, with any file names, in any subfolders. Names are ignored; only the content counts.

**3. Run `/paperwork:inbox`.** One pass does all of it:

- every file is hashed and registered; an exact copy is recorded as a copy, not as a second document;
- the content is read: e-invoice XML first, then a vendor template, otherwise Claude reads the text
  (or the scan and its OCR text) and proposes the fields;
- the engine checks the proposal against the document's own text and arithmetic, decides the entity
  from the billed party, and applies your rules;
- you see the plan: which file goes where under which name. Applying it creates the folders it
  needs, moves and renames the files, and sends the same document received twice to `_duplicates/`;
- the CSV index in `exports/` is rebuilt.

After a pass every document is in one of three states:

| Status | Where | What you do |
|---|---|---|
| `filed` | its entity folder, named by convention | nothing |
| `unconfirmed` | filed too, but Claude classified it alone, or its counterparty is new | confirm it, or correct it (`/paperwork:review`) |
| `review` | `_review/` | a check failed; `/paperwork:review` goes through them with you |

You run the inbox when you want, by hand or on a schedule. Nothing watches the folder in the
background.

**Already have years of documents in folders?** Make that folder the archive root, or copy the
documents into `_inbox/`, and run `/paperwork:catalog`. It indexes them where they are or
reorganises them into the structure, always as a plan you approve first.

## The skills

| Skill | Invoke | Job |
|---|---|---|
| **setup** | `/paperwork:setup` | Creates the archive and records your entities, categories, and optional classes. |
| **inbox** | `/paperwork:inbox` | The main loop: ingest `_inbox/`, read what the engine could not read itself, check, plan, file, export. |
| **review** | `/paperwork:review` | Works through `_review/` and the unconfirmed queue with you; writes rules and vendor templates so a correction happens once. |
| **catalog** | `/paperwork:catalog` | Brings existing folders in: index in place, or reorganise into the structure. |
| **ask** | `/paperwork:ask` | Answers questions from the CSV index ("Hetzner 2025 per entity", "input tax Q2", "contracts ending this year") with the paths of the documents. |
| **match** | `/paperwork:match` | Checks a list of payments (a bank statement, an accountant's list) against the archive and says which lines have no document. |

## The archive

```text
OneDrive/Belege/
├── _inbox/              drop anything here
├── _review/             failed a check or needs a decision
├── _duplicates/         copies and second versions, linked to their original
├── _paperwork/          config.json, rules.json, rules/<user>.json, vendors.json,
│                        one record per document, derived text, journal
├── _lists/              statements and lists you want matched
├── notes/<YYYY>/        one markdown note per document (notes/undated/ when it has no date)
├── <entity>/<YYYY>/in/  received documents (the default folder template)
├── <entity>/<YYYY>/out/ issued documents
├── <entity>/…           any folder a class template defines, e.g. <entity>/contracts/<counterparty>/
└── exports/             all/ and <entity>/: documents, lines, VAT summary, vendors, issues,
                         one class-<key>.csv per class with its own fields; -de variants for German Excel
```

```text
{issue date}_{type}_{counterparty}_{number}_{gross}{currency}_{id}.{ext}
2026-05-24_inv_hetzner-online_084000888874_39.25EUR_fdd7c80c.pdf
2024-02-28_cn_amazon-eu_DE426JLXAEUC_-24.04EUR_0c14567a.pdf
```

The `id` is the start of the file's SHA-256: names never clash, and a file found anywhere leads back
to its record. Names are ASCII only, so OneDrive on macOS and Windows agree.

## Notes

Every document gets a markdown note, `notes/<YYYY>/<id8>.md`, or `notes/undated/<id8>.md` when it has
no date. `paperwork notes` writes them, and `export` does too. Duplicates get none. Open the archive
folder as an [Obsidian](https://obsidian.md) vault and the notes link to the files.

```markdown
---
id: "pw:fdd7c80c"
title: "Hetzner Online inv 084000888874"
date: "2026-05-24"
entity: "acme-gmbh"
counterparty: "hetzner-online"
class: "inv"
number: "084000888874"
gross: "39.25"
currency: "EUR"
status: "filed"
file: "acme-gmbh/2026/in/2026-05-24_inv_hetzner-online_084000888874_39.25EUR_fdd7c80c.pdf"
---
# Hetzner Online inv 084000888874

[[acme-gmbh/2026/in/2026-05-24_inv_hetzner-online_084000888874_39.25EUR_fdd7c80c.pdf]]

| field | value |
| --- | --- |
| gross | 39.25 |
| … | … |

## Notes
```

Everything above `## Notes` is rebuilt from the record. Write below it: that text is yours, and it
survives rebuilds and moves. `paperwork notes --rebuild` regenerates every note. A note whose
document is gone is kept and reported when it has text. A file without a `pw:` id is never touched.
The entity slug `notes` is reserved.

## Matching a list

Put a bank statement or any list of payments into `_lists/` (`cp -n`, never overwrite) and run
`/paperwork:match`. Claude reads the list, writes every line to `_paperwork/lists/<name>.json` with
the text as printed, and the engine checks each line against the list's own text before it matches
anything. `paperwork match <name>` then writes `exports/matches/<name>.csv`: line, date, amount,
vendor, result, documents, suggestions, note.

| Result | Meaning |
|---|---|
| `found` | exactly one document has the amount (vendor and date window agree) |
| `combined` | one set of 2 to 6 documents of one vendor, within 3 days of each other, adds up to the amount |
| `unsure` | several documents or sets fit, a document fits two lines, or the vendor is unknown; you pick |
| `missing` | nothing fits; up to 5 suggestions are listed |

The date window is 30 days before and 7 days after the line (`--before`, `--after`). Suggestions are
the vendor's documents from 90 days before to 30 days after, or documents within 3% of the amount
when the line has no vendor. Narrow a run with `--entity`, `--from` and `--to`. Fees, salaries and
taxes stay in the list; you decide about them. Nothing is stored about your choices.

On a scan, evidence that is not in the OCR text is a warning. Evidence that does not read as the
value is always an error.

## Classes

A class is a document type, and it decides everything about the documents of that type: the
fields, which are required, the checks, the file name and the folder. The built-in classes cover
business mail: `inv` invoice, `cn` credit note or Storno, `rcpt` receipt, `rem` reminder, `notice`
(Bescheid), `oc` order confirmation, `quote`, `contract`, `other`. Their default templates give the
names above.

Add your own, or override a built-in, under `classes` in `_paperwork/config.json`:

```json
{
  "classes": {
    "contract": {
      "fields": {"start": {"type": "date"}, "end": {"type": "date"}, "notice": {"type": "text"}},
      "required": ["issue_date", "seller.name", "fields.start"],
      "name": "{fields.start}_{class}_{counterparty}_{id}",
      "folder": "{entity}/contracts/{counterparty}"
    },
    "payslip": {
      "label": "Payslip",
      "fields": {"employee": {"type": "text"}, "period": {"type": "text"}},
      "required": ["fields.employee"],
      "name": "{issue_date}_{class}_{fields.employee}_{id}",
      "folder": "{entity}/{year}/hr"
    }
  }
}
```

Field types are `text`, `date`, `money`, `number`, `bool` and `choice` (with a `choices` list).
Templates take `{issue_date}`, `{due_date}`, `{service_date}`, `{year}`, `{class}`,
`{counterparty}`, `{number}`, `{amount}`, `{id}`, `{entity}`, `{direction}`, `{category}` and
`{fields.<name>}`. A folder template starts with `{entity}`. After changing a template, `paperwork
plan` shows the renames before anything moves.

The engine checks every rendered path before it moves a file. `path:folder` catches an empty
segment or one starting with `_` or `.`, `path:name` an empty name, a leading `.` or a slash, and
`path:length` a path over 250 characters. These send the document to review and cannot be accepted
away.

## Rules

A rule sets values for every document that matches it, so a correction you made twice is made
automatically from then on.

```json
{"rules": [
  {"id": "hetzner-hosting", "when": {"counterparty": "hetzner-online"},
   "set": {"doc_type": "inv", "category": "hosting"}},
  {"id": "leases", "when": {"text": ["Mietvertrag"]},
   "set": {"doc_type": "contract", "entity": "acme"}}
]}
```

`when` matches on `counterparty`, `vat_id`, `text` (all phrases appear), `regex`, `doc_type` and
`entity`, exactly or by regex, never by loose word matching. `set` can set `doc_type`, `entity`,
`direction`, `category`, `tags` and `fields.<name>` (which needs the class in `set.doc_type` or
`when.doc_type`). Each rule needs a unique `id`.

Rules live in `_paperwork/rules.json` (the archive's) and `_paperwork/rules/<user>.json` (one
person's, chosen by `PAPERWORK_USER`). The archive's rules decide first and a person's rules only
fill what is left. The most specific rule wins, and two equally specific rules that disagree send
the document to review. A correction made with `paperwork set` always beats a rule.

Rules apply when a document is read. `paperwork rules test` shows what the current rules would
change in the archive without writing anything; `rules test --file draft.json` previews a draft
instead (keep drafts in `_paperwork/proposals/`, never in `_paperwork/rules/`, where a file becomes a
live rule layer). `paperwork rules apply` re-applies the rules to every document a person has not
corrected; `paperwork plan` then shows any resulting moves.

## Confirmation

Claude's reading is checked against the document, but a class or a counterparty can still be a
judgement call. So a document Claude recorded is `unconfirmed` when no rule decided its class, or
when Claude introduced its counterparty. It is filed like any other, keeps up to three ranked
alternatives, and waits in `paperwork list --status unconfirmed` until `paperwork confirm <id>...`
or a correction with `paperwork set`. E-invoice XML and template documents are never unconfirmed,
and neither are documents recorded before 0.2.0.

## How a document is checked

Whatever read it, the engine checks:

- the printed evidence appears in the document and means the value (`13. März 2024` is 2024-03-13,
  `2.894,19` is 2894.19), and names, numbers and VAT IDs appear in the text;
- net + tax = gross per rate, tax = net × rate, the lines add up, credit notes are negative;
- the entity follows from the billed party (name, VAT ID), never from the delivery address, and a
  private person at a company address is flagged;
- VAT IDs (with the German check digit), IBANs, currencies, and dates against the archive's start
  year and the day the document arrived;
- the class's required fields;
- §14 UStG mandatory content for German invoices (§33 UStDV for small ones), as warnings.

Accepted fields are frozen in the record; a rerun changes nothing. Exports are regenerated from the
records, sorted, and byte-identical for the same archive.

## The engine: `paperwork`

`bin/paperwork` is on the PATH while the plugin is enabled. It finds the archive from the current
folder, `$PAPERWORK_HOME`, `--root`, or the archive registered by `init`. The skills drive it; you
rarely need it directly.

```bash
paperwork init ~/OneDrive/Belege      # layout + config; registers the archive
paperwork doctor                      # tools, config, lock
paperwork ingest [--adopt]            # register new files; --adopt: everything in the archive
paperwork pending                     # what needs reading (no file names)
paperwork schema                      # the proposal format, with the classes and their fields
paperwork record <id> proposal.json   # check and store; exit 3 = review
paperwork set <id> entity=acme gross=36.98
paperwork confirm <id> [<id>...]      # accept what Claude classified alone
paperwork accept <id> <check> --reason "..."
paperwork list [--status unconfirmed|review|duplicate|...]
paperwork rules test [--file draft.json]
paperwork rules apply
paperwork plan                        # moves and renames, nothing done yet
paperwork apply <plan>                # journaled; never overwrites; copies across volumes
paperwork undo <plan>
paperwork export [--dialect csv|de|both]
paperwork notes [--rebuild]           # one markdown note per document
paperwork match <name> [--entity E] [--from D] [--to D] [--before N] [--after N]
paperwork verify                      # every file present, every hash right, nothing unregistered
paperwork vendors | vendor <slug> merge|rename|category|alias <value>
paperwork template test|set <vendor> [template.json]
```

Exit codes: 0 ok, 1 a check failed, 2 usage, 3 needs review, 4 locked, 5 Docker or tools missing.

## Guarantees and limits

- No code path deletes or overwrites a document. Records, the journal and exports are the engine's
  own files. `apply` refuses a plan whose target would land outside the archive.
- The guard hook denies `rm`, `mv`, overwriting `cp`, redirects, in-place edits, `find -delete` and
  `git clean` that touch the archive, and edits of anything but `config.json`, `rules.json`,
  `rules/`, proposals and templates. It parses shell commands; a script that deletes files from
  inside an interpreter is beyond what a hook can see.
- OCR quality bounds what the engine can verify on scans: evidence that is not in the OCR text is a
  warning there, not an error, and Claude reads the page images.
- One writer at a time (lock file), so two machines syncing the same OneDrive folder cannot both
  write.
- No background watcher and no mail import yet: the inbox is processed when you run it.

## Tests

```bash
plugins/paperwork/bin/paperwork __test    # the engine and guard tests, inside the tools image
```

Fixtures are synthetic (made-up companies and VAT IDs). Real invoices never go into git.
