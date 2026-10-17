---
name: inbox
description: >-
  Use when the user wants invoices, receipts, credit notes or other business
  documents (PDF, scans, photos, XRechnung/ZUGFeRD) sorted, filed, renamed,
  indexed or exported - "process my inbox", "file these invoices", "I dropped
  receipts in the inbox", "sort my Belege/Rechnungen", "extract the invoice
  data", "update the invoice CSV", "rename my invoices". Reads every new
  document in the paperwork archive's _inbox, proposes its fields from the
  document itself, lets the engine check and file them, and refreshes the
  CSV exports. Never deletes anything.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 0.2.0
---

# Inbox

Turn whatever is in `_inbox/` into filed, named, indexed documents. The `paperwork` engine
(Docker; `bin/paperwork`) does every file operation and every check. Your job is the one step it
cannot do: reading a document it could not read deterministically, and writing what it says as a
**proposal** the engine then checks against the document's own text.

If `paperwork doctor` says there is no archive or no entities, run the `setup` skill first.

## Rules

- **Never trust a file or folder name.** `invoice (3).pdf`, `06_Juni/`, `Telekom.pdf` say nothing.
  Every field comes from the document's content. `paperwork pending` deliberately hides the names.
- **Never move, rename, copy over, edit or delete a file in the archive yourself.** Only
  `paperwork apply` moves files, and nothing deletes. The guard hook blocks the rest. To add files,
  `cp -n <file> <archive>/_inbox/`.
- **Values as printed, numbers as decimals.** Write amounts as `1234.50` (dot, no thousands
  separator), dates as `YYYY-MM-DD`. Put the exact printed text in `evidence`: the engine checks that
  it appears in the document and that it means the value you wrote.
- **Only existing classes and entities.** `doc_type` is a class `paperwork schema` lists, the entity
  one from `config.json`. A new counterparty is fine, but it will be *unconfirmed*.
- **Unsure is review, not a guess.** Leave a field out rather than invent it; the engine sends the
  document to `_review/` and the `review` skill settles it with the user.

## Workflow

1. `paperwork ingest` hashes and registers every new file, reads text layers, OCRs scans, parses
   e-invoice XML and applies vendor templates. Exact duplicates are recorded as copies.
2. `paperwork pending` lists what still needs reading: the derived text file, page images for scans
   and the proposal path to write. `paperwork schema` prints the proposal format and the classes
   with their fields. Some items carry `rule_hints`, what a text or regex rule suggests: follow them
   unless the document clearly contradicts them, and then say so in `notes`.
3. For each pending document, read its text. For `pdf-scan`, `pdf-mixed` and `image`, **also look at
   the page images**: OCR misreads digits (`23.65.2024`, `14,56`), and the images are the truth.
   `doc_type` must be a class from `paperwork schema`; fill the `fields` that class declares. When
   you are unsure between classes, entities or counterparties, add `alternatives`
   (`{doc_type, entity, counterparty}`, best first, at most 3).
   Write the proposal JSON to the given path (one per document) and run
   `paperwork record <id> <proposal>`. Exit 3 means review; read the problems it prints. If a
   problem is your misreading, fix the proposal and record again with `--force`. If it is the
   document, leave it for review.
4. `paperwork plan`, show the user the moves grouped by destination, then `paperwork apply <plan>`.
   Without anyone to ask (headless, "don't wait for me"), apply: every move is journaled and
   `paperwork undo <plan>` reverses it.
5. `paperwork export` refreshes `exports/` (all entities and each entity; `-de` files for German Excel).
6. Report: how many were filed per entity, what is in review and why, duplicates, and warnings worth
   a human look (shared address, 0 % without a note, §14 UStG gaps, OCR-only evidence). List the
   *unconfirmed* documents (`paperwork list --status unconfirmed`: Claude classified them alone or
   introduced a new counterparty; they are filed anyway) with their alternatives, and offer
   `paperwork confirm <id>...`. When the same correction recurs, offer a rule in
   `_paperwork/rules.json` (see the `review` skill) and run `paperwork rules test` before saving it.

## Reading a document

| Field | How |
|---|---|
| `doc_type` | `inv` invoice; `cn` credit note, Gutschrift, Rechnungskorrektur, Storno-Rechnung; `rcpt` till receipt, Bewirtungsbeleg; `rem` reminder (Mahnung); `notice` Bescheid (tax office, IHK, fees); `oc` order confirmation (it is **not** an invoice); `quote`; `contract`; `other`. |
| `seller` | Who issued it. On marketplaces the party under "Verkauft von" / "Sold by", not the platform. |
| `buyer` | The **billed** party: the company in the billing address (Rechnungsadresse / Rechnungsempfänger / Bill to), never the delivery address (Lieferadresse) and never the attention line. A person's name alone is the person. |
| `buyer.address` | The billing address lines only. The engine decides the entity from the buyer name, VAT ID and this address; addresses alone never decide. |
| `invoice_number` | As printed, including spaces. `refers_to`: the original number on credit notes, Storno and reminders. |
| `issue_date` | Rechnungsdatum / Ausstellungsdatum / Invoice date. `service_date` or `service_period` when printed (Leistungsdatum, Lieferdatum, Abrechnungszeitraum). |
| Amounts | `net`, `gross` and `tax` per rate as printed on the document; credit notes and Storno **negative**. Reverse charge or a 0 % line: `rate "0"`, and `reverse_charge: true` when it says Reverse Charge / Steuerschuldumkehr / §13b. No tax shown at all: omit `tax` and `net`. |
| `currency` | ISO code from the symbol or code next to the total (`$` on an OpenAI invoice is USD, even in a German layout). |
| `lines` | Every position when legible: description, quantity, unit price, net and/or gross, tax rate. Discounts and shipping are lines. |
| `evidence` | At least `issue_date` and `gross`, exactly as printed (`13. März 2024`, `2.894,19 EUR`). Add `net`, `due_date` when printed. |
| `notes` | What a reader needs: tax-free intra-EU supply, VAT declared by a marketplace, an incomplete Bewirtungsbeleg. |

## Vendors that recur

When a counterparty has several documents with the same layout (hosting, telecom, SaaS), offer a
**template** after the first one is filed: anchored regular expressions on the text layer
(`paperwork vendors`, then see the `review` skill). Then `paperwork ingest` extracts that vendor's
next documents without you.
