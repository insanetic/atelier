# Before → after, with the spec that does it

Pull the example that fits the file; don't paste them all into a review. Each shows the
problem, why it matters in a warehouse, and the spec fragment that fixes it.

## 1. Report chrome: banner, blank rows, footer total

```
Acme Corp — Q2 Sales Report
Generated 2026-05-26

Region,Product,Units,Revenue
North,Widget,120,"$1,200.00"
TOTAL,,120,"$1,200.00"
```

A load expects one header and same-width rows. The banner breaks the header; the `TOTAL`
row loads as a fake observation and doubles every sum.

```json
"source": {"header_row": 4},
"tables": [{"filters": [{"field": "Region", "matches": "^TOTAL$", "reason": "footer total"}], ...}]
```

The profile reports the header record, preamble and footer rows. A preamble value worth
keeping (the report date) becomes a column: `{"preamble": 2, "regex": "(\\d{4}-\\d{2}-\\d{2})"}`.

## 2. Column names

`Order Date`, `Revenue ($)`, `2024 Target`, `%Margin`, `Nächte` →
`order_date`, `revenue_usd`, `target_2024`, `margin_pct`, `nights`.

Names become SQL identifiers: spaces, symbols and umlauts force quoting in every query,
and casing rules differ between warehouses. Units become words. The spec enforces
snake_case on every output name.

## 3. Money

`"$1,234.50"`, `"1.234,50 €"`, `(120,00)`, `120,00-` stored as text.

Text can't be summed and sorts lexically (`"$9" > "$10"`). Floats can't hold `0.10`
exactly. Warehouses store money as exact decimals (`NUMERIC`, `NUMBER(p,s)`, `Decimal`),
and an amount means nothing without its currency.

```json
{"name": "amount", "from": "Betrag", "type": "decimal", "scale": 2, "precision": 18,
 "locale": {"decimal": ",", "thousands": "."}, "required": true},
{"name": "currency", "from": "Währung", "type": "string", "allowed": ["EUR", "CHF"]}
```

The engine refuses values that don't match the declared locale: `1,234.50` under
`decimal: ","` is a reject, not a silent 1000× error. Sources in minor units: `"type":
"decimal", "scale": 2, "divide_by": 100` for cents, `"scale": 6, "divide_by": 1000000`
for micros. Never add amounts across currencies; say so in the review when the file mixes them.

## 4. Dates and timestamps

`05/06/2024` (May or June?), `26.05.2026`, `20260526`, `45905` (Excel serial),
`2026-06-13 14:31` (which timezone?).

```json
{"name": "arrival_date", "from": "Anreise", "type": "date", "formats": ["%d.%m.%Y"]},
{"name": "created_at", "from": "Erstellt am", "type": "timestamp",
 "formats": ["%Y-%m-%d %H:%M", "excel_serial"], "tz": "Europe/Vienna"}
```

Dates become ISO 8601; instants become UTC (`2026-06-13T12:31:00Z`), loaded as
`TIMESTAMP`/`TIMESTAMPTZ`/`TIMESTAMP_TZ`. The first matching format wins, so the order
decides ambiguous values: confirm it with the user. Times that happen twice at a DST
switch are rejected unless `dst_ambiguous` is set; times that don't exist, unless
`dst_gap: shift_forward`. Excel serials in a text date
column often mean someone edited the file in Excel; ask whether they are real.

## 5. A time column must exist

`dau_2026-05-26.csv` with `region,users` and no date. Without a date there is no trend,
partition or period comparison. Take it from the preamble, a param
(`{"param": "snapshot_date"}`), or ask for it in the export.

## 6. Tenant isolation

One hotel's bookings with no hotel column. The moment a second hotel's file lands in the
same table, its rows are indistinguishable.

```json
"params": {"tenant_id": {"pattern": "[a-z0-9_-]+"}},
{"name": "tenant_id", "from": {"param": "tenant_id"}, "type": "string", "required": true}
```

and make it part of the key: `"key": ["tenant_id", "booking_id"]`.

## 7. Wide → long (unpivot)

```
product,Jan,Feb,Mar
Widget,120,140,160
```

Every new month is a schema change, and `GROUP BY month` is impossible.

```json
"unpivot": {"columns": ["Jan", "Feb", "Mar"], "name_to": "month", "value_to": "units"},
"columns": [
  {"name": "product", "from": "product", "type": "string"},
  {"name": "month", "from": "month", "type": "string", "map": {"Jan": "2026-01", "Feb": "2026-02", "Mar": "2026-03"}},
  {"name": "units", "from": "units", "type": "integer"}]
```

The reverse (key/value rows that should be columns) is rarer and belongs in the warehouse
model (a pivot in SQL), not the cleaning spec.

## 8. NULL in disguise

`-`, `n/a`, `NULL`, `#N/A`, `0000-00-00`, empty strings. `COUNT(email)` counts `-` as an
address. List the tokens the file really uses in `null_tokens`; if `-` or `0` is a real
value in some column, set that column's own `null_tokens`.

## 9. Excel damage

- Leading zeros lost or kept: `01067` vs `1067`. Keep identifiers as strings.
- Scientific notation: `1.23457E+15` means the digits are gone; only a new export fixes it.
- Serial dates (`45905`) next to formatted dates.
- Thousands separators and currency typed into cells.

## 10. Categories with case or spelling variants

`Bestätigt`, `bestätigt`, `BESTÄTIGT`. Map them to one canonical value and list the
accepted set, so a new spelling fails `check` instead of silently creating a new group:

```json
{"name": "status", "from": "Status", "type": "string",
 "map": {"bestätigt": "confirmed", "storniert": "cancelled"}, "allowed": ["confirmed", "cancelled"]}
```

## 11. Keys and duplicates

The profile reports exact duplicate rows and candidate keys. Identical rows are not
automatically duplicates: two coffees for 3.80 on the same day are two bookings. A stated
total decides it (see 15). Then `dedupe`: `exact` for export duplicates, `key_last` when
later rows are updates, `key_consistent` when duplicates must agree.

## 12. Overlapping periodic exports

A weekly export of a 6-month window returns most rows every week, often with a changed
status. Appending duplicates them. `"load": {"mode": "merge", "newer_by": "updated_at"}`
on the key makes `data-max sql` emit a fresh staging table plus `MERGE` in one transaction:
a rerun is a no-op, and an older export never overwrites a newer state. Line items of a
changed order use `"replace_by"` with `by: ["order_id"]`, so a removed line disappears.
History of changes (status over time) is a warehouse snapshot, `data-max:model`'s job.

## 13. Personal data

Names, emails, phones, addresses, free-text notes. Decide per column: `keep` (restrict
access in the warehouse), `hash` (joinable, still personal data under GDPR), or `drop`.
Free text often contains personal data nobody planned for.

## 14. One file or several

```
order_id,customer,order_total,line_product,line_qty,line_price
1001,Acme,300.00,Widget,2,100.00
1001,Acme,300.00,Gadget,1,100.00
```

`SUM(order_total)` double-counts order 1001: two grains share one table. Two tables from
the same file, each with its own key; the order table uses `dedupe: key_consistent` so
conflicting order headers are caught:

```json
{"name": "orders", "key": ["order_id"], "dedupe": "key_consistent", "columns": [ /* order_id, customer, order_total */ ]},
{"name": "order_lines", "key": ["order_id", "line_product"], "columns": [
   {"name": "order_id", "from": "order_id", "type": "string", "references": "orders.order_id"} /* , line_product, line_qty, line_price */ ]}
```

For JSON, `rows_from` does the split: `orders[]` and `orders[].items[]`, with `"^orderId"`
carrying the parent key and `"#index"` numbering the lines.

**Don't split** when nobody sums the repeated column: one line-level table without
`order_total` is simpler.

## 15. Totals the export states itself

```
Anfangssaldo: 2.500,00 EUR        <- preamble record 4
Buchungstag;...;Betrag;Währung
...32 rows...
Endsaldo: 7.054,90 EUR            <- last record
```

Filter the footer row and make the stated numbers a check, so every run proves that
nothing was lost or doubled:

```json
"filters": [{"field": "Buchungstag", "matches": "^Endsaldo", "reason": "closing balance line"}],
"control_totals": [{"sum": "amount",
  "from": {"preamble": 4, "regex": "Anfangssaldo: ([\\d.,-]+)"},
  "to":   {"footer": 1, "regex": "Endsaldo: ([\\d.,-]+)"}}]
```

Also `{"count": true, "equals": {"root": "meta.total"}}` for an API page's record count,
and `{"sum": "amount", "equals": {"footer": 1, "regex": "Summe;([\\d.,]+)"}}` for a total
row.
