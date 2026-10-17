# Code patterns

Examples use the hotel bookings source from a data-max spec (`raw.bookings`: tenant_id,
booking_id, arrival_date, nights, amount, currency, status, created_at, updated_at). Adapt
names; keep the shapes.

## dbt

### Staging: rename, cast, standardize. Nothing else.

```sql
-- models/staging/pms/stg_pms__bookings.sql
-- Grain: one row per booking per tenant (latest state).
with source as (
    select * from {{ source('bookings', 'bookings') }}
)
select
    tenant_id,
    booking_id,
    arrival_date,
    nights,
    cast(amount as numeric(18, 2))      as amount,
    upper(currency)                      as currency,
    status,
    created_at,
    updated_at
from source
```

### Re-grain in intermediate: one row per stay night, money exact

```sql
-- models/intermediate/int_booking_nights.sql
-- Grain: one row per booking per stay night. Fans out on purpose (1 -> nights); day-use
-- bookings (nights = 0) keep one row. The rounding remainder goes to the last night, so
-- the nights sum back to the booking amount exactly.
with bookings as (select * from {{ ref('stg_pms__bookings') }}),
night_index as (
    select generated_number - 1 as night_index
    from ({{ dbt_utils.generate_series(upper_bound=60) }}) s   -- longest stay; tested below
),
nights as (
    select
        b.tenant_id,
        b.booking_id,
        {{ dbt.dateadd('day', 'n.night_index', 'b.arrival_date') }} as stay_date,
        n.night_index,
        greatest(b.nights, 1) as n_nights,
        b.amount,
        b.currency,
        b.status
    from bookings b
    join night_index n on n.night_index < greatest(b.nights, 1)
)
select
    tenant_id, booking_id, stay_date, currency, status,
    case when night_index = n_nights - 1
         then amount - round(amount / n_nights, 2) * (n_nights - 1)
         else round(amount / n_nights, 2) end as amount_per_night
from nights
```

Test that no booking is longer than the series (`max(nights) <= 60`). Otherwise nights are
silently cut off.

### Order-level values next to lines: aggregate first

```sql
-- Grain: one row per order. Lines are summed to the order before the order-level
-- discount is applied; joining orders to lines first would subtract the discount once per line.
with lines as (
    select order_id, sum(qty * unit_price) as gross from {{ ref('stg_shop__order_lines') }} group by 1
)
select o.order_id, o.currency, l.gross, coalesce(o.order_discount, 0) as discount,
       l.gross - coalesce(o.order_discount, 0) as net
from {{ ref('stg_shop__orders') }} o
join lines l on l.order_id = o.order_id   -- one-to-one after the aggregation
```

When a line-level mart needs the discount, allocate it by line share, and put the rounding
remainder on one line so the totals still reconcile.

### Incremental fact: merge on the grain, filter on what changes

```sql
-- models/marts/fct_bookings.sql
-- Grain: one row per booking per tenant. Status changes on old bookings arrive through
-- updated_at; filtering on created_at would skip them forever.
{{ config(
    materialized='incremental',
    unique_key=['tenant_id', 'booking_id'],
    incremental_strategy='merge',
    on_schema_change='append_new_columns'
) }}
with bookings as (select * from {{ ref('stg_pms__bookings') }})
select
    tenant_id,
    booking_id,
    arrival_date,
    nights,
    amount,
    currency,
    status = 'cancelled' as is_cancelled,
    created_at,
    updated_at
from bookings
{% if is_incremental() %}
where updated_at >= (select {{ dbt.dateadd('day', -3, 'max(updated_at)') }} from {{ this }})
{% endif %}
```

### History of a changing attribute (SCD2), dbt 1.9+ YAML snapshot

```yaml
# snapshots/bookings_snapshot.yml
snapshots:
  - name: bookings_snapshot
    relation: ref('stg_pms__bookings')
    description: "One row per booking per version: status history, valid_from/valid_to."
    config:
      unique_key: [tenant_id, booking_id]
      strategy: timestamp          # valid_from = updated_at; use check + check_cols without one
      updated_at: updated_at
      hard_deletes: invalidate
```

### As-of attribute with history before the first snapshot

`raw.customers` holds only the current segment. Snapshot it from now on, add earlier
versions from a seed (CRM export, finance's list), and label what nobody knows.

```sql
-- models/intermediate/int_customer_segment_history.sql
-- Grain: one row per customer per segment version; [valid_from, valid_to) never overlaps.
with snap as (
    select customer_id, segment, dbt_valid_from as valid_from, dbt_valid_to as valid_to, 'snapshot' as source
    from {{ ref('snap_shop__customers') }}
),
backfill as (   -- seeds/customer_segment_backfill.csv: customer_id, segment, valid_from, valid_to
    select customer_id, segment, valid_from, valid_to, 'backfill' as source
    from {{ ref('customer_segment_backfill') }}
)
select * from snap
union all
select b.* from backfill b
where b.valid_to <= (select min(s.valid_from) from snap s where s.customer_id = b.customer_id)
```

```sql
-- in the fact: as-of join, unknown when no version covers the order
left join {{ ref('int_customer_segment_history') }} h
  on h.customer_id = o.customer_id
 and o.created_at >= h.valid_from
 and (o.created_at < h.valid_to or h.valid_to is null)
-- select coalesce(h.segment, 'unknown') as segment_at_order
```

Test it: no overlapping versions per customer, and one order per row after the join.

### Tests and docs in YAML (dbt 1.10.5+ `arguments`)

```yaml
# models/marts/_marts.yml
models:
  - name: fct_bookings
    description: "One row per booking per tenant. Amount in `currency`; never sum across currencies."
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns: [tenant_id, booking_id]
    columns:
      - name: status
        data_tests:
          - accepted_values:
              arguments:
                values: ['confirmed', 'cancelled']
      - name: tenant_id
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_hotel')
                field: tenant_id
```

### Reconciliation (singular test: returns rows only on failure)

```sql
-- tests/assert_booking_nights_keep_the_money.sql
with a as (select tenant_id, currency, sum(amount) as total from {{ ref('fct_bookings') }} group by 1, 2),
     b as (select tenant_id, currency, sum(amount_per_night) as total from {{ ref('int_booking_nights') }} group by 1, 2)
select coalesce(a.tenant_id, b.tenant_id) as tenant_id, coalesce(a.currency, b.currency) as currency,
       a.total, b.total as nights_total
from a full outer join b on a.tenant_id = b.tenant_id and a.currency = b.currency
where a.total is distinct from b.total   -- exact: the remainder goes to the last night
```

### Unit test for a rule

```yaml
unit_tests:
  - name: cancelled_flag_follows_status
    model: fct_bookings
    overrides:
      macros:
        is_incremental: false
    given:
      - input: ref('stg_pms__bookings')
        rows:
          - {tenant_id: a, booking_id: B-1, status: cancelled, amount: 10.00, currency: EUR}
          - {tenant_id: a, booking_id: B-2, status: confirmed, amount: 20.00, currency: EUR}
    expect:
      rows:
        - {booking_id: B-1, is_cancelled: true}
        - {booking_id: B-2, is_cancelled: false}
```

## SQLMesh

```sql
MODEL (
  name marts.fct_bookings,
  kind INCREMENTAL_BY_UNIQUE_KEY (unique_key (tenant_id, booking_id)),
  grain (tenant_id, booking_id),
  audits (not_null(columns := (tenant_id, booking_id, amount, currency)))
);

SELECT tenant_id, booking_id, arrival_date, nights, amount, currency,
       status = 'cancelled' AS is_cancelled, created_at
FROM staging.bookings
```

Use `sqlmesh plan` to see the change before applying it. Time-partitioned facts use
`INCREMENTAL_BY_TIME_RANGE (time_column stay_date)`.

## Plain SQL (no framework)

Make the load idempotent with a staging table plus a `MERGE`.
`data-max sql spec --what ddl,load` emits both, for BigQuery, Snowflake, Postgres
(`ON CONFLICT`), DuckDB (`INSERT OR REPLACE`) and ClickHouse (`ReplacingMergeTree`).
Marts are views, or `CREATE OR REPLACE TABLE … AS SELECT`, run in dependency order from
one script, with the checks from `data-max sql spec --what checks` at the end.

## Local verification with DuckDB

With no warehouse at hand, run the same SQL against the files `data-max:clean` wrote:

```sql
create schema raw;
create table raw.bookings as select * from 'data/clean/bookings.parquet';
-- then run the model SQL, and finish with the grain check:
select tenant_id, booking_id, count(*) from fct_bookings group by all having count(*) > 1;
```

dbt-duckdb runs a whole dbt project this way (`profiles.yml` type `duckdb`).
