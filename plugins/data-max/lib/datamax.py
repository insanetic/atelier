#!/usr/bin/env python3
"""data-max: profile raw data exports, clean them with a declarative spec, check new
exports against it, and emit warehouse SQL.

Stdlib only, Python 3.9+. Deterministic: the same spec, input bytes and params produce
byte-identical CSV outputs and manifest. Nothing reads the clock or file timestamps.

    data-max profile <file> [--draft-spec spec.json]
    data-max apply   <spec.json> <input> [--param k=v ...] [--out-dir DIR] [--parquet]
    data-max check   <spec.json> <input> [--param k=v ...] [--baseline manifest.json]
    data-max sql     <spec.json> --dialect bigquery|snowflake|postgres|clickhouse|duckdb
                     [--what ddl,load,checks,monitors,dbt]
    data-max spec    (prints the spec format reference)
    data-max vendor  <dir>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python < 3.9
    sys.exit("data-max needs Python 3.9 or newer")

VERSION = "2.1.0"
SPEC_VERSION = 1
TYPES = ("string", "integer", "decimal", "boolean", "date", "timestamp", "datetime")
DEFAULT_NULL_TOKENS = ["", "null", "none", "n/a", "na", "#n/a", "-", "--", "—", "nan"]
TRUE_TOKENS = ["true", "t", "yes", "y", "1", "ja", "j", "wahr", "x"]
FALSE_TOKENS = ["false", "f", "no", "n", "0", "nein", "falsch"]
EXCEL_EPOCH = datetime(1899, 12, 30)
SNAKE = re.compile(r"^[a-z_][a-z0-9_]*$")
LOAD_MODES = ("append", "replace", "replace_by", "merge")
TOTAL_RE = re.compile(r"^\s*(grand\s*)?(total|totals|sum|subtotal|summe|gesamt|gesamtsumme|totaal|totale|somme)\b", re.I)


class SpecError(Exception):
    """The spec or the invocation is wrong; nothing was processed."""


class Reject(Exception):
    """One value or row cannot be converted; the row goes to the rejects file."""


# ----------------------------------------------------------------------------- reading


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_encoding(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def detect_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    return {".json": "json", ".jsonl": "jsonl", ".ndjson": "jsonl", ".xml": "xml", ".xlsx": "xlsx",
            ".xlsm": "xlsx", ".tsv": "csv", ".tab": "csv"}.get(ext, "csv")


def sniff_delimiter(text: str) -> str:
    best, best_score = ",", -1
    sample = text[:200000]
    for cand in (",", ";", "\t", "|"):
        rows = list(csv.reader(io.StringIO(sample), delimiter=cand))[:300]
        widths = Counter(len(r) for r in rows if any(c.strip() for c in r))
        if not widths:
            continue
        width, count = widths.most_common(1)[0]
        score = count if width > 1 else 0
        if score > best_score:
            best, best_score = cand, score
    return best


def read_xlsx(data: bytes, sheet=None) -> list:
    """Minimal .xlsx reader: one sheet as a list of rows of strings. Numbers keep the
    stored text, so date cells arrive as Excel serials (parse them with excel_serial)."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in safe_xml(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    wb = safe_xml(z.read("xl/workbook.xml"))
    sheets = wb.findall("m:sheets/m:sheet", ns)
    if not sheets:
        raise SpecError("workbook has no sheets")
    chosen = sheets[0]
    if sheet is not None:
        by_name = [s for s in sheets if s.get("name") == str(sheet)]
        if by_name:
            chosen = by_name[0]
        elif str(sheet).isdigit() and 1 <= int(sheet) <= len(sheets):
            chosen = sheets[int(sheet) - 1]
        else:
            raise SpecError(f"sheet {sheet!r} not found; sheets: {[s.get('name') for s in sheets]}")
    rid = chosen.get("{%s}id" % ns["r"])
    rels = safe_xml(z.read("xl/_rels/workbook.xml.rels"))
    target = next(r.get("Target") for r in rels if r.get("Id") == rid)
    target = target.lstrip("/")
    if not target.startswith("xl/"):
        target = "xl/" + target
    root = safe_xml(z.read(target))
    rows = []
    for row in root.iter("{%s}row" % ns["m"]):
        cells = {}
        for c in row.findall("m:c", ns):
            ref = c.get("r", "")
            col = 0
            for ch in re.match(r"[A-Z]+", ref).group(0) if ref else "":
                col = col * 26 + ord(ch) - 64
            t = c.get("t")
            v = c.find("m:v", ns)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
            else:
                val = v.text if v is not None and v.text is not None else ""
            cells[col or len(cells) + 1] = val
        width = max(cells) if cells else 0
        rows.append([cells.get(i, "") for i in range(1, width + 1)])
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) if any(x != "" for x in r) else r for r in rows]


def safe_xml(data: bytes):
    """Parse XML that declares no DTD or entities (blocks entity-expansion attacks)."""
    if re.search(rb"<!(DOCTYPE|ENTITY)", data[:65536] if len(data) > 65536 else data, re.I) or re.search(rb"<!ENTITY", data, re.I):
        raise SpecError("XML with a DOCTYPE/ENTITY declaration is refused; strip the DTD first")
    return ET.fromstring(data)


def xml_to_obj(elem):
    children = list(elem)
    if not children and not elem.attrib:
        return (elem.text or "").strip()
    obj = OrderedDict(("@" + k, v) for k, v in elem.attrib.items())
    for ch in children:
        val = xml_to_obj(ch)
        tag = ch.tag.split("}")[-1]
        if tag in obj:
            if not isinstance(obj[tag], list):
                obj[tag] = [obj[tag]]
            obj[tag].append(val)
        else:
            obj[tag] = val
    text = (elem.text or "").strip()
    if text:
        obj["#text"] = text
    return obj


class Source:
    """A loaded input: either tabular records (CSV/XLSX) or a tree (JSON/JSONL/XML)."""

    def __init__(self, path: str, src: dict):
        self.path = path
        self.data = Path(path).read_bytes()
        self.sha256 = sha256_bytes(self.data)
        self.format = src.get("format") or detect_format(path)
        self.tabular = self.format in ("csv", "xlsx")
        self.records = None  # tabular: list of lists (all physical records)
        self.tree = None
        self.encoding = src.get("encoding") or detect_encoding(self.data)
        self.delimiter = None
        if self.format == "csv":
            text = self.data.decode(self.encoding)
            self.delimiter = src.get("delimiter") or sniff_delimiter(text)
            if self.delimiter == "\\t":
                self.delimiter = "\t"
            self.records = list(csv.reader(io.StringIO(text, newline=""), delimiter=self.delimiter))
        elif self.format == "xlsx":
            self.records = read_xlsx(self.data, src.get("sheet"))
        elif self.format == "json":
            self.tree = json.loads(self.data.decode(self.encoding), parse_float=Decimal)
        elif self.format == "jsonl":
            lines = self.data.decode(self.encoding).splitlines()
            self.tree = [json.loads(l, parse_float=Decimal) for l in lines if l.strip()]
        elif self.format == "xml":
            root = safe_xml(self.data)
            self.tree = {root.tag.split("}")[-1]: xml_to_obj(root)}
        else:
            raise SpecError(f"unknown format {self.format!r}")


class Rec:
    """One input row. Tabular rows are dicts by header; tree rows keep their parents."""

    __slots__ = ("row", "data", "parent", "index", "extra")

    def __init__(self, row, data, parent=None, index=None):
        self.row, self.data, self.parent, self.index, self.extra = row, data, parent, index, {}

    def get(self, path: str):
        if path in self.extra:
            return self.extra[path]
        node = self
        while path.startswith("^"):
            node, path = node.parent, path[1:]
            if node is None:
                raise SpecError(f"path {path!r} climbs above the root")
        if path == "#index":
            return node.index
        if isinstance(node.data, dict) and path in node.data:
            return node.data[path]
        cur = node.data
        for part in path.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        return cur


def tree_rows(tree, rows_from: str):
    """Expand 'orders[].items[]' into Recs with parent links. '[]' alone = top-level array."""
    parts = [p for p in re.split(r"\[\]\.?", rows_from) if p != ""] if rows_from not in ("", "[]") else []
    steps = rows_from.count("[]")
    if rows_from == "":
        items = tree if isinstance(tree, list) else [tree]
        return [Rec(f"[{i}]", o, None, i) for i, o in enumerate(items, 1)]
    recs = [Rec("$", tree, None, None)]
    if rows_from.startswith("[]"):
        parts = [""] + parts
    for depth in range(steps):
        key = parts[depth] if depth < len(parts) else ""
        nxt = []
        for r in recs:
            cur = r.data
            for k in [k for k in key.split(".") if k]:
                cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                continue
            if not isinstance(cur, list):
                cur = [cur]
            label = (key or "") if r.row == "$" else f"{r.row}.{key}" if key else r.row
            for i, item in enumerate(cur, 1):
                nxt.append(Rec(f"{label}[{i}]", item, r if r.row != "$" else None, i))
        recs = nxt
    return recs


# ----------------------------------------------------------------------------- spec


def load_spec(path: str) -> dict:
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)
    except json.JSONDecodeError as e:
        raise SpecError(f"{path}: not valid JSON: {e}")
    validate_spec(spec)
    return spec


def find_todos(obj, path="spec"):
    if isinstance(obj, str) and "TODO" in obj:
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from find_todos(v, f"{path}.{k}")
            if isinstance(k, str) and "TODO" in k:
                yield f"{path}.{k}", k
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from find_todos(v, f"{path}[{i}]")


def validate_spec(spec: dict) -> None:
    errs = []
    todos = list(find_todos(spec))
    if todos:
        errs += [f"unresolved decision at {p}: {v}" for p, v in todos]
    if spec.get("spec_version") != SPEC_VERSION:
        errs.append(f"spec_version must be {SPEC_VERSION}")
    if not isinstance(spec.get("name"), str) or not SNAKE.match(spec.get("name", "")):
        errs.append("name must be snake_case")
    tables = spec.get("tables")
    if not isinstance(tables, list) or not tables:
        errs.append("tables must be a non-empty list")
        tables = []
    names = set()
    for ti, t in enumerate(tables):
        where = f"tables[{ti}]"
        tn = t.get("name", "")
        if not SNAKE.match(tn or ""):
            errs.append(f"{where}.name must be snake_case")
        if tn in names:
            errs.append(f"{where}.name {tn!r} is duplicated")
        names.add(tn)
        cols = t.get("columns") or []
        if not cols:
            errs.append(f"{where}.columns is empty")
        seen = set()
        for ci, c in enumerate(cols):
            cw = f"{where}.columns[{ci}]"
            n = c.get("name", "")
            if not SNAKE.match(n or ""):
                errs.append(f"{cw}.name {n!r} must be snake_case (lowercase ASCII, digits, _)")
            if n in seen:
                errs.append(f"{cw}.name {n!r} is duplicated")
            seen.add(n)
            if c.get("type") not in TYPES:
                errs.append(f"{cw}.type must be one of {', '.join(TYPES)}")
            if "from" not in c:
                errs.append(f"{cw} needs 'from'")
            if c.get("type") == "decimal" and not isinstance(c.get("scale"), int):
                errs.append(f"{cw}: decimal needs an integer 'scale'")
            if c.get("type") in ("date", "timestamp", "datetime") and not c.get("formats"):
                errs.append(f"{cw}: {c.get('type')} needs 'formats'")
            pii = c.get("pii")
            if pii is not None and pii.get("action") not in ("keep", "hash", "drop"):
                errs.append(f"{cw}.pii.action must be keep, hash or drop")
            if c.get("tz"):
                try:
                    ZoneInfo(c["tz"])
                except (ZoneInfoNotFoundError, ValueError):
                    errs.append(f"{cw}.tz {c['tz']!r} is not an IANA timezone")
        for k in t.get("key") or []:
            if k not in seen:
                errs.append(f"{where}.key column {k!r} is not a column of the table")
        if t.get("dedupe", "none") not in ("none", "exact", "key_first", "key_last", "key_consistent"):
            errs.append(f"{where}.dedupe must be none, exact, key_first, key_last or key_consistent")
        if t.get("dedupe", "none").startswith("key") and not t.get("key"):
            errs.append(f"{where}: dedupe {t.get('dedupe')} needs a key")
        by_name = {c.get("name"): c for c in cols}
        cts = t.get("control_totals") or []
        for i, ct in enumerate(cts if isinstance(cts, list) else []):
            cw = f"{where}.control_totals[{i}]"
            if ("sum" in ct) == bool(ct.get("count")):
                errs.append(f"{cw} needs exactly one of 'sum': <column> or 'count': true")
            elif "sum" in ct and (by_name.get(ct["sum"]) or {}).get("type") not in ("integer", "decimal"):
                errs.append(f"{cw}.sum must name an integer or decimal column of the table")
            if not ("equals" in ct or ("from" in ct and "to" in ct)):
                errs.append(f"{cw} needs 'equals', or 'from' and 'to' (opening + sum = closing)")
        mon = t.get("monitor")
        if isinstance(mon, dict):
            if (by_name.get(mon.get("time")) or {}).get("type") not in ("timestamp", "date", "datetime"):
                errs.append(f"{where}.monitor.time must name a timestamp, datetime or date column")
            for c in list(mon.get("sums", [])) + list(mon.get("by", [])):
                if c not in seen:
                    errs.append(f"{where}.monitor column {c!r} is not a column of the table")
        load = t.get("load", {})
        mode = load.get("mode", "append")
        if mode not in LOAD_MODES:
            errs.append(f"{where}.load.mode must be one of {', '.join(LOAD_MODES)}")
        if mode == "merge" and not t.get("key"):
            errs.append(f"{where}: load mode merge needs a key")
        if mode in ("replace_by",):
            by = load.get("by") or []
            if not by:
                errs.append(f"{where}: load mode replace_by needs 'by': the columns whose slice each load replaces")
            for b in by:
                if b not in seen:
                    errs.append(f"{where}.load.by column {b!r} is not a column of the table")
                elif not (by_name[b].get("required") or b in (t.get("key") or []) or isinstance(by_name[b].get("from"), dict)):
                    errs.append(f"{where}.load.by column {b!r} must be required (a NULL slice can't be replaced)")
        if mode == "replace":
            scoped = [c["name"] for c in cols if isinstance(c.get("from"), dict) and "param" in c["from"]]
            if scoped:
                errs.append(f"{where}: load mode replace empties the whole table, but {scoped} come from params "
                            f"(one tenant/slice per run); use replace_by with by: {scoped}")
        nb = load.get("newer_by")
        if nb is not None:
            if mode not in ("merge", "replace_by"):
                errs.append(f"{where}.load.newer_by only applies to merge and replace_by")
            elif (by_name.get(nb) or {}).get("type") not in ("timestamp", "datetime", "date", "integer") or not (by_name[nb].get("required") or nb in (t.get("key") or [])):
                errs.append(f"{where}.load.newer_by must be a required timestamp, datetime, date or integer column")
    for ti, t in enumerate(tables):
        for ci, c in enumerate(t.get("columns") or []):
            ref = c.get("references")
            if ref:
                rt, _, rc = ref.partition(".")
                target = next((x for x in tables if x.get("name") == rt), None)
                if not target or rc not in [x.get("name") for x in target.get("columns", [])]:
                    errs.append(f"tables[{ti}].columns[{ci}].references {ref!r} names no table.column in this spec")
    if errs:
        raise SpecError("spec is not valid:\n  " + "\n  ".join(errs))


def resolve_params(spec: dict, given: dict) -> dict:
    out = {}
    declared = spec.get("params", {})
    for k in given:
        if k not in declared:
            raise SpecError(f"unknown param {k!r}; the spec declares: {', '.join(declared) or 'none'}")
    for name, p in declared.items():
        if name in given:
            val = given[name]
        elif p.get("env") and os.environ.get(p["env"]):
            val = os.environ[p["env"]]
        elif "default" in p:
            val = p["default"]
        else:
            hint = f" or set ${p['env']}" if p.get("env") else ""
            raise SpecError(f"missing --param {name}=...{hint}  ({p.get('description', 'required')})")
        if p.get("pattern") and not re.fullmatch(p["pattern"], str(val)):
            raise SpecError(f"param {name}={val!r} does not match {p['pattern']}")
        out[name] = val
    return out


# ----------------------------------------------------------------------------- parsing values

ISO_CURRENCIES = ("EUR USD GBP CHF JPY CNY SEK NOK DKK PLN CZK HUF RON BGN TRY RUB UAH CAD AUD NZD SGD HKD "
                  "INR KRW BRL MXN ARS CLP COP ZAR ILS AED SAR THB MYR IDR PHP VND TWD").split()
CURRENCY_TOKEN = r"(?:%s|[€$£¥₹₽₺₩¤]|S?Fr\.)" % "|".join(ISO_CURRENCIES)
CURRENCY_RE = re.compile(r"^\s*%s\s*|\s*%s\s*$" % (CURRENCY_TOKEN, CURRENCY_TOKEN))
SPACES_RE = re.compile("[\\s\u00a0\u202f]")


def parse_number(s: str, decimal_sep: str, thousands_sep: str, parens: bool = True) -> Decimal:
    raw = s
    s = CURRENCY_RE.sub("", s.strip())
    if s[:1] in ("-", "+", "(") and CURRENCY_RE.search(s[1:]):  # "-€ 5"
        s = s[0] + CURRENCY_RE.sub("", s[1:])
    if s.endswith(")") and CURRENCY_RE.search(s[:-1]):  # "(€ 120)"
        s = CURRENCY_RE.sub("", s[:-1]) + ")"
    if thousands_sep != " ":
        s = SPACES_RE.sub("", s)
    neg = False
    if parens and s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.startswith(("-", "+")):
        neg, s = neg ^ (s[0] == "-"), s[1:]
    elif s.endswith("-"):
        neg, s = not neg, s[:-1]
    if thousands_sep == " ":
        s = SPACES_RE.sub(" ", s)
    d, t = re.escape(decimal_sep), re.escape(thousands_sep) if thousands_sep else None
    plain = rf"\d+(?:{d}\d+)?|{d}\d+"
    grouped = rf"\d{{1,3}}(?:{t}\d{{3}})+(?:{d}\d+)?" if t else None
    if not (re.fullmatch(plain, s) or (grouped and re.fullmatch(grouped, s))):
        raise Reject(f"{raw!r} is not a number with decimal separator {decimal_sep!r}"
                     + (f" and thousands separator {thousands_sep!r}" if thousands_sep else ""))
    if thousands_sep:
        s = s.replace(thousands_sep, "")
    val = Decimal(s.replace(decimal_sep, "."))
    return -val if neg else val


def number_locale(col: dict, src: dict):
    loc = dict(src.get("locale", {}))
    loc.update(col.get("locale", {}))
    dec = loc.get("decimal", ".")
    thou = loc.get("thousands", "," if dec == "." else ".")
    if dec == thou:
        raise SpecError(f"column {col['name']}: decimal and thousands separators are both {dec!r}")
    return dec, thou


def excel_serial(s: str) -> datetime:
    try:
        v = Decimal(s)
    except InvalidOperation:
        raise Reject(f"{s!r} is not an Excel serial")
    if not (1 <= v < 2958466):
        raise Reject(f"{s!r} is outside the Excel serial range")
    micro = int((v * 86400 * 1000000).to_integral_value(ROUND_HALF_EVEN))
    return EXCEL_EPOCH + timedelta(microseconds=micro)


def parse_datetime_any(s: str, formats) -> datetime:
    for f in formats:
        try:
            if f == "iso":
                v = s.replace("Z", "+00:00").replace("z", "+00:00")
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                    return datetime.fromisoformat(v)
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?([+-]\d{2}:\d{2})?", v):
                    continue
                return datetime.fromisoformat(v)
            if f == "excel_serial":
                if re.fullmatch(r"\d+(\.\d+)?", s):
                    return excel_serial(s)
                continue
            if f in ("unix_s", "unix_ms"):
                if re.fullmatch(r"-?\d+(\.\d+)?", s):
                    secs = Decimal(s) / (1000 if f == "unix_ms" else 1)
                    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=int(secs * 1000000))
                continue
            return datetime.strptime(s, f)
        except ValueError:
            continue
    raise Reject(f"{s!r} matches none of the formats {list(formats)}")


def localize(naive: datetime, tz: str, ambiguous, gap=None) -> datetime:
    z = ZoneInfo(tz)
    a, b = naive.replace(tzinfo=z, fold=0), naive.replace(tzinfo=z, fold=1)
    if a.utcoffset() != b.utcoffset():
        back = a.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None)
        if back != naive:
            if gap == "shift_forward":  # read with the offset before the jump: 02:30 -> 03:30 local
                return a.astimezone(timezone.utc)
            raise Reject(f"{naive.isoformat(sep=' ')} does not exist in {tz} (DST gap); set dst_gap")
        if ambiguous == "earlier":
            return a
        if ambiguous == "later":
            return b
        raise Reject(f"{naive.isoformat(sep=' ')} is ambiguous in {tz} (DST overlap); set dst_ambiguous")
    return a


def fmt_utc(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    frac = f".{dt.microsecond:06d}" if dt.microsecond else ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + frac + "Z"


def fmt_naive(dt: datetime) -> str:
    frac = f".{dt.microsecond:06d}" if dt.microsecond else ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + frac


def convert(col: dict, raw, src: dict, params: dict):
    """Raw input value -> canonical output string, or None for NULL. Raises Reject."""
    if isinstance(raw, (dict, list)):
        raise Reject("nested value; reach it with a dotted path or rows_from")
    if isinstance(raw, bool):
        raw = "true" if raw else "false"
    s = None if raw is None else str(raw)
    if s is not None and col.get("trim", True):
        s = s.strip()
    tokens = [t.casefold() for t in col.get("null_tokens", src.get("null_tokens", DEFAULT_NULL_TOKENS))]
    if s is None or s.casefold() in tokens:
        if col.get("required") or col.get("_key"):
            raise Reject("missing value in a required column")
        return None
    if "map" in col:
        m = col["map"]
        if col.get("map_case_sensitive"):
            s = m.get(s, s)
        else:
            folded = {str(k).casefold(): v for k, v in m.items()}
            s = folded.get(s.casefold(), s)
        if s is None:
            if col.get("required") or col.get("_key"):
                raise Reject("value maps to NULL in a required column")
            return None
        s = str(s)
    typ = col["type"]
    if typ == "string":
        case = col.get("case")
        if case == "lower":
            s = s.lower()
        elif case == "upper":
            s = s.upper()
        elif case == "title":
            s = s.title()
        if col.get("normalize_whitespace"):
            s = re.sub(r"\s+", " ", s)
        out = s
    elif typ in ("integer", "decimal"):
        dec, thou = number_locale(col, src)
        val = parse_number(s, dec, thou, col.get("negative_parens", True))
        if col.get("divide_by"):
            val = val / Decimal(str(col["divide_by"]))
        if col.get("multiply_by"):
            val = val * Decimal(str(col["multiply_by"]))
        scale = 0 if typ == "integer" else col["scale"]
        q = Decimal(1).scaleb(-scale)
        if val != val.quantize(q, rounding=ROUND_HALF_EVEN):
            mode = col.get("round")
            if mode is None:
                raise Reject(f"{s!r} has more than {scale} decimal places; set 'round' to allow rounding")
            val = val.quantize(q, rounding=ROUND_HALF_UP if mode == "half_up" else ROUND_HALF_EVEN)
        val = val.quantize(q)
        precision = col.get("precision", 38 if typ == "decimal" else 19)
        digits = len(str(abs(val)).split(".")[0].lstrip("0"))
        if digits > precision - scale:
            raise Reject(f"{s!r} needs more than {precision - scale} integer digits")
        if typ == "integer" and abs(val) > 2 ** 63 - 1:
            raise Reject(f"{s!r} does not fit a 64-bit integer")
        out = str(int(val)) if typ == "integer" else f"{val:f}"
        if "min" in col and val < Decimal(str(col["min"])):
            raise Reject(f"{out} is below the minimum {col['min']}")
        if "max" in col and val > Decimal(str(col["max"])):
            raise Reject(f"{out} is above the maximum {col['max']}")
    elif typ == "boolean":
        t = [x.casefold() for x in col.get("true", TRUE_TOKENS)]
        f = [x.casefold() for x in col.get("false", FALSE_TOKENS)]
        if s.casefold() in t:
            out = "true"
        elif s.casefold() in f:
            out = "false"
        else:
            raise Reject(f"{s!r} is not a known true/false token")
    else:
        dt = parse_datetime_any(s, col["formats"])
        if typ == "date":
            out = dt.date().isoformat()
        elif typ == "datetime":
            if dt.tzinfo is not None:
                raise Reject(f"{s!r} carries a UTC offset; use type timestamp")
            out = fmt_naive(dt)
        else:
            if dt.tzinfo is None:
                tz = col.get("tz") or src.get("timezone")
                if not tz:
                    raise SpecError(f"column {col['name']}: naive timestamps need 'tz' (or source.timezone)")
                dt = localize(dt, tz, col.get("dst_ambiguous"), col.get("dst_gap"))
            out = fmt_utc(dt)
        for bound in ("min", "max"):
            if bound in col and ((out < str(col[bound])) if bound == "min" else (out > str(col[bound]))):
                raise Reject(f"{out} is {'before' if bound == 'min' else 'after'} the {bound} {col[bound]}")
    if col.get("allowed") is not None and out not in [str(x) for x in col["allowed"]]:
        raise Reject(f"{out!r} is not an allowed value")
    if col.get("pattern") and not re.fullmatch(col["pattern"], out):
        raise Reject(f"{out!r} does not match {col['pattern']}")
    pii = col.get("pii")
    if pii and pii.get("action") == "hash":
        salt = params.get(pii.get("salt_param", "pii_salt"))
        if not salt:
            raise SpecError(f"column {col['name']}: hashing needs the param {pii.get('salt_param', 'pii_salt')}")
        out = hashlib.sha256((str(salt) + out.strip().casefold()).encode("utf-8")).hexdigest()
    return out


# ----------------------------------------------------------------------------- applying a spec


def preamble_value(source: Source, ref: dict):
    if not source.tabular:
        raise SpecError("'preamble' only works for CSV/XLSX inputs")
    idx = ref["preamble"]
    if not (1 <= idx <= len(source.records)):
        raise Reject(f"preamble record {idx} does not exist")
    line = " ".join(c for c in source.records[idx - 1] if c)
    if "regex" not in ref:
        return line
    m = re.search(ref["regex"], line)
    if not m:
        raise Reject(f"preamble record {idx} {line!r} does not match {ref['regex']}")
    return m.group(ref.get("group", 1))


def footer_value(source: Source, ref: dict):
    """Record counted from the end, ignoring blank records: 1 = the last one."""
    if not source.tabular:
        raise SpecError("'footer' only works for CSV/XLSX inputs; for trees use 'root'")
    filled = [r for r in source.records if any(c.strip() for c in r)]
    idx = ref["footer"]
    if not (1 <= idx <= len(filled)):
        raise Reject(f"footer record {idx} does not exist")
    line = " ".join(c for c in filled[-idx] if c)
    if "regex" not in ref:
        return line
    m = re.search(ref["regex"], line)
    if not m:
        raise Reject(f"footer record {idx} {line!r} does not match {ref['regex']}")
    return m.group(ref.get("group", 1))


def root_value(source: Source, ref: dict):
    if source.tabular:
        raise SpecError("'root' only works for JSON/JSONL/XML inputs")
    return Rec("$", source.tree).get(ref["root"])


def ref_value(ref: dict, source: Source, params: dict):
    """A value that is the same for every row: param, const, input lineage, preamble, footer, root."""
    if "param" in ref:
        return params[ref["param"]]
    if "const" in ref:
        return ref["const"]
    if "input" in ref:
        return {"name": Path(source.path).name, "sha256": source.sha256}[ref["input"]]
    if "preamble" in ref:
        return preamble_value(source, ref)
    if "footer" in ref:
        return footer_value(source, ref)
    if "root" in ref:
        return root_value(source, ref)
    raise SpecError(f"unknown value reference {ref!r}")


def raw_value(col: dict, rec: Rec, source: Source, params: dict):
    f = col["from"]
    if isinstance(f, str):
        return rec.get(f)
    if f.get("source_row"):
        return rec.row
    if "path" in f:
        return rec.get(f["path"])
    try:
        return ref_value(f, source, params)
    except SpecError as e:
        raise SpecError(f"column {col['name']}: {e}")


def field_refs(table: dict):
    out = []
    for c in table["columns"]:
        f = c["from"]
        if isinstance(f, str):
            out.append(f)
        elif isinstance(f, dict) and "path" in f:
            out.append(f["path"])
    for flt in table.get("filters", []):
        if "field" in flt:
            out.append(flt["field"])
    return out


def table_records(table: dict, source: Source, src: dict):
    """Returns (records, header, dropped Counter). Tabular sources honour header_row,
    skip blank records and refuse ragged ones; tree sources expand rows_from."""
    dropped = Counter()
    header = None
    if source.tabular:
        hrow = src.get("header_row", 1)
        if not (1 <= hrow <= len(source.records)):
            raise SpecError(f"header_row {hrow} is outside the file ({len(source.records)} records)")
        header = [h.strip() for h in source.records[hrow - 1]]
        recs, ragged = [], []
        for i, r in enumerate(source.records[hrow:], hrow + 1):
            if not any(c.strip() for c in r):
                dropped["blank record"] += 1
                continue
            data = {}
            for j, (h, v) in enumerate(zip(header, r), 1):
                data[f"#{j}"] = v
                data.setdefault(h, v)
            if len(r) != len(header):
                data["__ragged__"] = len(r)  # filters still see it, so a short footer can be dropped
                ragged.append(Rec(i, data))
                continue
            recs.append(Rec(i, data))
        recs = recs + ragged
        recs.sort(key=lambda x: x.row)
    else:
        recs = tree_rows(source.tree, table.get("rows_from", src.get("rows_from", "")))
    unp = table.get("unpivot")
    if unp:
        if not source.tabular:
            raise SpecError("unpivot works on CSV/XLSX inputs; for trees use rows_from")
        cols = unp.get("columns") or [h for h in header if re.fullmatch(unp["match"], h)]
        if not cols:
            raise SpecError("unpivot selects no columns")
        out = []
        for r in recs:
            if "__ragged__" in r.data:
                out.append(r)
                continue
            for c in cols:
                nr = Rec(f"{r.row}:{c}", r.data, r.parent, r.index)
                nr.extra = {unp.get("name_to", "name"): c, unp.get("value_to", "value"): r.data.get(c)}
                out.append(nr)
        recs = out
    return recs, header, dropped


def filter_reason(table: dict, rec: Rec, tokens):
    for flt in table.get("filters", []):
        v = rec.get(flt["field"]) if "field" in flt else None
        s = "" if v is None else str(v).strip()
        if "matches" in flt and re.search(flt["matches"], s):
            return flt.get("reason", f"{flt['field']} matches {flt['matches']}")
        if "equals" in flt and s == str(flt["equals"]):
            return flt.get("reason", f"{flt['field']} = {flt['equals']}")
        if flt.get("is_null") and s.casefold() in tokens:
            return flt.get("reason", f"{flt['field']} is empty")
    return None


def run_table(table: dict, source: Source, spec: dict, params: dict):
    src = spec.get("source", {})
    tokens = [t.casefold() for t in src.get("null_tokens", DEFAULT_NULL_TOKENS)]
    recs, header, dropped = table_records(table, source, src)
    if header is not None:
        missing = [f for f in field_refs(table)
                   if not f.startswith("#") and f not in header
                   and f not in (table.get("unpivot") or {}).values()]
        if missing:
            raise SpecError(f"table {table['name']}: source columns not in the file header: {missing}")
    key = table.get("key") or []
    cols = []
    for c in table["columns"]:
        c = dict(c)
        c["_key"] = c["name"] in key
        cols.append(c)
    rows, rejects = [], []
    for rec in recs:
        why = filter_reason(table, rec, tokens)
        if why:
            dropped[why] += 1
            continue
        if "__ragged__" in rec.data:
            rejects.append((rec.row, "", "", f"record has {rec.data['__ragged__']} fields, header has {len(header)}"))
            continue
        out, bad = OrderedDict(), None
        for c in cols:
            raw = None
            try:
                raw = raw_value(c, rec, source, params)
                out[c["name"]] = convert(c, raw, src, params)
            except Reject as e:
                bad = (rec.row, c["name"], "" if raw is None else str(raw), str(e))
                break
        if bad:
            rejects.append(bad)
        else:
            rows.append((rec.row, out))
    n_in = len(recs)
    deduped = 0
    mode = table.get("dedupe", "none")
    if mode == "exact":
        seen, kept = set(), []
        for r in rows:
            sig = tuple(r[1].values())
            if sig in seen:
                deduped += 1
            else:
                seen.add(sig)
                kept.append(r)
        rows = kept
    elif mode in ("key_first", "key_last", "key_consistent"):
        groups = OrderedDict()
        for r in rows:
            groups.setdefault(tuple(r[1][k] for k in key), []).append(r)
        kept = []
        for k, grp in groups.items():
            if mode == "key_first":
                kept.append(grp[0])
            elif mode == "key_last":
                kept.append(grp[-1])
            else:
                if len({tuple(r[1].values()) for r in grp}) == 1:
                    kept.append(grp[0])
                else:
                    for r in grp:
                        rejects.append((r[0], ",".join(key), "|".join(map(str, k)), "rows with this key disagree"))
                    continue
            deduped += len(grp) - 1
        kept.sort(key=lambda r: _row_order(r[0]))
        rows = kept
    rejects.sort(key=lambda r: _row_order(r[0]))
    return {"rows": rows, "rejects": rejects, "dropped": dropped, "deduped": deduped, "records_in": n_in,
            "header": header}


def _row_order(row):
    if isinstance(row, int):
        return (row, "")
    m = re.match(r"(\d+)(.*)", str(row))
    return (int(m.group(1)), m.group(2)) if m else (0, str(row))


def control_total(spec: dict, t: dict, res: dict, ct: dict, source, params) -> dict:
    """Compare the rows written with a total the export states itself (footer sum, record count,
    opening/closing balance). Values are parsed with the summed column's locale."""
    rows = [r[1] for r in res["rows"]]
    col = next((c for c in t["columns"] if c["name"] == ct.get("sum")), {"name": "count"})
    dec, thou = number_locale(col, spec.get("source", {})) if "sum" in ct else (".", "")

    def num(ref):
        v = ref_value(ref, source, params)
        return parse_number(str(v), dec, thou) if not isinstance(v, (int, Decimal)) else Decimal(v)

    label = f"control_total:{ct.get('sum', 'count')}"
    try:
        got = sum((Decimal(r[ct["sum"]]) for r in rows if r[ct["sum"]] is not None), Decimal(0)) \
            if "sum" in ct else Decimal(len(rows))
        if "equals" in ct:
            want, how = num(ct["equals"]), "stated total"
        else:
            start = num(ct["from"])
            want, how, got = num(ct["to"]), f"closing value (opening {start} + sum)", start + got
    except Reject as e:
        return {"table": t["name"], "check": label, "ok": False, "detail": f"stated total not readable: {e}"}
    tol = Decimal(str(ct.get("tolerance", 0)))
    return {"table": t["name"], "check": label, "ok": abs(got - want) <= tol,
            "detail": f"{got} vs {how} {want}" + (f" (tolerance {tol})" if tol else "")}


def run_checks(spec: dict, results: dict, source=None, params=None) -> list:
    checks = []
    tables = {t["name"]: t for t in spec["tables"]}
    for name, t in tables.items():
        res = results[name]
        rows = [r[1] for r in res["rows"]]
        key = t.get("key") or []
        accounted = len(res["rows"]) + len(res["rejects"]) + sum(res["dropped"].values()) + res["deduped"]
        blank = res["dropped"].get("blank record", 0)
        checks.append({"table": name, "check": "reconcile", "ok": accounted == res["records_in"] + blank,
                       "detail": f"{res['records_in'] + blank} in = {len(res['rows'])} written + {len(res['rejects'])} rejected"
                                 f" + {sum(res['dropped'].values())} dropped + {res['deduped']} deduplicated"})
        max_rej = t.get("max_rejects", 0)
        checks.append({"table": name, "check": "rejects", "ok": len(res["rejects"]) <= max_rej,
                       "detail": f"{len(res['rejects'])} rejected (allowed {max_rej})"})
        min_rows = t.get("min_rows", 1)
        checks.append({"table": name, "check": "min_rows", "ok": len(rows) >= min_rows,
                       "detail": f"{len(rows)} rows (minimum {min_rows})"})
        if key:
            counts = Counter(tuple(r[k] for k in key) for r in rows)
            dups = [k for k, n in counts.items() if n > 1]
            checks.append({"table": name, "check": "unique_key", "ok": not dups,
                           "detail": f"key ({', '.join(key)}) unique" if not dups else
                           f"{len(dups)} duplicate keys, e.g. {['|'.join(map(str, d)) for d in dups[:3]]}; set 'dedupe'"})
        for c in t["columns"]:
            if c.get("references"):
                rt, _, rc = c["references"].partition(".")
                parent = {r[1][rc] for r in results[rt]["rows"]}
                orphans = sorted({r[c["name"]] for r in rows if r[c["name"]] is not None and r[c["name"]] not in parent})
                checks.append({"table": name, "check": f"references:{c['name']}", "ok": not orphans,
                               "detail": f"{c['name']} -> {c['references']}" + (f": {len(orphans)} orphans, e.g. {orphans[:3]}" if orphans else "")})
        for ct in t.get("control_totals", []):
            checks.append(control_total(spec, t, res, ct, source, params or {}))
    return checks


def output_columns(table: dict):
    return [c["name"] for c in table["columns"] if (c.get("pii") or {}).get("action") != "drop"]


def render_csv(header, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue().encode("utf-8")


def execute(spec_path: str, input_path: str, params_in: dict):
    spec = load_spec(spec_path)
    params = resolve_params(spec, params_in)
    source = Source(input_path, spec.get("source", {}))
    results = OrderedDict((t["name"], run_table(t, source, spec, params)) for t in spec["tables"])
    checks = run_checks(spec, results, source, params)
    return spec, params, source, results, checks


def build_manifest(spec_path, spec, params, source, results, checks, outputs):
    declared = spec.get("params", {})
    shown = {k: ("<secret>" if declared.get(k, {}).get("secret") else v) for k, v in params.items()}
    tables = OrderedDict()
    for t in spec["tables"]:
        res = results[t["name"]]
        cols = output_columns(t)
        nulls = OrderedDict((c, sum(1 for _, r in res["rows"] if r[c] is None)) for c in cols)
        tables[t["name"]] = OrderedDict([
            ("rows", len(res["rows"])), ("records_in", res["records_in"]), ("rejected", len(res["rejects"])),
            ("dropped", OrderedDict(sorted(res["dropped"].items()))), ("deduplicated", res["deduped"]),
            ("null_counts", nulls), ("outputs", outputs.get(t["name"], {})),
        ])
    return OrderedDict([
        ("engine", f"data-max {VERSION}"),
        ("spec", OrderedDict([("name", spec["name"]), ("version", spec.get("version", "")),
                              ("sha256", sha256_bytes(Path(spec_path).read_bytes()))])),
        ("input", OrderedDict([("name", Path(source.path).name), ("sha256", source.sha256), ("bytes", len(source.data))])),
        ("params", OrderedDict(sorted(shown.items()))),
        ("status", "passed" if all(c["ok"] for c in checks) else "failed"),
        ("tables", tables),
        ("checks", checks),
    ])


def duckdb_type(c: dict) -> str:
    return {"string": "VARCHAR", "integer": "BIGINT", "boolean": "BOOLEAN", "date": "DATE",
            "timestamp": "TIMESTAMPTZ", "datetime": "TIMESTAMP"}.get(c["type"]) or \
        f"DECIMAL({min(c.get('precision', 38), 38)},{c['scale']})"


def duckdb_available() -> bool:
    try:
        import duckdb  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return bool(shutil.which("duckdb"))


def write_parquet(csv_path: Path, pq_path: Path, table: dict):
    cols = [c for c in table["columns"] if (c.get("pii") or {}).get("action") != "drop"]
    sel = ", ".join(f"CAST({c['name']} AS {duckdb_type(c) if (c.get('pii') or {}).get('action') != 'hash' else 'VARCHAR'}) AS {c['name']}" for c in cols)
    types = ", ".join(f"'{c['name']}': 'VARCHAR'" for c in cols)
    lit = lambda p: "'" + str(p).replace("'", "''") + "'"
    sql = (f"SET TimeZone='UTC'; COPY (SELECT {sel} FROM read_csv({lit(csv_path)}, header=true, delim=',', quote='\"', "
           f"escape='\"', columns={{{types}}})) TO {lit(pq_path)} (FORMAT parquet)")
    try:
        import duckdb  # type: ignore
        duckdb.connect().execute(sql)
        return
    except ImportError:
        pass
    exe = shutil.which("duckdb")
    if not exe:
        raise SpecError("--parquet needs DuckDB: `pip install duckdb` or `brew install duckdb`")
    p = subprocess.run([exe, "-c", sql], capture_output=True, text=True)
    if p.returncode != 0:
        raise SpecError(f"duckdb failed writing {pq_path}: {p.stderr.strip()}")


def write_rejects(path: Path, rejects):
    path.write_bytes(render_csv(["source_row", "column", "value", "reason"], rejects))


def summarize(spec, results, checks, out=None):
    out = out or sys.stdout
    for t in spec["tables"]:
        res = results[t["name"]]
        drops = ", ".join(f"{n} {why}" for why, n in sorted(res["dropped"].items()))
        print(f"{t['name']}: {len(res['rows'])} rows ({res['records_in']} records in; "
              f"{len(res['rejects'])} rejected, {res['deduped']} deduplicated"
              + (f"; dropped before parsing: {drops}" if drops else "") + ")", file=out)
        if res["rejects"]:
            by = Counter((r[1], re.sub(r"'[^']*'", "'…'", r[3])) for r in res["rejects"])
            for (col, why), n in by.most_common(8):
                rows = [str(r[0]) for r in res["rejects"] if r[1] == col and re.sub(r"'[^']*'", "'…'", r[3]) == why][:4]
                ex = next(r for r in res["rejects"] if r[1] == col and re.sub(r"'[^']*'", "'…'", r[3]) == why)
                print(f"  reject x{n} [{col or 'row'}] {ex[3]}  (rows {', '.join(rows)})", file=out)
    failed = [c for c in checks if not c["ok"]]
    print(f"checks: {len(checks) - len(failed)}/{len(checks)} passed", file=out)
    for c in failed:
        print(f"  FAILED {c['table']}.{c['check']}: {c['detail']}", file=out)


def cmd_apply(a):
    if a.parquet and not duckdb_available():
        raise SpecError("--parquet needs DuckDB (`pip install duckdb` or `brew install duckdb`); "
                        "nothing was written. Rerun without --parquet for CSV only.")
    spec, params, source, results, checks = execute(a.spec, a.input, parse_params(a.param))
    out_dir = Path(a.out_dir or ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    summarize(spec, results, checks)
    ok = all(c["ok"] for c in checks)
    outputs = {}
    staged = []
    any_rejects = any(results[t["name"]]["rejects"] for t in spec["tables"])
    rej_path = out_dir / f"{spec['name']}.rejects.csv"
    if any_rejects:
        allrej = [(t["name"],) + r for t in spec["tables"] for r in results[t["name"]]["rejects"]]
        rej_path.write_bytes(render_csv(["table", "source_row", "column", "value", "reason"], allrej))
        print(f"rejects -> {rej_path}")
    elif rej_path.exists():
        rej_path.unlink()
    if not ok:
        print("nothing written: fix the spec (never the data) and run again", file=sys.stderr)
        return 1
    try:  # every file is staged first, then swapped in together: no half-written outputs
        for t in spec["tables"]:
            cols = output_columns(t)
            body = render_csv(cols, [[r[c] for c in cols] for _, r in results[t["name"]]["rows"]])
            fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=f".{t['name']}.", suffix=".csv")
            with os.fdopen(fd, "wb") as fh:
                fh.write(body)
            staged.append((tmp, out_dir / f"{t['name']}.csv"))
            outputs[t["name"]] = OrderedDict([("csv", f"{t['name']}.csv"), ("csv_sha256", sha256_bytes(body))])
            if a.parquet:
                fd, tmpq = tempfile.mkstemp(dir=out_dir, prefix=f".{t['name']}.", suffix=".parquet")
                os.close(fd)
                staged.append((tmpq, out_dir / f"{t['name']}.parquet"))
                write_parquet(Path(tmp), Path(tmpq), t)
                outputs[t["name"]]["parquet"] = f"{t['name']}.parquet"
    except BaseException:
        for tmp, _ in staged:
            Path(tmp).unlink(missing_ok=True)
        raise
    manifest = build_manifest(a.spec, spec, params, source, results, checks, outputs)
    body = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    for tmp, final in staged:
        os.replace(tmp, final)
    mpath = out_dir / f"{spec['name']}.manifest.json"
    mpath.write_bytes(body)
    hist = out_dir / "manifests" / f"{spec['name']}.{source.sha256[:12]}.manifest.json"
    hist.parent.mkdir(exist_ok=True)
    hist.write_bytes(body)
    for t in spec["tables"]:
        print(f"wrote {out_dir / (t['name'] + '.csv')}" + (" (+ .parquet)" if a.parquet else ""))
    print(f"manifest -> {mpath} (history: {hist})")
    return 0


def cmd_check(a):
    spec = load_spec(a.spec)
    src = spec.get("source", {})
    source = Source(a.input, src)
    drift = []
    if source.tabular:
        hrow = src.get("header_row", 1)
        header = [h.strip() for h in source.records[hrow - 1]] if len(source.records) >= hrow else []
        used = set()
        for t in spec["tables"]:
            used.update(field_refs(t))
            if t.get("unpivot"):
                used.update(t["unpivot"].get("columns") or [h for h in header if re.fullmatch(t["unpivot"]["match"], h)])
        new = [h for h in header if h and h not in used]
        missing = [f for f in used if not f.startswith("#") and f not in header
                   and not any(f in (t.get("unpivot") or {}).values() for t in spec["tables"])]
        if missing:
            print(f"DRIFT columns the spec reads are gone from the header: {sorted(missing)}")
            print("verdict: needs a decision (exit 3): the export layout changed; map the columns in the spec")
            return 3
        if new:
            drift.append(f"new source columns the spec ignores: {new}")
    spec, params, source, results, checks = execute(a.spec, a.input, parse_params(a.param))
    summarize(spec, results, checks)
    tol = spec.get("drift", {})
    row_tol = a.row_tolerance if a.row_tolerance is not None else tol.get("rows", 0.3)
    null_tol = a.null_tolerance if a.null_tolerance is not None else tol.get("nulls", 0.1)
    if a.baseline:
        base = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
        if base.get("spec", {}).get("name") != spec["name"]:
            raise SpecError(f"baseline {a.baseline} is a manifest of {base.get('spec', {}).get('name')!r}, not {spec['name']!r}")
        for t in spec["tables"]:
            b = base.get("tables", {}).get(t["name"])
            if not b:
                continue
            n, bn = len(results[t["name"]]["rows"]), b["rows"]
            if bn and abs(n - bn) / bn > row_tol:
                drift.append(f"{t['name']}: {n} rows vs {bn} in the baseline ({(n - bn) / bn:+.0%}; tolerance ±{row_tol:.0%})")
            for c in output_columns(t):
                if c not in b.get("null_counts", {}) or not n or not bn:
                    continue
                rate, brate = sum(1 for _, r in results[t["name"]]["rows"] if r[c] is None) / n, b["null_counts"][c] / bn
                if abs(rate - brate) > null_tol:
                    drift.append(f"{t['name']}.{c}: {rate:.0%} NULL vs {brate:.0%} in the baseline (tolerance ±{null_tol:.0%})")
    for w in drift:
        print(f"DRIFT {w}")
    if not all(c["ok"] for c in checks):
        print("verdict: don't load (exit 1): checks failed")
        return 1
    if drift and not a.allow_drift:
        print("verdict: needs a decision (exit 3): drift against the spec or baseline; "
              "load anyway only after someone accepts it (--allow-drift)")
        return 3
    print("verdict: loadable" + (" (drift accepted with --allow-drift)" if drift else ""))
    return 0


def parse_params(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SpecError(f"--param expects key=value, got {it!r}")
        k, v = it.split("=", 1)
        out[k] = v
    return out


# ----------------------------------------------------------------------------- SQL


def sql_type(c: dict, dialect: str) -> str:
    t = c["type"]
    if (c.get("pii") or {}).get("action") == "hash":
        t = "string"
    p, s = c.get("precision", 38), c.get("scale", 0)
    if dialect == "bigquery":
        if t == "decimal":
            return f"NUMERIC({p},{s})" if p - s <= 29 and s <= 9 else f"BIGNUMERIC({min(p, 76)},{s})"
        return {"string": "STRING", "integer": "INT64", "boolean": "BOOL", "date": "DATE",
                "timestamp": "TIMESTAMP", "datetime": "DATETIME"}[t]
    if dialect == "snowflake":
        return {"string": "VARCHAR", "integer": "NUMBER(38,0)", "decimal": f"NUMBER({min(p, 38)},{s})",
                "boolean": "BOOLEAN", "date": "DATE", "timestamp": "TIMESTAMP_TZ", "datetime": "TIMESTAMP_NTZ"}[t]
    if dialect == "postgres":
        return {"string": "TEXT", "integer": "BIGINT", "decimal": f"NUMERIC({p},{s})", "boolean": "BOOLEAN",
                "date": "DATE", "timestamp": "TIMESTAMPTZ", "datetime": "TIMESTAMP"}[t]
    if dialect == "clickhouse":
        base = {"string": "String", "integer": "Int64", "decimal": f"Decimal({min(p, 76)},{s})", "boolean": "Bool",
                "date": "Date32", "timestamp": "DateTime64(6, 'UTC')", "datetime": "DateTime64(6)"}[t]
        return base if c.get("required") or c.get("_key") else f"Nullable({base})"
    if dialect == "duckdb":
        return duckdb_type(dict(c, type=t))
    raise SpecError(f"unknown dialect {dialect}")


def qualified(name, schema):
    return f"{schema}.{name}" if schema else name


def sql_ddl(t: dict, dialect: str, schema: str) -> str:
    key = t.get("key") or []
    cols = [c for c in t["columns"] if (c.get("pii") or {}).get("action") != "drop"]
    lines = []
    for c in cols:
        c = dict(c, _key=c["name"] in key)
        nn = " NOT NULL" if (c.get("required") or c["_key"]) and dialect != "clickhouse" else ""
        lines.append(f"  {c['name']} {sql_type(c, dialect)}{nn}")
    name = qualified(t["name"], schema)
    if dialect == "clickhouse":
        load = t.get("load", {})
        engine = "MergeTree"
        if load.get("mode") == "merge":
            engine = f"ReplacingMergeTree({load['newer_by']})" if load.get("newer_by") else "ReplacingMergeTree"
        order = ", ".join(key) or "tuple()"
        return f"CREATE TABLE IF NOT EXISTS {name} (\n" + ",\n".join(lines) + f"\n) ENGINE = {engine}\nORDER BY ({order});"
    if key:
        pk = f"  PRIMARY KEY ({', '.join(key)})" + (" NOT ENFORCED" if dialect == "bigquery" else "")
        lines.append(pk)
    return f"CREATE TABLE IF NOT EXISTS {name} (\n" + ",\n".join(lines) + "\n);"


def staging_ddl(t: dict, dialect: str, schema: str) -> str:
    """A fresh, empty staging table on every load: rows from an earlier load can never leak in."""
    st = dict(t, name=t["name"] + "__staging", key=[], load={})
    ddl = sql_ddl(st, dialect, schema)
    name = qualified(st["name"], schema)
    if dialect in ("bigquery", "snowflake", "duckdb"):
        return ddl.replace("CREATE TABLE IF NOT EXISTS", "CREATE OR REPLACE TABLE")
    ddl = ddl.replace("CREATE TABLE IF NOT EXISTS", "CREATE TABLE")
    if dialect == "clickhouse":
        ddl = ddl.split(") ENGINE")[0] + ") ENGINE = MergeTree\nORDER BY tuple();"
    return f"DROP TABLE IF EXISTS {name};\n{ddl}"


def sql_load(t: dict, dialect: str, schema: str, out_dir: str, into: str, replace=False) -> str:
    """Shell or SQL that copies the clean file into table `into` (target or staging)."""
    name = qualified(into, schema)
    csvp = f"{out_dir.rstrip('/')}/{t['name']}.csv"
    pq = f"{out_dir.rstrip('/')}/{t['name']}.parquet"
    if dialect == "bigquery":
        r = "--replace " if replace else ""
        return (f"# shell: Parquet keeps the types (apply ... --parquet); or the CSV line below\n"
                f"bq load {r}--source_format=PARQUET {name} {pq}\n"
                f"# bq load {r}--source_format=CSV --skip_leading_rows=1 --allow_quoted_newlines {name} {csvp}")
    if dialect == "snowflake":
        return (f"PUT file://{csvp} @%{into} OVERWRITE = TRUE;\n"
                f"COPY INTO {name} FROM @%{into}\n"
                f"  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '\"' "
                f"EMPTY_FIELD_AS_NULL = TRUE)\n  ON_ERROR = ABORT_STATEMENT PURGE = TRUE;")
    if dialect == "postgres":
        return f"\\copy {name} FROM '{csvp}' WITH (FORMAT csv, HEADER true)"
    if dialect == "clickhouse":
        return f"# shell:\nclickhouse-client --query \"INSERT INTO {name} FORMAT CSVWithNames\" < {csvp}"
    if dialect == "duckdb":
        return f"COPY {name} FROM '{pq}' (FORMAT parquet);  -- or FROM '{csvp}' (HEADER)"
    raise SpecError(f"unknown dialect {dialect}")


def in_transaction(dialect: str, stmts: list) -> str:
    if dialect == "clickhouse":  # no multi-statement transactions; each statement is atomic
        return "\n".join(stmts)
    begin, commit = ("BEGIN TRANSACTION;", "COMMIT TRANSACTION;") if dialect == "bigquery" else ("BEGIN;", "COMMIT;")
    return "\n".join([begin] + stmts + [commit])


def sql_apply_staging(t: dict, dialect: str, schema: str) -> str:
    """Staging -> target for replace_by and merge, inside one transaction."""
    load = t.get("load", {})
    cols = output_columns(t)
    target, stg = qualified(t["name"], schema), qualified(t["name"] + "__staging", schema)
    ins = ", ".join(cols)
    if load.get("mode") == "replace_by":
        by, nb = load["by"], load.get("newer_by")
        match = " AND ".join(f"s.{b} = t.{b}" for b in by)
        if dialect == "clickhouse":
            cond = f"({', '.join(by)}) IN (SELECT DISTINCT {', '.join(by)} FROM {stg})"
            if nb:
                cond = (f"({', '.join(by)}, {nb}) IN (SELECT t.{', t.'.join(by)}, t.{nb} FROM {target} AS t "
                        f"JOIN {stg} AS s ON {match} WHERE s.{nb} >= t.{nb})")
            delete = f"DELETE FROM {target} WHERE {cond};"
        else:
            newer = f" AND s.{nb} >= t.{nb}" if nb else ""
            delete = f"DELETE FROM {target} AS t WHERE EXISTS (SELECT 1 FROM {stg} AS s WHERE {match}{newer});"
        insert = f"INSERT INTO {target} ({ins}) SELECT {ins} FROM {stg} AS s"
        if nb:  # a slice that already holds newer rows keeps them: an old export can't bring back old lines
            insert += f"\nWHERE NOT EXISTS (SELECT 1 FROM {target} AS t WHERE {match} AND t.{nb} > s.{nb})"
        note = f"-- replace every ({', '.join(by)}) slice present in this load" + (f", unless the warehouse holds a newer {nb}" if nb else "")
        return in_transaction(dialect, [note, delete, insert + ";"])
    key, nb = t["key"], load.get("newer_by")
    if dialect == "clickhouse":
        return (f"-- ReplacingMergeTree keeps the {'row with the highest ' + nb if nb else 'last inserted row'} per key; "
                f"read with FINAL\nINSERT INTO {target} ({ins}) SELECT {ins} FROM {stg};")
    upd = [c for c in cols if c not in key]
    if dialect in ("postgres", "duckdb"):
        guard = f"\n  WHERE EXCLUDED.{nb} >= t.{nb}" if nb else ""
        action = ("DO UPDATE SET " + ", ".join(f"{c} = EXCLUDED.{c}" for c in upd) + guard) if upd else "DO NOTHING"
        return in_transaction(dialect, [f"INSERT INTO {target} AS t ({ins})\nSELECT {ins} FROM {stg}\n"
                                        f"ON CONFLICT ({', '.join(key)}) {action};"])
    on = " AND ".join(f"t.{k} = s.{k}" for k in key)
    when = f"WHEN MATCHED AND s.{nb} >= t.{nb} THEN" if nb else "WHEN MATCHED THEN"
    upd_sql = f"{when} UPDATE SET " + ", ".join(f"{c} = s.{c}" for c in upd) + "\n" if upd else ""
    return in_transaction(dialect, [f"MERGE INTO {target} AS t\nUSING {stg} AS s\nON {on}\n{upd_sql}"
                                    f"WHEN NOT MATCHED THEN INSERT ({ins}) VALUES ({', '.join('s.' + c for c in cols)});"])


def sql_load_block(t: dict, dialect: str, schema: str, out_dir: str) -> str:
    mode = t.get("load", {}).get("mode", "append")
    target = qualified(t["name"], schema)
    if mode == "append":
        return ("-- append: every run adds rows; rerunning the same file duplicates them\n"
                + sql_load(t, dialect, schema, out_dir, t["name"]))
    if mode == "replace":
        if dialect == "bigquery":
            return "-- replace: the load swaps the whole table\n" + sql_load(t, dialect, schema, out_dir, t["name"], replace=True)
        if dialect == "clickhouse":
            return f"TRUNCATE TABLE {target};\n" + sql_load(t, dialect, schema, out_dir, t["name"])
        load = sql_load(t, dialect, schema, out_dir, t["name"])
        if dialect == "snowflake":  # PUT is a client command; keep it outside the transaction
            put, copy = load.split("\n", 1)
            return put + "\n" + in_transaction(dialect, [f"DELETE FROM {target};", copy])
        return in_transaction(dialect, [f"DELETE FROM {target};", load])
    if dialect == "clickhouse" and mode == "merge":
        return sql_load(t, dialect, schema, out_dir, t["name"]) + \
            "\n-- ReplacingMergeTree deduplicates on the key in the background; read with FINAL"
    return "\n".join([f"-- 1. fresh staging table", staging_ddl(t, dialect, schema),
                      "-- 2. load the clean file into staging",
                      sql_load(t, dialect, schema, out_dir, t["name"] + "__staging", replace=True),
                      f"-- 3. {mode}: staging -> {t['name']}" + ("" if dialect == "clickhouse" else " in one transaction"),
                      sql_apply_staging(t, dialect, schema)])


def sql_checks(spec: dict, t: dict, schema: str) -> str:
    name = qualified(t["name"], schema)
    key = t.get("key") or []
    qs = []
    if key:
        k = ", ".join(key)
        qs.append(f"SELECT '{t['name']}.unique_key' AS check_name, COUNT(*) AS failures FROM "
                  f"(SELECT {k} FROM {name} GROUP BY {k} HAVING COUNT(*) > 1) d")
    for c in t["columns"]:
        if (c.get("pii") or {}).get("action") == "drop":
            continue
        if c.get("required") or c["name"] in key:
            qs.append(f"SELECT '{t['name']}.{c['name']}.not_null', COUNT(*) FROM {name} WHERE {c['name']} IS NULL")
        if c.get("allowed"):
            quote = c["type"] in ("string", "date", "timestamp", "datetime")
            vals = ", ".join(("'" + str(v).replace("'", "''") + "'") if quote else str(v) for v in c["allowed"])
            qs.append(f"SELECT '{t['name']}.{c['name']}.accepted_values', COUNT(*) FROM {name} "
                      f"WHERE {c['name']} IS NOT NULL AND {c['name']} NOT IN ({vals})")
        if c.get("references"):
            rt, _, rc = c["references"].partition(".")
            qs.append(f"SELECT '{t['name']}.{c['name']}.references', COUNT(*) FROM {name} x "
                      f"LEFT JOIN {qualified(rt, schema)} p ON x.{c['name']} = p.{rc} "
                      f"WHERE x.{c['name']} IS NOT NULL AND p.{rc} IS NULL")
    return "\nUNION ALL\n".join(qs) + ";"


def dbt_sources(spec: dict, schema: str) -> str:
    lines = ["# Generated by data-max from the cleaning spec. Needs dbt >= 1.10.5 (test 'arguments').",
             "version: 2", "", "sources:", f"  - name: {spec['name']}"]
    if schema:
        lines.append(f"    schema: {schema}")
    lines.append("    tables:")
    for t in spec["tables"]:
        key = t.get("key") or []
        lines.append(f"      - name: {t['name']}")
        if t.get("grain"):
            lines.append(f"        description: {json.dumps('Grain: ' + t['grain'], ensure_ascii=False)}")
        m = t.get("monitor")
        if m:
            h = m.get("max_age_hours", 26)
            lines += ["        config:", f"          loaded_at_field: {m['time']}", "          freshness:",
                      f"            warn_after: {{count: {h}, period: hour}}",
                      f"            error_after: {{count: {h * 2}, period: hour}}"]
        if len(key) > 1:
            lines += ["        data_tests:", "          - dbt_utils.unique_combination_of_columns:",
                      "              arguments:", f"                combination_of_columns: [{', '.join(key)}]"]
        lines.append("        columns:")
        for c in t["columns"]:
            if (c.get("pii") or {}).get("action") == "drop":
                continue
            lines.append(f"          - name: {c['name']}")
            if c.get("description"):
                lines.append(f"            description: {json.dumps(c['description'], ensure_ascii=False)}")
            tests = []
            if c.get("required") or c["name"] in key:
                tests.append("              - not_null")
            if key == [c["name"]]:
                tests.append("              - unique")
            if c.get("allowed"):
                vals = ", ".join(json.dumps(str(v), ensure_ascii=False) for v in c["allowed"])
                tests += ["              - accepted_values:", "                  arguments:", f"                    values: [{vals}]"]
            if c.get("references"):
                rt, _, rc = c["references"].partition(".")
                tests += ["              - relationships:", "                  arguments:",
                          f"                    to: source('{spec['name']}', '{rt}')", f"                    field: {rc}"]
            if tests:
                lines += ["            data_tests:"] + tests
    return "\n".join(lines) + "\n"


def median_sql(dialect: str, x: str) -> str:
    return {"bigquery": f"APPROX_QUANTILES({x}, 2)[OFFSET(1)]",
            "postgres": f"percentile_cont(0.5) WITHIN GROUP (ORDER BY {x})"}.get(dialect, f"MEDIAN({x})")


def days_ago_sql(dialect: str, n: int) -> str:
    return {"bigquery": f"DATE_SUB(CURRENT_DATE(), INTERVAL {n} DAY)",
            "snowflake": f"DATEADD(day, -{n}, CURRENT_DATE())",
            "clickhouse": f"today() - {n}"}.get(dialect, f"CURRENT_DATE - {n}")


def hours_ago_sql(dialect: str, n) -> str:
    return {"bigquery": f"TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {n} HOUR)",
            "snowflake": f"DATEADD(hour, -{n}, CURRENT_TIMESTAMP())",
            "clickhouse": f"now() - INTERVAL {n} HOUR"}.get(dialect, f"CURRENT_TIMESTAMP - INTERVAL '{n} hours'")


def weekday_sql(dialect: str, d: str) -> str:
    return {"bigquery": f"EXTRACT(DAYOFWEEK FROM {d})", "snowflake": f"DAYOFWEEKISO({d})",
            "postgres": f"EXTRACT(ISODOW FROM {d})", "duckdb": f"isodow({d})",
            "clickhouse": f"toDayOfWeek({d})"}[dialect]


def stale_sql(dialect: str, col_type: str, hours) -> str:
    """'n hours ago' in the column's own kind of time: instants vs UTC wall clock vs dates."""
    if col_type == "date":
        return days_ago_sql(dialect, -(-int(hours) // 24))
    if col_type == "datetime":  # naive columns hold UTC wall clock by convention
        return {"bigquery": f"DATETIME_SUB(CURRENT_DATETIME(), INTERVAL {hours} HOUR)",
                "snowflake": f"DATEADD(hour, -{hours}, SYSDATE())",
                "clickhouse": f"toDateTime(now(), 'UTC') - INTERVAL {hours} HOUR"}.get(
            dialect, f"(now() AT TIME ZONE 'UTC') - INTERVAL '{hours} hours'")
    return hours_ago_sql(dialect, hours)


def sql_monitors(t: dict, dialect: str, schema: str) -> str:
    """Freshness and daily volume/sum anomalies: what a single file can't show. Each query
    returns rows only when something is wrong."""
    m = t.get("monitor")
    if not m:
        return f"-- {t['name']}: no 'monitor' in the spec; add {{\"time\": <timestamp column>}} for freshness and volume checks"
    name = qualified(t["name"], schema)
    time, days, recent = m["time"], int(m.get("days", 28)), int(m.get("recent_days", 3))
    ttype = next(c["type"] for c in t["columns"] if c["name"] == time)
    lo, hi = m.get("volume", [0.5, 1.8])  # below 2.0: an exactly doubled load must fire
    by = list(m.get("by", []))
    where = f" AND ({m['where']})" if m.get("where") else ""
    grp = by or ["grp"]
    sel_by = ", ".join(by) if by else "'all' AS grp"
    hours = m.get("max_age_hours", 26)
    out = [f"-- {t['name']}: freshness: newest {time} older than {hours} hours (or no rows)",
           f"SELECT '{t['name']}.freshness' AS check_name, newest FROM (SELECT MAX({time}) AS newest FROM {name}) x\n"
           f"WHERE newest IS NULL OR newest < {stale_sql(dialect, ttype, hours)};"]
    sums = list(m.get("sums", []))
    meas = ["COUNT(*) AS n_rows"] + [f"SUM({c}) AS sum_{c}" for c in sums]
    med = [f"{median_sql(dialect, 'd.n_rows')} AS med_rows"] + [f"{median_sql(dialect, 'd.sum_' + c)} AS med_{c}" for c in sums]
    weekday = m.get("compare", "weekday") == "weekday"
    same_day = f"\n  AND {weekday_sql(dialect, 'd.day')} = {weekday_sql(dialect, 'r.day')}" if weekday else ""
    cal = " UNION ALL ".join(f"SELECT {days_ago_sql(dialect, i)} AS day" for i in range(1, recent + 1))
    conds = [f"COALESCE(y.n_rows, 0) NOT BETWEEN {lo} * b.med_rows AND {hi} * b.med_rows"] + \
            [f"COALESCE(y.sum_{c}, 0) NOT BETWEEN {lo} * b.med_{c} AND {hi} * b.med_{c}" for c in sums]
    gcols = ", ".join(grp)
    out += [f"-- {t['name']}: each of the last {recent} days, rows{' and sums' if sums else ''} per {', '.join(by) or 'table'} outside "
            f"{lo}x-{hi}x of the median {'same weekday' if weekday else 'day'} in the {days} days before (a missing day counts as 0)",
            f"WITH daily AS (\n  SELECT CAST({time} AS DATE) AS day, {sel_by}, {', '.join(meas)}\n  FROM {name}\n"
            f"  WHERE CAST({time} AS DATE) >= {days_ago_sql(dialect, days + recent)}{where}\n"
            f"  GROUP BY 1, {', '.join(str(i + 2) for i in range(len(grp)))}\n),\n"
            f"r AS (SELECT c.day, g.{', g.'.join(grp)} FROM ({cal}) c CROSS JOIN (SELECT DISTINCT {gcols} FROM daily) g),\n"
            f"b AS (\n  SELECT r.day, r.{', r.'.join(grp)}, {', '.join(med)}\n  FROM r JOIN daily d ON "
            + " AND ".join(f"d.{g} = r.{g}" for g in grp) +
            f"\n  WHERE d.day < {days_ago_sql(dialect, recent)}{same_day}\n  GROUP BY r.day, r.{', r.'.join(grp)}\n)\n"
            f"SELECT '{t['name']}.daily_volume' AS check_name, b.day, {', '.join('b.' + g for g in grp)}, y.n_rows, b.med_rows"
            + "".join(f", y.sum_{c}, b.med_{c}" for c in sums) +
            f"\nFROM b LEFT JOIN daily y ON y.day = b.day AND " + " AND ".join(f"y.{g} = b.{g}" for g in grp) +
            "\nWHERE " + "\n   OR ".join(conds) + ";"]
    return "\n".join(out)


def cmd_sql(a):
    spec = load_spec(a.spec)
    what = [w.strip() for w in a.what.split(",")]
    unknown = [w for w in what if w not in ("ddl", "load", "checks", "monitors", "dbt")]
    if unknown:
        raise SpecError(f"--what accepts ddl, load, checks, monitors, dbt; not {unknown}")
    parts = []
    for t in spec["tables"]:
        mode = t.get("load", {}).get("mode", "append")
        if "ddl" in what:
            parts.append(f"-- {t['name']}: grain = {t.get('grain', '?')}; load mode = {mode}")
            parts.append(sql_ddl(t, a.dialect, a.schema))
        if "load" in what:
            parts.append(sql_load_block(t, a.dialect, a.schema, a.out_dir))
        if "checks" in what:
            parts.append(f"-- {t['name']}: every row must show failures = 0")
            parts.append(sql_checks(spec, t, a.schema))
        if "monitors" in what:
            parts.append(sql_monitors(t, a.dialect, a.schema))
    if "dbt" in what:
        parts.append(dbt_sources(spec, a.schema))
    print("\n\n".join(parts))
    return 0


# ----------------------------------------------------------------------------- profiling

MONTHS = {m.casefold() for m in "jan feb mar apr may jun jul aug sep sept oct nov dec january february march april june july august september october november december "
          "jän mär mai okt dez januar februar märz juni juli oktober dezember".split()}
DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y%m%d", "%d.%m.%y",
                "%d %b %Y", "%b %d %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y"]
TS_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d/%m/%Y %H:%M",
              "%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M %p", "%Y-%m-%dT%H:%M:%S"]
PII_HEADER = re.compile(r"(^|_)(name|first_?name|last_?name|full_?name|vorname|nachname|gast|guest|guest_?name|"
                        r"customer_?name|email|e_?mail|mail|phone|tel|telefon|mobile|handy|address|adresse|street|"
                        r"strasse|birth_?date|date_of_birth|geburtsdatum|dob|iban|ip|ip_?address|ssn|tax_?id|passport)($|_)", re.I)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9 ]{10,32}$")
PHONE_RE = re.compile(r"^\+?[\d\s()/.-]{7,20}$")


def snake(name: str, used=None) -> str:
    s = name.strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss"),
                 ("%", " pct "), ("#", " no "), ("€", " eur "), ("$", " usd "), ("£", " gbp ")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower() or "column"
    if s[0].isdigit():
        parts = s.split("_", 1)
        s = (parts[1] + "_" + parts[0]) if len(parts) == 2 else "c_" + s
    if used is not None:
        base, i = s, 2
        while s in used:
            s, i = f"{base}_{i}", i + 1
        used.add(s)
    return s


def try_number(v: str, dec: str, thou: str):
    try:
        return parse_number(v, dec, thou)
    except Reject:
        return None


def profile_column(name: str, values: list, tokens) -> dict:
    n = len(values)
    nonnull = [v.strip() for v in values if v is not None and v.strip().casefold() not in tokens]
    null_found = Counter(("" if v is None else v.strip()) for v in values
                         if v is None or v.strip().casefold() in tokens)
    distinct = Counter(nonnull)
    info = OrderedDict([("name", name), ("suggested_name", snake(name)), ("values", n), ("non_null", len(nonnull)),
                        ("null_tokens", OrderedDict((repr(k), c) for k, c in null_found.most_common())),
                        ("distinct", len(distinct)), ("top", distinct.most_common(5))])
    flags = []
    if not nonnull:
        info.update(type="string", flags=["all values empty"])
        return info
    ws = sum(1 for v in values if v and v != v.strip())
    if ws:
        flags.append(f"{ws} values with leading/trailing whitespace")
    ints = [v for v in nonnull if re.fullmatch(r"[+-]?\d+", v)]
    lead0 = [v for v in ints if re.fullmatch(r"0\d+", v)]
    sci = [v for v in nonnull if re.fullmatch(r"[+-]?\d(\.\d+)?[eE][+-]?\d+", v)]
    if sci:
        flags.append(f"{len(sci)} values in scientific notation (e.g. {sci[0]}); Excel probably destroyed digits")
    num_en = [v for v in nonnull if try_number(v, ".", ",") is not None]
    num_de = [v for v in nonnull if try_number(v, ",", ".") is not None]
    currency = [v for v in nonnull if CURRENCY_RE.search(v)]
    parens = [v for v in nonnull if re.match(r"^\(.*\)", CURRENCY_RE.sub("", v.strip()).strip())]
    date_hits = Counter()
    for f in DATE_FORMATS:
        for v in nonnull[:2000]:
            try:
                datetime.strptime(v, f)
                date_hits[f] += 1
            except ValueError:
                pass
    ts_hits = Counter()
    for f in TS_FORMATS:
        for v in nonnull[:2000]:
            try:
                datetime.strptime(v, f)
                ts_hits[f] += 1
            except ValueError:
                pass
    iso_off = [v for v in nonnull if re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})", v)]
    serials = [v for v in ints if 20000 <= int(v) <= 80000]
    sample_n = min(len(nonnull), 2000)
    typ, extra = "string", OrderedDict()
    if lead0:
        flags.append(f"{len(lead0)} values with leading zeros (e.g. {lead0[0]}); keep as string, never cast to a number")
    if lead0:
        pass  # identifiers such as postal codes: stay a string
    elif len(ints) == len(nonnull):
        typ = "integer"
        if serials and re.search(r"date|datum|day|tag|created|erstellt|time|zeit|_at$|_on$", snake(name)):
            flags.append("integers in the Excel serial range in a date-like column; maybe dates (format excel_serial)")
    elif iso_off and len(iso_off) >= len(nonnull) * 0.6:
        typ, extra["formats"] = "timestamp", ["iso"]
    elif ts_hits and (ts_hits.most_common(1)[0][1] + sum(date_hits.values()) * 0 + len(serials)) >= sample_n * 0.6:
        best = [f for f, _ in ts_hits.most_common()]
        typ, extra["formats"] = "timestamp", best[:2]
    elif date_hits and date_hits.most_common(1)[0][1] + len(serials) >= sample_n * 0.6:
        best = [f for f, c in date_hits.most_common()]
        typ, extra["formats"] = "date", best[:2]
        if "%d/%m/%Y" in date_hits and "%m/%d/%Y" in date_hits:
            dm = date_hits["%d/%m/%Y"]
            md = date_hits["%m/%d/%Y"]
            flags.append(f"day/month order ambiguous: {dm} values parse as DD/MM, {md} as MM/DD; confirm with the source")
    elif len(num_en) == len(nonnull) or len(num_de) == len(nonnull):
        if len(num_de) == len(nonnull) and len(num_en) < len(nonnull):
            dec, thou = ",", "."
        elif len(num_en) == len(nonnull) and len(num_de) < len(nonnull):
            dec, thou = ".", ","
        else:
            dec, thou = ".", ","
            flags.append("decimal separator cannot be told from the values; confirm '.' or ','")
        vals = [try_number(v, dec, thou) for v in nonnull]
        scale = max((-v.as_tuple().exponent for v in vals if v.as_tuple().exponent < 0), default=0)
        typ = "decimal"
        extra["locale"] = {"decimal": dec, "thousands": thou}
        extra["scale"] = max(scale, 2 if currency else scale)
        extra["min"], extra["max"] = str(min(vals)), str(max(vals))
        if currency:
            flags.append(f"{len(currency)} values carry a currency sign/code (e.g. {currency[0]!r}); keep a separate currency column")
        if parens:
            flags.append(f"{len(parens)} accounting negatives in parentheses (e.g. {parens[0]!r})")
    elif len(num_en) >= len(nonnull) * 0.8 or len(num_de) >= len(nonnull) * 0.8:
        bad = [v for v in nonnull if try_number(v, ".", ",") is None and try_number(v, ",", ".") is None]
        flags.append(f"mostly numeric but {len(bad)} values are not numbers, e.g. {bad[:3]}")
    if typ in ("date", "timestamp"):
        fmts = extra["formats"]
        bad = []
        for v in nonnull:
            try:
                parse_datetime_any(v, fmts)
            except Reject:
                bad.append(v)
        ser = [v for v in bad if re.fullmatch(r"\d{5}(\.\d+)?", v)]
        if ser:
            flags.append(f"{len(ser)} Excel serial numbers among the dates (e.g. {ser[0]}); add format excel_serial if they are real")
            extra["formats"] = fmts + ["excel_serial"]
        other = [v for v in bad if v not in ser]
        if other:
            flags.append(f"{len(other)} values match no date format, e.g. {other[:3]}")
        if typ == "timestamp" and extra["formats"][0] != "iso":
            flags.append("timestamps carry no timezone; the source system's IANA timezone must be confirmed")
    if typ == "string" and 1 < len(distinct) <= 50:
        folded = {}
        for v in distinct:
            folded.setdefault(v.casefold(), set()).add(v)
        variants = [sorted(s) for s in folded.values() if len(s) > 1]
        if variants:
            flags.append(f"case variants of the same value: {variants[:4]}")
    pii = None
    if sum(1 for v in nonnull if EMAIL_RE.match(v)) >= len(nonnull) * 0.5:
        pii = "email"
    elif sum(1 for v in nonnull if IBAN_RE.match(v)) >= len(nonnull) * 0.5:
        pii = "iban"
    elif PII_HEADER.search(snake(name)):
        pii = "personal (by column name)"
    elif typ == "string" and sum(1 for v in nonnull if PHONE_RE.match(v) and sum(ch.isdigit() for ch in v) >= 7) >= len(nonnull) * 0.5:
        pii = "phone"
    if pii:
        flags.append(f"PII: {pii}")
        info["pii"] = pii
    info["type"] = typ
    info.update(extra)
    if typ == "string" and len(distinct) <= 12 and len(nonnull) > len(distinct):
        info["candidate_values"] = sorted(distinct)
    info["flags"] = flags
    return info


def detect_header(records) -> int:
    nonblank = [r for r in records if any(c.strip() for c in r)]
    if not nonblank:
        return 1
    width = Counter(len(r) for r in nonblank).most_common(1)[0][0]
    for i, r in enumerate(records, 1):
        if len(r) == width and sum(1 for c in r if c.strip()) >= max(1, int(width * 0.8)):
            if not all(re.fullmatch(r"[\d.,\s-]*", c) for c in r):
                return i
    return 1


def profile_tabular(source: Source, header_row=None) -> dict:
    recs = source.records
    hrow = header_row or detect_header(recs)
    header = [h.strip() for h in recs[hrow - 1]] if recs else []
    width = len(header)
    data_idx = [(i, r) for i, r in enumerate(recs[hrow:], hrow + 1)]
    blank = [i for i, r in data_idx if not any(c.strip() for c in r)]
    ragged = [(i, len(r)) for i, r in data_idx if any(c.strip() for c in r) and len(r) != width]
    good = [(i, r) for i, r in data_idx if any(c.strip() for c in r) and len(r) == width]
    totals = [(i, r) for i, r in good if r and (TOTAL_RE.match(r[0] or "") or
                                                 (width >= 3 and sum(1 for c in r if c.strip()) == 1))]
    good_nt = [(i, r) for i, r in good if (i, r) not in totals]
    dup_counter = Counter(tuple(r) for _, r in good_nt)
    dups = sum(n - 1 for n in dup_counter.values() if n > 1)
    dup_examples = [i for i, r in good_nt if dup_counter[tuple(r)] > 1][:6]
    tokens = [t.casefold() for t in DEFAULT_NULL_TOKENS]
    cols = []
    for j, h in enumerate(header):
        cols.append(profile_column(h, [r[j] for _, r in good_nt], tokens))
    distinct_rows = list(OrderedDict.fromkeys(tuple(r) for _, r in good_nt))
    for j, c in enumerate(cols):
        vals = [r[j].strip() for r in distinct_rows]
        c["unique_non_null"] = bool(vals) and all(v.casefold() not in tokens for v in vals) and len(set(vals)) == len(vals)
    hdr_flags = []
    hc = Counter(header)
    if any(n > 1 for n in hc.values()):
        hdr_flags.append(f"duplicate header names: {[h for h, n in hc.items() if n > 1]} (reference them as #<position>)")
    if any(not h for h in header):
        hdr_flags.append(f"blank header names at positions {[i + 1 for i, h in enumerate(header) if not h]}")
    period = [h for h in header if h.casefold().rstrip(".") in MONTHS or re.fullmatch(r"(19|20)\d\d|(19|20)\d\d[-/](0?[1-9]|1[0-2])|Q[1-4]( ?\d{2,4})?", h, re.I)]
    if len(period) >= 2:
        hdr_flags.append(f"wide format: {len(period)} headers look like periods {period[:6]}; consider unpivot")
    keys = [c["name"] for c in cols if c.get("unique_non_null") and c["type"] != "decimal"]  # measures aren't keys
    if not keys and len(distinct_rows) > 1:  # try pairs of dimension-like columns: day + campaign
        idish = re.compile(r"(^|[^a-z])(id|nr|no|key|code|number|nummer)([^a-z]|$)", re.I)
        dims = [j for j, c in enumerate(cols) if c["distinct"] < len(distinct_rows) and
                (c["type"] in ("string", "date", "timestamp", "datetime") or (c["type"] == "integer" and idish.search(header[j])))]
        for x in range(len(dims)):
            for y in range(x + 1, len(dims)):
                pairs = [(r[dims[x]].strip(), r[dims[y]].strip()) for r in distinct_rows]
                if len(set(pairs)) == len(pairs) and all(v.casefold() not in tokens for pr in pairs for v in pr):
                    keys.append(f"{header[dims[x]]} + {header[dims[y]]}")
        keys = keys[:3]
    for c in cols:
        c.pop("unique_non_null", None)
    return OrderedDict([
        ("format", source.format), ("encoding", source.encoding), ("delimiter", source.delimiter),
        ("bytes", len(source.data)), ("sha256", source.sha256),
        ("line_endings", "CRLF" if b"\r\n" in source.data or b"\r\x00\n\x00" in source.data else "LF"),
        ("records_total", len(recs)), ("header_row", hrow),
        ("preamble", [" | ".join(c for c in r if c) for r in recs[:hrow - 1]]),
        ("data_records", len(good_nt)), ("blank_records", len(blank)), ("ragged_records", ragged[:10]),
        ("total_rows", [(i, " | ".join(c for c in r if c)) for i, r in totals]),
        ("duplicate_rows", dups), ("duplicate_examples", dup_examples),
        ("header_flags", hdr_flags), ("candidate_keys", keys), ("columns", cols),
    ])


def walk_tree(obj, path="", stats=None):
    if stats is None:
        stats = OrderedDict()
    if isinstance(obj, list):
        p = path + "[]"
        st = stats.setdefault(p, Counter())
        st["array_items"] += len(obj)
        for it in obj:
            walk_tree(it, p, stats)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            st = stats.setdefault(p, Counter())
            st[type(v).__name__ if not isinstance(v, Decimal) else "float"] += 1
            walk_tree(v, p, stats)
    return stats


def flat_fields(obj, prefix=""):
    out = OrderedDict()
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        p = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat_fields(v, p + "."))
        elif not isinstance(v, list):
            out[p] = v
    return out


def profile_tree(source: Source, rows_from=None) -> dict:
    stats = walk_tree(source.tree)
    candidates = [p for p, st in stats.items() if p.endswith("[]") and st["array_items"]
                  and any(q.startswith(p + ".") for q in stats)]
    if source.format == "jsonl":
        candidates = [""] + [c[2:] if c.startswith("[]") else c for c in candidates if c != "[]"]
    chosen = [rows_from] if rows_from is not None else candidates
    tables = []
    tokens = [t.casefold() for t in DEFAULT_NULL_TOKENS]
    for rf in chosen:
        recs = tree_rows(source.tree, rf)
        fields = OrderedDict()
        types = OrderedDict()
        for r in recs:
            for k, v in flat_fields(r.data).items():
                fields.setdefault(k, [])
                types.setdefault(k, Counter())[type(v).__name__ if not isinstance(v, Decimal) else "float"] += 1
        for r in recs:
            ff = flat_fields(r.data)
            for k in fields:
                fields[k].append(None if ff.get(k) is None else str(ff.get(k)))
        cols = []
        for k, vals in fields.items():
            c = profile_column(k, vals, tokens)
            if len(types[k]) > 1:
                c["flags"].insert(0, f"mixed JSON types {dict(types[k])}")
            cols.append(c)
        tables.append(OrderedDict([("rows_from", rf), ("rows", len(recs)), ("columns", cols)]))
    return OrderedDict([("format", source.format), ("bytes", len(source.data)), ("sha256", source.sha256),
                        ("structure", OrderedDict((p, dict(st)) for p, st in stats.items())),
                        ("rows_from_candidates", candidates), ("tables", tables)])


def print_columns(cols, out):
    for c in cols:
        bits = [c["type"]]
        if c.get("formats"):
            bits.append("formats " + ", ".join(c["formats"]))
        if c.get("locale"):
            bits.append(f"decimal {c['locale']['decimal']!r}")
        if c.get("min") is not None:
            bits.append(f"range {c['min']} .. {c['max']}")
        nulls = ", ".join(f"{k} x{v}" for k, v in c["null_tokens"].items())
        print(f"  {c['name']!r} -> {c['suggested_name']}: {'; '.join(bits)}; {c['non_null']}/{c['values']} filled, "
              f"{c['distinct']} distinct" + (f"; nulls: {nulls}" if nulls else ""), file=out)
        if c.get("candidate_values"):
            print(f"      values: {c['candidate_values']}", file=out)
        elif c["top"] and c["type"] == "string":
            print(f"      top: {', '.join(f'{v!r} x{n}' for v, n in c['top'][:3])}", file=out)
        for f in c["flags"]:
            print(f"      ! {f}", file=out)


def print_profile(p: dict, out=None):
    out = out or sys.stdout
    print(f"file: {p['format']}, {p['bytes']} bytes, sha256 {p['sha256'][:12]}…", file=out)
    if "columns" in p:
        print(f"encoding {p['encoding']}, delimiter {p['delimiter']!r}, {p['line_endings']} line endings", file=out)
        print(f"records: {p['records_total']} total; header at record {p['header_row']}; "
              f"{p['data_records']} data records", file=out)
        if p["preamble"]:
            print(f"preamble (before the header): {p['preamble']}", file=out)
        if p["blank_records"]:
            print(f"blank records: {p['blank_records']}", file=out)
        if p["ragged_records"]:
            print(f"ragged records (record, fields): {p['ragged_records']}", file=out)
        if p["total_rows"]:
            print(f"total/footer rows (filter them; stated totals can become control_totals): {p['total_rows']}", file=out)
        if p["duplicate_rows"]:
            print(f"exact duplicate rows: {p['duplicate_rows']} (e.g. records {p['duplicate_examples']})", file=out)
        for f in p["header_flags"]:
            print(f"! {f}", file=out)
        print(f"candidate keys (unique, never empty): {p['candidate_keys'] or 'none'}", file=out)
        print("columns:", file=out)
        print_columns(p["columns"], out)
    else:
        print(f"rows_from candidates: {p['rows_from_candidates']}", file=out)
        for t in p["tables"]:
            print(f"\nrows_from {t['rows_from']!r}: {t['rows']} rows", file=out)
            print_columns(t["columns"], out)


def draft_column(c: dict, used: set, from_path: str) -> OrderedDict:
    col = OrderedDict([("name", snake(c["name"].replace(".", "_"), used)), ("from", from_path), ("type", c["type"])])
    if c["type"] == "decimal":
        col["scale"] = c.get("scale", 2)
        col["locale"] = c["locale"]
    if c.get("formats"):
        col["formats"] = c["formats"]
    if c["type"] == "timestamp" and c["formats"][0] != "iso":
        col["tz"] = "TODO: IANA timezone of the source system, e.g. Europe/Berlin"
    if c["non_null"] == c["values"] and c["values"]:
        col["required"] = True
    if c.get("candidate_values") and any("case variants" in f for f in c["flags"]):
        col["map"] = OrderedDict((v, "TODO: canonical value")
                                 for v in OrderedDict.fromkeys(x.casefold() for x in c["candidate_values"]))
    if c.get("pii"):
        col["pii"] = OrderedDict([("kind", c["pii"]), ("action", "TODO: keep | hash | drop")])
    return col


def draft_spec(p: dict, input_path: str) -> OrderedDict:
    stem = snake(Path(input_path).stem)
    spec = OrderedDict([("spec_version", SPEC_VERSION), ("name", stem), ("version", "1.0.0"),
                        ("description", "TODO: what this export is and where it comes from")])
    if "columns" in p:
        src = OrderedDict([("format", p["format"]), ("encoding", p["encoding"])])
        if p["format"] == "csv":
            src["delimiter"] = p["delimiter"]
        src["header_row"] = p["header_row"]
        spec["source"] = src
        used = set()
        cols = [draft_column(c, used, c["name"]) for c in p["columns"]]
        cols_meta = [{"name": c["name"], "name_out": d["name"]} for c, d in zip(p["columns"], cols)]
        table = OrderedDict([("name", stem), ("grain", "TODO: what one row means"),
                             ("key", ["TODO: column(s) that identify a row"] if not p["candidate_keys"] else
                                     [next(c["name_out"] for c in cols_meta if c["name"] == k) for k in p["candidate_keys"][0].split(" + ")]),
                             ("dedupe", f"TODO: {p['duplicate_rows']} rows repeat exactly: real repeats (keep: none) "
                                        f"or export duplicates (exact)? A control total can tell" if p["duplicate_rows"] else "none")])
        if p["total_rows"]:
            first = p["columns"][0]["name"]
            words = sorted({re.split(r"[\s:|]", t[1])[0] for t in p["total_rows"] if not TOTAL_RE.match(t[1])} - {""})
            pattern = TOTAL_RE.pattern + ("|^\\s*(" + "|".join(map(re.escape, words)) + ")" if words else "")
            table["filters"] = [OrderedDict([("field", first), ("matches", pattern), ("reason", "footer total")])]
            table["control_totals"] = "TODO: the file states totals; check them ({sum|count, equals: {footer: 1, regex}}) or delete this"
        if any("wide format" in f for f in p["header_flags"]):
            table["unpivot"] = "TODO: headers look like periods; decide unpivot {columns|match, name_to, value_to} or delete"
        table["columns"] = cols
        table["load"] = OrderedDict([("mode", "TODO: append | replace | replace_by | merge (+ newer_by)")])
        spec["tables"] = [table]
    else:
        spec["source"] = OrderedDict([("format", p["format"])])
        tables = []
        for t in p["tables"]:
            used = set()
            name = snake(t["rows_from"].replace("[]", "").split(".")[-1] or stem)
            cols = [draft_column(c, used, c["name"]) for c in t["columns"]]
            tables.append(OrderedDict([("name", name), ("rows_from", t["rows_from"]),
                                       ("grain", "TODO: what one row means"),
                                       ("key", ["TODO: column(s) that identify a row"]),
                                       ("columns", cols), ("load", OrderedDict([("mode", "TODO: append | replace | replace_by | merge (+ newer_by)")]))]))
        spec["tables"] = tables
    return spec


def cmd_profile(a):
    src = OrderedDict()
    for k in ("format", "delimiter", "encoding", "sheet"):
        if getattr(a, k):
            src[k] = getattr(a, k)
    source = Source(a.file, src)
    p = profile_tabular(source, a.header_row) if source.tabular else profile_tree(source, a.rows_from)
    if a.json:
        print(json.dumps(p, indent=2, ensure_ascii=False, default=str))
    else:
        print_profile(p)
    if a.draft_spec:
        if Path(a.draft_spec).exists() and not a.force:
            raise SpecError(f"{a.draft_spec} exists; it may hold decisions already made. "
                            f"Draft to another path (e.g. *.draft.json) or pass --force")
        d = draft_spec(p, a.file)
        Path(a.draft_spec).write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        n = len(list(find_todos(d)))
        print(f"\ndraft spec -> {a.draft_spec} ({n} TODO decisions to resolve before apply)")
    return 0


def cmd_spec(a):
    print((Path(__file__).with_name("spec.md")).read_text(encoding="utf-8"))
    return 0


def cmd_vendor(a):
    dest = Path(a.dir)
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / "datamax.py"
    shutil.copyfile(__file__, target)
    print(f"copied data-max {VERSION} -> {target}\nrun it without the plugin: python3 {target} apply <spec> <input> ...")
    return 0


# ----------------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="data-max", description="Profile, clean and check data exports deterministically.")
    ap.add_argument("--version", action="version", version=f"data-max {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("profile", help="profile a file (CSV/TSV/XLSX/JSON/JSONL/XML), every row")
    p.add_argument("file")
    p.add_argument("--format", choices=["csv", "xlsx", "json", "jsonl", "xml"])
    p.add_argument("--delimiter")
    p.add_argument("--encoding")
    p.add_argument("--sheet")
    p.add_argument("--header-row", type=int)
    p.add_argument("--rows-from", help="tree inputs: e.g. 'orders[]' or 'orders[].items[]'")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--draft-spec", metavar="PATH", help="write a starter spec with TODO decisions")
    p.add_argument("--force", action="store_true", help="let --draft-spec overwrite an existing file")
    p.set_defaults(fn=cmd_profile)

    for name, fn, hlp in (("apply", cmd_apply, "apply a spec: clean tables, rejects, manifest"),
                          ("check", cmd_check, "dry run plus drift: does this export still fit the spec?")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("spec")
        s.add_argument("input")
        s.add_argument("--param", action="append", metavar="KEY=VALUE")
        if name == "apply":
            s.add_argument("--out-dir", help="default: current directory")
            s.add_argument("--parquet", action="store_true", help="also write typed Parquet (needs DuckDB)")
        else:
            s.add_argument("--baseline", help="manifest of an earlier good run, for volume and null-rate drift")
            s.add_argument("--row-tolerance", type=float, help="allowed relative row-count change (default: spec drift.rows or 0.3)")
            s.add_argument("--null-tolerance", type=float, help="allowed NULL-rate change, absolute (default: spec drift.nulls or 0.1)")
            s.add_argument("--allow-drift", action="store_true", help="exit 0 despite drift (someone accepted it)")
        s.set_defaults(fn=fn)

    s = sub.add_parser("sql", help="warehouse DDL, load, merge, SQL checks or dbt sources from a spec")
    s.add_argument("spec")
    s.add_argument("--dialect", required=True, choices=["bigquery", "snowflake", "postgres", "clickhouse", "duckdb"])
    s.add_argument("--what", default="ddl,load", help="comma list of ddl, load, checks, dbt (default ddl,load)")
    s.add_argument("--schema", default="", help="dataset/schema prefix")
    s.add_argument("--out-dir", default=".", help="where apply wrote the files")
    s.set_defaults(fn=cmd_sql)

    s = sub.add_parser("spec", help="print the spec format reference")
    s.set_defaults(fn=cmd_spec)

    s = sub.add_parser("vendor", help="copy this engine into a project (for CI or reruns without the plugin)")
    s.add_argument("dir")
    s.set_defaults(fn=cmd_vendor)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except SpecError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
