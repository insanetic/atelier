# Modelling methods

The methods below are the defaults. Deviate only with a stated reason.

## Dimensional modelling (Kimball)

Design in four steps, in order:

1. **Business process**: the event being measured (a booking is made, a night is stayed,
   an order ships). One fact table per process, not per report.
2. **Grain**: what one fact row is, in one sentence, at the lowest level available. "One
   row per booking" and "one row per booking per stay night" are different tables with
   different sums. Declare the grain before choosing columns.
3. **Dimensions**: the context, as foreign keys: who (guest, customer), what (product,
   room type), where (hotel, channel), when (date). A dimension row describes one thing;
   it carries the attributes people filter and group by.
4. **Facts**: the numbers at that grain.
   - Additive: sums across every dimension (amount, nights, quantity).
   - Semi-additive: sums across some dimensions but not time (balances, inventory, open
     bookings). Use the period end value or an average across time.
   - Non-additive: ratios and prices. Store numerator and denominator, compute the ratio
     at query time.

Fact table types:
- **Transaction**: one row per event.
- **Periodic snapshot**: one row per entity per period, such as daily occupancy per hotel.
- **Accumulating snapshot**: one row per process instance, with milestone dates (booked,
  confirmed, arrived, paid), updated as it moves on.

Conformed dimensions (one `dim_hotel`, one `dim_date`) are shared by every fact that uses
them, so numbers from different facts line up.

Keys:
- The natural key (from the source) plus `tenant_id` stays on the dimension.
- A surrogate key (a hash of the natural key columns) is useful when sources disagree on
  keys or when SCD2 creates several rows per entity.
- The fact references the dimension's key that was valid at the event time.

## Layering

| Layer | Contains | Rules |
|---|---|---|
| sources | Raw loaded tables | Declared with tests (`data-max sql --what dbt`); never queried by marts directly |
| staging `stg_<source>__<table>` | One model per source table | Rename, cast, standardize units and time zones, light dedup. No joins, no business logic. Usually views. |
| intermediate `int_<entity>_<verb>` | Reusable building blocks | Joins, business rules, re-graining (e.g. booking → booking nights) |
| marts `fct_<process>`, `dim_<entity>` | What consumers query | Stated grain, tested keys, descriptions; tables or incremental |

Medallion (bronze / silver / gold) is the same idea with different names.

## Idempotent and incremental loads

- **A rerun must not change the result.** Full rebuilds are the reference; an incremental
  model must produce the same table as a full rebuild.
- **Incremental with a unique key**: `merge` (or `delete+insert` where merge isn't
  available or the key isn't guaranteed unique) on the grain key. Without a unique key,
  every rerun appends duplicates.
- **Filter on what changes**: select rows by `updated_at` or a load timestamp, never by
  `created_at`. A status change on an old order keeps its old `created_at` and would be
  skipped forever.
- **Lookback**: reprocess a window (for example the last 3 days, or the export's period)
  to catch late and corrected rows. Choose the window from how late the data really
  arrives.
- **Partition overwrite** (insert_overwrite by date) for large append-only event tables.
- **Overlapping exports** (a 6-month window loaded weekly) are merges on the natural key,
  never appends.
- **Deletes**: decide how a row that vanished from the source is handled: ignore it,
  mark it deleted, or close it in a snapshot (`hard_deletes`).

## History: slowly changing dimensions

| Type | Behaviour | When |
|---|---|---|
| 0 | Never changes | Original values, such as signup channel |
| 1 | Overwrite | Corrections, or attributes nobody reports historically |
| 2 | New row per change: `valid_from`, `valid_to`, current flag | Status, price, owner, segment, anything a report needs "as it was then" |

Implement Type 2 with a snapshot:
- Use the `timestamp` strategy when the source has a reliable `updated_at`. `dbt_valid_from`
  is then that `updated_at`.
- Otherwise use `check` on the tracked columns. `dbt_valid_from` is then the snapshot's run
  time, not the moment of the change.

dbt names the columns `dbt_valid_from` / `dbt_valid_to`. The current row has
`dbt_valid_to IS NULL`, unless `dbt_valid_to_current` is configured.

Join facts on `event_time >= valid_from AND (event_time < valid_to OR valid_to IS NULL)`.

- **Facts older than the first snapshot** match no version. Either:
  - backfill earlier versions from another record (a seed or audit log) in an intermediate
    history model that unions them with the snapshot, or
  - label those facts `unknown`.

  Stretching the first version back to the beginning of time is right only when the
  attribute never changes (Type 0).
- **Take snapshots on every load.** A change between two runs is lost, so the snapshot
  cadence is the history's resolution.

## Time zones and business dates

Store instants in UTC, and report in the business's time zone. Convert before truncating:
`date(created_at AT TIME ZONE 'Europe/Vienna')`, or `DATE(created_at, 'Europe/Vienna')` in
BigQuery. Otherwise an order at 23:30 local time lands on the next day or month. A
multi-tenant model takes the zone from the tenant dimension.

## Currencies

Never add amounts in different currencies. Either:
- group by `currency` all the way to the report, or
- convert with a rate table (`fx_rates(date, from_currency, to_currency, rate)`) at the
  event date, and keep the original amount and currency next to the converted one.

State which rate source and date rule is used: event date, or month-end for accounting.

## Joins and grain safety

- Before every join, write down the cardinality: many-to-one into a dimension is safe;
  one-to-many multiplies every measure on the left.
- Pre-aggregate the many side to the target grain before joining it.
- Never use `SELECT DISTINCT` to hide a fan-out. Find the join that caused it.
- After a model is built: assert the grain key is unique, and reconcile one measure
  against the layer below (the sum of amount in the fact equals the sum in staging for
  the same filter).

## Naming and style

- snake_case everywhere, plural or singular consistently (pick what the project uses).
- Prefixes: `stg_`, `int_`, `fct_`, `dim_`; source in staging names
  (`stg_pms__bookings`).
- Columns:
  - Keys: `<entity>_id`.
  - Booleans: `is_` / `has_`.
  - Timestamps: `<event>_at` (UTC) and dates `<event>_date`.
  - Amounts carry their unit (`amount`, `currency`; `weight_kg`).
- One CTE per logical step. Import CTEs at the top (`with bookings as (select * from
  {{ ref(...) }})`), the final `select` at the bottom.

## Testing

| Kind | What | Where |
|---|---|---|
| Contract | Types, not-null, accepted values, uniqueness of every grain key | Generic tests on sources and marts |
| Relationships | Every fact foreign key exists in its dimension | Generic test |
| Unit | Logic on fixed inputs: date math, status rules, currency handling, incremental filters | dbt `unit_tests` / SQLMesh tests, in dev and CI |
| Reconciliation | A mart total equals the staging total; row counts across layers explained | Singular test returning failing rows |
| Freshness | Newest data is recent enough | Source freshness |

A test is a query that returns rows only when something is wrong.

## Documentation

- Every model's description starts with its grain: "One row per booking night. …".
- Every column gets a description; units and time zones are stated.
- Every metric-relevant rule is stated where it is implemented. For example: "revenue
  excludes cancelled bookings".
