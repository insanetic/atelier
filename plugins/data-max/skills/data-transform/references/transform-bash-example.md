# Transform script — bash example (the shape to follow)

This is the **reference style** for a small, dependency-free shell transform you
write ad-hoc into the user's `tools/` folder. It is an *example*, not a bundled
tool — copy the conventions, not the specifics.

**Use bash only for genuinely simple, line-oriented fixes** where no field contains
an embedded delimiter or quoting: dropping a known number of preamble/footer lines,
swapping a header line, a straight column passthrough. **The moment fields are
quoted or you must parse money/dates/reshape, switch to the Python example** — POSIX
text tools mangle quoted CSV.

**Conventions this example demonstrates (follow all of them):**

- `set -euo pipefail` and explicit input/output paths — never edit in place.
- Drops the export preamble and footer total by line position / pattern, replaces
  the header line, and reports kept/dropped counts to stderr.
- Named by what it does (`strip_report_chrome.sh`) with a sibling
  `strip_report_chrome.md` (see the sibling `.md` shape in SKILL.md).

```bash
#!/usr/bin/env bash
# strip_report_chrome.sh — drop the banner + blank lines + TOTAL footer from a
# simple report export and rewrite the header. Line-oriented only: use this when
# NO field is quoted. For quoted fields or money/date coercion, use Python instead.
#
# Run:  tools/strip_report_chrome.sh sales_q2.csv sales_q2_clean.csv
set -euo pipefail

in=${1:?usage: strip_report_chrome.sh <input.csv> <output.csv>}
out=${2:?usage: strip_report_chrome.sh <input.csv> <output.csv>}

clean_header='region,product,units,revenue_usd'

# Pipeline: drop blank lines -> drop any line starting with TOTAL/SUBTOTAL ->
# drop the original messy header line -> prepend the clean header.
{
  printf '%s\n' "$clean_header"
  grep -v '^[[:space:]]*$' "$in" \
    | grep -viE '^[[:space:]]*(grand[[:space:]]*)?(total|subtotal|sum)\b' \
    | grep -viE '^[[:space:]]*region[[:space:]]*,'   # drop the raw header row
} > "$out"

kept=$(( $(wc -l < "$out") - 1 ))   # minus the header we added
echo "wrote $kept data rows -> $out" >&2
```

**Note the limits in action:** this example only strips chrome and relabels the
header — it does *not* touch money or dates, because doing that safely in bash on
quoted CSV is a trap. Pair it with the Python example when the file needs more than
line surgery.
