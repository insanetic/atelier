# Worked before → after examples

Concrete examples for each review dimension. Pull the one that fits the user's
file; don't dump all of them into a report. Every example shows the *why* in
action, not just the mechanical change.

## 1. Structural junk from an Excel export

A warehouse load wants one header row + uniform rows. Reports rarely come that way.

**Before** (raw export):

```
Acme Corp — Q2 Sales Report
Generated 2026-05-26

Region,Product,Units,Revenue
North,Widget,120,"$1,200.00"
North,Gadget,80,"$960.00"

South,Widget,,
TOTAL,,200,"$2,160.00"
```

**Problems:** two title lines + a blank line before the header; a blank-ish row
(`South,Widget,,`); a `TOTAL` footer that would be summed *again* if loaded.

**After:**

```
region,product,units,revenue_usd
North,Widget,120,1200.00
North,Gadget,80,960.00
```

Drop the banner, the blank rows, and the TOTAL (the warehouse computes totals
itself — keeping it double-counts). Keep only real observations.

## 2. Column names

**Before:** `Order Date`, `Revenue ($)`, `Customer ID`, `2024 Target`, `%Margin`

**After:** `order_date`, `revenue_usd`, `customer_id`, `target_2024`, `margin_pct`

Units and symbols become *words in the name* (`_usd`, `_pct`), so the identifier
needs no quoting and reads the same in every warehouse. `2024 Target` can't start
with a digit as an identifier → `target_2024`.

## 3. Money → integer minor units

**Before:**

```
invoice_id,amount
INV-1,"$1,234.50"
INV-2,"$0.10"
INV-3,"$0.20"
```

`amount` lands as VARCHAR — `SUM(amount)` fails or sorts text. If instead coerced
to float, `0.10 + 0.20` famously yields `0.30000000000000004`; over millions of
rows the cents drift.

**After** (keep the readable column, add the exact one):

```
invoice_id,amount,amount_mills
INV-1,1234.50,1234500
INV-2,0.10,100
INV-3,0.20,200
```

`amount_mills` is an exact BIGINT (value × 1000). `SUM(amount_mills)` is exact;
divide by 1000 for display. Use `_micros` (× 1,000,000) when you need sub-cent
precision — ad spend, FX rates, per-unit costs: `$0.00123` → `1230` micros.

**Why mills/micros over a decimal type?** Even where the warehouse has DECIMAL,
integer minor units are unambiguous across every system, never silently coerced to
float by a careless cast, and trivial to transport in JSON/CSV. They're the safe
lingua franca for money.

## 4. Dates / datetimes

**Before:** `05/06/2024` (May 6 or June 5?), `26.05.2026`, `May 26 2026`,
`20260526`

**After:** `2024-05-06` (ISO 8601 date), and for an event time
`2026-05-26T14:30:00Z` (RFC 3339, explicit UTC).

ISO/RFC strings sort chronologically as plain text (so `MIN`/`MAX`/`ORDER BY` work
even before typing), parse identically in BigQuery/Snowflake/ClickHouse/Postgres,
and carry timezone explicitly so `14:30` isn't silently misread across regions.

## 5. Add a missing time dimension

**Before:** a `daily_active_users.csv` with `region,users` and no date — the file's
date lives only in its name (`dau_2026-05-26.csv`).

**After:** add `date` to every row:

```
date,region,users
2026-05-26,North,1840
2026-05-26,South,1210
```

Without it you can't build a trend, partition by day, or stack multiple days into
one table — the whole point of putting it in a warehouse.

## 6. Tenant isolation

**Before:** `order_id,product,amount_mills` — one customer's orders, no label.

**After:** `tenant_id,order_id,product,amount_mills` with `tenant_id` on every row.

The instant a second customer's file loads into the same table, unlabeled rows are
unrecoverable and every aggregate silently mixes customers. Stamp the id now even
if "it's obviously just Acme's data."

## 7. Wide → long (unpivot) — the big one

**Before** (months as columns — the most common analytics anti-pattern):

```
product,Jan,Feb,Mar
Widget,120,140,160
Gadget,80,75,90
```

Adding April means **altering the table**. You can't `WHERE month BETWEEN …`, and
summing a quarter means naming each column. Columnar engines hate this.

**After** (long / tidy — one row per observation):

```
product,month,units
Widget,2026-01,120
Widget,2026-02,140
Widget,2026-03,160
Gadget,2026-01,80
Gadget,2026-02,75
Gadget,2026-03,90
```

Now a new month is just new *rows*, `GROUP BY month` works, date ranges filter, and
the measure lives in one column (`units`) that any aggregate can touch. Note the
months became real ISO-ish period values (`2026-01`), not bare labels.

**Reverse case (long → wide):** occasionally an attribute is split across rows that
should be one row with several columns — e.g. a `key,value` EAV table with rows
`(height, 12), (width, 8)` per item. If downstream always needs them together,
pivot to `item_id,height,width`. Rarer; only do it when the access pattern demands
a fixed, small set of attributes.

## One file → several CSVs (normalization, but only where it pays)

**Before** (orders and their line items crammed into one grain — what does one row
mean?):

```
order_id,customer,order_total_mills,line_product,line_qty,line_price_mills
1001,Acme,30000,Widget,2,10000
1001,Acme,30000,Gadget,1,10000
1002,Beta,5000,Widget,1,5000
```

`order_total_mills` repeats per line — `SUM(order_total_mills)` double-counts order
1001. Two grains are fighting in one table.

**After** — two CSVs, each with a clean grain and a join key:

`orders.csv` — grain: one row per order; key: `order_id`

```
order_id,customer,order_total_mills
1001,Acme,30000
1002,Beta,5000
```

`order_lines.csv` — grain: one row per line item; key: `order_id` (→ orders)

```
order_id,line_product,line_qty,line_price_mills
1001,Widget,2,10000
1001,Gadget,1,10000
1002,Widget,1,5000
```

**When NOT to split:** if you only ever query at the line grain and never sum
order totals, a single denormalized line-level table (drop `order_total_mills`,
recompute when needed) is simpler and fine. Split only when mixed grains would
actually corrupt a number the user cares about.
