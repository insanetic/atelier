---
name: metric-creator
description: >-
  Build or debug declarative DSL metric (data cube) and dimension definitions as
  copy-pasteable JSON for a data source, driven by a DDL JSON schema the user
  provides. Use this whenever the user wants to define a metric or KPI as JSON
  (e.g. "CTR from search ads", "total revenue", "booking count", "cancellation
  rate"), provides or is asked to provide a DDL/schema JSON, works on a versioned
  metric JSON file or a dimensions.md, or needs to modify or debug an existing metric
  definition. Produces one named, versioned <source>/<metric>.vX.Y.json file per
  metric plus a source-level dimensions.md — JSON and Markdown definition artifacts
  only, never application code. This extends a DSL-compatible Business Analytics platform.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 1.0.0
---

# Metric Creator

Author and debug **metrics** (data cubes) and **dimensions** for a data source as
copy-pasteable artifacts. The two outputs are:

- **a metric file** — a single data cube: a select expressed in the DSL JSON dialect
  that returns exactly **one** number, aliased `value`. Named and versioned, e.g.
  `total_revenue.v1.0.json`.
- **`dimensions.md`** — the source's reusable dimensions (how the metric is sliced
  and filtered), human-readable and copy-pasteable.

## The DSL is a standalone representation, not SQL

The metric file is a **declarative JSON DSL** — a self-contained, structured
representation of a query, not SQL text. Its semantics are *derived from* and
*resemble* PostgreSQL, so leaning on what you know about PostgreSQL (how `coalesce`,
`nullif`, `sum`, division, casts behave) is a fine way to reason about a definition.
But treat that only as an aid to understanding: **don't describe these artifacts as
"SQL", and don't frame the work as "generating SQL"** — you are authoring DSL nodes
(`$project`, `$from`, `$where`, `$variadic`, …) that the platform interprets itself.

## What this is for

This skill **extends a DSL-compatible Business Analytics platform** — it authors the
analytical data cubes (metrics) and dimensions that power the platform's analytics. It
is **not** a general business-intelligence/reporting tool, not a dashboard builder, and
not a query-builder for arbitrary databases: every artifact targets the platform's
semantic layer and its runtime contract (below). If a request is really about generic
BI, ad-hoc querying, or another platform, say so rather than forcing it into this
shape.

Metrics are decision-critical: a wrong number is worse than a missing one. When you
are not certain a definition is correct, **research it, then ask — do not guess.**

## When to use

- The user wants a metric/KPI expressed as JSON (named or described).
- The user is working under `metrics/`, or hands you a DDL/schema JSON.
- The user wants to modify or debug an existing metric file or `dimensions.md`
  (wrong value, double counting, missing filter, returns >1 row, etc.).

## Output layout

Artifacts are grouped by **source** (the schema name the data lives in). Each metric
is **one named, versioned JSON file** directly under its source folder — there is no
folder per metric. By default sources live under a `metrics/` folder in the working
directory; if the user keeps their definitions elsewhere, write them there instead —
ask if it isn't obvious. The tree shape is what matters, not the base path:

```
metrics/                          # default base — point it wherever definitions live
  <source>/                       # schema name used in $from  (hotel_data_source, search_ads, …)
    dimensions.md                 # ALL dimensions for the source; shared across its metrics
    requirements.md               # OPTIONAL — only when a metric needs custom runtime vars
    total_revenue.v1.0.json       # <metric_slug>.v<MAJOR>.<MINOR>.json — one data cube → one "value"
    interaction_rate.v1.0.json
    avg_revenue_per_night.v1.0.json
```

A metric file is a **bare select node** (`$project` + `$from` + `$where`, no
wrapper) — no id, no name field inside the JSON. The metric's identity and version
come from its **filename**; ids and the display name are assigned by the platform
when the file is ingested. Dimensions carry
no ids either.

When **modifying or debugging**, read the existing `metrics/<source>/` files first
and preserve everything you are not deliberately changing.

## Naming and versioning

The filename *is* the contract — `<metric_slug>.v<MAJOR>.<MINOR>.json`. Get both
halves right.

**Metric slug — `snake_case`, business-analytics conventions.** Name by what the
number *is*, using the standard analytics vocabulary so a slug reads predictably:

| Kind of metric            | Slug prefix / shape        | Examples (slug → display)                          |
|---------------------------|----------------------------|----------------------------------------------------|
| Sum of an amount/quantity | `total_…`                  | `total_revenue` → "Total Revenue"                  |
| Count of rows/events      | `total_…`                  | `total_bookings` → "Total Bookings"                |
| Distinct count            | `unique_…`                 | `unique_guests` → "Unique Guests"                  |
| Average                   | `avg_…`                    | `avg_revenue_per_night` → "Avg Revenue per Night"  |
| Ratio / rate / percentage | `…_rate`                   | `interaction_rate` → "Interaction Rate"            |
| Min / max                 | `min_…` / `max_…`          | `max_lead_time` → "Max Lead Time"                  |

The display name is the slug in Title Case with `total_`→"Total", `avg_`→"Avg",
`unique_`→"Unique", `…_rate`→"… Rate". Keep slugs free of source names and dates —
the source is the folder, the version is the suffix.

**Version — decimal `vMAJOR.MINOR`, tagged from `v1.0`.** Every metric file is
versioned from creation (`total_revenue.v1.0.json`); there is no bare, untagged file.
New versions are added **alongside** the old ones (never overwrite), so existing
dashboards keep resolving the version they pinned:

- **Bump MINOR** (`v1.0` → `v1.1`) for a backward-compatible refinement that does not
  change what the number *means* — e.g. adding a `coalesce`, tightening a cast, fixing
  a guard. A consumer can move up without re-interpreting the metric.
- **Bump MAJOR** (`v1.1` → `v2.0`) when the **definition's meaning changes** — a
  different formula, a new business rule, a changed denominator. Consumers must opt in.

The highest version present is the current/active definition; older files are kept
for reproducibility and migration. When you supersede a metric, write the new file
and **leave the prior version in place** — call out in your summary that you did.

## The non-negotiables for a metric file

These exist because the platform rewrites your statement at query time (see
*Runtime contract* below). Break them and the metric silently returns the wrong
thing.

1. **One value out.** The outer `$project` carries exactly one expression, aliased
   `"value"`. Subqueries and CTEs may be as wide as you like internally, but the
   final result is a single value. The platform attaches the human-facing **label**
   itself, from the grouping dimension — your job is only the number.

2. **The connection filter is mandatory and unconditional.** `$where` is **always an
   `$and` array** — even with a single predicate — so filters compose cleanly. Every
   non-benchmark metric must restrict to the caller's connection as one element of
   that `$and`, never under an `$or`, never optional:
   ```json
   {
     "$and": [
       {
         "$eq": {
           "$left":  [ { "$identifier": "_connection_id", "$qualifier": { "$table": "res" } } ],
           "$right": [ { "$arg": ":connection_id" } ]
         }
       }
     ]
   }
   ```
   Qualify `_connection_id` with the alias of the table it belongs to. Omit this
   **only** for an explicitly requested benchmark/anonymized metric (those aggregate
   across peers on purpose).

3. **`$where` holds business filters only.** No time-window predicate, no grouping
   column, no dimension projection. The runtime injects the time window and the
   grouping — if you add them too you get double filtering or a broken `GROUP BY`.

4. **The projected `value` must never be null.** Wrap the outer expression so an
   empty window returns `0`, not null — `coalesce(…, 0)` around sums, averages, and
   the result of any division/rounding. A null leaks into dashboards as a gap or an
   error. (Plain counts already return `0` on an empty set, so they don't strictly
   need it — but wrapping anything that *could* go null is the safe default.)

5. **Guard division.** A ratio (CTR, conversion rate, average-per-x) must divide by
   `nullif(<denominator>, 0)` so a zero denominator yields null (then `coalesce`d to
   0) instead of erroring. Cast the numerator so you get real division, not integer
   division.

6. **Alias the base table** in `$from` (e.g. `reservation` → `res`) and qualify
   every column by that alias.

7. **Respect the data types.** Read the column types from the DDL. Add a cast only
   where the computation genuinely needs one (e.g. integer → numeric before
   dividing). If the available columns/types cannot express the metric correctly,
   **say so** rather than forcing a tower of casts that produces a plausible-looking
   wrong number.

8. **Joins are a last resort, and must not change the value.** A one-to-many join
   fans out rows and silently multiplies a `SUM`/`COUNT`. If you must join, also
   join on `_connection_id`, and **pre-aggregate the many-side in a CTE/subquery to
   one row per join key before joining** (see `references/expression-cookbook.md`).
   Prefer a metric that needs no join at all.

9. **Money must be in the proper unit — confirm the scale.** Money columns (revenue,
   spend, ADR, cost-per-x) are often **not** in the major currency unit: **minor units
   / cents** (`1999` = 19.99 → ÷100) or **micros** (ad platforms like Google Ads,
   `19990000` = 19.99 → ÷1e6) are common. Getting this wrong is off by 100× or
   1,000,000×, so **ask the user which scale the column uses** — major / cents / micros
   — unless the DDL is unambiguous (a `NUMERIC(…,2)` amount is already major units).
   When a conversion is needed, do it **in the projection** and note the chosen scale
   in your summary. See `references/expression-cookbook.md` (*Money unit conversion*)
   for the exact cast — the short version: cast to `NUMERIC` (not `DOUBLE`), divide by
   a constant `$scalar`, no `nullif` on that divisor.

## Runtime contract

You write a *fragment*; the platform completes it per request. Knowing what it adds
tells you what to leave out.

**Magic variables** — all start with `:` and are bound at query time. Reference them
with `$arg`. The standard set, always available:

| Variable             | Meaning                                          |
|----------------------|--------------------------------------------------|
| `:connection_id`     | The caller's connection (the mandatory filter).  |
| `:window_start`      | Inclusive start of the requested time window.    |
| `:window_end`        | Inclusive end of the requested time window.      |
| `:periodicity_unit`  | The grain for time bucketing (day, month, …).    |

**What the runtime injects, so you must not:**

- The **time window** — from the chosen temporal dimension, as
  `<column> BETWEEN :window_start AND :window_end`. Do not put this in `$where`.
- The **grouping** — from the chosen `group` dimension: it adds the dimension's
  projection (bucketing temporal ones with `:periodicity_unit`), the `GROUP BY`, and
  the `ORDER BY`. Do not project or group by the dimension yourself.
- User **filters** chosen against `perspective` dimensions, merged into `$where`.

So a finished metric file is: one `value`, a `$from`, optional `$join`, and a
`$where` containing the connection filter plus any intrinsic business filters — and
nothing time- or grouping-related.

## Dimensions (`dimensions.md`)

Dimensions are defined **once per source** and reused across its metrics. Two
dimensions are needed at minimum so a metric can be both sliced and filtered:

- **`group`** scope → the runtime adds it to `GROUP BY`; it produces the row label.
- **`perspective`** scope → the runtime adds it to `$where` as a user filter.

Every metric needs **at least one `group` and one `perspective`** dimension visible
to it. Temporal columns are usually defined as a **pair** — the same column in both
`group` and `perspective` scope — so the metric can be both bucketed over time and
filtered by it.

Use this block per dimension — readable, and every value is copy-pasteable:

```markdown
### Created On
- **Display Name:** Created On
- **Scope:** group            # group → GROUP BY (label) | perspective → WHERE filter
- **Semantic Type:** temporal  # categorical | temporal
- **Identifier:** create_date_time      # exact column name from the DDL
- **Alias:** res_create_date_time_label # referenceable result alias
- **Qualifier:** res                     # table alias from the metric $from (schema if unaliased)
- **Used by:** total_revenue, avg_revenue_per_night
```

Field meanings:

- **Identifier** — the exact column name in the table.
- **Alias** — the alias the runtime gives the projected dimension; what the label
  comes from and what other clauses can reference. Convention:
  `<qualifier>_<column>_label`.
- **Qualifier** — the table **alias** used in the metric's `$from` (e.g. `res`). Use
  the **schema** name instead only if that table is referenced unaliased.
- **Used by** — every metric slug that uses this dimension. This is the index that
  keeps the source coherent; keep it accurate (next rule).

**Keep `Used by` current — the dimension and the metric must agree.** Whenever you
add or change a metric, reconcile `dimensions.md` in the **same** edit:

- If the metric reuses an **existing** dimension, **append its slug** to that
  dimension's `Used by` (don't duplicate the dimension). Add the slug to *both* the
  `group` and `perspective` member of a pair if the metric uses both scopes.
- If the metric needs a dimension that doesn't exist yet, **add the dimension**
  (usually a group/perspective pair) with this metric in `Used by`.
- Reference metrics by their **base slug**, not the versioned filename — dimensions
  are shared across all versions of a metric, so `total_revenue` (not
  `total_revenue.v1.0`). A new metric *version* needs no `Used by` change unless it
  starts or stops using a dimension.
- When debugging, if a metric references a dimension that isn't listed against it,
  that mismatch is itself a likely bug — fix the `Used by`, and check the metric is
  actually sliceable/filterable the way the dimension implies.

**Reuse and duplication:** dimensions are shared across metrics built on the **same
table**. If two different tables happen to have a same-named column (e.g. both have
`status`), define a **separate** dimension for each, qualified to its own table —
they are not interchangeable. A dimension whose column lives in a table the metric
doesn't already select forces a join into that metric; avoid that when you can.

## `requirements.md` (source level, optional)

Create this only when a metric needs a **custom** magic variable beyond the four
standard ones — because that's a contract the platform must satisfy for the whole
source, not a property of one metric. Document each custom variable: its `:` name,
what it means, its type, and which metric(s) rely on it. If no metric needs a custom
variable, this file doesn't exist.

## Workflow

1. **Detect the mode.** New metric, or modify/debug an existing one? For
   modify/debug, read the relevant `metrics/<source>/` files first. Decide whether
   the change is a MINOR refinement or a MAJOR redefinition (see *Naming and
   versioning*) and write the new version **alongside** the old file.

2. **Get the DDL.** You need the source's schema as a DDL JSON (an array of
   `{ name, tables: [ { name, columns: [ { name, dataType, … } ] } ] }`). If the
   user hasn't provided one, **ask them for it** — don't invent a schema. The
   `name` at the top is the source/schema; each `tables[].name` is a table.

3. **Pin down the metric.** Exactly what single number is wanted, from which source,
   at what grain, with what business rules (e.g. does "revenue" mean only confirmed
   bookings)? Restate it before building, and settle the **slug + display name** from
   the naming conventions (see *Naming and versioning*).

4. **Locate the columns** in the DDL and check their `dataType`s actually support
   the computation. **If the metric is about money, resolve the unit scale now**
   (major / cents ÷100 / micros ÷1e6) — ask the user unless the DDL is unambiguous.

5. **Unsure how the metric is defined? Research before building.** If the formula or
   convention is at all ambiguous (how a platform defines CTR, what its impression
   field is called, what counts as a "session"), **WebSearch first.** Confirm the
   definition against an authoritative source.

6. **Still unsure, or columns missing? Ask the user.** Not implementing beats
   implementing wrong. State precisely what's missing or ambiguous.

7. **Build** the metric file `<slug>.v<MAJOR>.<MINOR>.json` (single `value`,
   connection filter, business filters only) and reconcile `dimensions.md` in the
   same pass — append this metric's slug to the `Used by` of every dimension it
   reuses, and add any new dimension it needs (≥1 `group` + ≥1 `perspective`). Add
   `requirements.md` only if a custom variable is needed.

8. **Validate and deliver.** Run the checklist below, then present the JSON as a
   copy-pasteable block (and the dimension blocks), stating the filename, version,
   and — for money — the unit scale you applied.

## Validation checklist

Before delivering, confirm:

- [ ] The filename is `<slug>.v<MAJOR>.<MINOR>.json`; the slug follows the naming
      conventions (see *Naming and versioning*) and a superseded prior version, if any,
      is left in place.
- [ ] The outer projection is exactly one expression, `"$as": "value"`.
- [ ] The projected `value` can never be null — `coalesce(…, 0)` wraps the outer
      result (sum/avg/division/rounding).
- [ ] `$where` contains the `_connection_id = :connection_id` filter, ANDed and
      unconditional (unless this is an explicit benchmark metric).
- [ ] `$where` contains **no** time-window predicate and **no** grouping column.
- [ ] Divisions use `nullif(denominator, 0)` and a numeric cast.
- [ ] If money: the unit scale is resolved and converted in the projection (÷100 for
      cents, ÷1e6 for micros) with a numeric cast — or confirmed already in major units.
- [ ] Every column is qualified by its table alias; the base table is aliased in
      `$from`.
- [ ] If there's a join: it includes `_connection_id`, and the many-side is
      pre-aggregated so no value is multiplied. Re-derive the row count in your head.
- [ ] The metric has ≥1 `group` and ≥1 `perspective` dimension in `dimensions.md`,
      and each dimension it uses lists this metric's base slug in `Used by` (append it
      to existing dimensions rather than duplicating them).
- [ ] The JSON validates against `references/semantic-layer-schema.json`.

## References

Read these as needed — they aren't required for every metric:

| File | When to read |
|------|--------------|
| `references/semantic-layer-schema.json` | The full DSL grammar. Consult for any clause or function you're unsure is expressible, and to validate output. |
| `references/expression-cookbook.md` | Copy-pasteable JSON for the common shapes: sum, count-distinct, the CTR/ratio pattern, the rounded-percentage + flag-denominator rate, money unit conversion, filtered aggregates, CASE, and the CTE pre-aggregation that prevents join fan-out. Also the `$arg` vs `$var` vs `$scalar` distinction. |
| `references/examples/hotel_data_source/` | A complete worked source: `dimensions.md` plus `total_revenue`, `avg_revenue_per_night`, and the more involved `interaction_rate` metric files. Read it to see how the pieces fit together end to end. |
