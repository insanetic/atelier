# paperwork

A [Claude Code](https://claude.com/claude-code) **plugin** for business documents: drop invoices,
receipts, credit notes and scans into an inbox, and they come out read, checked, named by one
convention, filed per entity, year and direction, deduplicated and indexed into CSV. **Nothing is
ever deleted**, and every move can be undone.

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

## The skills

| Skill | Invoke | Job |
|---|---|---|
| **setup** | `/paperwork:setup` | Creates the archive (e.g. in OneDrive) and records your entities: companies and the private person, with name variants, VAT IDs, tax numbers and every address. |
| **inbox** | `/paperwork:inbox` | The main loop: ingest `_inbox/`, read what the engine could not read itself, record the fields, show the plan, file, export. |
| **review** | `/paperwork:review` | Works through `_review/` and `issues.csv` with you; teaches the archive a vendor's layout with a tested template. |
| **catalog** | `/paperwork:catalog` | Brings existing folders in: index in place, or reorganise into the structure, always as a plan you approve. |
| **ask** | `/paperwork:ask` | Answers questions from the CSV index ("Hetzner 2025 per entity", "input tax Q2") with the paths of the documents. |

## The archive

```text
OneDrive/Belege/
├── _inbox/              drop anything here: PDFs, scans, photos, XRechnung/ZUGFeRD; any names, any subfolders
├── _review/             failed a check or needs a decision
├── _duplicates/         copies and second versions, linked to their original
├── _paperwork/          config.json, rules.json, rules/<user>.json, vendors.json, one record per document, derived text, journal
├── <entity>/<YYYY>/in/  received documents
├── <entity>/<YYYY>/out/ issued documents
└── exports/             all/*.csv and <entity>/*.csv, plus -de variants for German Excel
```

```text
{issue date}_{type}_{counterparty}_{number}_{gross}{currency}_{id}.{ext}
2026-05-24_inv_hetzner-online_084000888874_39.25EUR_fdd7c80c.pdf
2024-02-28_cn_amazon-eu_DE426JLXAEUC_-24.04EUR_0c14567a.pdf
```

Types (the built-in classes): `inv`, `cn` (credit note, Storno), `rcpt`, `rem`, `notice` (Bescheid),
`oc`, `quote`, `contract`, `other`. Names and folders come from the class's `name` and `folder`
templates; the defaults give exactly the names above. The `id` is the start of the file's SHA-256: names never clash, and a file found
anywhere leads back to its record. ASCII only, so OneDrive on macOS and Windows agree.

## Classes and rules

A class decides a document type's fields, checks, file name and folder. Add your own, or override
a built-in, under `classes` in `_paperwork/config.json`. A rule sets values for documents that
match, so a recurring correction is made once.

```json
{
  "classes": {
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

```json
{"rules": [{"id": "hetzner-hosting", "when": {"counterparty": "hetzner-online"},
            "set": {"doc_type": "inv", "category": "hosting"}}]}
```

Templates take the placeholders `{issue_date}`, `{due_date}`, `{service_date}`, `{year}`, `{class}`,
`{counterparty}`, `{number}`, `{amount}`, `{id}`, `{entity}`, `{direction}`, `{category}` and
`{fields.<name>}` for a field the class declares. A folder template must start with `{entity}`.
The engine checks every rendered path before it moves anything: `path:folder` (an empty segment,
or one starting with `_` or `.`), `path:name` (an empty name, a leading `.`, or a slash) and
`path:length`. These send the document to review and cannot be accepted.

Each rule needs a unique `id`. Rules live in `_paperwork/rules.json` (the archive) and
`_paperwork/rules/<user>.json` (one person, chosen by `PAPERWORK_USER`). The archive's come first,
the most specific rule wins, and two equal rules that disagree send the document to review. A
correction made with `paperwork set` beats a rule. A rule that sets `fields.<name>` also needs
`set.doc_type` or `when.doc_type`. Save a draft for `rules test --file` in `_paperwork/proposals/`,
never in `_paperwork/rules/`, where a file can become a live user layer.

A document Claude recorded is filed with status `unconfirmed` when Claude classified it alone or
its counterparty is new. XML and template documents are never unconfirmed. The queue is
`paperwork list --status unconfirmed`, and `paperwork confirm <id>...` settles it. Documents
recorded before 0.2.0 are never unconfirmed.

## How a document is read

1. **E-invoice XML** (XRechnung UBL/CII, ZUGFeRD/Factur-X embedded in a PDF): parsed by the engine.
2. **Vendor template**: anchored patterns on the text layer, saved only after they reproduce every
   confirmed document of that vendor exactly.
3. **Claude** reads the text layer, or the OCR text plus the page images for scans, and writes a
   proposal. File and folder names are never used.

Then the engine checks it, whatever the source:

- the printed evidence appears in the document and means the value (`13. März 2024` is 2024-03-13,
  `2.894,19` is 2894.19), and names, numbers and VAT IDs appear in the text;
- net + tax = gross per rate, tax = net × rate, the lines add up, credit notes are negative;
- the entity follows from the billed party (name, VAT ID), never from the delivery address, and a
  private person at a company address is flagged;
- VAT IDs (with the German check digit), IBANs, currencies, dates against the archive's start year
  and the day the document arrived;
- §14 UStG mandatory content for German invoices (§33 UStDV for small ones), as warnings.

A document that fails goes to `_review/`. Accepted fields are frozen in its record; a rerun changes
nothing. Exports are regenerated from the records, sorted, and byte-identical for the same archive.

## The engine: `paperwork`

`bin/paperwork` is on the PATH while the plugin is enabled. It finds the archive from the current
folder, `$PAPERWORK_HOME`, `--root`, or the archive registered by `init`.

```bash
paperwork init ~/OneDrive/Belege      # layout + config; registers the archive
paperwork doctor                      # tools, config, lock
paperwork ingest [--adopt]            # register new files; --adopt: everything in the archive
paperwork pending                     # what needs reading (no file names)
paperwork schema                      # the proposal format
paperwork record <id> proposal.json   # check and store; exit 3 = review
paperwork set <id> entity=acme gross=36.98
paperwork confirm <id> [<id>...]      # accept what Claude classified alone
paperwork rules test [--file draft.json]   # preview rules, writes nothing
paperwork rules apply                 # re-apply rules to documents a person did not set
paperwork accept <id> <check> --reason "..."
paperwork plan                        # moves and renames, nothing done yet
paperwork apply <plan>                # journaled; never overwrites; copies across volumes
paperwork undo <plan>
paperwork export [--dialect csv|de|both]
paperwork verify                      # every file present, every hash right, nothing unregistered
paperwork vendors | vendor <slug> merge|rename|category|alias <value>
paperwork template test|set <vendor> [template.json]
```

Exit codes: 0 ok, 1 a check failed, 2 usage, 3 needs review, 4 locked, 5 Docker or tools missing.

## Guarantees and limits

- No code path deletes or overwrites a document. Records, the journal and exports are the engine's
  own files.
- The guard hook denies `rm`, `mv`, overwriting `cp`, redirects, in-place edits, `find -delete` and
  `git clean` that touch the archive, and edits of anything but `config.json`, `rules.json`,
  `rules/`, proposals and templates. It parses shell commands; a script that deletes files from inside an interpreter is
  beyond what a hook can see.
- OCR quality bounds what the engine can verify on scans: evidence that is not in the OCR text is a
  warning there, not an error, and Claude reads the page images.
- One writer at a time (lock file), so two machines syncing the same OneDrive folder cannot both write.

## Tests

```bash
plugins/paperwork/bin/paperwork __test    # the engine and guard tests, inside the tools image
```

Fixtures are synthetic (made-up companies and VAT IDs). Real invoices never go into git.
