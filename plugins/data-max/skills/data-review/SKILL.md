---
name: data-review
description: >-
  Review a data file (CSV today; JSON/XML/Excel exports too) for how well it
  will land in a data warehouse when uploaded mostly as-is, and produce a tiered
  cleansing report. Use this whenever the user shares or points at a CSV/TSV/
  spreadsheet/JSON/XML and asks how to clean it up, prepare it for a warehouse or
  BigQuery/Snowflake/ClickHouse/Postgres, fix column names, handle money or date
  columns, deal with Excel header/footer junk, decide whether one file should
  become several, or asks "is this table any good for analytics / what's wrong
  with this data". Also trigger on phrases like "review this data model", "clean
  this export", "get this ready for the warehouse", "unpivot", "tidy this up for
  loading", or when money is stored as text and dates are in weird formats.
  Produces a markdown review report and explains the reasoning behind every
  recommendation. Performing the cleanup is a separate step — see the
  data-transform skill, which consumes this report.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 1.0.0
---

# Data Max — Data Review

Review a data file for **warehouse readiness** and tell the user, with reasons,
how to cleanse it. The mental model: the user wants to upload this file **mostly
as-is** into a columnar data warehouse and then run analytics and calculations on
it. Your job is to find everything that will make that painful or wrong, and to
propose the smallest set of changes that buys the biggest benefit — while still
showing the ideal target.

**This skill reviews; it does not transform.** The deliverable is a **markdown
report** (`<filename>-review.md`) plus a short inline summary. You never hand-edit
data and you never write transformation scripts here. When the user wants the
cleanup actually done, that report is the hand-off to the **data-transform** skill
(see "Handing off" below).

## Core principles

- **Explain the why, every time.** A recommendation without a reason is noise.
  The user often *can't* change the source freely (it's an export, an API dump,
  a vendor file), so they need to understand the payoff to decide what's worth it.
- **Tier everything by cost/benefit.** Separate what *breaks* loading from what
  *improves* analytics from what's merely *nice*. See the report template.
- **Minimal viable change first, ideal second.** Always give a cheap path that
  still helps, *and* the better redesign. Let the user choose. Don't bury them.
- **Denormalization is fine.** This is analytics, not OLTP. Duplication that
  makes one flat, query-friendly table is usually *better* than textbook 3NF.
  Don't normalize for its own sake.
- **CSV is the target output.** If the input is JSON/XML/Excel, describe the
  CSV(s) it should become. If it's already CSV, describe the cleaned CSV.

## Workflow

1. **Inspect the file yourself.** Read it directly — the header row, the first
   chunk of rows, and the tail (footers hide there). Judge each review dimension
   by eye:
   - rows that aren't part of the table (title banners, blank separators,
     repeated mid-table headers, `TOTAL` footers) and rows whose column count
     differs from the rest;
   - column-name hygiene (spaces, capitals, punctuation, units-as-symbols,
     leading digits, blanks, duplicates);
   - money columns stored as text (`"$1,234.50"`) or float;
   - date/datetime columns and whether they're ISO 8601 / RFC 3339;
   - whether any column anchors each row in time;
   - headers that are really *period or category values* (`Jan, Feb, …`,
     `2021, 2022`) — the wide-format smell.

   For a large file you don't need every row — read a representative sample (the
   first ~50 rows plus a tail) and reason from it. For JSON/XML/Excel, inspect
   the structure (list keys / sheets / nesting depth, read a sample record) and
   reason about which flat CSV(s) it should become.

2. **Ask the two questions the data can't answer for you** (only if not already
   clear from context):
   - **Isolation:** "Is this data scoped to a tenant / customer / account / brand?
     Should rows from different ones ever be queried separately?" If yes, every
     row needs an isolation column (see below).
   - **Change budget:** "Can you change how this file is produced, or are you
     stuck with it as an export?" This sets how aggressive your "must" tier is
     versus what you push into a transformation later.

3. **Review across the dimensions below**, as a checklist — but apply judgment.

4. **Decide single vs. multiple CSVs** (see "One file or several"). This decision
   is what the data-transform skill will execute as "file A → N files", so be
   explicit about it.

5. **Write the report** using the template. Lead with the inline summary, write
   the full `<filename>-review.md`.

6. **Hand off** (see "Handing off").

For worked before/after examples of every dimension, read
`references/examples.md`. Don't inline those examples here — point the user there
or pull the one that fits.

## Review dimensions

Each item below is: what to look for → why it matters → what to recommend.

### 1. Structural junk (Excel/report exports)

Title banners, logos, merged cells, blank separator rows, repeated mid-table
headers, and footer "Total" rows. **Why it breaks:** a warehouse load expects
exactly one header row followed by uniform, same-width data rows; anything else
either fails the load or pollutes the table with garbage rows that corrupt every
aggregate. **Recommend:** strip everything except the single real header + data
rows. This is almost always a **must**. Spot it by reading the head and tail and
watching for rows whose column count differs from the rest.

### 2. Column names

Spaces, capitals, punctuation, unit suffixes like `Revenue ($)`, leading digits,
duplicate names, blank headers. **Why it matters:** these become SQL identifiers.
Non-standard names force fragile quoting (`"Revenue ($)"`), break case-sensitively
across warehouses, and collide. **Recommend:** lowercase `snake_case`, ASCII,
descriptive, unique; move units into the name as meaning, not punctuation
(`revenue_usd`, not `Revenue ($)`). Usually **recommended**, occasionally a
**must** (blank/duplicate headers break loads).

### 3. Money / financial columns  ← high-value

Amounts stored as text (`"$1,234.50"`, `"1.234,50 €"`) or as floats. **Why it's
wrong on two counts:**
- **Text can't be summed or compared numerically.** A warehouse will type it as
  VARCHAR and every `SUM`/`AVG`/`>` either fails or sorts lexically ("$9" > "$10").
- **Floats lose money.** Binary floating point can't represent `0.10` exactly, so
  sums drift by cents over millions of rows — unacceptable for financial figures.

  **Recommend:** add a companion integer column holding the value in **minor
  units** — *mills* (×1000, 3 implied decimals) or *micros* (×1,000,000, 6
  decimals) — e.g. `amount` → add `amount_mills`. Integers are exact, sum
  perfectly, sort correctly, and divide back to a display value when needed. Use
  micros when sub-cent precision matters (FX, ad spend, unit costs); mills is
  plenty for ordinary currency. Keep the original column too if it aids reading —
  duplication is fine. Always name the unit in the column (`_mills` / `_micros`)
  so nobody mistakes scaled integers for raw values. This is a flagship
  **recommended** change; explain it clearly because it's non-obvious.

### 4. Dates and datetimes  ← high-value

Formats like `05/26/2026`, `26.05.2026`, `May 26, 2026`, `20260526`. **Why it
matters:** ambiguous (is `05/06` May 6 or June 5?), they sort wrong as text, and
every warehouse parses them inconsistently. **Recommend:** ISO 8601 for dates
(`2026-05-26`) and RFC 3339 for timestamps (`2026-05-26T14:30:00Z`, with explicit
timezone). These sort chronologically as plain text, parse unambiguously
everywhere, and carry timezone correctly. Typically a **recommended**/**must**
depending on whether the load would misparse them.

### 5. A time dimension must exist

If no column anchors each row in time, analytics can't do trends, partitioning,
retention, or period comparisons — the bread and butter of a warehouse. **Why:**
columnar warehouses are built to slice by time; a table with no date is nearly
inert for analytics. **Recommend:** identify the event/record date; if it only
exists implicitly (e.g. in the filename or a report title), add an explicit column
and populate it. Often a **must** for the data to be useful at all.

### 6. Tenant / customer isolation

If you confirmed the data is per-tenant/customer/account, **why it matters:** in a
shared warehouse, rows from different tenants must be filterable and never silently
mixed into a cross-tenant aggregate — that's both a correctness and a data-leakage
problem. **Recommend:** add an explicit isolation column to *every* row
(`tenant_id`, `customer_id`, `account_id`) with a stable identifier, even if the
file "is obviously just one customer's data" today — because the moment two such
files land in the same table, unlabeled rows are unrecoverable. Usually a **must**
when isolation was confirmed.

### 7. Shape: long vs. wide (columnar fit)  ← high-value

The classic problem: **periods or categories encoded as column headers** — e.g.
columns `Jan, Feb, Mar, …` or `2021, 2022, 2023`, with values spread across them.
**Why it's wrong for a warehouse:** each new period forces a *schema change* (a new
column), you can't `GROUP BY month` or filter a date range, and aggregation across
periods means naming every column by hand. Columnar analytics wants **long/tidy**
data: one row per observation, the period as a *value* in a `date`/`period` column,
and the measure in one `value` column. **Recommend:** unpivot (rotate wide→long) —
remove the period columns, add a `period`/`date` column plus a `value` column, and
write one row per (entity, period). The reverse also happens (one attribute split
across many rows that should be columns); pivot long→wide in that case. This is
high-value but can be a bigger lift — present it as **recommended** with a clear
before/after.

## One file or several

When the input is nested (JSON with arrays of arrays, XML, a multi-sheet workbook,
or a CSV that crams two different grains into one table), decide whether it should
become **multiple related CSVs**. **Why:** mixing grains (e.g. order headers and
line items, or customers and their events) in one flat file forces repetition that
can be wrong (which columns are per-order vs per-line?) and makes some aggregates
double-count. **But don't over-split** — only separate when the grains are genuinely
different and would otherwise corrupt counts. For each proposed CSV, give: its
**grain** (what one row means), its columns, and the **key** that joins it back to
the others. If one denormalized file is fine, say so and explain why splitting
wouldn't pay off. See `references/examples.md` for a normalization example.

## Report template

Write `<filename>-review.md` with this structure. Keep reasons attached to every
item — the tiers are about *cost/benefit*, not severity for its own sake. This
report is also the **spec** the transformer reads, so make the "Target CSV shape"
and the single-vs-multiple decision concrete and unambiguous.

```markdown
# Data model review — <filename>

## Summary
<2–4 sentences: what the file is, the grain, the headline issues, and whether
it's close to warehouse-ready or needs real work.>

## ✅ What's already good
<Things to keep. Builds trust and tells the user what NOT to touch.>

## 🔴 Must fix — blocks or corrupts a warehouse load
<Change / remove / add items that, left alone, make the load fail or produce
wrong results. Each: what, why, and the concrete fix.>

## 🟡 Recommended — makes analytics correct and pleasant
<High-value improvements: money→mills, ISO dates, unpivot, tenant column, name
cleanup. Each with its why and before→after.>

## ⚪ Optional — nice to have
<Lower-priority polish. Be honest that these are skippable.>

## 🎯 Target CSV shape
<The cleaned header row and 1–2 example rows. If multiple CSVs: one block each,
stating grain + join key. This is what the transformer will produce.>

## 🪜 Minimal viable change
<If the user is constrained: the smallest subset of the above that still gives
real benefit, and what they give up by stopping there.>
```

## Handing off

When the user wants the cleanup **actually done** — files transformed, not just
described — that is the **data-transform** skill. It consumes this
report (the `<filename>-review.md`) plus the original file and produces the cleaned
CSV(s) via an ad-hoc, rerunnable script.

Do **not** write transformation scripts in this skill. After delivering the report,
offer the next step: *"Want me to apply this? That's the transformer step — it
takes this review and produces the cleaned file(s)."* The clearer your "Target CSV
shape" and single-vs-multiple decision, the cleaner that hand-off.

## Other input formats

The dimensions above are format-agnostic — they're about the *target* table. For
JSON/XML/Excel the extra work is deciding how nesting flattens into rows and
columns and how many CSVs result; everything else (money, dates, names, isolation,
time dimension, shape) applies identically to the resulting CSV(s).
