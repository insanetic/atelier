---
name: model
description: >-
  Use when warehouse tables (loaded or about to be) need durable models on top -
  staging models, fact and dimension tables, a star schema, a mart for a report,
  incremental loads, history of changing records (SCD2, snapshots), dbt or
  SQLMesh models and their tests - "build a fact table for bookings", "model
  this in dbt", "monthly revenue by segment", "keep the history of status
  changes", "load this incrementally without duplicates", "design the marts".
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 2.1.0
---

# Model

Build tables people can trust: one stated grain each, tested, documented, identical after a
rebuild, and verified on data before anyone calls them done. Read `references/methods.md`
before designing; code shapes are in `references/patterns.md`.

## Workflow

1. **Read the sources, invent nothing.** Use data-max specs (`specs/*.spec.json`), DDL,
   `information_schema` or the project's sources. Stay in the stack you find: `dbt_project.yml`
   → dbt; SQLMesh config → SQLMesh; otherwise plain SQL for the user's warehouse.

2. **Write the design table first**, with these columns: model | grain ("one row per …")
   | key | sources and join cardinality | measures (additive or not) | tests.
   Get a yes on the grains. With nobody to ask, state them and continue.

3. **Find the traps before writing SQL**, and name how each is handled:
   - **Fan-out**: an order-level value (discount, shipping, total) joined to lines is
     multiplied. Aggregate lines to the order first, or allocate the value explicitly.
   - **History**: an attribute "as it was at the time" (segment, price, owner) needs SCD2.
     A source that only holds the current state has **no past**. Snapshot from now on,
     backfill the past from another record (seed, CRM, audit log), and label the rest
     `unknown`. Never attribute old facts to today's value.
   - **Time**: business days are local days. A UTC timestamp needs the business's time zone
     before it becomes a date or month.
   - **Currency**: never add currencies together. Group by currency, or convert with a rate
     table at the event date.
   - **Late changes**: refunds and cancellations change past periods. Say whether reports
     restate or book the change when it happens.
   - **Deletes**: decide what a row that vanished upstream means.

4. **Layer**: staging (rename, cast; no joins) → intermediate (joins, rules, re-graining) →
   marts. Source tests for data-max specs: `data-max sql specs/<name>.spec.json --dialect <wh> --what dbt`.

5. **Make loads idempotent.** Incremental models:
   - merge on the grain key
   - filter on a change column (`updated_at` or load time), never on the creation date
   - reprocess a lookback window
   - must equal a full rebuild

6. **Test**: per model, `unique` + `not_null` on the grain key, `relationships`,
   `accepted_values`, a unit test for each rule with a trap (allocation, as-of join, time
   zone), and a reconciliation of the mart total against staging. Descriptions start with
   the grain.

7. **Run it and show numbers.** `dbt build` against the real warehouse, or locally:
   dbt-duckdb, or the SQL in DuckDB, on sample rows or the clean files from
   `data-max:clean`. If there are no rows, write a few that hit each trap. Show the mart's
   rows and the test results, and run it twice to prove the rerun changes nothing. Never
   call a model done that hasn't run.

## Red flags: stop and fix the design

- A grain you can't say in one sentence, or `SELECT DISTINCT` hiding a fan-out.
- A sum that changes when a dimension is joined.
- An as-of attribute taken from a current-state table.
- An incremental filter on `created_at`, or a model that can't be rebuilt from scratch.
- Amounts in different currencies added together.
