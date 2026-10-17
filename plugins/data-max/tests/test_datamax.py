import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import datamax  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
BOOKINGS = ["--param", "tenant_id=alpenhof", "--param", "pii_salt=s3cret"]


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = datamax.main(list(args))
    return code, out.getvalue(), err.getvalue()


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text, encoding="utf-8"):
        p = self.dir / name
        p.write_text(text, encoding=encoding)
        return str(p)

    def spec(self, tables, **top):
        doc = {"spec_version": 1, "name": top.pop("name", "t"), "tables": tables}
        doc.update(top)
        return self.write("spec.json", json.dumps(doc))


class Numbers(unittest.TestCase):
    def test_german_and_english_grouping(self):
        self.assertEqual(datamax.parse_number("1.234,50 €", ",", "."), Decimal("1234.50"))
        self.assertEqual(datamax.parse_number("$1,234.50", ".", ","), Decimal("1234.50"))

    def test_wrong_locale_is_rejected_not_scaled(self):
        # the old reference script turned this into 1.2345 silently
        with self.assertRaises(datamax.Reject):
            datamax.parse_number("1.234,50 €", ".", ",")
        with self.assertRaises(datamax.Reject):
            datamax.parse_number("1,234.50", ",", ".")

    def test_negatives(self):
        self.assertEqual(datamax.parse_number("(120,00) €", ",", "."), Decimal("-120.00"))
        self.assertEqual(datamax.parse_number("120,00-", ",", "."), Decimal("-120.00"))
        self.assertEqual(datamax.parse_number("-0.10", ".", ","), Decimal("-0.10"))

    def test_swiss_apostrophe(self):
        self.assertEqual(datamax.parse_number("1'234.50", ".", "'"), Decimal("1234.50"))

    def test_scale_overflow_needs_round(self):
        col = {"name": "x", "type": "decimal", "scale": 2}
        with self.assertRaises(datamax.Reject):
            datamax.convert(col, "1.005", {}, {})
        self.assertEqual(datamax.convert(dict(col, round="half_up"), "1.005", {}, {}), "1.01")
        self.assertEqual(datamax.convert(dict(col, round="half_even"), "1.005", {}, {}), "1.00")

    def test_cents_to_major(self):
        col = {"name": "x", "type": "decimal", "scale": 2, "divide_by": 100}
        self.assertEqual(datamax.convert(col, "1999", {}, {}), "19.99")

    def test_integer_keeps_no_fraction(self):
        col = {"name": "n", "type": "integer"}
        self.assertEqual(datamax.convert(col, "1,234", {}, {}), "1234")
        with self.assertRaises(datamax.Reject):
            datamax.convert(col, "1.5", {}, {})


class Times(unittest.TestCase):
    def test_local_to_utc(self):
        col = {"name": "t", "type": "timestamp", "formats": ["%d.%m.%Y %H:%M"], "tz": "Europe/Berlin"}
        self.assertEqual(datamax.convert(col, "26.05.2026 14:30", {}, {}), "2026-05-26T12:30:00Z")

    def test_offset_wins_over_tz(self):
        col = {"name": "t", "type": "timestamp", "formats": ["iso"], "tz": "Europe/Berlin"}
        self.assertEqual(datamax.convert(col, "2026-03-01T10:00:00+01:00", {}, {}), "2026-03-01T09:00:00Z")
        self.assertEqual(datamax.convert(col, "2026-03-01T10:00:00Z", {}, {}), "2026-03-01T10:00:00Z")

    def test_dst_gap_and_overlap(self):
        col = {"name": "t", "type": "timestamp", "formats": ["%Y-%m-%d %H:%M"], "tz": "Europe/Berlin"}
        with self.assertRaises(datamax.Reject):
            datamax.convert(col, "2026-03-29 02:30", {}, {})  # does not exist
        with self.assertRaises(datamax.Reject):
            datamax.convert(col, "2026-10-25 02:30", {}, {})  # happens twice
        self.assertEqual(datamax.convert(dict(col, dst_ambiguous="earlier"), "2026-10-25 02:30", {}, {}),
                         "2026-10-25T00:30:00Z")

    def test_naive_timestamp_without_tz_is_a_spec_error(self):
        col = {"name": "t", "type": "timestamp", "formats": ["%Y-%m-%d %H:%M"]}
        with self.assertRaises(datamax.SpecError):
            datamax.convert(col, "2026-05-26 14:30", {}, {})

    def test_excel_serial(self):
        col = {"name": "d", "type": "date", "formats": ["%d.%m.%Y", "excel_serial"]}
        self.assertEqual(datamax.convert(col, "45000", {}, {}), "2023-03-15")
        self.assertEqual(datamax.convert(col, "15.03.2023", {}, {}), "2023-03-15")

    def test_format_order_decides_ambiguous_dates(self):
        col = {"name": "d", "type": "date", "formats": ["%d/%m/%Y"]}
        self.assertEqual(datamax.convert(col, "05/06/2024", {}, {}), "2024-06-05")


class Values(unittest.TestCase):
    def test_null_tokens_and_required(self):
        col = {"name": "x", "type": "string", "required": True}
        with self.assertRaises(datamax.Reject):
            datamax.convert(col, "n/a", {}, {})
        self.assertIsNone(datamax.convert({"name": "x", "type": "string"}, " - ", {}, {}))

    def test_map_is_case_insensitive_then_allowed(self):
        col = {"name": "s", "type": "string", "map": {"bestätigt": "confirmed"}, "allowed": ["confirmed"]}
        self.assertEqual(datamax.convert(col, "BESTÄTIGT", {}, {}), "confirmed")
        with self.assertRaises(datamax.Reject):
            datamax.convert(col, "offen", {}, {})

    def test_hash_needs_salt_and_normalizes(self):
        col = {"name": "e", "type": "string", "pii": {"kind": "email", "action": "hash"}}
        with self.assertRaises(datamax.SpecError):
            datamax.convert(col, "a@b.de", {}, {})
        self.assertEqual(datamax.convert(col, " A@B.de ", {}, {"pii_salt": "x"}),
                         datamax.convert(col, "a@b.de", {}, {"pii_salt": "x"}))


class Spec(Case):
    def test_todo_blocks_the_run(self):
        p = self.spec([{"name": "a", "columns": [{"name": "x", "from": "X", "type": "string"}],
                        "grain": "TODO: what one row means"}])
        code, _, err = run("apply", p, self.write("a.csv", "X\n1\n"))
        self.assertEqual(code, 2)
        self.assertIn("unresolved decision", err)

    def test_column_names_must_be_snake_case(self):
        p = self.spec([{"name": "a", "columns": [{"name": "Revenue ($)", "from": "X", "type": "string"}]}])
        code, _, err = run("apply", p, self.write("a.csv", "X\n1\n"))
        self.assertEqual(code, 2)
        self.assertIn("snake_case", err)

    def test_missing_source_column_is_reported(self):
        p = self.spec([{"name": "a", "columns": [{"name": "x", "from": "Y", "type": "string"}]}])
        code, _, err = run("apply", p, self.write("a.csv", "X\n1\n"))
        self.assertEqual(code, 2)
        self.assertIn("not in the file header", err)


class Bookings(Case):
    def apply(self, *extra):
        return run("apply", str(FIX / "bookings.spec.json"), str(FIX / "bookings_export.csv"), *BOOKINGS,
                   "--out-dir", str(self.dir), *extra)

    def test_end_to_end(self):
        code, out, err = self.apply()
        self.assertEqual(code, 0, out + err)
        rows = read_csv(self.dir / "bookings.csv")
        self.assertEqual(len(rows), 40)
        sums = {}
        for r in rows:
            sums[r["currency"]] = sums.get(r["currency"], Decimal(0)) + Decimal(r["amount"])
        self.assertEqual(sums, {"EUR": Decimal("70970.51"), "CHF": Decimal("17642.54")})
        self.assertNotIn("guest_name", rows[0])
        self.assertEqual(len(rows[0]["guest_email_hash"]), 64)
        self.assertTrue(any(r["guest_postal_code"] == "01067" for r in rows))
        self.assertEqual({r["status"] for r in rows}, {"confirmed", "cancelled"})
        refund = next(r for r in rows if r["booking_id"] == "B-1013")
        self.assertEqual(refund["amount"], "-120.00")
        self.assertTrue(all(r["created_at"].endswith("Z") for r in rows))
        self.assertTrue(all(r["export_period_start"] == "2026-01-01" for r in rows))
        manifest = json.loads((self.dir / "bookings.manifest.json").read_text())
        self.assertEqual(manifest["status"], "passed")
        self.assertEqual(manifest["params"]["pii_salt"], "<secret>")
        self.assertEqual(manifest["tables"]["bookings"]["dropped"], {"footer total": 1})

    def test_byte_identical_reruns(self):
        self.apply()
        first = (self.dir / "bookings.csv").read_bytes() + (self.dir / "bookings.manifest.json").read_bytes()
        os.utime(FIX / "bookings_export.csv", (0, 0))  # mtime must not matter
        self.apply()
        second = (self.dir / "bookings.csv").read_bytes() + (self.dir / "bookings.manifest.json").read_bytes()
        self.assertEqual(first, second)

    def test_wrong_locale_fails_loudly_and_writes_nothing(self):
        spec = json.loads((FIX / "bookings.spec.json").read_text())
        amount = next(c for c in spec["tables"][0]["columns"] if c["name"] == "amount")
        amount["locale"] = {"decimal": ".", "thousands": ","}
        p = self.write("spec.json", json.dumps(spec))
        code, out, err = run("apply", p, str(FIX / "bookings_export.csv"), *BOOKINGS, "--out-dir", str(self.dir))
        self.assertEqual(code, 1)
        self.assertIn("FAILED bookings.rejects", out)
        self.assertFalse((self.dir / "bookings.csv").exists())
        rejects = read_csv(self.dir / "bookings.rejects.csv")
        self.assertTrue(rejects and all(r["column"] == "amount" for r in rejects))

    def test_check_reports_drift_and_new_columns(self):
        text = (FIX / "bookings_export.csv").read_bytes().decode("utf-8-sig")
        text = text.replace("Währung;Status", "Währung;Kanal;Status")
        lines = text.split("\r\n")
        lines = [l if i < 4 or not l or l.startswith("Summe") else _insert_field(l, 9, "web") for i, l in enumerate(lines)]
        p = self.dir / "next_week.csv"
        p.write_bytes("\r\n".join(lines).encode("utf-8-sig"))
        p = str(p)
        code, out, _ = run("check", str(FIX / "bookings.spec.json"), p, *BOOKINGS)
        self.assertEqual(code, 3, out)  # drift blocks until someone accepts it
        self.assertIn("new source columns the spec ignores", out)
        self.assertIn("Kanal", out)
        code, out, _ = run("check", str(FIX / "bookings.spec.json"), p, *BOOKINGS, "--allow-drift")
        self.assertEqual(code, 0, out)

    def test_check_with_baseline_flags_volume_drop(self):
        self.apply()
        text = (FIX / "bookings_export.csv").read_bytes().decode("utf-8-sig").split("\r\n")
        short = text[:10] + [l for l in text if l.startswith("Summe")] + [""]
        p = self.dir / "short.csv"
        p.write_bytes("\r\n".join(short).encode("utf-8-sig"))
        p = str(p)
        code, out, _ = run("check", str(FIX / "bookings.spec.json"), p, *BOOKINGS,
                           "--baseline", str(self.dir / "bookings.manifest.json"))
        self.assertEqual(code, 3, out)
        self.assertIn("rows vs 40 in the baseline", out)
        self.assertIn("needs a decision", out)
        code, out, _ = run("check", str(FIX / "bookings.spec.json"), p, *BOOKINGS,
                           "--baseline", str(self.dir / "bookings.manifest.json"), "--row-tolerance", "0.9",
                           "--null-tolerance", "0.5")
        self.assertEqual(code, 0, out)

    def test_sql_outputs(self):
        spec = str(FIX / "bookings.spec.json")
        code, out, _ = run("sql", spec, "--dialect", "bigquery", "--schema", "raw", "--what", "ddl,load,checks,dbt")
        self.assertEqual(code, 0)
        self.assertIn("amount NUMERIC(18,2) NOT NULL", out)
        self.assertIn("created_at TIMESTAMP NOT NULL", out)
        self.assertIn("PRIMARY KEY (tenant_id, booking_id) NOT ENFORCED", out)
        self.assertIn("MERGE INTO raw.bookings AS t", out)
        self.assertIn("CREATE OR REPLACE TABLE raw.bookings__staging", out)  # fresh staging every load
        self.assertIn("bq load --replace --source_format=PARQUET raw.bookings__staging", out)
        self.assertIn("BEGIN TRANSACTION;", out)
        self.assertNotIn("guest_name", out)
        self.assertIn("accepted_values", out)
        self.assertNotIn("VARCHAR", out)  # BigQuery has no VARCHAR
        for dialect in ("snowflake", "postgres", "clickhouse", "duckdb"):
            code, out, _ = run("sql", spec, "--dialect", dialect)
            self.assertEqual(code, 0, dialect)

    def test_generated_duckdb_sql_runs(self):
        import shutil
        import subprocess
        if not shutil.which("duckdb"):
            self.skipTest("duckdb CLI not installed")
        self.apply()
        spec = str(FIX / "bookings.spec.json")
        _, ddl, _ = run("sql", spec, "--dialect", "duckdb", "--what", "ddl,load", "--out-dir", str(self.dir))
        _, checks, _ = run("sql", spec, "--dialect", "duckdb", "--what", "checks")
        ddl = ddl.replace(f"FROM '{self.dir}/bookings.parquet' (FORMAT parquet)", f"FROM '{self.dir}/bookings.csv' (HEADER)")
        p = subprocess.run(["duckdb", "-csv", "-c", ddl + "\n" + checks], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        failures = [l for l in p.stdout.splitlines()[1:] if l and not l.endswith(",0")]
        self.assertEqual(failures, [])


DUCK_ORDERS = {"spec_version": 1, "name": "shop", "source": {"format": "csv"}, "tables": [
    {"name": "orders", "key": ["order_id"], "columns": [
        {"name": "order_id", "from": "id", "type": "integer"},
        {"name": "status", "from": "status", "type": "string", "required": True},
        {"name": "amount", "from": "amount", "type": "decimal", "scale": 2, "precision": 18},
        {"name": "updated_at", "from": "updated_at", "type": "timestamp", "formats": ["iso"], "required": True}],
     "load": {"mode": "merge", "newer_by": "updated_at"},
     "monitor": {"time": "updated_at", "sums": ["amount"], "max_age_hours": 26}}]}


class Loads(Case):
    """The generated load SQL, executed in DuckDB: reruns, stale exports and slices."""

    def setUp(self):
        super().setUp()
        import shutil
        if not shutil.which("duckdb"):
            self.skipTest("duckdb CLI not installed")
        self.db = str(self.dir / "wh.duckdb")

    def duck(self, sql):
        import subprocess
        p = subprocess.run(["duckdb", "-csv", self.db, "-c", sql], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr + sql)
        return p.stdout

    def load(self, spec_doc, csv_text, first=False):
        spec = self.write("spec.json", json.dumps(spec_doc))
        src = self.write("in.csv", csv_text)
        out = self.dir / "clean"
        code, o, e = run("apply", spec, src, "--out-dir", str(out))
        self.assertEqual(code, 0, o + e)
        _, sql, _ = run("sql", spec, "--dialect", "duckdb", "--what", ("ddl," if first else "") + "load", "--out-dir", str(out))
        for t in spec_doc["tables"]:
            sql = sql.replace(f"FROM '{out}/{t['name']}.parquet' (FORMAT parquet)", f"FROM '{out}/{t['name']}.csv' (HEADER)")
        self.duck(sql)

    def test_merge_is_idempotent_and_ignores_stale_exports(self):
        new = "id,status,amount,updated_at\n1,paid,10.00,2026-10-02T10:00:00Z\n2,refunded,5.00,2026-10-02T11:00:00Z\n"
        old = "id,status,amount,updated_at\n2,paid,5.00,2026-10-01T11:00:00Z\n3,paid,7.50,2026-10-01T12:00:00Z\n"
        self.load(DUCK_ORDERS, new, first=True)
        self.load(DUCK_ORDERS, new)  # rerun: no duplicates
        self.load(DUCK_ORDERS, old)  # an older export must not undo the refund
        rows = self.duck("SELECT order_id, status FROM orders ORDER BY 1").split()
        self.assertEqual(rows, ["order_id,status", "1,paid", "2,refunded", "3,paid"])

    def test_replace_by_swaps_only_the_slices_in_the_load(self):
        spec = {"spec_version": 1, "name": "lines", "params": {"tenant_id": {}}, "tables": [
            {"name": "order_lines", "key": ["tenant_id", "order_id", "line_no"], "columns": [
                {"name": "tenant_id", "from": {"param": "tenant_id"}, "type": "string"},
                {"name": "order_id", "from": "order", "type": "integer"},
                {"name": "line_no", "from": "line", "type": "integer"},
                {"name": "sku", "from": "sku", "type": "string"}],
             "load": {"mode": "replace_by", "by": ["tenant_id", "order_id"]}}]}
        def go(tenant, text, first=False):
            doc = json.loads(json.dumps(spec))
            doc["tables"][0]["columns"][0]["from"] = {"const": tenant}
            del doc["params"]
            self.load(doc, text, first)
        go("a", "order,line,sku\n1,1,X\n1,2,Y\n2,1,Z\n", first=True)
        go("b", "order,line,sku\n1,1,Q\n")
        go("a", "order,line,sku\n1,1,X\n")  # order 1 lost a line upstream; order 2 not in this load
        rows = self.duck("SELECT tenant_id, order_id, line_no, sku FROM order_lines ORDER BY 1,2,3").split()
        self.assertEqual(rows, ["tenant_id,order_id,line_no,sku", "a,1,1,X", "a,2,1,Z", "b,1,1,Q"])

    def test_replace_by_newer_keeps_newer_slices(self):
        spec = {"spec_version": 1, "name": "lines", "tables": [
            {"name": "order_lines", "key": ["order_id", "line_no"], "columns": [
                {"name": "order_id", "from": "order", "type": "integer"},
                {"name": "line_no", "from": "line", "type": "integer"},
                {"name": "sku", "from": "sku", "type": "string"},
                {"name": "order_updated_at", "from": "upd", "type": "timestamp", "formats": ["iso"], "required": True}],
             "load": {"mode": "replace_by", "by": ["order_id"], "newer_by": "order_updated_at"}}]}
        new = "order,line,sku,upd\n1,1,X,2026-10-02T00:00:00Z\n"
        old = "order,line,sku,upd\n1,1,X,2026-10-01T00:00:00Z\n1,2,Y,2026-10-01T00:00:00Z\n2,1,Z,2026-10-01T00:00:00Z\n"
        self.load(spec, new, first=True)
        self.load(spec, old)  # older export: order 1 keeps its newer single line, order 2 is new
        self.load(spec, new)  # rerun: no change
        rows = self.duck("SELECT order_id, line_no, sku FROM order_lines ORDER BY 1,2").split()
        self.assertEqual(rows, ["order_id,line_no,sku", "1,1,X", "2,1,Z"])

    def test_monitors_fire_on_doubled_days_and_stay_silent_when_healthy(self):
        spec_doc = {"spec_version": 1, "name": "shop", "tables": [{"name": "orders", "key": ["order_id"], "columns": [
            {"name": "order_id", "from": "id", "type": "integer"},
            {"name": "currency", "from": "c", "type": "string", "required": True},
            {"name": "amount", "from": "a", "type": "decimal", "scale": 2},
            {"name": "created_at", "from": "t", "type": "timestamp", "formats": ["iso"], "required": True}],
            "monitor": {"time": "created_at", "sums": ["amount"], "by": ["currency"]}}]}
        spec = self.write("spec.json", json.dumps(spec_doc))
        _, sql, _ = run("sql", spec, "--dialect", "duckdb", "--what", "monitors")
        # 40 days, weekends quieter; one order id per row so duplicates are visible
        healthy = ("CREATE OR REPLACE TABLE orders AS SELECT row_number() OVER () AS order_id, 'EUR' AS currency, "
                   "10.00::DECIMAL(18,2) AS amount, (current_date - d::INTEGER)::TIMESTAMPTZ + INTERVAL 12 HOUR AS created_at "
                   "FROM range(1, 41) r(d), range(0, 100) n(i) WHERE i < CASE WHEN isodow(current_date - d::INTEGER) >= 6 THEN 40 ELSE 100 END;")
        self.assertNotIn("daily_volume", self.duck(healthy + sql))
        doubled = healthy + ("INSERT INTO orders SELECT order_id + 100000, currency, amount, created_at FROM orders "
                             "WHERE CAST(created_at AS DATE) IN (current_date - 2, current_date - 3);")
        out = self.duck(doubled + sql)
        self.assertEqual(out.count("orders.daily_volume"), 2, out)

    def test_monitor_sql_runs(self):
        self.load(DUCK_ORDERS, "id,status,amount,updated_at\n1,paid,10.00,2026-10-02T10:00:00Z\n", first=True)
        spec = self.write("spec.json", json.dumps(DUCK_ORDERS))
        code, sql, _ = run("sql", spec, "--dialect", "duckdb", "--what", "monitors")
        self.assertEqual(code, 0)
        out = self.duck(sql)
        self.assertIn("orders.freshness", out)  # the only row is long past 26 hours


BANK = ("Kontoauszug;;;\r\nAnfangssaldo: 2.500,00 EUR;;;\r\n;;;\r\nBuchungstag;Empfänger;Betrag;Währung\r\n"
        "01.09.2026;Miete;1.250,00-;EUR\r\n01.09.2026;Miete;1.250,00-;EUR\r\n02.09.2026;Gehalt;3.456,78;EUR\r\n"
        ";;;\r\nEndsaldo: 3.456,78 EUR;;;\r\n")


class Contracts(Case):
    def bank_spec(self, closing_regex=r"Endsaldo: ([\d.,-]+)"):
        return self.spec([{"name": "tx", "filters": [{"field": "Buchungstag", "matches": "^Endsaldo", "reason": "footer"}],
                           "columns": [
                               {"name": "booking_date", "from": "Buchungstag", "type": "date", "formats": ["%d.%m.%Y"]},
                               {"name": "amount", "from": "Betrag", "type": "decimal", "scale": 2},
                               {"name": "closing", "from": {"footer": 1, "regex": closing_regex}, "type": "decimal", "scale": 2}],
                           "control_totals": [{"sum": "amount",
                                               "from": {"preamble": 2, "regex": r"Anfangssaldo: ([\d.,-]+)"},
                                               "to": {"footer": 1, "regex": closing_regex}},
                                              {"count": True, "equals": {"const": "3"}}]}],
                         name="bank", source={"header_row": 4, "locale": {"decimal": ",", "thousands": "."}})

    def test_balance_reconciles_with_identical_rows_kept(self):
        src = self.write("k.csv", BANK, "cp1252")
        code, out, err = run("apply", self.bank_spec(), src, "--out-dir", str(self.dir))
        self.assertEqual(code, 0, out + err)
        self.assertIn("control_total", (self.dir / "bank.manifest.json").read_text())
        self.assertEqual(read_csv(self.dir / "tx.csv")[0]["closing"], "3456.78")

    def test_wrong_balance_fails_and_writes_nothing(self):
        src = self.write("k.csv", BANK.replace("Endsaldo: 3.456,78", "Endsaldo: 4.706,78"), "cp1252")
        code, out, _ = run("apply", self.bank_spec(), src, "--out-dir", str(self.dir))
        self.assertEqual(code, 1)
        self.assertIn("FAILED tx.control_total:amount", out)
        self.assertFalse((self.dir / "tx.csv").exists())

    def test_root_values_and_env_params(self):
        doc = {"export": {"total": 2}, "rows": [{"id": 1}, {"id": 2}]}
        src = self.write("e.json", json.dumps(doc))
        spec = self.spec([{"name": "rows", "rows_from": "rows[]", "columns": [
            {"name": "id", "from": "id", "type": "integer"},
            {"name": "tenant", "from": {"param": "tenant"}, "type": "string"}],
            "control_totals": [{"count": True, "equals": {"root": "export.total"}}]}],
            params={"tenant": {"env": "DM_TEST_TENANT"}})
        code, _, err = run("check", spec, src)
        self.assertEqual(code, 2)
        self.assertIn("$DM_TEST_TENANT", err)
        os.environ["DM_TEST_TENANT"] = "acme"
        try:
            code, out, err = run("apply", spec, src, "--out-dir", str(self.dir))
        finally:
            del os.environ["DM_TEST_TENANT"]
        self.assertEqual(code, 0, out + err)
        self.assertEqual(read_csv(self.dir / "rows.csv")[1], {"id": "2", "tenant": "acme"})

    def test_dst_gap_reject_or_shift(self):
        col = {"name": "t", "type": "timestamp", "formats": ["%Y-%m-%d %H:%M"], "tz": "Europe/Berlin"}
        with self.assertRaises(datamax.Reject):
            datamax.convert(col, "2026-03-29 02:30", {}, {})
        self.assertEqual(datamax.convert(dict(col, dst_gap="shift_forward"), "2026-03-29 02:30", {}, {}),
                         "2026-03-29T01:30:00Z")

    def test_draft_spec_never_overwrites(self):
        src = self.write("a.csv", "id,x\n1,2\n")
        target = self.write("s.json", "{}")
        code, _, err = run("profile", src, "--draft-spec", target)
        self.assertEqual(code, 2)
        self.assertEqual(Path(target).read_text(), "{}")

    def test_replace_with_tenant_param_is_refused(self):
        spec = self.spec([{"name": "t", "load": {"mode": "replace"}, "columns": [
            {"name": "tenant_id", "from": {"param": "tenant"}, "type": "string"},
            {"name": "x", "from": "x", "type": "string"}]}], params={"tenant": {}})
        code, _, err = run("sql", spec, "--dialect", "postgres")
        self.assertEqual(code, 2)
        self.assertIn("replace_by", err)

    def test_manifest_history_and_bigquery_numeric(self):
        src = self.write("a.csv", "id,v\n1,2.5\n")
        spec = self.spec([{"name": "t", "columns": [{"name": "id", "from": "id", "type": "integer"},
                                                    {"name": "v", "from": "v", "type": "decimal", "scale": 2}]}])
        run("apply", spec, src, "--out-dir", str(self.dir))
        self.assertEqual(len(list((self.dir / "manifests").glob("t.*.manifest.json"))), 1)
        self.assertEqual(datamax.sql_type({"type": "decimal", "precision": 38, "scale": 9}, "bigquery"), "NUMERIC(38,9)")
        self.assertEqual(datamax.sql_type({"type": "decimal", "precision": 38, "scale": 2}, "bigquery"), "BIGNUMERIC(38,2)")
        self.assertEqual(datamax.sql_type({"type": "decimal", "precision": 31, "scale": 9}, "bigquery"), "NUMERIC(31,9)")

    def test_check_missing_column_is_drift_and_bad_param_is_usage(self):
        src = self.write("a.csv", "id\n1\n")
        spec = self.spec([{"name": "t", "columns": [{"name": "id", "from": "id", "type": "integer"},
                                                    {"name": "v", "from": "v", "type": "string"}]}])
        code, out, _ = run("check", spec, src)
        self.assertEqual(code, 3)
        self.assertIn("gone from the header", out)
        code, _, _ = run("check", spec, self.write("b.csv", "id,v\n1,x\n"), "--param", "nope=1")
        self.assertEqual(code, 2)


def _insert_field(line, pos, value):
    row = next(csv.reader([line], delimiter=";"))
    row.insert(pos, value)
    buf = io.StringIO()
    csv.writer(buf, delimiter=";", lineterminator="").writerow(row)
    return buf.getvalue()


class Trees(Case):
    def test_split_orders_and_items(self):
        spec = self.spec([
            {"name": "orders", "rows_from": "orders[]", "key": ["order_id"], "columns": [
                {"name": "order_id", "from": "orderId", "type": "string"},
                {"name": "placed_at", "from": "placedAt", "type": "timestamp", "formats": ["iso", "%m/%d/%Y"], "tz": "Europe/Berlin"},
                {"name": "customer_id", "from": "customer.id", "type": "string", "required": True},
                {"name": "total", "from": "totalCents", "type": "decimal", "scale": 2, "divide_by": 100}]},
            {"name": "order_items", "rows_from": "orders[].items[]", "key": ["order_id", "line_no"], "columns": [
                {"name": "order_id", "from": "^orderId", "type": "string", "references": "orders.order_id"},
                {"name": "line_no", "from": "#index", "type": "integer"},
                {"name": "sku", "from": "sku", "type": "string", "required": True},
                {"name": "qty", "from": "qty", "type": "integer", "min": 1},
                {"name": "unit_price", "from": "unitPriceCents", "type": "decimal", "scale": 2, "divide_by": 100}]},
        ], name="orders")
        code, out, err = run("apply", spec, str(FIX / "orders.json"), "--out-dir", str(self.dir))
        self.assertEqual(code, 0, out + err)
        orders, items = read_csv(self.dir / "orders.csv"), read_csv(self.dir / "order_items.csv")
        self.assertEqual(len(orders), 8)
        self.assertEqual(orders[0]["placed_at"], "2026-03-01T09:00:00Z")
        self.assertEqual(orders[3]["placed_at"], "2026-03-03T23:00:00Z")  # 03/04/2026 local midnight
        self.assertEqual(items[0], {"order_id": "O-1", "line_no": "1", "sku": "SKU-1", "qty": "1", "unit_price": "19.99"})
        self.assertTrue(all(i["order_id"] in {o["order_id"] for o in orders} for i in items))

    def test_orphan_reference_fails(self):
        p = self.write("o.json", json.dumps({"a": [{"id": 1}], "b": [{"a_id": 2}]}))
        spec = self.spec([
            {"name": "a", "rows_from": "a[]", "columns": [{"name": "id", "from": "id", "type": "integer"}]},
            {"name": "b", "rows_from": "b[]", "columns": [{"name": "a_id", "from": "a_id", "type": "integer", "references": "a.id"}]}])
        code, out, _ = run("apply", spec, p, "--out-dir", str(self.dir))
        self.assertEqual(code, 1)
        self.assertIn("orphans", out)

    def test_jsonl_and_xml(self):
        p = self.write("e.jsonl", '{"id": 1, "amount": 1.10}\n{"id": 2, "amount": 0.20}\n')
        spec = self.spec([{"name": "e", "columns": [{"name": "id", "from": "id", "type": "integer"},
                                                    {"name": "amount", "from": "amount", "type": "decimal", "scale": 2}]}])
        self.assertEqual(run("apply", spec, p, "--out-dir", str(self.dir))[0], 0)
        self.assertEqual([r["amount"] for r in read_csv(self.dir / "e.csv")], ["1.10", "0.20"])
        x = self.write("o.xml", '<orders><order id="1"><total>9.50</total></order><order id="2"><total>1</total></order></orders>')
        spec = self.spec([{"name": "o", "rows_from": "orders.order[]", "columns": [
            {"name": "id", "from": "@id", "type": "integer"}, {"name": "total", "from": "total", "type": "decimal", "scale": 2}]}])
        self.assertEqual(run("apply", spec, x, "--out-dir", str(self.dir))[0], 0)
        self.assertEqual(read_csv(self.dir / "o.csv")[1], {"id": "2", "total": "1.00"})

    def test_xml_dtd_is_refused(self):
        x = self.write("bomb.xml", '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa">]><l>&a;</l>')
        code, _, err = run("profile", x)
        self.assertEqual(code, 2)
        self.assertIn("DOCTYPE", err)


class Tabular(Case):
    def test_unpivot_wide_months(self):
        p = self.write("w.csv", "product,Jan,Feb,Mar\nWidget,120,140,160\nGadget,80,,90\n")
        spec = self.spec([{"name": "sales", "unpivot": {"columns": ["Jan", "Feb", "Mar"], "name_to": "month", "value_to": "units"},
                           "columns": [{"name": "product", "from": "product", "type": "string"},
                                       {"name": "month", "from": "month", "type": "string", "map": {"Jan": "2026-01", "Feb": "2026-02", "Mar": "2026-03"}},
                                       {"name": "units", "from": "units", "type": "integer"}]}])
        self.assertEqual(run("apply", spec, p, "--out-dir", str(self.dir))[0], 0)
        rows = read_csv(self.dir / "sales.csv")
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[4], {"product": "Gadget", "month": "2026-02", "units": ""})

    def test_ragged_rows_are_rejected(self):
        p = self.write("r.csv", "a,b\n1,2\n3\n")
        spec = self.spec([{"name": "r", "max_rejects": 1, "columns": [
            {"name": "a", "from": "a", "type": "integer"}, {"name": "b", "from": "b", "type": "integer"}]}])
        code, out, _ = run("apply", spec, p, "--out-dir", str(self.dir))
        self.assertEqual(code, 0, out)
        self.assertEqual(read_csv(self.dir / "t.rejects.csv")[0]["source_row"], "3")

    def test_key_consistent_rejects_conflicts(self):
        p = self.write("k.csv", "id,v\n1,a\n1,b\n2,c\n2,c\n")
        spec = self.spec([{"name": "k", "key": ["id"], "dedupe": "key_consistent", "max_rejects": 5,
                           "columns": [{"name": "id", "from": "id", "type": "integer"}, {"name": "v", "from": "v", "type": "string"}]}])
        code, out, _ = run("apply", spec, p, "--out-dir", str(self.dir))
        self.assertEqual(code, 0, out)
        self.assertEqual(read_csv(self.dir / "k.csv"), [{"id": "2", "v": "c"}])
        self.assertEqual(len(read_csv(self.dir / "t.rejects.csv")), 2)

    def test_duplicate_key_without_dedupe_fails(self):
        p = self.write("k.csv", "id\n1\n1\n")
        spec = self.spec([{"name": "k", "key": ["id"], "columns": [{"name": "id", "from": "id", "type": "integer"}]}])
        code, out, _ = run("apply", spec, p, "--out-dir", str(self.dir))
        self.assertEqual(code, 1)
        self.assertIn("duplicate keys", out)

    def test_xlsx(self):
        p = self.dir / "s.xlsx"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                       '<sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                       '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                       '<si><t>Day</t></si><si><t>Revenue</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
                       '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                       '<row r="2"><c r="A2"><v>45000</v></c><c r="B2"><v>12.5</v></c></row></sheetData></worksheet>')
        spec = self.spec([{"name": "x", "columns": [{"name": "day", "from": "Day", "type": "date", "formats": ["excel_serial"]},
                                                    {"name": "revenue", "from": "Revenue", "type": "decimal", "scale": 2}]}])
        code, out, err = run("apply", spec, str(p), "--out-dir", str(self.dir))
        self.assertEqual(code, 0, out + err)
        self.assertEqual(read_csv(self.dir / "x.csv"), [{"day": "2023-03-15", "revenue": "12.50"}])


class Profile(Case):
    def test_bookings_profile_finds_the_traps(self):
        draft = self.dir / "draft.json"
        code, out, _ = run("profile", str(FIX / "bookings_export.csv"), "--draft-spec", str(draft))
        self.assertEqual(code, 0)
        for needle in ("header at record 4", "total/footer rows", "exact duplicate rows: 1", "leading zeros",
                       "accounting negatives", "Excel serial", "no timezone", "case variants", "PII: email"):
            self.assertIn(needle, out)
        d = json.loads(draft.read_text())
        self.assertEqual(d["source"]["delimiter"], ";")
        plz = next(c for c in d["tables"][0]["columns"] if c["from"] == "PLZ")
        self.assertEqual(plz["type"], "string")
        code, _, err = run("apply", str(draft), str(FIX / "bookings_export.csv"))
        self.assertEqual(code, 2)
        self.assertIn("unresolved decision", err)

    def test_tree_profile_lists_rows_from(self):
        code, out, _ = run("profile", str(FIX / "orders.json"))
        self.assertEqual(code, 0)
        self.assertIn("orders[].items[]", out)
        self.assertIn("mixed JSON types", out)

    def test_composite_key_and_sparse_footer(self):
        p = self.write("ads.csv", "Report;;;\nDay;Campaign;Clicks;Cost\n2026-10-01;A;5;1.50\n2026-10-01;B;5;2.50\n"
                                  "2026-10-02;A;7;3.10\nEndsumme 7,10;;;\n")
        draft = self.dir / "d.json"
        _, out, _ = run("profile", p, "--draft-spec", str(draft))
        self.assertIn("['Day + Campaign']", out)
        self.assertIn("Endsumme", out)
        t = json.loads(draft.read_text())["tables"][0]
        self.assertEqual(t["key"], ["day", "campaign"])
        self.assertIn("Endsumme", t["filters"][0]["matches"])
        self.assertIn("TODO", t["control_totals"])

    def test_wide_format_detected(self):
        p = self.write("w.csv", "product,Jan,Feb,Mar\nWidget,120,140,160\n")
        _, out, _ = run("profile", p)
        self.assertIn("wide format", out)

    def test_snake(self):
        self.assertEqual(datamax.snake("Revenue ($)"), "revenue_usd")
        self.assertEqual(datamax.snake("Nächte"), "naechte")
        self.assertEqual(datamax.snake("2024 Target"), "target_2024")
        self.assertEqual(datamax.snake("%Margin"), "pct_margin")
        self.assertEqual(datamax.snake("orderId"), "order_id")


if __name__ == "__main__":
    unittest.main()
