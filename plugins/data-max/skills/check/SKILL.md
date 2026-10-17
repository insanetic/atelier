---
name: check
description: >-
  Use when a new or recurring export must be validated before loading, when an
  export's format may have changed, when loaded warehouse tables need
  data-quality checks or monitoring, or when a bad load must be caught next
  time - "check this week's export", "did the format change", "is next month's
  file OK", "write data quality tests for this table", "alert us when a load
  breaks", "revenue doubled on the dashboard", schema drift, row counts
  dropped, freshness.
user-invocable: true
license: MIT
metadata:
  author: Stanislav Schmidt
  version: 2.1.0
---

# Check

Answer one question with evidence: does this data still match its contract? The contract is
a data-max spec (`specs/<name>.spec.json`). Checks come from the engine, so they are the
same in every run and in CI. Never improvise a validation script.

## A new export (file)

```
data-max check specs/<name>.spec.json <file> --param … --baseline data/clean/<name>.manifest.json
```

Without a spec, run `data-max:inspect` first. The baseline is the last good run's manifest;
older ones are in `data/clean/manifests/`.

| Exit | Verdict | Do |
|---|---|---|
| 0 | loadable | Hand over to `data-max:clean` or the runbook. |
| 1 | don't load: rejects, duplicate keys or control totals failed | Show the failing rows and values. Propose the spec change; never raise `max_rejects`. |
| 2 | spec or usage error | Fix the call or the spec. |
| 3 | needs a decision: header, row-count or NULL-rate drift | Show the drift. Load only after someone accepts it (`--allow-drift`), or change the spec. |

What each finding usually means:
- **Spec column gone**: the layout changed. Show the header diff; the mapping needs a human
  (MAJOR spec bump).
- **New column**: ignore it or add it (MINOR).
- **New category value**: map, allow or reject. A business decision.
- **Fewer rows**: a partial export. `replace_by` would delete the missing rows.
- **NULL rate jumped**: an upstream field broke.

Tolerances live in the spec (`"drift": {"rows": 0.3, "nulls": 0.1}`).

Report the verdict first, then findings with row numbers and values, then the proposed spec
change. Change the spec only after the user agrees what the change means. With nobody to ask,
report and change nothing.

## Tables in the warehouse

1. **Contract.** Use the spec that loads the table. If there is none (the table is loaded
   by another tool), write one from the DDL: one column per table column, `from` = its
   name, `key`, `required`, `allowed`. It is the same contract the files would have.

2. **Monitor.** Add `monitor` to each table: `time`, plus `sums` and `by` for the numbers a
   dashboard shows (e.g. `amount` by `currency`, `where` `status = 'paid'`). Then:

   ```
   data-max sql specs/<name>.spec.json --dialect <wh> --schema <schema> --what checks,monitors
   ```

   This prints:
   - contract checks: key uniqueness, NOT NULL, accepted values, references
   - freshness
   - yesterday's volume and sums against the median day of the last 28

   Every query returns rows only when something is wrong. Volume compares yesterday with
   the same weekday. For dbt, `--what dbt` writes `sources.yml` with the same tests and
   freshness. Add anything the incident needs beyond these, such as amount ranges or a
   reconciliation against the source system, as further queries in the same shape.

3. **Map the incident to the check that catches it**, e.g. doubled revenue:
   - duplicate keys → `unique_key`
   - a reloaded window → `daily_volume` and the sums
   - a stopped job → `freshness`

   If none catches it, say what's missing. If the load itself caused it, fix the load mode
   (`merge` / `replace_by` via `data-max:clean`), not just the alarm.

4. **Deliver the schedule, not advice.** A check nobody runs catches nothing. Write the
   artifact that runs the checks after each load and alerts or fails, such as a Snowflake
   `ALERT`/`TASK`, a BigQuery scheduled query with `ASSERT`, a dbt job step (`dbt test`,
   `dbt source freshness`), or a CI/cron step that exits non-zero when any query returns
   rows.

5. **Prove it.** Replay the incident on local data (DuckDB) and show each check firing;
   then show the checks silent on healthy data.

## CI gate for files

```bash
python3 tools/datamax.py check specs/<name>.spec.json "$FILE" --baseline data/clean/<name>.manifest.json \
  && python3 tools/datamax.py apply specs/<name>.spec.json "$FILE" --out-dir data/clean
```

`data-max vendor tools/` provides `tools/datamax.py`. Exit 1 or 3 stops the load. Commit
`data/clean/manifests/` so baselines survive.
