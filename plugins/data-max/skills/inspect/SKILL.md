---
name: inspect
description: >-
  Use when the user shares or points at a raw data file or export (CSV, TSV,
  Excel, JSON, JSONL, XML, a bank, shop, PMS or ads report) and wants to know
  what's in it, what's wrong or weird about it, how to clean it, or how it
  should land in a warehouse (BigQuery, Snowflake, Postgres, ClickHouse,
  DuckDB) - "what's in this file", "take a look at this file", "what does this
  data look like", "anything I should know before loading it",
  "anything weird in here", "review this export", "profile this", "is this
  ready for the warehouse", "get this into Postgres", money stored as text, odd
  date formats, Excel junk rows, nested JSON. Writes the cleaning spec that
  data-max:clean runs.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 2.1.0
---

# Inspect

Turn an unknown export into a **spec** (`specs/<name>.spec.json`) that the `data-max` engine
proves on every row, plus a **review** (`specs/<name>.review.md`). The source file is never
modified. `data-max spec` prints the spec format; read it before writing one.

## Workflow

1. **Profile every row**: `data-max profile <file> --draft-spec specs/<name>.spec.json`
   (`--rows-from 'orders[]'` for JSON/XML arrays, `--sheet`, `--header-row`, `--encoding`
   when detection is wrong). The profile covers the whole file; also read the head and tail
   yourself. If the spec already exists, draft to `specs/<name>.draft.json`.

2. **Decide every `TODO`** in the draft, plus anything the profile flags. Ask in one batch
   (AskUserQuestion, recommended option first). With nobody to ask (headless, "don't wait
   for me"), take the default and add it to the spec's `assumptions`:

   | Decision | Default without an answer |
   |---|---|
   | Grain, key | A stable business key from the profile's candidates (`#index` for child lines). Never the file row number for recurring exports. |
   | Repeated identical rows | Keep (`dedupe: none`) unless a control total proves they are duplicates. |
   | Load mode | `merge` on the key with `newer_by` when records change and exports overlap; `replace_by` for child rows (`by` parent key, `newer_by` the parent's `updated_at` via `^`) and keyless period files (`by` period); `append` only for files loaded once. |
   | Naive timestamps | `datetime` (wall clock) with the zone as an open question. Never guess a zone. |
   | Ambiguous day/month | Stop: it changes the data. Ask, or leave the TODO and say so. |
   | Category variants | `map` case/spelling variants; `allowed` = values seen. |
   | PII | `drop`. `hash` only when needed as a join key, with the salt in an env var (`"env"` on the param). |
   | Implausible values | Keep; list them as open questions. |

3. **Use what the file states about itself.** Footer totals, record counts, opening and
   closing balances, page metadata: filter those rows out and turn the numbers into
   `control_totals`. Then every run proves that nothing was lost or double-counted.

4. **Prove it**: `data-max check specs/<name>.spec.json <file> --param …` until the verdict
   is "loadable" with zero rejects. A failure means the spec is wrong or a decision is
   missing. Don't raise `max_rejects` to hide it.

5. **Write the review** (template below). The reply carries the same content: verdict, every
   finding with its evidence, decisions, assumptions, open questions. Many users read only
   the reply.

6. **Continue or hand over.** If the user asked for loadable or clean data ("get it into
   Postgres", "ready for BigQuery"), run `data-max:clean` now. Otherwise offer it.

## Review template

```markdown
# Review: <file>
**Verdict:** <loadable as-is / after cleaning / blocked by an open question>

## File
<encoding and BOM, delimiter, header row and preamble, footer/total rows, NULL tokens,
records in vs data rows. The spec handles these, but a loader without it breaks on them.>

## Decisions
| Decision | Choice | Why, or "assumed" |

## Blocks the load or corrupts numbers
<each: what (rows and values from the profile), why it matters, how the spec handles it>

## Makes analytics correct
<money, time, categories, names, NULLs, lineage>

## Target tables
<per table: grain, key, load mode, columns with types; join keys>

## Open questions
<only the data owner can answer; implausible values>
```

Cite counts and row numbers, not impressions. Each item says why it matters: the user
often can't change the source.

## Judgment calls

- **Money**: `decimal` with explicit `scale` plus a `currency` column. Minor units (cents,
  micros) use `divide_by`.
- **Time**: offsets present → `timestamp` (UTC). Known zone → `timestamp` + `tz`.
  Unknown zone → `datetime`.
- **Identifiers** with leading zeros stay strings. IBANs and phone numbers: strip spaces
  with a `map` only if downstream joins need it.
- **Split** a file only when two grains would double-count, such as order totals on every
  line.
- **Business logic** (net revenue, status rules) belongs in the warehouse model
  (`data-max:model`), not the spec.

`references/examples.md` has before → after spec fragments for common export problems.
