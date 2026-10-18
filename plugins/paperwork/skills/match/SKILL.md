---
name: match
description: >-
  Use when the user has a list of payments or lines and wants to know which
  have a document in the paperwork archive - "my accountant is missing
  invoices", "check this list", "which of these payments have an invoice",
  "Kontoauszug abgleichen", "fehlende Belege", "welche Buchungen haben keinen
  Beleg". Reads the list (PDF, scan, CSV, XML), matches every line against the
  archive and writes a CSV of found, combined, unsure and missing lines.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 0.3.0
---

# Match

Match a list of payments against the archive. The engine does the matching; you read the list.

1. **Copy the list in.** `cp -n <file> <archive>/_lists/`. Never overwrite, never move the original.
2. **Read it.** Open PDFs and images, read CSV and XML as text. Write
   `_paperwork/lists/<name>.json` with every line:

   ```json
   {"source": "_lists/statement-2026-05.pdf", "entity": "acme-gmbh", "from": "2026-05-01", "to": "2026-05-31",
    "items": [{"date": "2026-05-24", "amount": "-39.25", "vendor": "Hetzner", "text": "SEPA Hetzner Online",
               "evidence": {"date": "24.05.2026", "amount": "-39,25", "vendor": "Hetzner Online"}}]}
   ```

   `source` is a file inside `_lists/`. `entity`, `from` and `to` are optional. Every line needs
   `evidence.date` and `evidence.amount`, copied exactly as the list prints them, character for
   character. `evidence.vendor` is optional.
3. **Run it.** `paperwork match <name>`, adding `--entity`, `--from` and `--to` when the user named
   them. `--before N` and `--after N` change the day window (default 30 before, 7 after).
4. **Fix refusals.** The engine refuses a line whose evidence is not in the list or does not read as
   the value. Reread that line, correct the JSON, rerun. On scans a missing text is only a warning.
5. **Report every warning** from `paperwork match` to the user, line by line. On scans a warning
   is the only sign that a line was not checked against the file.
6. **Present** `exports/matches/<name>.csv` by result:
   - **missing** first, with the suggestions, and say what to ask for;
   - **unsure**: show the candidates and ask the user to pick;
   - **combined** (one payment for several documents) and **found**: the count, and the paths on request.

   Give the path of every document you cite.
7. **Later**, rerun `paperwork match <name>` after new documents arrive.

Rules:

- Never invent a line. Every line in the JSON is a line in the list.
- Fees, salaries and taxes stay in the list; the user decides about them.
- When the user picks a document for an unsure line, repeat the choice in your reply. Nothing is stored.
