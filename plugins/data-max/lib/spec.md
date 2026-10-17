# The data-max cleaning spec

One JSON file per kind of export, `<name>.spec.json`, kept in the user's repo (default `specs/`).
It is the contract between the export and the warehouse: `data-max apply` executes it,
`data-max check` tests new exports against it, `data-max sql` turns it into DDL, load
statements, SQL checks and dbt sources. Same spec + same input bytes + same params =
byte-identical output.

Any string containing `TODO` blocks every command: unresolved decisions are visible, never
guessed. `data-max profile <file> --draft-spec specs/<name>.spec.json` writes a starter.

## Top level

```json
{
  "spec_version": 1,
  "name": "bookings",                    // snake_case; names the manifest and rejects file
  "version": "1.0.0",                    // bump MINOR for added columns/values, MAJOR when a column changes meaning
  "description": "Weekly booking export from the PMS, one file per hotel.",
  "assumptions": ["created_at is hotel local time (Europe/Vienna); not confirmed by the PMS vendor"],
  "params": {                            // values given at run time: --param tenant_id=alpenhof
    "tenant_id": {"description": "hotel tenant", "pattern": "[a-z0-9_-]+"},
    "pii_salt":  {"description": "salt for hashed PII", "secret": true, "env": "DATAMAX_PII_SALT"},
    "region":    {"default": "eu"}
  },                                     // secret: masked in the manifest; env: read from that variable when no --param
  "drift": {"rows": 0.3, "nulls": 0.1},  // check: allowed row-count change (relative) and NULL-rate change (absolute)
  "source": { ... },
  "tables": [ ... ]
}
```

## `source`: how to read the file

| Key | Meaning |
|---|---|
| `format` | `csv` (also TSV), `xlsx`, `json`, `jsonl`, `xml`. Default: from the extension. |
| `encoding` | `utf-8`, `utf-8-sig` (BOM), `cp1252`, `utf-16`… Default: detected. |
| `delimiter` | `,` `;` `\t` `|`. Default: sniffed. |
| `header_row` | 1-based record number of the header (records, not lines: a quoted multi-line field is one record). Records before it are the preamble. |
| `sheet` | xlsx: sheet name or 1-based number. |
| `rows_from` | json/xml default for tables (see tables). |
| `null_tokens` | Values that mean NULL, compared case-insensitively after trimming. Default: `"", null, none, n/a, na, #n/a, -, --, —, nan`. Set it explicitly when `-` or `0` is a real value. |
| `locale` | Default number format: `{"decimal": ",", "thousands": "."}`. `thousands` may be `""`, `" "` or `"'"`. |
| `timezone` | Default IANA zone for naive timestamps. Prefer per-column `tz`. |

## `tables[]`: one output table each

| Key | Meaning |
|---|---|
| `name` | snake_case; output file `<name>.csv`. |
| `grain` | What one row means. Required in practice: the reviewer and the warehouse both depend on it. |
| `key` | Output columns that identify a row. Key columns are implicitly required; uniqueness is checked. |
| `dedupe` | `none` (duplicates fail the run), `exact` (drop rows identical to an earlier one), `key_first` / `key_last` (keep one row per key by input order), `key_consistent` (collapse identical rows per key, reject keys whose rows disagree). |
| `rows_from` | json/xml: which array becomes rows. `orders[]`, `orders[].items[]` (one row per item), `[]` for a top-level array, `""` for jsonl lines. xml: `orders.order[]`. |
| `unpivot` | csv/xlsx wide → long: `{"columns": ["Jan","Feb"]` or `"match": "^\\d{4}-\\d{2}$", "name_to": "month", "value_to": "units"}`. Columns then read `month` / `units` as fields. |
| `filters` | Rows to drop before parsing, counted by reason: `{"field": "Region", "matches": "^TOTAL", "reason": "footer total"}`, also `"equals"` or `"is_null": true`. Filters see short (ragged) records too. |
| `max_rejects` | Rows allowed to fail conversion before the run fails. Default `0`. Raise it only with the user's consent, and say so. |
| `min_rows` | Default `1`. |
| `load` | How the warehouse table changes per load (see below). |
| `control_totals` | Totals the export states itself, checked against the rows written: `{"sum": "amount", "equals": <value>}`, `{"count": true, "equals": <value>}`, or a running balance `{"sum": "amount", "from": <opening>, "to": <closing>}`. `<value>` is any fixed-value `from` form (preamble, footer, root, const, param). Optional `tolerance`. |
| `monitor` | Warehouse-side checks for `data-max sql --what monitors` and dbt freshness: `{"time": "created_at", "max_age_hours": 26, "volume": [0.5, 1.8], "sums": ["amount"], "by": ["currency"], "where": "status = 'paid'", "days": 28, "compare": "weekday"}`. Each of the last `recent_days` (default 3) is compared with the median of the same weekday before them (`"compare": "day"`: any day); the band excludes its ends, so keep `hi` below 2 to catch a doubled load. |
| `columns` | The output columns, in order. |

## `columns[]`

Every column needs `name` (snake_case), `from` and `type`.

### `from`: where the value comes from

| Form | Meaning |
|---|---|
| `"Buchungs-Nr."` | csv/xlsx header name (exact, after trimming). `"#3"` = third column, for blank or duplicate headers. |
| `"customer.id"` | tree: dotted path inside the row object. |
| `"^orderId"` | tree: field of the parent row (`^^` = grandparent). Use it to carry the parent key into child rows. |
| `"#index"` | tree: 1-based position in the array (a line number). |
| `{"param": "tenant_id"}` | A run-time param, e.g. the tenant. |
| `{"const": "pms_v2"}` | A literal. |
| `{"input": "sha256"}` / `{"input": "name"}` | Lineage: the input file's hash or name. Never a timestamp: outputs must not depend on when or where it ran. |
| `{"preamble": 2, "regex": "(\\d{2}\\.\\d{2}\\.\\d{4})", "group": 1}` | A value from a record above the header, e.g. the export period. |
| `{"footer": 1, "regex": "Endsaldo: ([\\d.,-]+)"}` | A value from the end of the file: 1 = last non-blank record. |
| `{"root": "meta.exported_at"}` | json/xml: a value outside the row arrays (page metadata, totals). |
| `{"source_row": true}` | The source record number. |

### `type` and its options

| Type | Output | Options |
|---|---|---|
| `string` | as is, trimmed | `case`: lower/upper/title; `normalize_whitespace`; `pattern` (regex the whole value must match) |
| `integer` | `1234` | `locale`, `min`, `max` |
| `decimal` | fixed scale, `1234.50` | `scale` (required), `precision` (default 38), `locale`, `round`: `half_up`/`half_even` (default: more decimals than `scale` is a reject), `divide_by` / `multiply_by` (e.g. `100` for cents → major units), `negative_parens` (default true), `min`, `max` |
| `boolean` | `true` / `false` | `true` / `false` token lists (defaults include yes/no, y/n, 1/0, ja/nein, x) |
| `date` | `2026-05-26` | `formats` (required, tried in order), `min`, `max` |
| `timestamp` | UTC instant `2026-05-26T12:30:00Z` | `formats`, `tz` (IANA zone for values without an offset; required then), `dst_ambiguous`: `earlier`/`later` (default: reject times that happen twice), `dst_gap`: `shift_forward` (default: reject times that don't exist) |
| `datetime` | wall clock `2026-05-26T14:30:00` | `formats`. Only when the zone is truly unknown; say so in the review. |

`formats` entries: Python `strptime` patterns (`%d.%m.%Y`, `%m/%d/%Y %I:%M %p`, `%Y-%m-%dT%H:%M:%S%z`), `iso`, `excel_serial` (1900 date system), `unix_s`, `unix_ms`. The first format that parses wins, so the order is the decision for ambiguous values like `05/06/2024`.

Money is `decimal` with an explicit `scale` and its own `currency` column. Never a float, never summed across currencies. Amounts stored as integer minor units (cents, micros) are read as `integer` or converted with `divide_by`.

### Rules, applied in this order

1. `null_tokens` → NULL. `required: true` (or key column) and NULL → reject.
2. `map` → replaces raw values before typing, case-insensitive unless `map_case_sensitive`: `{"bestätigt": "confirmed"}`. Map a value to `null` to turn it into NULL.
3. Type conversion.
4. `allowed` (list of accepted output values), `pattern`, `min`, `max` → reject when violated.
5. `pii`: `{"kind": "email", "action": "keep" | "hash" | "drop"}`. `hash` = SHA-256 of salt + trimmed, case-folded value; needs the param named by `salt_param` (default `pii_salt`). Hashed data is still personal data under GDPR (pseudonymised, not anonymised). `drop` removes the column from every output.
6. `references`: `"orders.order_id"` checks that every value exists in that table of this spec.

## `load`: how each load changes the warehouse table

| Mode | Effect | Use for |
|---|---|---|
| `append` | Adds the rows. A rerun duplicates them. | Immutable event files, loaded exactly once. |
| `replace` | Swaps the whole table. Refused when a column comes from a param (one tenant per run would wipe the others). | Full snapshots of a single-tenant table. |
| `replace_by` + `by: [cols]` (+ `newer_by`) | Deletes every slice (`by` values) present in the load, then inserts the load. Rows missing upstream disappear. With `newer_by` (e.g. the parent's `updated_at` carried into each line via `"^updated_at"`), a slice the warehouse holds in a newer state is left alone. | Child rows per parent (`by: [tenant_id, order_id]`), one tenant or period per file (`by: [tenant_id, month]`). |
| `merge` + `key` (+ `newer_by`) | Upserts on the key. With `newer_by` (a timestamp/version column) an older export never overwrites newer data. Rows missing upstream stay. | Overlapping periodic exports of changing records. |

`replace_by` and `merge` load into a fresh `<table>__staging` and change the target in one transaction.

## What a run produces

`data-max apply <spec> <input> [--param k=v] [--out-dir data/clean] [--parquet]`

- `<table>.csv`: UTF-8, comma, `\n`, header row, NULL = empty field. Written atomically, only when every check passes.
- `<table>.parquet` with `--parquet` (needs DuckDB): typed, UTC timestamps.
- `<spec name>.rejects.csv`: `table, source_row, column, value, reason` for every rejected row (also written when the run fails).
- `<spec name>.manifest.json`: engine and spec version, spec and input SHA-256, params (secrets masked), rows in/written/rejected/dropped/deduplicated per table, NULL counts per column, output hashes, every check. No timestamps. A copy goes to `manifests/<name>.<input sha>.manifest.json`: the history baselines come from.

Checks: reconciliation (records in = written + rejected + dropped + deduplicated), rejects ≤ `max_rejects`, `min_rows`, key uniqueness, references, control totals. Exit codes: `0` passed, `1` checks failed (nothing written), `2` spec or usage error.

`data-max check` runs the same without writing and adds drift: spec columns gone from the header, new columns, and with `--baseline <manifest>` row-count and NULL-rate changes beyond `drift` (or `--row-tolerance`, `--null-tolerance`). Exit `3` = drift, needs a decision; `--allow-drift` once someone accepted it. So `check && apply` is a real gate.

`data-max sql <spec> --dialect bigquery|snowflake|postgres|clickhouse|duckdb --what ddl,load,checks,monitors,dbt [--schema raw] [--out-dir data/clean]` prints DDL with exact types, the load per mode, SQL checks that return failure counts, monitors (freshness, daily volume and sums) that return rows only when something is wrong, and a dbt `sources.yml` with tests and freshness.

Large inputs: the engine holds one file in memory; split multi-GB exports (per day or tenant) first.

`data-max vendor tools/` copies the engine into the project, so CI and reruns work without the plugin.
