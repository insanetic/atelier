# paperwork: document cards and list matching

Date: 2026-10-18. Plugin: `plugins/paperwork` (currently 0.2.0). Target: 0.3.0.

## Intent

Two additions to the paperwork archive.

1. **Cards.** One markdown file per document, generated from its JSON record, so the archive can be
   read, linked and annotated in Obsidian and linked from the atlas brain. Cards are a view; the JSON
   record stays the truth.
2. **List matching.** The user hands paperwork any list of items that should have a document behind
   them, and paperwork says which ones the archive has, which it probably has, and which are
   missing. The driving case: the accountant closes a month or year and sends a list of payments
   with missing invoices for the Finanzamt, usually with a date and an amount. Other lists: a bank
   export (CSV, XML, PDF), a credit card statement for a period, any spreadsheet or letter shaped
   like "these amounts on these dates". The format must not matter.

## Goals

- `paperwork cards` regenerates every card from the records; it is incremental (writes only what
  changed) and deterministic. `paperwork export` also refreshes the cards.
- A person can write notes in a card; regeneration keeps them.
- Cards link the document to its entity, its counterparty, its file and the lists that requested it,
  using wikilinks, so Obsidian and atlas can follow them.
- Any list file can be dropped into `_inbox/` like a document. It becomes a record of class `list`
  whose items are read deterministically when the format is known, and by Claude (checked against the
  file's text) when it is not.
- Each item is matched against the archive and ends up `found`, `probable`, `missing` or `ignored`,
  with the documents (or suggestions) that support the verdict.
- One item can be covered by several documents from the same vendor whose amounts add up (the
  Amazon marketplace case: one payment, up to about six invoices, usually with the same date).
- When nothing matches, the user gets suggestions: documents from the likely vendor around that
  date, and documents with a near amount.
- Lists stay open: every `paperwork match` run (and every inbox run) re-matches the open items, so a
  missing invoice that arrives later is found without the user asking.
- The user can hand the accountant the found documents: a command copies them into an export
  folder for that list.

## Non-goals

- Fetching anything from a bank, a card provider or a mailbox (no network; the user downloads).
- Mail import, a background watcher, the DuckDB index, the web UI, a working-files plugin, writing
  into the atlas brain. These come later and only read the cards.
- Excel files in this version: the user exports CSV, or Claude reads the values from what the user
  pastes.
- Payment status for every invoice ("unpaid invoices") as its own feature. It falls out of a bank
  list that covers a period, but no separate tracking is built.

## Anti-goals (failure even if it technically works)

- **A wrong match shown as found.** A real gap then stays hidden from the Finanzamt. Automatic
  `found` needs strong evidence; everything weaker is `probable` and waits for confirmation.
- **The same document counted for two items of one list**, or one payment counted twice because two
  overlapping bank exports were both imported.
- **Cards become a second truth.** Values edited in a card's frontmatter are overwritten on the next
  run; only the notes section belongs to the user. Nothing ever reads values back from a card.
- **Lost notes.** Regeneration never drops a note, also when the card's title or path changes.
- **Slow regeneration** on an archive of about 10,000 documents (target: a full `cards` run with
  nothing changed in a few seconds; it reads every card once to keep notes, and writes nothing).

## Constraints

- Everything from the existing guarantees holds: no code path deletes or overwrites a document;
  every move goes through plan, apply, journal and undo; Python stdlib only, inside the existing
  Docker image with no network; byte-identical output for the same archive.
- An archive from 0.2.0 upgrades with zero moves and no change to any record's status.
- Cards and lists follow the shared card contract below, because other plugins (atlas, the later
  hub with DuckDB and the UI, a later library plugin for working files) will read cards from several
  plugins and must not depend on paperwork internals.
- Never derive anything from file or folder names, including the list file's name.

## Part A: cards

### Where

A new engine-owned top folder `cards/` in the archive root (added to the managed folders, so ingest
never registers a card as a document):

```text
cards/
├── documents/<YYYY>/<id8>.md      one per document record (YYYY from the issue date, 0000 when unknown)
├── lists/<id8>.md                 one per list record
├── counterparties/<slug>.md       hub card per counterparty
└── entities/<slug>.md             hub card per entity
```

File names are stable ids and slugs, never titles, so a corrected field never renames a card.
Display names come from the frontmatter (`title`, `aliases`) and from link aliases
(`[[counterparties/hetzner-online|Hetzner Online GmbH]]`).

### The shared card contract (frontmatter)

Every card, from any plugin, starts with these keys; paperwork adds its own after them.

| Key | Meaning |
|---|---|
| `id` | stable id, never reused (`pw:<id8>` for paperwork documents and lists, `pw:cp:<slug>`, `pw:en:<slug>` for hubs) |
| `type` | what the card is: the class key for documents (`inv`, `contract`, …), `list`, `counterparty`, `entity` |
| `title` | human title |
| `date` | ISO date or empty |
| `entity` | wikilink to the entity hub card, or empty |
| `source` | the plugin: `paperwork` |

Rules for all frontmatter: flat keys only; every scalar written as a double-quoted JSON string
(`"39.25"`, `"NO"`, `"084000888874"`), so YAML readers never turn values into numbers, booleans or
dates; lists as JSON arrays of strings; keys in a fixed order. This avoids the silent coercions the
atlas study verified in the DuckDB YAML reader.

Paperwork document cards add at least: `class` (label), `counterparty` (wikilink), `direction`,
`number`, `amount` (e.g. `"39.25 EUR"`), `gross`, `currency`, `status`, `confirmed`, `file`
(wikilink to the document file), `category`, `tags`, one `field_<name>` per class field, and
`lists` (wikilinks to the list cards that request this document).

### Body

A short generated summary (what it is, from whom, amount, number, dates), a lines table for
invoices when lines exist, backlinks ("Requested in", "Duplicates"), then:

```markdown
## Notes
```

Everything after the line `## Notes` belongs to the user and is copied verbatim into the new card.
A card without that heading gets it appended empty. Hub cards list their documents (newest first,
capped with a count of the rest) and totals per year; list cards show the items table with status
and links.

### Command and efficiency

`paperwork cards [--rebuild]`:

- renders every card from the records in memory, reads the existing card only to keep its notes,
  and writes a file only when its bytes differ (the existing `write_state` already does this);
- removes a card file whose record no longer exists **only when its notes section is empty**;
  otherwise it keeps the file and reports it (records are never deleted, so this happens only after
  a manual edit of the engine's state);
- `--rebuild` ignores nothing; it is the same run, reporting every card (useful after a template
  change in a later version);
- prints counts: written, unchanged, kept-orphans.

`paperwork export` runs the same card refresh after the CSVs. The inbox and review skills need no
new step beyond what `export` already does.

The guard hook allows writes to `cards/` (Claude may add notes on request); the engine overwrites
everything outside the notes section anyway.

## Part B: list matching

### A list is a document

The list file goes into `_inbox/` like any document and is filed and named like one (a new built-in
class `list`, folder `{entity}/{year}/lists`, name `{issue_date}_list_{counterparty}_{id}`, where
the counterparty is the sender: the accountant, the bank, the card provider). Its record holds the
items.

Media: ingest must accept CSV files (`csv`, detected by content) and recognise ISO 20022 bank
statements in XML (camt.052/053/054, by namespace) in addition to the formats it reads today. PDFs
are already supported.

Class `list` fields: `kind` (`bank`, `card`, `accountant`, `other`), `period_start`, `period_end`,
`account` (IBAN or card number tail, as printed). Its record data gets `items`: an ordered array of

```json
{"n": 1, "date": "2026-03-14", "amount": "-119.00", "currency": "EUR",
 "text": "AMAZON EU SARL ...", "counterparty": "Amazon EU", "iban": null, "reference": "...",
 "evidence": {"amount": "-119,00", "date": "14.03.2026"}}
```

### Reading the items

In this order, like documents today:

1. **ISO 20022 XML (camt):** parsed by the engine.
2. **CSV with a known layout:** a *list format* (like a vendor template) maps columns to item keys,
   with the decimal separator, date format, delimiter and encoding. Formats live in
   `_paperwork/formats.json`, are matched by the header row, and are saved only after they reproduce
   the items of every list already read with them (the same rule as vendor templates).
3. **Anything else** (PDF statement, accountant's letter, an unknown CSV): Claude proposes the items
   with evidence; the engine checks that every item's printed amount and date appear in the list's
   text and mean the value, and sends the list to review otherwise. After the first unknown CSV is
   read, the skill offers to save a list format.

### Matching

Candidates are documents of money classes (`inv`, `cn`, `rcpt` and any class with `money: true`)
of the list's entity (when the list has one), not duplicates. Documents in review are considered but
never produce `found`.

For each item, in order:

1. **Single document.** Equal absolute amount (tolerance 0.01) in the item's currency, issue date
   within the window (default: from 45 days before the item date to 10 days after; configurable).
   Sign is used when present: a negative bank amount points to received invoices or issued credit
   notes; an accountant's unsigned list matches either.
2. **Several documents from one vendor** (marketplace case). When step 1 finds nothing, take each
   counterparty with documents in the window; search subsets of its documents whose issue dates lie
   within 3 days of each other and whose amounts add up to the item's amount. Bounds: at most 6
   documents per subset, at most 20 candidates per counterparty (closest dates first). Only a unique
   subset counts.
3. **Suggestions** when nothing matched: the likely vendor's documents in a wider window (90 days
   before, 30 after), and documents whose amount is within 3 % (currency conversion, tips), best
   first, at most 5.

Evidence that strengthens a candidate: the document's invoice number appears in the item's text or
reference; the IBAN matches the document's or the vendor's; the item text contains one of the
vendor's known names (normalised as the engine already does for company names).

Verdicts:

- `found`: exactly one candidate (single or subset) and at least one strong signal (number in
  reference, IBAN, or vendor name plus a unique amount in the window); or a person confirmed it.
- `probable`: one best candidate without a strong signal, or a subset match. Waits for confirmation.
- `missing`: nothing matched; carries the suggestions.
- `ignored`: a rule or a person said no document is expected (bank fees, salaries, tax payments,
  transfers between own accounts), with the reason.

One document may support only one item of the same list; when two items want the same document,
both become `probable` and the conflict is shown. The same document supporting items in different
lists is normal (an accountant's list and a bank export showing the same payment). Importing the
same bank export twice is caught by the existing duplicate detection (same file hash).

Confirmed and manual links are frozen in the list record. Automatic verdicts are recomputed on every
run, so open lists keep improving as documents arrive.

### Rules for items

`rules.json` gets a second top-level key `items` with the same `when`/`set` shape: `when` on
`text`, `regex`, `counterparty`, `iban`, `sign`; `set` with `expect: "none"` and `reason`, or with a
`counterparty` hint for the matcher. Precedence and validation follow the document rules.

### Commands

```bash
paperwork match [<list>]                         # re-match one or all open lists
paperwork match show <list> [--status missing]   # items with verdicts, documents, suggestions
paperwork match confirm <list> <n> [<doc>...]    # accept the proposed match (or the named docs)
paperwork match link <list> <n> <doc>...         # link by hand
paperwork match unlink <list> <n>
paperwork match ignore <list> <n> --reason "..."
paperwork match pack <list>                      # copy the found documents to exports/lists/<id8>/
```

`pack` copies, never moves; the folder is engine-owned like the rest of `exports/`.

Exports: `exports/<scope>/lists/<id8>.csv` per list (items, verdict, linked document paths) and
`exports/<scope>/missing.csv` (every open `missing` and `probable` item across lists, with
suggestions). Cards: the list card shows the items table; each document card links back to the lists
that requested it.

### Skill

A new skill `reconcile`: "my accountant sent me a list of missing invoices", "check this bank
export", "which receipts are missing for March". It ingests the list, reads the items, runs `match`,
walks the user through `probable` items, shows `missing` with suggestions, offers rules for items
that never need a document, and ends with a reply the user can send to the accountant (found with
paths, still missing) plus `match pack` when they want to send files.

## Precise rules (settled after the builder check)

### A list's entity and the record pipeline

- Entities in `config.json` gain optional `accounts`: IBANs and card number tails as printed. A list
  finds its entity from its account first, then from the addressee (an accountant's letter is
  addressed to a company, which `resolve_entity` already handles as the buyer), then from a rule or
  Claude's proposal setting `entity`. Unresolved → the list goes to review with the existing
  `entity` error until the user sets it. Matching is always scoped to the list's entity.
- The `list` class is built in, with `required: ["issue_date"]` only (no `seller.name`); its sender
  is the counterparty, proposed as `seller`. `list` gets no VAT, sum or §14 checks (`money: false`).
- Lists use the normal proposal and `record` flow. `items` is a proposal key accepted only for class
  `list`, normalised like the other fields. The "list's text" a check compares against is the derived
  text: the PDF text or OCR as today, and for CSV and camt the file's own text, stored as the derived
  `text.txt` at ingest.
- Lists are never `unconfirmed`; their items carry the verdicts. `set`, `accept`, `reextract` and
  `rules apply` work on lists as on any record. A list in review is not matched.
- A user class named `list` shallow-merges over the built-in like any other; no 0.2.0 archive has
  one, so the upgrade stays at zero moves.

### Overlapping exports

Every item gets a fingerprint: account, date, amount, and the normalised reference (or text when
there is no reference). An item whose fingerprint already exists in an earlier list of the same
account is marked `seen in <list>`: it shows that list's verdict and links, and it is not counted
again in `missing.csv` or in any total. File-level duplicates (same hash) remain caught at ingest.

### Sign and date table

| Item amount | Documents it can match |
|---|---|
| negative (money out) | `in` documents of classes with `sign: positive` (invoices, receipts), or `out` credit notes |
| positive (money in) | `out` invoices, or `in` credit notes (refunds) |
| unsigned (accountant lists) | any of the above |

Amounts compare as absolute values of `gross`. The window is anchored on the document's issue date
(45 days before the item date to 10 days after); when the document has a due date, the window end
extends to the due date plus 10 days.

### When an item is `found`

| Candidate | Extra condition | Verdict |
|---|---|---|
| exactly one document, amount equal, in window | its invoice number appears in the item's reference or text | found |
| exactly one document, amount equal, in window | IBAN equals the document's or its vendor's | found |
| exactly one document, amount equal, in window | the item text contains a known name of its vendor, and no other candidate document in the window has the same amount, and no other item of this list with the same amount is within the window | found |
| exactly one document | none of the above | probable |
| two or more documents with the amount | any | probable (best first, rest listed) |
| a unique subset from one vendor | every document's invoice number appears in the reference | found |
| a unique subset from one vendor | otherwise | probable |
| nothing | | missing, with suggestions |

A person's confirmation or manual link always gives `found`.

### Cards: vault root and links

The vault root is the archive root. All wikilinks are paths relative to it:
`[[cards/counterparties/hetzner-online|Hetzner Online GmbH]]`,
`[[acme/2026/in/2026-05-24_inv_hetzner-online_084000888874_39.25EUR_fdd7c80c.pdf]]`. This is part of
the shared contract: links in cards are archive-root-relative paths.

Cards exist for every record with data (filed, unconfirmed, review, lists). Documents not yet read
get no card. Duplicates get no card of their own; the original's card lists them. `vendor merge` and
`vendor rename` move the old hub card's notes to the new slug's card; any other orphan with notes is
kept and reported.

### `match` writes state

`match` runs under the lock and writes the list records. Its output is deterministic. A frozen link
whose document later becomes a duplicate, goes to review, is re-extracted or changes its amount is
flagged `stale` and the item becomes `probable` until the user confirms again. `ignored` set by a
rule is recomputed on every run; `ignored` set by a person is frozen.

### `pack`

`match pack <list>` copies the documents of `found` items (never `probable`) into
`exports/<entity>/lists/<id8>/` under their archive names, plus an `index.csv` (item, verdict,
document). The folder is engine-owned and rebuilt on each `pack`: files in it that the current pack
did not produce are removed; nothing outside that folder is touched.

## Decided by me (the user handed these over)

- Lists are kept and re-matched on every run rather than producing one-off reports.
- The date window, the 3-day subset spread, the subset size bound and the suggestion thresholds
  above are starting defaults, configurable in `config.json` under `match`.
- Cards live in an engine-owned `cards/` folder with id-based file names.
- Lists are documents with a class, so they are filed, deduplicated and named like everything else.
- Excel support is deferred.

## Left to the builder

- Scoring details between candidates once the verdict rules above are met.
- The exact card body layout and the hub cards' caps.
- How list formats detect a header row (exact match or normalised).
- Internal storage layout of items and matches inside the list record.
- How `match` hooks into `export`/inbox (it must run after records are updated and before cards).
