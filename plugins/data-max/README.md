# data-max

A [Claude Code](https://claude.com/claude-code) **plugin** for getting raw data exports into a warehouse and modelling them there, with transformations that are **deterministic**: the same spec, input and params give byte-identical output, and every run is reconciled and leaves a manifest.

Part of the [atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install data-max@atelier
```

---

## The skills

| Skill | Invoke | Size¹ | Job |
|---|---|---|---|
| **inspect** | `/data-max:inspect` | 1,100 | Profiles a raw export (CSV/TSV/Excel/JSON/JSONL/XML), every row. Settles the decisions the data can't answer (grain, key, timezone, PII, load mode) with you, or with written defaults when nobody can answer. Turns the totals the file states into checks, and writes a **spec** and a **review**. The source file is never touched. |
| **clean** | `/data-max:clean` | 981 | Runs the spec. Produces typed tables (CSV, optionally Parquet), a rejects file, a manifest, warehouse DDL and a load that is safe to repeat, plus a runbook for the next export. Failures are fixed in the spec, never in the data. |
| **check** | `/data-max:check` | 1,049 | Gates a new export before loading: rejects, control totals, header, row-count and NULL-rate drift against the last good run. For tables already in the warehouse it writes contract checks, freshness and volume monitors, and dbt tests, mapped to the incident they would catch. |
| **model** | `/data-max:model` | 801 | Builds warehouse models on top: grain first, the usual traps named before any SQL (fan-out, as-of history, business time zone, currencies), layers, idempotent incremental loads, SCD2, tests. It runs them on data before calling them done. dbt, SQLMesh or plain SQL. |

¹ Tokens the `SKILL.md` body adds **when the skill activates**; at rest only the description is loaded, and `references/` load on demand. Measured with [tiktoken](https://github.com/openai/tiktoken) (`o200k_base`) as a portable proxy.

```text
raw export ──inspect──▶ specs/<name>.spec.json + review ──clean──▶ data/clean/*.csv|parquet + manifest
                                     │                                   │
                       next export ──check── (drift, rejects)            └──▶ warehouse ──model──▶ staging → marts
```

---

## The engine: `data-max`

The skills don't write a new ad-hoc script each time: they write a **spec**, and one tested engine executes it. `bin/data-max` is on the PATH while the plugin is enabled. It needs only Python 3.9+ and the standard library; Parquet output additionally needs DuckDB.

```bash
data-max profile export.csv --draft-spec specs/bookings.spec.json   # every row; draft with TODO decisions
data-max check   specs/bookings.spec.json export.csv --param tenant_id=alpenhof
data-max apply   specs/bookings.spec.json export.csv --param tenant_id=alpenhof --out-dir data/clean --parquet
data-max sql     specs/bookings.spec.json --dialect bigquery --schema raw --what ddl,load,checks,monitors,dbt
data-max spec                                                        # the spec format
data-max vendor  tools/                                              # copy the engine into a repo for CI
```

What it guarantees:

- **No silent conversions.** Numbers must match the declared locale (`1,234.50` under a decimal comma is a reject, not a 1000× error). Money is exact decimal plus a currency column. Timestamps become UTC instants, and DST gaps and overlaps are rejected unless decided. Identifiers keep their leading zeros.
- **Every decision is in the spec.** A `TODO` blocks every command; assumptions are listed in the spec.
- **Every row is accounted for.** Records in = written + rejected + dropped (by reason) + deduplicated. Rejects go to a file with row, column, value and reason. A failed run writes no tables.
- **The file's own totals are checked.** Footer sums, record counts, opening + movements = closing balance (`control_totals`).
- **A real gate.** `check` exits 1 when checks fail and 3 when the export drifts (layout, row count, NULL rates) from the last good run, so `check && apply` stops a bad file.
- **Reproducible.** Nothing depends on the clock or file timestamps. The manifest records the engine version, the spec and input SHA-256, the counts, the NULL counts and the output hashes.
- **Loads that are safe to repeat.** Exact DDL for BigQuery, Snowflake, Postgres, ClickHouse and DuckDB.
  - `merge` and `replace_by` load through a fresh staging table, in one transaction.
  - `newer_by` stops an older export from overwriting newer data.
  - `replace_by` swaps whole slices (an order's lines, one tenant's month), so rows deleted upstream disappear.
  - `replace` refuses tables shared by several tenants.
- **Monitoring.** SQL checks, plus freshness and daily volume/sum monitors that return rows only when something is wrong. A dbt `sources.yml` with tests and freshness.
- **PII decided per column**: keep, salted hash or drop. Secrets come from environment variables, never the command line.

---

## Layout

```text
.claude-plugin/plugin.json   # manifest
bin/data-max                 # CLI wrapper (on the PATH while enabled)
lib/datamax.py               # the engine: profile, apply, check, sql, vendor (stdlib only)
lib/spec.md                  # spec format reference (`data-max spec`)
skills/<skill>/SKILL.md      # the four skills; references/ load on demand
tests/                       # unit tests + fixtures
evals/                       # behaviour evals, with and without the plugin
```

## Development

```bash
python3 -m unittest discover -s tests          # engine tests (Python 3.9+)
claude plugin eval . --runs 2                  # skill behaviour, with and without the plugin
```

- **`name`** must equal the skill's directory name, or the skill won't resolve; it is also the `/data-max:<name>` token. The plugin name already namespaces the skills, so names are bare verbs.
- **`description`** is all Claude sees when deciding to load a skill: it says *when*, with the phrases users actually type, not *how*.
- Keep `SKILL.md` lean; depth lives in `references/` and in `data-max spec`.
- Engine changes need a test. Spec format changes bump `SPEC_VERSION` and the docs together.
- Frontmatter: `name`, `description`, `user-invocable: true`, `license: MIT`, `metadata` with `author` and `version`.

## Other agents

The skill folders are plain Agent Skills, and the engine is a Python file. Copy `skills/<name>` into another agent's skills directory (`~/.codex/skills/`, `~/.gemini/skills/`, `~/.copilot/skills/`) and put `bin/` on the PATH.
