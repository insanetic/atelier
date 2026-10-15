# Transform script — Python example (the shape to follow)

This is the **reference style** for a transformation script you write ad-hoc into
the user's `tools/` folder. It is an *example*, not a bundled tool — copy the
conventions, not the specifics. Adapt the actual fixes to what the review report
specified.

**Conventions this example demonstrates (follow all of them):**

- **Stdlib only** (`csv`, `argparse`, `sys`, `re`, `datetime`) so it runs anywhere
  with no `pip install`.
- **One cohesive read-write pass** that applies every row-level fix to the same
  rows: strip preamble/footer, rename headers, scale money to integer minor units,
  normalize dates to ISO, stamp an isolation column. Don't chain micro-scripts that
  each re-parse the file.
- **Reads input path, writes output path** — never edits in place.
- **Drops junk explicitly** (preamble rows, footer totals, ragged rows) and
  **reports counts to stderr** so the user can sanity-check what was kept/dropped.
- **Names the script by what it does** (`clean_sales_export.py`) and ships a
  sibling `clean_sales_export.md` (see the sibling `.md` shape in SKILL.md).

```python
#!/usr/bin/env python3
"""clean_sales_export.py — one-pass warehouse cleanup for the Q2 sales export.

Strips the Excel banner + TOTAL footer, renames headers to snake_case, adds an
exact integer money column (mills), normalizes the date to ISO 8601, and stamps
tenant_id on every row. Stdlib only; reads input, writes output, never in place.

Run:  python tools/clean_sales_export.py sales_q2.csv sales_q2_clean.csv --tenant acme
"""

import argparse
import csv
import re
import sys
from datetime import datetime

# Map raw headers → clean snake_case identifiers. Units move into the name.
RENAME = {
    "Region": "region",
    "Product": "product",
    "Order Date": "order_date",
    "Units": "units",
    "Revenue ($)": "revenue_usd",
}

MONEY_CHARS = re.compile(r"[^\d.\-]")          # strip $ , spaces etc.
TOTAL_RE = re.compile(r"^\s*(grand\s*)?(total|sum|subtotal)\b", re.I)


def to_mills(text: str) -> int | None:
    """'$1,234.50' -> 1234500 (exact integer, value x 1000). None if unparseable."""
    s = MONEY_CHARS.sub("", (text or "").strip())
    if not s:
        return None
    return round(float(s) * 1000)


def to_iso_date(text: str) -> str:
    """Parse the known source format (MM/DD/YYYY) into ISO 8601; pass through if already ISO."""
    s = (text or "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    return datetime.strptime(s, "%m/%d/%Y").date().isoformat()


def main() -> None:
    ap = argparse.ArgumentParser(description="One-pass cleanup of the Q2 sales export.")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--tenant", required=True, help="Stable tenant id stamped on every row.")
    args = ap.parse_args()

    kept = dropped = 0
    with open(args.input, encoding="utf-8-sig", newline="") as fin:
        rows = list(csv.reader(fin))

    # Find the real header: first row matching the modal (most common) width.
    widths = [len(r) for r in rows if any(c.strip() for c in r)]
    n_cols = max(set(widths), key=widths.count)
    header_idx = next(i for i, r in enumerate(rows) if len(r) == n_cols)
    raw_header = rows[header_idx]
    out_header = ["tenant_id", *(RENAME.get(h.strip(), h.strip()) for h in raw_header), "revenue_usd_mills"]

    with open(args.output, "w", encoding="utf-8", newline="") as fout:
        w = csv.writer(fout)
        w.writerow(out_header)
        for r in rows[header_idx + 1:]:
            if len(r) != n_cols:                       # ragged: blank/merged/separator
                dropped += 1
                continue
            if TOTAL_RE.match((r[0] or "").strip()):   # footer total: warehouse re-aggregates
                dropped += 1
                continue
            record = dict(zip(raw_header, r))
            mills = to_mills(record.get("Revenue ($)", ""))
            w.writerow([
                args.tenant,
                record.get("Region", "").strip(),
                record.get("Product", "").strip(),
                to_iso_date(record.get("Order Date", "")),
                record.get("Units", "").strip(),
                f"{int(mills) / 1000:.2f}" if mills is not None else "",
                mills if mills is not None else "",
            ])
            kept += 1

    print(f"wrote {kept} rows, dropped {dropped} -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
```

**When to reach for Python over bash:** any real parsing — quoted fields with
embedded commas, money/date coercion, reshaping (unpivot, splitting one file into
several grains). The `csv` module handles quoting correctly; `awk`/`sed` do not.
