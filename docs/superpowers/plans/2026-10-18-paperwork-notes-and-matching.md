# paperwork 0.3.0: notes and list matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one markdown note per document, and match any list of date and amount lines against the archive's invoices (found, combined, unsure, missing).

**Architecture:** Everything lives in the single-file stdlib engine `plugins/paperwork/lib/paperwork.py`, like the rest of the engine. Notes are output derived from the records, as the CSVs are. Matching is a pure function (`match_lines`) over plain dicts, with a thin command around it that reads the list JSON, checks its evidence against the list file's text, and writes a CSV.

**Tech Stack:** Python 3 stdlib, poppler and tesseract inside the existing Docker image, unittest.

**Spec:** `docs/superpowers/specs/2026-10-18-paperwork-notes-and-matching-design.md`

## Global Constraints

- Stdlib only. No new dependencies, no change to the Docker image.
- Tests run with `plugins/paperwork/bin/paperwork __test` (Docker must be running). Filter with `-k <pattern>`. All 78 existing tests stay green.
- Every company, VAT ID and address in a test is made up.
- Engine output files are written with `write_state` (atomic, only when changed). No code path deletes or overwrites a document. The only files the engine removes are notes it wrote itself that have nothing below `## Notes`.
- Note frontmatter: flat keys in this fixed order: `id, title, date, entity, counterparty, class, number, gross, currency, status, file`. Every value is a double-quoted JSON string (`json.dumps(str)`), and a missing value is `""`. The `id` is `pw:<id8>`.
- Matching defaults: window 30 days before to 7 days after the line date. Combinations of 2 to 6 documents from one counterparty, issued within 3 days of each other, at most 20 candidates per counterparty and line. Missing-line suggestions: at most 5, from 90 days before to 30 days after the line date, closest amount first; without a vendor, only documents within 3% of the amount.
- Amounts compare as the absolute gross, exact to the cent (`Decimal`).
- Version 0.3.0 in `VERSION`, `.claude-plugin/plugin.json` and every skill's `metadata.version`.
- No attribution lines in commits.

## Review Focus

1. **A note whose document's date changes:** the note moves to the new year folder, and the person's text under `## Notes` moves with it. Test in Task 1.
2. **`paperwork verify` and `ingest --adopt` after notes or lists exist:** `notes/` and `_lists/` are not reported as unregistered and not ingested as documents. Tests in Tasks 1 and 3.
3. **A vendor in the list that the registry doesn't know:** matching runs without the vendor filter, but the line can never be `found` or `combined`, only `unsure` (with a note) or `missing`. Test in Task 2.
4. **The same invoice fitting two lines:** both lines become `unsure` and neither claims it. Test in Task 2.
5. **Evidence that isn't in the list file:** `match` refuses with exit 1 and names the line. For an image or scanned source this is a warning, because OCR text is unreliable. Test in Task 3.

---

### Task 1: `paperwork notes`

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py`: constants near line 34, `MANAGED_TOP`, `cmd_verify` (line ~2512, add `NOTES` to `skip_top`), `config_problems` (reserve the slug), `cmd_export`, `parser()`
- Modify: `plugins/paperwork/hooks/guard.py:18` (`WRITABLE` gains `"notes/"`) and its docstring
- Test: `plugins/paperwork/tests/test_paperwork.py` (new tests in `class Archive`, a guard test in `class Guard`)

**Interfaces:**
- Produces: `NOTES = "notes"` in `MANAGED_TOP`; `note_path(record) -> str` (archive-relative, `notes/<YYYY>/<id8>.md`, `notes/undated/<id8>.md` without an issue date); `note_text(record, archive, user_notes: str) -> str`; `user_notes(text: str) -> str` (everything after the first line that is exactly `## Notes`, or `""`); `write_notes(archive, rebuild=False) -> dict` with keys `written, removed, kept` (lists of archive-relative paths); `cmd_notes(args)`.

- [ ] **Step 1: Write the failing tests** in `class Archive`. Reuse the existing helpers (`drop`, `pending_id`, `propose`, `file_all`, `hoster_invoice()` or whichever fixture an existing test uses for a filed invoice).

```python
def test_notes_written_and_incremental(self):
    # one filed invoice -> notes/<year>/<id8>.md
    code, res, err = self.pw("notes")
    self.assertEqual(code, 0, err)
    path = os.path.join(self.root, res["written"][0])
    text = read(path)
    self.assertTrue(text.startswith('---\nid: "pw:'))
    keys = [l.split(":")[0] for l in text.split("---")[1].strip().splitlines()]
    self.assertEqual(keys, ["id", "title", "date", "entity", "counterparty", "class", "number",
                            "gross", "currency", "status", "file"])
    self.assertIn("\n## Notes\n", text)
    code, res, _ = self.pw("notes")
    self.assertEqual(res["written"], [])          # nothing changed, nothing written

def test_notes_keep_person_text(self):
    # write notes, append "paid by card\n" below ## Notes, run `notes --rebuild`
    # -> the text is still there; `paperwork set <id> issue_date=<other year>` then `notes`
    # -> the note is under the new year, the old path is gone, the text moved with it

def test_orphan_note_with_text_is_kept(self):
    # a note file whose id is no longer a record: removed when empty below ## Notes,
    # kept and listed in res["kept"] when it has text

def test_export_writes_notes_and_verify_ignores_them(self):
    # `export` creates notes/; `verify` exits 0 and reports nothing unregistered under notes/
```

And in `class Guard`, a test that a Write to `<archive>/notes/2026/abcd1234.md` is allowed while a Write to `<archive>/exports/x.csv` stays denied. Copy the shape of the existing guard tests.

- [ ] **Step 2: Run them to see them fail**

Run: `plugins/paperwork/bin/paperwork __test -k notes -k Guard`
Expected: FAIL (no `notes` command).

- [ ] **Step 3: Implement.**
  - **Which records get a note:** those that have `data` and whose status is not `duplicate`.
  - **Title:** `<counterparty display name or slug> <class> <number>`, leaving out empty parts.
  - **Body:** after the frontmatter comes `# <title>`. Then a wikilink to the file (`[[<record path>]]`, which is archive-relative because the archive root is the vault root). Then a two-column field table with issue date, due date, net, tax, gross, entity, counterparty, category, tags and each `fields.<name>` of the class. Then `## Notes` and the person's text unchanged.
  - **Where existing notes come from:** `write_notes` scans every existing `notes/**/*.md` once and reads its `id:` line, so a person's text is found wherever the note was before.
  - **Writing and removing:** each file is written with `write_state`. An old path is removed after the new one is written. `--rebuild` rewrites every note even when the bytes are unchanged.
  - **Commands:** `cmd_notes` takes the lock and emits the dict as JSON. `cmd_export` calls `write_notes(archive)` inside its lock and adds `"notes": {...}` to its output.
  - **Reserved slug:** `config_problems` rejects an entity slug `notes`.

- [ ] **Step 4: Run the full suite**

Run: `plugins/paperwork/bin/paperwork __test`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/paperwork/lib/paperwork.py plugins/paperwork/hooks/guard.py plugins/paperwork/tests/test_paperwork.py
git commit -m "feat(paperwork): notes command writes one markdown note per document"
```

---

### Task 2: the matcher

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py` (new section `# List matching` before the export section)
- Test: `plugins/paperwork/tests/test_paperwork.py` (new `class Matching(unittest.TestCase)`, pure functions, no archive)

**Interfaces:**
- Produces:
  - `match_lines(items: list[dict], docs: list[dict], before: int = 30, after: int = 7) -> list[dict]`.
  - Each item is `{"n": int, "date": "YYYY-MM-DD", "amount": "47.11", "vendor": str|None, "slug": str|None}`. Here `slug` is the resolved counterparty, and it is None when there is no vendor or the vendor is unknown.
  - Each doc is `{"id", "path", "counterparty", "issue_date", "gross"}`, with all values strings.
  - Each result is `{"n", "date", "amount", "vendor", "result", "documents": [path...], "suggestions": [path...], "note": str}`. `result` is one of `found`, `combined`, `unsure` and `missing`.
- Rules (from the spec):
  1. **Window:** a doc is a candidate when its issue date is between the line date minus `before` and the line date plus `after`, both ends included. With a `slug`, it must also have that counterparty.
  2. **found:** exactly one candidate with `abs(gross) == abs(amount)`. Two or more such candidates make the line `unsure`, with all of them in `documents`.
  3. **combined:** no single candidate fits, and exactly one set of 2 to 6 candidates fits:
     - all from one counterparty;
     - with `max(issue_date) - min(issue_date) <= 3` days;
     - with absolute grosses summing to the absolute amount;
     - searching at most the 20 candidates of each counterparty closest in date.

     More than one fitting set makes the line `unsure`, listing the documents of every set and naming the sets in `note`.
  4. **Unknown vendor:** when `vendor` is set and `slug` is None, a `found` or `combined` result becomes `unsure`, with note `vendor "<vendor>" is not in the registry`.
  5. **One document, one line:** a document in the `documents` of two or more `found`/`combined` lines turns all of those lines into `unsure`.
  6. **missing:** up to 5 suggestions, closest amount first, then date, then id. Documents used by a `found`/`combined` line are left out.
     - With a `slug`: that counterparty's documents in [date−90, date+30].
     - Without one: all documents in that range whose gross is within 3% of the amount.
  7. **Order:** deterministic for the same input (sort candidates by `(issue_date, id)`).

- [ ] **Step 1: Write the failing tests** with a small `doc(id, cp, date, gross)` helper.

```python
def test_single_found_with_date_off(self):       # doc 2026-09-01 39.25, line 2026-09-05 -39.25 -> found
def test_outside_window_is_missing(self):        # doc 31 days before -> missing, doc in suggestions when slug given
def test_two_equal_amounts_unsure(self):         # two docs 10.00 in window -> unsure, both listed
def test_amazon_combined(self):                  # amazon 12.99+20.00+14.12 on 09-02/09-03/09-04, line 47.11 -> combined, 3 paths
def test_combined_spread_over_3_days_not_used(self):  # same parts on 09-01 and 09-05 -> missing
def test_two_combinations_unsure(self):          # 10+20 and 15+15 for 30.00 same vendor -> unsure
def test_unknown_vendor_never_found(self):       # vendor "Foo", slug None, one exact doc -> unsure with note
def test_same_doc_two_lines_unsure(self):        # one 50.00 doc, two 50.00 lines -> both unsure
def test_missing_suggestions_without_vendor_3_percent(self):  # 100.00 line; docs 102.50 (in), 104.00 (out) -> suggestions == [102.50 doc]
def test_suggestions_exclude_used_docs(self):
def test_deterministic(self):                    # shuffled docs -> identical results
```

- [ ] **Step 2: Run them to see them fail**

Run: `plugins/paperwork/bin/paperwork __test -k Matching`
Expected: FAIL (`match_lines` not defined).

- [ ] **Step 3: Implement `match_lines`.** For the combination search, group a counterparty's candidates by 3-day spans: for each candidate as the earliest, take the candidates within 3 days of it. Within that group, enumerate subsets of size 2 to 6 with `itertools.combinations`, pruning by running sum when sorted by amount. Deduplicate the sets found across spans.

- [ ] **Step 4: Run the full suite.** Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(paperwork): match list lines to single or combined invoices"
```

---

### Task 3: `paperwork match` on a list file

**Files:**
- Modify: `plugins/paperwork/lib/paperwork.py`: `LISTS = "_lists"` in `MANAGED_TOP`, `cmd_init` creates `_lists/`, `cmd_verify` skips `LISTS`, the new functions, `parser()`
- Modify: `plugins/paperwork/hooks/guard.py`: `WRITABLE` gains `"_paperwork/lists/"`; `cp -n` into `_lists/` is allowed exactly like `_inbox/` (line ~132)
- Test: `plugins/paperwork/tests/test_paperwork.py`

**Interfaces:**
- Consumes: `match_lines` (Task 2), `amount_candidates`, `date_candidates`, `squash`, `fold`, `company_key`, `tool`, `ocr_image`, `sniff`.
- Produces:
  - **The list file**, `_paperwork/lists/<name>.json`:

    ```json
    {"source": "_lists/offene-posten.pdf", "entity": "nordlicht", "from": "2026-09-01", "to": "2026-09-30",
     "items": [{"date": "2026-09-03", "amount": "-47.11", "vendor": "Amazon", "text": "AMAZON EU SARL",
                "evidence": {"date": "03.09.2026", "amount": "-47,11", "vendor": "AMAZON"}}]}
    ```

    `entity`, `from`, `to`, `vendor`, `text` and `evidence.vendor` are optional. `<name>` is the file stem.
  - **`list_text(archive, rel_path) -> tuple[str, bool]`:** the source's text and whether it came from OCR.
    - PDF: `pdftotext -layout` over all pages. If that yields fewer than `OCR_MIN_CHARS` characters, the pages are rendered and OCRed as `derive` does.
    - Image: OCR.
    - Anything else: decoded as UTF-8 with `errors="replace"`.
  - **`list_problems(items, text) -> list[str]`:** for line `n`, `evidence.date` must appear in the text (`squash(e) in squash(text)`) and `date_candidates(e)` must contain `date`. `evidence.amount` must appear, and `amount_candidates(e)` must contain `amount` or its negation. `evidence.vendor`, when given, must appear (`fold`). Messages read `line <n>: <field> evidence "<e>" ...`.
  - **`resolve_vendor(archive, name) -> str|None`:** a registry slug equal to `slugify(name)`. Otherwise a unique vendor that has a name with that `company_key`. Otherwise a unique vendor whose name key contains `company_key(name)`. Otherwise None.
  - **`match_docs(archive, entity, start, end) -> list[dict]`:** records with status `filed`, `ok` or `unconfirmed`, a gross and an issue date, in the entity (when given) and the date range (when given), in the shape Task 2 consumes.
  - **`cmd_match(args)`:** `paperwork match <list> [--entity E] [--from D] [--to D] [--before N] [--after N]`.
    - `<list>` is a name or a path under `_paperwork/lists/`. Flags override the JSON.
    - Errors (exit 1, nothing written): a missing source; evidence problems from a non-OCR source; a source outside the archive.
    - Writes `exports/matches/<name>.csv` (columns `line, date, amount, vendor, result, documents, suggestions, note`, with lists joined by ` | `) via `table_text`.
    - Emits `{"list", "csv", "counts": {result: n}, "lines": [...], "warnings": [...]}`.
    - Takes the lock.

- [ ] **Step 1: Write the failing tests** in `class Archive`.

```python
def test_match_finds_combined_and_missing(self):
    # file three invoices from one made-up vendor on consecutive days (text_pdf + propose + file_all),
    # write _lists/liste.csv with lines "03.09.2026;47,11;Versandhaus Beispiel" and "10.09.2026;99,00;"
    # and _paperwork/lists/liste.json with matching evidence
    code, res, err = self.pw("match", "liste")
    self.assertEqual(code, 0, err)
    self.assertEqual(res["counts"], {"combined": 1, "missing": 1})
    rows = self.csv_rows("matches", "liste.csv")   # exports/matches/liste.csv
    self.assertEqual(len(rows[0]["documents"].split(" | ")), 3)

def test_match_refuses_evidence_not_in_list(self):
    # evidence amount "48,11" not in the CSV -> exit 1, stderr names "line 1", no CSV written

def test_match_from_to_limits_documents(self):
    # --from after the invoices' dates -> the line is missing

def test_lists_folder_is_not_ingested_or_unregistered(self):
    # a file in _lists/: `ingest --adopt` does not register it, `verify` exits 0
```

And in `class Guard`: `cp -n x.pdf <archive>/_lists/` is allowed, `cp x.pdf <archive>/_lists/` (overwriting) is denied, and a Write to `_paperwork/lists/a.json` is allowed.

- [ ] **Step 2: Run them to see them fail**

Run: `plugins/paperwork/bin/paperwork __test -k match -k lists -k Guard`
Expected: FAIL.

- [ ] **Step 3: Implement** the functions above. `csv_rows` in the test reads `exports/<scope>/<name>`, so `"matches"` works as the scope.

- [ ] **Step 4: Run the full suite.** Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(paperwork): match command checks a list against the archive"
```

---

### Task 4: the match skill, docs and version

**Files:**
- Create: `plugins/paperwork/skills/match/SKILL.md`
- Modify: `plugins/paperwork/README.md`, `plugins/paperwork/DESIGN.md` (short sections for notes and matching), `plugins/paperwork/lib/paperwork.py` (`VERSION = "0.3.0"`), `plugins/paperwork/.claude-plugin/plugin.json` (`"version": "0.3.0"`, description mentions notes and list matching), every `skills/*/SKILL.md` `metadata.version: 0.3.0`, `skills/ask/SKILL.md` (can point to notes), root `README.md` paperwork row

- [ ] **Step 1: Write `skills/match/SKILL.md`** with the same frontmatter shape as `skills/ask/SKILL.md`.
  - **Trigger:** the description fires on "my accountant is missing invoices", "check this list", "which of these payments have an invoice", "Kontoauszug abgleichen", "fehlende Belege" and similar.
  - **Steps:**
    1. Copy the list file into `_lists/` with `cp -n`.
    2. Read it: open PDFs and images, read CSV and XML as text. Write `_paperwork/lists/<name>.json` with every line, keeping the evidence exactly as printed.
    3. Run `paperwork match <name>`, adding the period and entity when the user named them.
    4. Fix any line it refuses, then rerun.
    5. Present the results grouped as missing first (with suggestions), then unsure (ask the user to pick), then combined and found. Give paths.
    6. To re-check later, rerun `paperwork match <name>`.
  - **Rules:**
    - Never invent a line.
    - Fees, salaries and taxes stay in the list. The user decides about them.
    - When the user picks a document for an unsure line, say so in the reply. No state is stored.

- [ ] **Step 2: README.** Add `## Notes` and `## Matching a list` sections in the style of the existing ones:
  - the note layout and frontmatter;
  - notes open in Obsidian with the archive as vault;
  - the four results table;
  - the default windows.

  Add `notes` and `match` to the command block, the skill to the skills table, and `notes/` and `_lists/` to the archive tree.

- [ ] **Step 3: Bump the versions**, then run `plugins/paperwork/bin/paperwork __test`. Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add plugins/paperwork README.md
git commit -m "docs(paperwork): match skill, notes and matching docs, 0.3.0"
```
