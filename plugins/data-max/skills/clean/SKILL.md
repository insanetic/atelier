---
name: clean
description: >-
  Use when a raw data export should be turned into clean, typed,
  warehouse-ready tables or files, or loaded, or an existing cleaning spec
  should run on a new file - "clean this up", "fix the amounts/dates and give
  me a clean CSV", "convert this JSON/CSV to Parquet for BigQuery", "write
  it as Parquet", "turn this into a table I can
  import", "clean this week's export", "give me the load statements", "split
  this into orders and line items". Needs a data-max spec (specs/*.spec.json);
  without one, data-max:inspect writes it first.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 2.1.0
---

# Clean

Run a spec and hand over tables a warehouse can load: typed, reconciled, identical on every
rerun, with a load that is safe to repeat. Only `data-max apply` touches data, never an
ad-hoc script. That is what makes reruns, CI and next month's file give the same answer.

**No spec, no cleaning.** Without `specs/<name>.spec.json`, run `data-max:inspect` first:
it makes the grain, key, timezone and PII decisions.

## Workflow

1. **Apply**: `data-max apply specs/<name>.spec.json <input> --param … --out-dir data/clean --parquet`.
   Drop `--parquet` when the engine says DuckDB is missing. Pass params the way the user
   gave them. If the spec names an env var for a secret, use that. Don't restructure params
   unasked. With nobody to ask for a missing param, stop and say which one.

2. **On failure, fix the spec, never the data.** Read the summary and
   `data/clean/<name>.rejects.csv`:

   | Reject or failed check | Spec change | Without an answer |
   |---|---|---|
   | New format, NULL token, footer row | `formats` / `null_tokens` / `filters` | Make the change if unambiguous |
   | Value not in `allowed` | extend `map` / `allowed` | Don't load; ask (new business value) |
   | Duplicate keys | `dedupe` | Don't load; ask which row wins |
   | Control total mismatch | none: rows are missing or doubled | Don't load; report both numbers |
   | Wrong locale, DST gap or overlap | `locale` / `dst_gap` / `dst_ambiguous` | Fix locale if the profile proves it; ask otherwise |
   | Rows that are simply bad | `max_rejects` | Never without consent; name the rows |

   Bump the spec `version` (MINOR: formats or values added; MAJOR: a column's meaning
   changed). Rerun until it passes.

3. **Load statements**: `data-max sql specs/<name>.spec.json --dialect <wh> --schema <schema> --what ddl,load,checks --out-dir data/clean`.
   The load follows the spec's `load.mode`:
   - `merge` and `replace_by` go through a fresh staging table, in one transaction.
   - `newer_by` keeps older exports from overwriting newer data.

   Use these statements as generated. If one doesn't fit, change the spec's load mode,
   not the SQL. Run nothing against a warehouse without the user's go-ahead. With a local
   database the user named, run it and show the checks returning 0.

4. **Report from the manifest** (`data/clean/<name>.manifest.json`):
   - per table: rows in → written, rejected, dropped by reason, deduplicated
   - control totals
   - output files
   - every assumption still open in the spec

5. **Runbook** `specs/<name>.md`, so the next export is one command:

   ```markdown
   # <name>
   <what the export is, its grain, where it comes from>
   ## Each new file
   data-max check specs/<name>.spec.json <file> --param … --baseline data/clean/<name>.manifest.json \
     && data-max apply specs/<name>.spec.json <file> --param … --out-dir data/clean --parquet
   ## Load
   <the data-max sql command>; exit 3 from check = drift, decide before loading
   ```

6. **CI or scheduler**: `data-max vendor tools/` puts the engine in the repo
   (`python3 tools/datamax.py …`), pinned with the code.

## When the spec can't express it

- **Business rules and derived values** (nights, net revenue, status logic) go to the
  warehouse model: `data-max:model`.
- **A reshape the engine lacks** (two header rows, a cross-tab): write a pre-step
  `tools/<verb>_<subject>.py` that flattens the export into a single table, then run the
  spec on its output. Rules:
  - stdlib only; input path in, output path out
  - no clock, randomness or file times
  - `Decimal` for numbers
  - exit non-zero on anything unexpected

  Put its command in the runbook.
