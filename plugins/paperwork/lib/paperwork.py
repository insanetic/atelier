#!/usr/bin/env python3
"""paperwork: an archive for business documents that never deletes.

Files dropped into _inbox/ are hashed, read (e-invoice XML, text layer, OCR), checked, named by one
convention, filed per entity, year and direction, and indexed into CSV. Every file operation, check
and export is done here; the only input that is not deterministic, a proposal of fields read by
Claude, is checked against the document's own text and then frozen in the document's record.

Run `paperwork --help`. The engine runs inside the plugin's Docker image (bin/paperwork).
"""

import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

VERSION = "0.1.0"

EXIT_OK, EXIT_CHECK, EXIT_USAGE, EXIT_REVIEW, EXIT_LOCKED, EXIT_TOOL = 0, 1, 2, 3, 4, 5

STATE = "_paperwork"
INBOX = "_inbox"
REVIEW = "_review"
DUPLICATES = "_duplicates"
EXPORTS = "exports"
MANAGED_TOP = {STATE, INBOX, REVIEW, DUPLICATES, EXPORTS}

FIELD_TYPES = {"text", "date", "money", "number", "bool", "choice"}
NAME_TEMPLATE = "{issue_date}_{class}_{counterparty}_{number}_{amount}_{id}"
FOLDER_TEMPLATE = "{entity}/{year}/{direction}"
PLACEHOLDERS = {"issue_date", "due_date", "service_date", "year", "class", "counterparty", "number", "amount",
                "id", "entity", "direction", "category"}
HOLE = re.compile(r"\{([^{}]*)\}")
CLASS_KEY = re.compile(r"[a-z][a-z0-9-]{0,15}")
FIELD_KEY = re.compile(r"[a-z][a-z0-9_]{0,31}")
BILLED = ["buyer.name", "invoice_number", "currency", "gross"]


def builtin_class(label, money=False, sign=None, required=(), checks=()):
    return {"label": label, "money": money, "sign": sign, "required": ["issue_date", "seller.name", *required],
            "checks": list(checks), "name": NAME_TEMPLATE, "folder": FOLDER_TEMPLATE, "fields": {}}


BUILTIN_CLASSES = {
    "inv": builtin_class("invoice", True, "positive", BILLED, ["ustg14"]),
    "cn": builtin_class("credit note, Storno, Rechnungskorrektur", True, "negative", BILLED),
    "rcpt": builtin_class("receipt", True, "positive", ["currency", "gross"]),
    "rem": builtin_class("reminder"),
    "notice": builtin_class("Bescheid: tax, fee, IHK"),
    "oc": builtin_class("order confirmation"),
    "quote": builtin_class("quote"),
    "contract": builtin_class("contract"),
    "other": builtin_class("other"),
}
CLASS_DEFAULTS = {**builtin_class(""), "required": ["issue_date"]}
DIRECTIONS = ["in", "out"]
MEDIA_EXT = {"pdf": "pdf", "xml": "xml", "jpeg": "jpg", "png": "png", "tiff": "tif", "gif": "gif",
             "webp": "webp", "bmp": "bmp"}
IGNORED_FILES = {".ds_store", "desktop.ini", "thumbs.db", ".localized"}
SOURCE_RANK = {"xml": 0, "pdf-text": 1, "pdf-mixed": 2, "pdf-scan": 3, "image": 3}
MAX_PATH = 250
OCR_MIN_CHARS = 25

CURRENCIES = set("""EUR USD GBP CHF JPY CNY CAD AUD NZD SEK NOK DKK PLN CZK HUF RON BGN HRK TRY ILS
INR SGD HKD KRW ZAR BRL MXN AED SAR THB MYR IDR PHP TWD ISK RUB UAH""".split())

LEGAL_FORMS = [
    "gmbh & co. kg", "gmbh & co kg", "partg mbb", "(haftungsbeschraenkt)", "haftungsbeschraenkt",
    "s.a r.l.", "s.a.r.l.", "s. a r. l.", "s.a.r.l", "sarl", "gmbh", "mbh", "ag", "ug", "kg", "ohg",
    "gbr", "e.k.", "ek", "e.v.", "partg", "llc", "l.l.c.", "inc.", "inc", "ltd.", "ltd", "limited",
    "plc", "corp.", "corp", "co.", "s.a.", "sa", "s.l.", "sl", "b.v.", "bv", "n.v.", "nv", "a/s",
    "aps", "ab", "oy", "srl", "s.r.l.", "spa", "s.p.a.", "sas", "se", "kft", "sp. z o.o.",
]

MONTHS = {
    "januar": 1, "jänner": 1, "jan": 1, "january": 1, "februar": 2, "feb": 2, "february": 2,
    "märz": 3, "maerz": 3, "mär": 3, "mrz": 3, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "mai": 5, "may": 5, "juni": 6, "jun": 6, "june": 6, "juli": 7, "jul": 7, "july": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "oktober": 10, "okt": 10,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12,
    "december": 12, "dec": 12,
}

VAT_FORMATS = {
    "AT": r"U\d{8}", "BE": r"[01]\d{9}", "BG": r"\d{9,10}", "CY": r"\d{8}[A-Z]", "CZ": r"\d{8,10}",
    "DE": r"\d{9}", "DK": r"\d{8}", "EE": r"\d{9}", "EL": r"\d{9}", "ES": r"[A-Z0-9]\d{7}[A-Z0-9]",
    "FI": r"\d{8}", "FR": r"[A-HJ-NP-Z0-9]{2}\d{9}", "HR": r"\d{11}", "HU": r"\d{8}",
    "IE": r"\d{7}[A-W][A-I]?|\d[A-Z+*]\d{5}[A-W]", "IT": r"\d{11}", "LT": r"\d{9}|\d{12}",
    "LU": r"\d{8}", "LV": r"\d{11}", "MT": r"\d{8}", "NL": r"\d{9}B\d{2}", "PL": r"\d{10}",
    "PT": r"\d{9}", "RO": r"\d{2,10}", "SE": r"\d{12}", "SI": r"\d{8}", "SK": r"\d{10}",
    "XI": r"\d{9}|\d{12}", "GB": r"\d{9}|\d{12}", "CH": r"E\d{9}(MWST|TVA|IVA)?", "EU": r"\d{9}",
}


class Fail(Exception):
    def __init__(self, message, code=EXIT_USAGE):
        super().__init__(message)
        self.code = code


# ----------------------------------------------------------------------------------------------
# Text, money and dates


def nfkc(s):
    return unicodedata.normalize("NFKC", s or "")


def squash(s):
    """Casefolded NFKC text with all whitespace removed: what evidence is matched on."""
    return re.sub(r"\s+", "", nfkc(s).casefold())


def fold(s):
    """ASCII transliteration: ä ö ü ß become ae oe ue ss."""
    s = nfkc(s)
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"),
                 ("ß", "ss"), ("ẞ", "SS")):
        s = s.replace(a, b)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).encode("ascii", "ignore").decode()


def slugify(s, limit=32):
    s = re.sub(r"[^a-z0-9]+", "-", fold(s).lower()).strip("-")
    if len(s) > limit:
        s = s[:limit].rsplit("-", 1)[0] if "-" in s[:limit] else s[:limit]
    return s.strip("-")


def safe_number(s, limit=40):
    s = fold(s).strip()
    s = re.sub(r"[/\\:*?\"<>|\s_]+", "-", s)
    s = re.sub(r"[^A-Za-z0-9.\-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-.")
    return s[:limit].rstrip("-.") or "-"


def company_key(name):
    """A name without legal form and punctuation, for matching counterparties."""
    s = fold(name).lower()
    s = s.split(",")[0] if "," in s and not re.match(r"^[^,]{0,3},", s) else s
    s = re.sub(r"\s+", " ", s).strip()
    changed = True
    while changed:
        changed = False
        for form in LEGAL_FORMS:
            if s.endswith(" " + form) or s == form:
                s = s[: -len(form)].strip(" ,.-&")
                changed = True
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def dec(value, field="value"):
    """A canonical decimal: "1234.50", "-12.5" or a number. Locale formats are refused here."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise Fail(f"{field}: not a number: {value!r}")
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    s = str(value).strip()
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        raise Fail(f"{field}: write numbers as 1234.50 (dot decimal, no thousands separator), got {value!r}")
    return Decimal(s)


def money(d):
    return None if d is None else str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def plain(d):
    if d is None:
        return None
    s = format(d.normalize(), "f")
    return s if s not in ("-0",) else "0"


def amount_candidates(text):
    """Every value a printed amount can mean: "1.234,50 €" -> {1234.50}; "1,234" -> {1234, 1.234}."""
    if text is None:
        return set()
    s = nfkc(str(text)).strip()
    negative = bool(re.search(r"^\s*[-−–]|[-−–]\s*$|^\(.*\)$|\(\s*[^\d]*[\d.,' ]+[^\d]*\)", s))
    s = re.sub(r"[^\d.,']", "", s.replace(" ", "").replace(" ", ""))
    s = s.replace("'", "")
    if not re.search(r"\d", s):
        return set()
    out = set()
    seps = [c for c in s if c in ".,"]
    if not seps:
        out.add(Decimal(s))
    else:
        last = max(s.rfind("."), s.rfind(","))
        head, tail = s[:last], s[last + 1:]
        head_digits = re.sub(r"[.,]", "", head)
        if len(set(seps)) == 2 or len(tail) != 3 or seps.count(s[last]) > 1:
            if seps.count(s[last]) > 1 and len(set(seps)) == 1:
                out.add(Decimal(re.sub(r"[.,]", "", s)))
            else:
                out.add(Decimal(f"{head_digits or '0'}.{tail or '0'}"))
        else:
            out.add(Decimal(f"{head_digits or '0'}.{tail}"))
            out.add(Decimal(head_digits + tail))
    return {-v if negative else v for v in out}


def date_candidates(text):
    """Every date a printed date can mean, German and English formats."""
    s = nfkc(str(text or "")).strip().lower()
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)
    out = set()

    def add(y, m, d):
        try:
            y = int(y)
            if y < 100:
                y += 2000
            out.add(dt.date(y, int(m), int(d)))
        except ValueError:
            pass

    for y, m, d in re.findall(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", s):
        add(y, m, d)
    for y, m, d in re.findall(r"\b(\d{4})(\d{2})(\d{2})\b", s):
        add(y, m, d)
    for d, m, y in re.findall(r"\b(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{2,4})\b", s):
        add(y, m, d)
    for a, b, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", s):
        add(y, b, a)
        add(y, a, b)
    words = "|".join(sorted(MONTHS, key=len, reverse=True))
    for d, mon, y in re.findall(rf"\b(\d{{1,2}})\.?\s+({words})\.?,?\s+(\d{{4}})\b", s):
        add(y, MONTHS[mon], d)
    for mon, d, y in re.findall(rf"\b({words})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", s):
        add(y, MONTHS[mon], d)
    return out


def iso_date(value, field):
    if value in (None, ""):
        return None
    try:
        return dt.date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise Fail(f"{field}: write dates as YYYY-MM-DD, got {value!r}")


def vat_ok(vat):
    v = re.sub(r"[\s.\-]", "", vat or "").upper()
    m = re.fullmatch(r"([A-Z]{2})(.+)", v)
    if not m or m.group(1) not in VAT_FORMATS:
        return None  # unknown scheme (e.g. a non-EU tax number): not judged
    cc, rest = m.groups()
    if not re.fullmatch(VAT_FORMATS[cc], rest):
        return False
    if cc == "DE":
        product = 10
        for ch in rest[:8]:
            total = (int(ch) + product) % 10 or 10
            product = (2 * total) % 11
        return (11 - product) % 10 == int(rest[8])
    return True


def iban_ok(iban):
    v = re.sub(r"\s", "", iban or "").upper()
    if not v or re.search(r"[*X]{2,}", v[4:]) or "…" in v:
        return None  # masked
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", v):
        return False
    n = "".join(str(int(c, 36)) for c in v[4:] + v[:4])
    return int(n) % 97 == 1


def norm_vat(v):
    return re.sub(r"[\s.\-]", "", v or "").upper()


# ----------------------------------------------------------------------------------------------
# Files


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_state(path, text):
    """Writes an engine state file (never a document) atomically, only when it changed."""
    try:
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() == text:
                return False
    except FileNotFoundError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)
    return True


def sniff(path):
    with open(path, "rb") as f:
        head = f.read(512)
    if head.startswith(b"%PDF") or b"%PDF-" in head[:64]:
        return "pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:2] == b"BM":
        return "bmp"
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"mif1", b"heif"):
        return "heic"
    text = head.lstrip(b"\xef\xbb\xbf").lstrip()
    if text.startswith(b"<?xml") or re.match(rb"<[A-Za-z][\w.:-]*[\s>]", text):
        return "xml"
    return "unknown"


# ----------------------------------------------------------------------------------------------
# Tools


def tool(args, binary=False, check=True):
    try:
        p = subprocess.run(args, capture_output=True, timeout=600)
    except FileNotFoundError:
        raise Fail(f"tool not found: {args[0]} (run the engine through bin/paperwork)", EXIT_TOOL)
    if check and p.returncode != 0:
        raise RuntimeError(f"{args[0]} failed: {p.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return p.stdout if binary else p.stdout.decode("utf-8", "replace")


_VERSIONS = {}


def tool_versions():
    if not _VERSIONS:
        def first(args):
            try:
                p = subprocess.run(args, capture_output=True, timeout=30)
                out = (p.stdout + p.stderr).decode("utf-8", "replace").strip().splitlines()
                return out[0] if out else "?"
            except FileNotFoundError:
                return "missing"
        _VERSIONS["engine"] = VERSION
        _VERSIONS["poppler"] = first(["pdftotext", "-v"]).replace("pdftotext version ", "")
        _VERSIONS["tesseract"] = first(["tesseract", "--version"]).replace("tesseract ", "")
    return dict(_VERSIONS)


def pdf_pages(path):
    info = tool(["pdfinfo", path])
    m = re.search(r"^Pages:\s+(\d+)", info, re.M)
    if re.search(r"^Encrypted:\s+yes", info, re.M) and not m:
        raise RuntimeError("encrypted PDF")
    return int(m.group(1)) if m else 0


def ocr_image(path):
    return tool(["tesseract", path, "-", "-l", "deu+eng", "--psm", "4"])


def derive(archive, sha, path, kind):
    """Reads a document's text: text layer per page, OCR for pages without one, embedded XML."""
    out_dir = archive.p(STATE, "derived", sha)
    os.makedirs(out_dir, exist_ok=True)
    info = {"pages": 0, "media": kind, "images": [], "einvoice": None, "embedded_xml": None}
    layout, raw = [], []
    if kind == "pdf":
        pages = pdf_pages(path)
        info["pages"] = pages
        ocr_pages = 0
        for i in range(1, pages + 1):
            t = tool(["pdftotext", "-layout", "-enc", "UTF-8", "-f", str(i), "-l", str(i), path, "-"])
            if len(re.sub(r"\s", "", t)) >= OCR_MIN_CHARS:
                layout.append(t)
                raw.append(tool(["pdftotext", "-raw", "-enc", "UTF-8", "-f", str(i), "-l", str(i), path, "-"]))
                continue
            ocr_pages += 1
            base = os.path.join(out_dir, f"page-{i}")
            tool(["pdftoppm", "-r", "300", "-gray", "-png", "-singlefile", "-f", str(i), "-l", str(i), path, base])
            png = base + ".png"
            info["images"].append(archive.rel(png))
            t = ocr_image(png)
            layout.append(t)
            raw.append(t)
        if pages and ocr_pages == pages:
            info["media"] = "pdf-scan"
        elif ocr_pages:
            info["media"] = "pdf-mixed"
        else:
            info["media"] = "pdf-text"
        listing = tool(["pdfdetach", "-list", path], check=False)
        for n, name in re.findall(r"^(\d+):\s+(.+?)\s*$", listing, re.M):
            if not name.lower().endswith(".xml"):
                continue
            target = os.path.join(out_dir, f"embedded-{n}.xml")
            tool(["pdfdetach", "-save", n, "-o", target, path], check=False)
            if os.path.exists(target) and einvoice_kind(target):
                info["embedded_xml"] = archive.rel(target)
                info["einvoice"] = einvoice_kind(target)
                break
    elif kind == "xml":
        info["pages"] = 1
        info["media"] = "xml"
        info["einvoice"] = einvoice_kind(path)
        try:
            root = safe_xml(path)
            layout.append("\n".join(t.strip() for t in root.itertext() if t.strip()))
        except Exception:
            with open(path, encoding="utf-8", errors="replace") as f:
                layout.append(f.read())
        raw = layout[:]
    elif kind in ("jpeg", "png", "tiff", "gif", "webp", "bmp"):
        info["pages"] = 1
        info["media"] = "image"
        info["images"].append(archive.rel(path))
        t = ocr_image(path)
        layout.append(t)
        raw.append(t)
    write_state(os.path.join(out_dir, "text.txt"), "\f".join(layout))
    write_state(os.path.join(out_dir, "raw.txt"), "\f".join(raw))
    return info


# ----------------------------------------------------------------------------------------------
# E-invoices: XRechnung / ZUGFeRD / Factur-X (CII) and UBL


def safe_xml(path):
    with open(path, "rb") as f:
        data = f.read()
    if b"<!DOCTYPE" in data[:4096] or b"<!ENTITY" in data:
        raise ValueError("XML with a DOCTYPE or entities is refused")
    return ET.fromstring(data)


def local(tag):
    return tag.rsplit("}", 1)[-1]


def einvoice_kind(path):
    try:
        root = safe_xml(path)
    except Exception:
        return None
    name = local(root.tag)
    if name == "CrossIndustryInvoice":
        return "cii"
    if name in ("Invoice", "CreditNote") and "oasis" in root.tag:
        return "ubl"
    return None


def kids(el, *names):
    """Descendants by a path of local names."""
    cur = [el]
    for n in names:
        cur = [c for e in cur for c in e if local(c.tag) == n]
    return cur


def text_at(el, *names):
    found = kids(el, *names)
    return found[0].text.strip() if found and found[0].text and found[0].text.strip() else None


def parse_cii(root):
    doc = kids(root, "ExchangedDocument")[0]
    tx = kids(root, "SupplyChainTradeTransaction")[0]
    agreement = kids(tx, "ApplicableHeaderTradeAgreement")[0]
    settlement = kids(tx, "ApplicableHeaderTradeSettlement")[0]
    type_code = text_at(doc, "TypeCode")
    sign = Decimal(-1) if type_code in ("381", "261", "262", "396", "532") else Decimal(1)

    def party(p):
        if p is None:
            return {}
        addr = (kids(p, "PostalTradeAddress") or [None])[0]
        lines = []
        if addr is not None:
            for n in ("LineOne", "LineTwo", "LineThree"):
                v = text_at(addr, n)
                if v:
                    lines.append(v)
            city = " ".join(x for x in (text_at(addr, "PostcodeCode"), text_at(addr, "CityName")) if x)
            if city:
                lines.append(city)
        vat = None
        tax_number = None
        for reg in kids(p, "SpecifiedTaxRegistration"):
            ids = kids(reg, "ID")
            if ids and ids[0].text:
                if ids[0].get("schemeID") == "VA":
                    vat = ids[0].text.strip()
                elif ids[0].get("schemeID") == "FC":
                    tax_number = ids[0].text.strip()
        return {"name": text_at(p, "Name"), "address": lines, "vat_id": vat, "tax_number": tax_number,
                "country": text_at(addr, "CountryID") if addr is not None else None}

    seller = party((kids(agreement, "SellerTradeParty") or [None])[0])
    buyer = party((kids(agreement, "BuyerTradeParty") or [None])[0])
    summ = kids(settlement, "SpecifiedTradeSettlementHeaderMonetarySummation")[0]

    def amt(el, *names):
        v = text_at(el, *names)
        return None if v is None else str(Decimal(v) * sign)

    tax = []
    reverse = False
    for t in kids(settlement, "ApplicableTradeTax"):
        cat = text_at(t, "CategoryCode")
        reverse = reverse or cat == "AE"
        tax.append({"rate": text_at(t, "RateApplicablePercent") or "0",
                    "net": amt(t, "BasisAmount"), "tax": amt(t, "CalculatedAmount") or "0"})
    lines = []
    for li in kids(tx, "IncludedSupplyChainTradeLineItem"):
        lines.append({
            "description": text_at(li, "SpecifiedTradeProduct", "Name"),
            "quantity": text_at(li, "SpecifiedLineTradeDelivery", "BilledQuantity"),
            "unit_price": text_at(li, "SpecifiedLineTradeAgreement", "NetPriceProductTradePrice", "ChargeAmount"),
            "net": amt(li, "SpecifiedLineTradeSettlement", "SpecifiedTradeSettlementLineMonetarySummation",
                       "LineTotalAmount"),
            "tax_rate": text_at(li, "SpecifiedLineTradeSettlement", "ApplicableTradeTax", "RateApplicablePercent"),
        })

    def cii_date(el, *names):
        v = text_at(el, *names)
        return dt.datetime.strptime(v[:8], "%Y%m%d").date().isoformat() if v and re.match(r"\d{8}", v) else None

    period = (kids(settlement, "BillingSpecifiedPeriod") or [None])[0]
    tax_total = text_at(summ, "TaxTotalAmount")
    return {
        "doc_type": "cn" if sign < 0 else "inv",
        "invoice_number": text_at(doc, "ID"),
        "issue_date": cii_date(doc, "IssueDateTime", "DateTimeString"),
        "due_date": cii_date(settlement, "SpecifiedTradePaymentTerms", "DueDateDateTime", "DateTimeString"),
        "service_period": {"start": cii_date(period, "StartDateTime", "DateTimeString"),
                           "end": cii_date(period, "EndDateTime", "DateTimeString")} if period is not None else None,
        "currency": text_at(settlement, "InvoiceCurrencyCode"),
        "seller": seller, "buyer": buyer,
        "net": amt(summ, "TaxBasisTotalAmount"),
        "gross": amt(summ, "GrandTotalAmount"),
        "tax": tax if tax else ([{"rate": "0", "net": amt(summ, "TaxBasisTotalAmount"),
                                  "tax": str(Decimal(tax_total) * sign)}] if tax_total else []),
        "reverse_charge": reverse,
        "iban": text_at(settlement, "SpecifiedTradeSettlementPaymentMeans", "PayeePartyCreditorFinancialAccount", "IBANID"),
        "lines": lines,
        "refers_to": [v for v in [text_at(settlement, "InvoiceReferencedDocument", "IssuerAssignedID")] if v],
    }


def parse_ubl(root):
    credit = local(root.tag) == "CreditNote"
    sign = Decimal(-1) if credit else Decimal(1)

    def party(path):
        p = (kids(root, *path, "Party") or [None])[0]
        if p is None:
            return {}
        addr = (kids(p, "PostalAddress") or [None])[0]
        lines = []
        if addr is not None:
            for n in ("StreetName", "AdditionalStreetName"):
                v = text_at(addr, n)
                if v:
                    lines.append(v)
            city = " ".join(x for x in (text_at(addr, "PostalZone"), text_at(addr, "CityName")) if x)
            if city:
                lines.append(city)
        name = text_at(p, "PartyLegalEntity", "RegistrationName") or text_at(p, "PartyName", "Name")
        vat = None
        for scheme in kids(p, "PartyTaxScheme"):
            if text_at(scheme, "TaxScheme", "ID") == "VAT":
                vat = text_at(scheme, "CompanyID")
        return {"name": name, "address": lines, "vat_id": vat, "tax_number": None,
                "country": text_at(addr, "Country", "IdentificationCode") if addr is not None else None}

    def amt(el, *names):
        v = text_at(el, *names)
        return None if v is None else str(Decimal(v) * sign)

    total = kids(root, "LegalMonetaryTotal")[0]
    tax = []
    reverse = False
    for sub in kids(root, "TaxTotal", "TaxSubtotal"):
        reverse = reverse or text_at(sub, "TaxCategory", "ID") == "AE"
        tax.append({"rate": text_at(sub, "TaxCategory", "Percent") or "0",
                    "net": amt(sub, "TaxableAmount"), "tax": amt(sub, "TaxAmount") or "0"})
    lines = []
    for li in kids(root, "CreditNoteLine" if credit else "InvoiceLine"):
        lines.append({
            "description": text_at(li, "Item", "Name"),
            "quantity": text_at(li, "CreditedQuantity" if credit else "InvoicedQuantity"),
            "unit_price": text_at(li, "Price", "PriceAmount"),
            "net": amt(li, "LineExtensionAmount"),
            "tax_rate": text_at(li, "Item", "ClassifiedTaxCategory", "Percent"),
        })
    period = (kids(root, "InvoicePeriod") or [None])[0]
    return {
        "doc_type": "cn" if credit else "inv",
        "invoice_number": text_at(root, "ID"),
        "issue_date": text_at(root, "IssueDate"),
        "due_date": text_at(root, "DueDate") or text_at(root, "PaymentMeans", "PaymentDueDate"),
        "service_period": {"start": text_at(period, "StartDate"), "end": text_at(period, "EndDate")}
        if period is not None else None,
        "currency": text_at(root, "DocumentCurrencyCode"),
        "seller": party(("AccountingSupplierParty",)),
        "buyer": party(("AccountingCustomerParty",)),
        "net": amt(total, "TaxExclusiveAmount"),
        "gross": amt(total, "TaxInclusiveAmount"),
        "tax": tax,
        "reverse_charge": reverse,
        "iban": text_at(root, "PaymentMeans", "PayeeFinancialAccount", "ID"),
        "lines": lines,
        "refers_to": [v for v in [text_at(root, "BillingReference", "InvoiceDocumentReference", "ID")] if v],
    }


def parse_einvoice(path):
    root = safe_xml(path)
    kind = einvoice_kind(path)
    proposal = parse_cii(root) if kind == "cii" else parse_ubl(root)
    proposal["evidence"] = {}
    return proposal


# ----------------------------------------------------------------------------------------------
# Proposals: the shape every source (XML, template, Claude, the user) produces


PARTY_KEYS = {"name", "address", "vat_id", "tax_number", "country"}
LINE_KEYS = {"description", "quantity", "unit", "unit_price", "net", "tax_rate", "gross"}
PROPOSAL_KEYS = {
    "doc_type", "language", "issue_date", "service_date", "service_period", "due_date", "seller",
    "buyer", "invoice_number", "refers_to", "currency", "net", "tax", "gross", "reverse_charge",
    "iban", "payment_method", "paid", "category", "tags", "lines", "evidence", "notes",
    "entity", "direction", "fields",
}


def normalize_fields(raw, specs, doc_type):
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        raise Fail("fields maps a field name to its value")
    out = {}
    for name, v in sorted(raw.items()):
        spec = specs.get(name)
        if spec is None:
            raise Fail(f"unknown field {name!r} for class {doc_type} (declared: {', '.join(sorted(specs)) or 'none'})")
        if v in (None, ""):
            continue
        kind, key = spec["type"], f"fields.{name}"
        if kind == "date":
            out[name] = iso_date(v, key)
        elif kind == "money":
            out[name] = money(dec(v, key))
        elif kind == "number":
            out[name] = plain(dec(v, key))
        elif kind == "bool":
            if not isinstance(v, bool):
                raise Fail(f"{key} is true or false")
            out[name] = v
        elif kind == "choice":
            if v not in spec["choices"]:
                raise Fail(f"{key} must be one of {', '.join(spec['choices'])}, got {v!r}")
            out[name] = v
        else:
            out[name] = str(v).strip()
    return out


def normalize_proposal(p, classes=BUILTIN_CLASSES):
    if not isinstance(p, dict):
        raise Fail("a proposal is a JSON object")
    unknown = sorted(set(p) - PROPOSAL_KEYS)
    if unknown:
        raise Fail(f"unknown proposal fields: {', '.join(unknown)} (see `paperwork schema`)")
    d = {}
    doc_type = p.get("doc_type")
    if doc_type not in classes:
        raise Fail(f"doc_type must be one of {', '.join(classes)}, got {doc_type!r}")
    d["doc_type"] = doc_type
    d["fields"] = normalize_fields(p.get("fields"), classes[doc_type]["fields"], doc_type)
    for k in ("issue_date", "service_date", "due_date"):
        d[k] = iso_date(p.get(k), k)
    sp = p.get("service_period")
    if sp:
        if not isinstance(sp, dict):
            raise Fail("service_period is {\"start\": \"YYYY-MM-DD\", \"end\": \"YYYY-MM-DD\"}")
        d["service_period"] = {"start": iso_date(sp.get("start"), "service_period.start"),
                               "end": iso_date(sp.get("end"), "service_period.end")}
    else:
        d["service_period"] = None
    for side in ("seller", "buyer"):
        party = p.get(side) or {}
        if not isinstance(party, dict):
            raise Fail(f"{side} is an object with {', '.join(sorted(PARTY_KEYS))}")
        bad = sorted(set(party) - PARTY_KEYS)
        if bad:
            raise Fail(f"unknown {side} fields: {', '.join(bad)}")
        addr = party.get("address") or []
        if isinstance(addr, str):
            addr = [a.strip() for a in addr.split("\n") if a.strip()]
        d[side] = {"name": (party.get("name") or "").strip() or None,
                   "address": [str(a).strip() for a in addr if str(a).strip()],
                   "vat_id": norm_vat(party.get("vat_id")) or None,
                   "tax_number": (party.get("tax_number") or "").strip() or None,
                   "country": (party.get("country") or "").strip().upper() or None}
    d["invoice_number"] = (str(p.get("invoice_number")).strip() if p.get("invoice_number") not in (None, "") else None)
    refers = p.get("refers_to") or []
    d["refers_to"] = [str(r).strip() for r in ([refers] if isinstance(refers, str) else refers) if str(r).strip()]
    cur = p.get("currency")
    d["currency"] = str(cur).strip().upper() if cur else None
    for k in ("net", "gross"):
        d[k] = money(dec(p.get(k), k))
    tax = []
    for i, t in enumerate(p.get("tax") or []):
        if not isinstance(t, dict):
            raise Fail("tax is a list of {\"rate\", \"net\", \"tax\"}")
        rate = dec(t.get("rate"), f"tax[{i}].rate")
        tax.append({"rate": plain(rate) if rate is not None else None,
                    "net": money(dec(t.get("net"), f"tax[{i}].net")),
                    "tax": money(dec(t.get("tax"), f"tax[{i}].tax"))})
    d["tax"] = sorted(tax, key=lambda t: (Decimal(t["rate"] or "0"), t["net"] or ""))
    lines = []
    for i, li in enumerate(p.get("lines") or []):
        if not isinstance(li, dict):
            raise Fail("lines is a list of objects")
        bad = sorted(set(li) - LINE_KEYS)
        if bad:
            raise Fail(f"unknown line fields: {', '.join(bad)}")
        lines.append({
            "description": (li.get("description") or "").strip() or None,
            "quantity": plain(dec(li.get("quantity"), f"lines[{i}].quantity")),
            "unit": (li.get("unit") or "").strip() or None,
            "unit_price": plain(dec(li.get("unit_price"), f"lines[{i}].unit_price")),
            "net": money(dec(li.get("net"), f"lines[{i}].net")),
            "tax_rate": plain(dec(li.get("tax_rate"), f"lines[{i}].tax_rate")),
            "gross": money(dec(li.get("gross"), f"lines[{i}].gross")),
        })
    d["lines"] = lines
    d["reverse_charge"] = bool(p.get("reverse_charge"))
    d["paid"] = p.get("paid") if isinstance(p.get("paid"), bool) else None
    for k in ("language", "iban", "payment_method", "category", "notes"):
        v = p.get(k)
        d[k] = str(v).strip() if v not in (None, "") else None
    if d["iban"]:
        d["iban"] = re.sub(r"\s", "", d["iban"]).upper()
    tags = p.get("tags") or []
    d["tags"] = sorted({str(t).strip() for t in ([tags] if isinstance(tags, str) else tags) if str(t).strip()})
    ev = p.get("evidence") or {}
    if not isinstance(ev, dict):
        raise Fail("evidence maps a field to the text printed on the document")
    d["evidence"] = {str(k): str(v) for k, v in sorted(ev.items()) if v not in (None, "")}
    d["entity"] = p.get("entity") or None
    if p.get("direction") not in (None, "", *DIRECTIONS):
        raise Fail("direction is in or out")
    d["direction"] = p.get("direction") or None
    return d


SCHEMA = {
    "doc_type": "the document class key (see the classes in config.json)",
    "language": "de | en | ...",
    "issue_date": "YYYY-MM-DD, the issue date (Rechnungsdatum)",
    "service_date": "YYYY-MM-DD (Leistungsdatum / Lieferdatum), or null",
    "service_period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
    "due_date": "YYYY-MM-DD or null",
    "seller": {"name": "who issued it, as printed (on Amazon: the 'Verkauft von' party)",
               "address": ["street", "postcode city", "country"], "vat_id": "as printed",
               "tax_number": "Steuernummer, as printed", "country": "ISO 3166 alpha-2"},
    "buyer": {"name": "the billed party as printed (the company, not the attention line)",
              "address": ["the BILLING address only, never the delivery address"],
              "vat_id": "as printed", "tax_number": None, "country": "ISO 3166 alpha-2"},
    "invoice_number": "as printed",
    "refers_to": ["the invoice number a credit note or reminder refers to"],
    "currency": "ISO 4217",
    "net": "1234.50 (dot decimal; negative for credit notes)",
    "tax": [{"rate": "19", "net": "1037.39", "tax": "197.11"}],
    "gross": "1234.50",
    "reverse_charge": "true when tax is owed by the recipient (§13b, Reverse Charge, Steuerschuldumkehr)",
    "iban": "the seller's IBAN as printed, or null",
    "payment_method": "card | sepa | transfer | paypal | cash | ...",
    "paid": "true when the document says it is paid",
    "category": "one of the config categories, or null",
    "tags": [],
    "lines": [{"description": "", "quantity": "1", "unit": None, "unit_price": "10.00",
               "net": "10.00", "tax_rate": "19", "gross": "11.90"}],
    "evidence": {"issue_date": "the date exactly as printed", "gross": "the total exactly as printed",
                 "net": "as printed", "tax": "as printed", "due_date": "as printed"},
    "notes": "anything a reader needs: what is unusual",
    "fields": "values of the class's own fields, {name: value}; only for classes that declare fields",
}


def merge_classes(cfg):
    classes = {k: dict(v) for k, v in BUILTIN_CLASSES.items()}
    for key, over in (cfg.get("classes") or {}).items():
        classes[key] = {**classes.get(key, {**CLASS_DEFAULTS, "label": key}), **over}
    return classes


# ----------------------------------------------------------------------------------------------
# Templates: per-vendor extraction from the text layer


def apply_template(template, text):
    fields = {}
    evidence = {}
    flags = re.M
    for key, spec in sorted((template.get("fields") or {}).items()):
        pattern = re.compile(spec["pattern"], flags)
        kind = spec.get("type", "text")
        if spec.get("repeat"):
            rows = []
            for m in pattern.finditer(text):
                row = {}
                for name, group in spec["groups"].items():
                    raw = m.group(group)
                    row[name] = convert(raw, spec.get("types", {}).get(name, kind), spec, f"{key}.{name}")
                rows.append(row)
            fields[key] = rows
            continue
        m = pattern.search(text)
        if not m:
            if spec.get("optional"):
                continue
            raise ValueError(f"{key}: pattern did not match")
        raw = m.group(spec.get("group", 1))
        fields[key] = convert(raw, kind, spec, key)
        if kind in ("amount", "date"):
            evidence[key.split(".")[0]] = raw.strip()
    proposal = json.loads(json.dumps(template.get("fixed") or {}))
    for key, value in fields.items():
        cur = proposal
        parts = key.split(".")
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
    proposal["evidence"] = {**(proposal.get("evidence") or {}), **evidence}
    return proposal


def convert(raw, kind, spec, key):
    raw = (raw or "").strip()
    if kind == "amount":
        if spec.get("decimal") in (",", "."):
            other = "." if spec["decimal"] == "," else ","
            digits = re.sub(r"[^\d" + re.escape(spec["decimal"]) + "]", "", raw.replace(other, ""))
            c = amount_candidates(("-" if re.search(r"^\s*[-−]|\(", raw) else "") + digits.replace(spec["decimal"], "."))
        else:
            c = amount_candidates(raw)
        if len(c) != 1:
            raise ValueError(f"{key}: amount {raw!r} is ambiguous")
        v = c.pop()
        return str(-abs(v) if spec.get("negate") else v)
    if kind == "date":
        c = date_candidates(raw)
        if len(c) > 1 and spec.get("order") == "dmy":
            c = {d for d in c if raw.startswith(str(d.day)) or raw.startswith(f"{d.day:02d}")}
        if len(c) != 1:
            raise ValueError(f"{key}: date {raw!r} is ambiguous or unreadable")
        return c.pop().isoformat()
    if kind == "lines":
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]
    return re.sub(r"\s+", " ", raw)


# ----------------------------------------------------------------------------------------------
# The archive


class Archive:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        if not os.path.isfile(self.p(STATE, "config.json")):
            raise Fail(f"not an archive (no {STATE}/config.json): {self.root}; run `paperwork init`")
        self.config = self.load_config()
        self.vendors = read_json(self.p(STATE, "vendors.json"), {"vendors": []})
        self.rules = load_rules(self)
        self._records = None
        self.today = dt.datetime.now(dt.timezone.utc).date()

    @property
    def classes(self):
        return merge_classes(self.config)

    def p(self, *parts):
        return os.path.join(self.root, *parts)

    def rel(self, path):
        return os.path.relpath(os.path.abspath(path), self.root).replace(os.sep, "/")

    def load_config(self):
        cfg = read_json(self.p(STATE, "config.json"))
        problems = config_problems(cfg)
        if problems:
            raise Fail("config.json: " + "; ".join(problems))
        return cfg

    # records ----------------------------------------------------------------------------------

    @property
    def records(self):
        if self._records is None:
            self._records = {}
            d = self.p(STATE, "docs")
            if os.path.isdir(d):
                for name in sorted(os.listdir(d)):
                    if name.endswith(".json"):
                        r = read_json(os.path.join(d, name))
                        self._records[r["id"]] = r
        return self._records

    def save(self, record):
        write_state(self.p(STATE, "docs", record["id"] + ".json"), dumps(record))

    def save_vendors(self):
        self.vendors["vendors"].sort(key=lambda v: v["slug"])
        write_state(self.p(STATE, "vendors.json"), dumps(self.vendors))

    def find(self, prefix):
        prefix = prefix.lower()
        hits = [i for i in self.records if i.startswith(prefix)]
        if len(prefix) < 6 or not hits:
            raise Fail(f"no document {prefix!r} (give at least 6 characters of its id)")
        if len(hits) > 1:
            raise Fail(f"{prefix!r} matches {len(hits)} documents")
        return self.records[hits[0]]

    def text(self, record, kind="text"):
        try:
            with open(self.p(STATE, "derived", record["id"], f"{kind}.txt"), encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    # lock -------------------------------------------------------------------------------------

    @contextlib.contextmanager
    def lock(self):
        path = self.p(STATE, "lock")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            with open(path, encoding="utf-8", errors="replace") as f:
                who = f.read().strip()
            raise Fail(f"the archive is locked by {who or 'another run'}; if no run is active: `paperwork unlock`",
                       EXIT_LOCKED)
        with os.fdopen(fd, "w") as f:
            f.write(f"{socket.gethostname()} pid {os.getpid()} since {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}\n")
        try:
            yield
        finally:
            with contextlib.suppress(FileNotFoundError):
                os.remove(path)  # the lock is engine state, never a document

    # journal ----------------------------------------------------------------------------------

    def journal(self, entries):
        if not entries:
            return
        path = self.p(STATE, "journal.jsonl")
        with open(path, "a", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def journal_entries(self):
        try:
            with open(self.p(STATE, "journal.jsonl"), encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            return []

    # vendors ----------------------------------------------------------------------------------

    def vendor(self, slug):
        for v in self.vendors["vendors"]:
            if v["slug"] == slug:
                return v
        return None

    def resolve_counterparty(self, party, create=True):
        """The registry slug for a party: by VAT ID, then by name. New parties are added."""
        name = (party or {}).get("name")
        vat = norm_vat((party or {}).get("vat_id"))
        if not name and not vat:
            return None
        key = company_key(name or "")
        by_vat = [v for v in self.vendors["vendors"] if vat and vat in v.get("vat_ids", [])]
        by_name = [v for v in self.vendors["vendors"]
                   if key and key in {company_key(n) for n in v.get("names", [])}]
        hit = by_vat[0] if len(by_vat) == 1 else (by_name[0] if len(by_name) == 1 and not by_vat else None)
        if hit is None and (len(by_vat) > 1 or len(by_name) > 1):
            return None
        if hit is None:
            if not create:
                return None
            base = slugify(key or name or vat) or "unknown"
            slug, n = base, 2
            while self.vendor(slug):
                slug, n = f"{base}-{n}", n + 1
            hit = {"slug": slug, "names": [], "vat_ids": [], "category": None, "template": None}
            self.vendors["vendors"].append(hit)
        if name and name not in hit["names"]:
            hit["names"] = sorted(set(hit["names"]) | {name})
        if vat and vat not in hit["vat_ids"] and not by_name[1:]:
            hit["vat_ids"] = sorted(set(hit["vat_ids"]) | {vat})
        return hit["slug"]


def config_problems(cfg):
    out = []
    if not isinstance(cfg, dict):
        return ["not a JSON object"]
    ents = cfg.get("entities")
    if not isinstance(ents, list):
        return ["entities must be a list"]
    seen = set()
    for i, e in enumerate(ents):
        slug = e.get("slug") if isinstance(e, dict) else None
        if not slug or slugify(slug, 64) != slug:
            out.append(f"entities[{i}].slug must be a lowercase slug, got {slug!r}")
            continue
        if slug in seen:
            out.append(f"entity {slug} is listed twice")
        seen.add(slug)
        if e.get("kind", "business") not in ("business", "private"):
            out.append(f"entity {slug}: kind is business or private")
        if not (e.get("names") or e.get("name")):
            out.append(f"entity {slug}: needs a name")
        for v in e.get("vat_ids", []):
            if vat_ok(v) is False:
                out.append(f"entity {slug}: VAT ID {v} is not valid")
    out += class_problems(cfg.get("classes", {}))
    return out


def class_problems(classes):
    if not isinstance(classes, dict):
        return ["classes must be an object keyed by class key"]
    out = []
    for key, c in classes.items():
        if not CLASS_KEY.fullmatch(key):
            out.append(f"classes.{key}: the key must match {CLASS_KEY.pattern}")
            continue
        if not isinstance(c, dict):
            out.append(f"classes.{key}: must be an object")
            continue
        fields = c.get("fields", BUILTIN_CLASSES.get(key, CLASS_DEFAULTS)["fields"])
        if not isinstance(fields, dict):
            out.append(f"classes.{key}: fields must be an object")
            fields = {}
        for name, spec in fields.items():
            if not FIELD_KEY.fullmatch(name):
                out.append(f"classes.{key}: field name {name!r} must match {FIELD_KEY.pattern}")
            elif not isinstance(spec, dict) or spec.get("type") not in FIELD_TYPES:
                out.append(f"classes.{key}: field {name} needs a type of {', '.join(sorted(FIELD_TYPES))}")
            elif spec["type"] == "choice" and not (isinstance(spec.get("choices"), list) and spec["choices"]):
                out.append(f"classes.{key}: choice field {name} needs a non-empty choices list")
        required = c.get("required", [])
        if not isinstance(required, list):
            out.append(f"classes.{key}: required must be a list")
            continue
        for r in required:
            if r.startswith("fields."):
                ok = r[len("fields."):] in fields
            else:
                head, _, tail = str(r).partition(".")
                ok = (head in PROPOSAL_KEYS and not tail) or (head in ("seller", "buyer") and tail in PARTY_KEYS)
            if not ok:
                out.append(f"classes.{key}: required entry {r!r} is not a proposal key or a declared field")
        base = BUILTIN_CLASSES.get(key, CLASS_DEFAULTS)
        for part in ("name", "folder"):
            template = c.get(part, base[part])
            if not isinstance(template, str):
                out.append(f"classes.{key}: {part} must be a template string")
                continue
            out += [f"classes.{key}: {m}" for m in template_problems(template, {"fields": fields}, part == "folder", part)]
        if c.get("sign") not in (None, "positive", "negative"):
            out.append(f"classes.{key}: sign is positive, negative or null")
        if not set(c.get("checks", [])) <= {"ustg14"}:
            out.append(f"classes.{key}: the only known check is ustg14")
    return out


def template_problems(template, cls, folder=False, part="name"):
    out = []
    for hole in HOLE.findall(template):
        if hole in PLACEHOLDERS:
            continue
        if hole.startswith("fields.") and hole[len("fields."):] in cls.get("fields", {}):
            continue
        out.append(f"{part} template: unknown placeholder {{{hole}}}")
    literal = HOLE.sub("", template)
    if "{" in literal or "}" in literal:
        out.append(f"{part} template: unbalanced braces in {template!r}")
    if not template:
        out.append(f"{part} template must not be empty")
    if folder:
        if template.split("/")[0] != "{entity}":
            out.append(f"{part} template must start with {{entity}}")
        allowed = r"[A-Za-z0-9._ /-]*"
    else:
        allowed = r"[A-Za-z0-9._ -]*"
    if not re.fullmatch(allowed, literal.replace("{", "").replace("}", "")):
        out.append(f"{part} template: text outside placeholders may only use letters, digits, space, . _ -"
                   + (" and /" if folder else ""))
    return out


def default_config():
    return {
        "version": 1,
        "start_year": 2015,
        "tolerance": "0.01",
        "rate_tolerance": "0.02",
        "small_invoice_limit": "250.00",
        "entities": [],
        "categories": ["software", "hosting", "telecom", "hardware", "office", "travel", "hospitality",
                       "advisory", "fees-and-taxes", "marketing", "insurance", "rent", "other"],
    }


# ----------------------------------------------------------------------------------------------
# Entities and checks


def entity_names(e):
    return [n for n in ([e.get("name")] + list(e.get("names") or [])) if n]


def party_block(party):
    return squash(" ".join([party.get("name") or ""] + list(party.get("address") or [])))


def match_entities(cfg, party, kinds=("business",)):
    if not party:
        return []
    block = party_block(party)
    vat = norm_vat(party.get("vat_id"))
    hits = []
    for e in cfg["entities"]:
        if e.get("kind", "business") not in kinds:
            continue
        if vat and vat in {norm_vat(v) for v in e.get("vat_ids", [])}:
            hits.append(e["slug"])
            continue
        if any(squash(n) and squash(n) in block for n in entity_names(e)):
            hits.append(e["slug"])
    return sorted(set(hits))


def resolve_entity(cfg, d):
    """(entity, direction, problem) from the document's parties; never from file or folder names."""
    if d.get("entity"):
        if d["entity"] not in {e["slug"] for e in cfg["entities"]}:
            return None, None, f"entity {d['entity']!r} is not in config.json"
        return d["entity"], d.get("direction") or "in", None
    seller = match_entities(cfg, d["seller"])
    buyer = match_entities(cfg, d["buyer"])
    if d.get("direction") == "out" or (seller and not buyer):
        if len(seller) == 1:
            return seller[0], "out", None
        return None, None, "the seller matches several entities" if seller else "the seller matches no entity"
    if len(buyer) == 1:
        return buyer[0], "in", None
    if len(buyer) > 1:
        return None, None, f"the buyer matches several entities: {', '.join(buyer)}"
    private = match_entities(cfg, d["buyer"], kinds=("private",))
    if len(private) == 1:
        return private[0], "in", None
    if not d["buyer"].get("name"):
        return None, None, "no buyer on the document: set the entity (`paperwork set <id> entity=<slug>`)"
    return None, None, "the buyer matches no entity in config.json"


# ----------------------------------------------------------------------------------------------
# Rules


RULE_WHEN = {"counterparty", "vat_id", "text", "regex", "doc_type", "entity"}
RULE_SET = {"doc_type", "entity", "direction", "category", "tags"}
LAYERS = ("archive", "user")


def rule_problems(rule, classes, cfg, seen):
    rid = rule.get("id") if isinstance(rule, dict) else None
    if not isinstance(rid, str) or not rid:
        return ["a rule needs an id"]
    if rid in seen:
        return [f"{rid}: the id is used twice"]
    seen.add(rid)
    out = []
    unknown = sorted(set(rule) - {"id", "when", "set"})
    if unknown:
        out.append(f"{rid}: unknown keys {', '.join(unknown)}")
    when, sets = rule.get("when"), rule.get("set")
    if not isinstance(when, dict) or not when:
        out.append(f"{rid}: when needs at least one condition")
        when = {}
    if not isinstance(sets, dict) or not sets:
        out.append(f"{rid}: set needs at least one field")
        sets = {}
    for k in sorted(set(when) - RULE_WHEN):
        out.append(f"{rid}: unknown condition {k!r} (known: {', '.join(sorted(RULE_WHEN))})")
    if "text" in when and not (isinstance(when["text"], list) and when["text"]
                               and all(isinstance(t, str) and squash(t) for t in when["text"])):
        out.append(f"{rid}: text is a list of phrases")
    if "regex" in when:
        try:
            re.compile(when["regex"], re.I | re.M)
        except (re.error, TypeError) as e:
            out.append(f"{rid}: regex is invalid: {e}")
    for k in ("counterparty", "vat_id", "doc_type", "entity"):
        if k in when and not isinstance(when[k], str):
            out.append(f"{rid}: {k} is a string")
    entities = {e["slug"] for e in cfg["entities"]}
    if isinstance(when.get("doc_type"), str) and when["doc_type"] not in classes:
        out.append(f"{rid}: class {when['doc_type']!r} is not defined")
    if isinstance(when.get("entity"), str) and when["entity"] not in entities:
        out.append(f"{rid}: entity {when['entity']!r} is not in config.json")
    dt_set = sets.get("doc_type")
    if dt_set is not None and not (isinstance(dt_set, str) and dt_set in classes):
        dt_set = None
        out.append(f"{rid}: class {sets['doc_type']!r} is not defined")
    for k, v in sorted(sets.items()):
        if k.startswith("fields."):
            name = k[len("fields."):]
            specs = [c["fields"] for t, c in classes.items() if dt_set in (None, t) and name in c.get("fields", {})]
            if not specs:
                out.append(f"{rid}: no class declares field {name!r}")
                continue
            try:
                normalize_fields({name: v}, specs[0], dt_set or "?")
            except Fail as e:
                out.append(f"{rid}: {e}")
        elif k not in RULE_SET:
            out.append(f"{rid}: unknown field {k!r} (settable: {', '.join(sorted(RULE_SET))}, fields.<name>)")
        elif k == "entity" and not (isinstance(v, str) and v in entities):
            out.append(f"{rid}: entity {v!r} is not in config.json")
        elif k == "direction" and v not in ("in", "out"):
            out.append(f"{rid}: direction is in or out")
        elif k == "category" and not (isinstance(v, str) and v in cfg.get("categories", [])):
            out.append(f"{rid}: category {v!r} is not in config.json")
        elif k == "tags" and not (isinstance(v, list) and all(isinstance(t, str) and t for t in v)):
            out.append(f"{rid}: tags is a list of words")
    return out


def rules_problems(doc, classes, cfg, layer):
    if not isinstance(doc, dict) or set(doc) - {"rules"} or not isinstance(doc.get("rules"), list):
        return [f"rules[{layer}]: expected {{\"rules\": [...]}}"]
    seen = set()
    return [f"rules[{layer}].{m}" for rule in doc["rules"] for m in rule_problems(rule, classes, cfg, seen)]


def load_rules(archive):
    user = slugify(os.environ.get("PAPERWORK_USER", ""), 64)
    paths = {"archive": archive.p(STATE, "rules.json"),
             "user": archive.p(STATE, "rules", user + ".json") if user else None}
    rules, problems = [], []
    for layer in LAYERS:
        path = paths[layer]
        if not path or not os.path.isfile(path):
            continue
        try:
            doc = read_json(path)
        except ValueError as e:
            problems.append(f"rules[{layer}]: not valid JSON: {e}")
            continue
        found = rules_problems(doc, archive.classes, archive.config, layer)
        problems += found
        if not found:
            rules += [dict(r, layer=layer) for r in doc["rules"]]
    if problems:
        raise Fail("rules: " + "; ".join(problems))
    return rules


def match_rules(rules, record, text):
    """The rules whose conditions all hold. `record` carries data, counterparty and entity."""
    d = record["data"]
    party = d["buyer"] if d.get("direction") == "out" else d["seller"]
    block = squash(text)
    hits = []
    for r in rules:
        w = r["when"]
        checks = {
            "counterparty": lambda: record.get("counterparty") == w["counterparty"],
            "vat_id": lambda: bool(norm_vat(party.get("vat_id"))) and norm_vat(party.get("vat_id")) == norm_vat(w["vat_id"]),
            "text": lambda: all(squash(t) in block for t in w["text"]),
            "regex": lambda: re.search(w["regex"], text, re.I | re.M) is not None,
            "doc_type": lambda: d["doc_type"] == w["doc_type"],
            "entity": lambda: record.get("entity") == w["entity"],
        }
        if all(checks[k]() for k in w):
            hits.append(r)
    return hits


def decide(matches, skip=()):
    """Field -> (value, rule id), and the conflicts. The archive layer decides first, the user layer fills gaps.
    Fields in `skip` (a person edited them) are left alone and cannot conflict."""
    decided, conflicts, blocked = {}, [], set()
    tags = {}
    for layer in LAYERS:
        wanted = {}
        for r in (m for m in matches if m["layer"] == layer):
            for k, v in r["set"].items():
                if k in skip:
                    continue
                if k == "tags":
                    for t in v:
                        tags.setdefault(t, r["id"])
                else:
                    wanted.setdefault(k, []).append((len(r["when"]), v, r["id"]))
        for k, cands in sorted(wanted.items()):
            if k in decided or k in blocked:
                continue
            top = max(n for n, _, _ in cands)
            best = [(v, rid) for n, v, rid in cands if n == top]
            if any(v != best[0][0] for v, _ in best):
                blocked.add(k)
                conflicts.append(f"rules {', '.join(sorted({rid for _, rid in best}))} disagree on {k}: "
                                 + " vs ".join(json.dumps(v, ensure_ascii=False) for v in
                                               sorted({json.dumps(v, ensure_ascii=False) for v, _ in best})))
            else:
                decided[k] = best[0]
    if tags:
        decided["tags"] = (list(tags), min(tags.values()))
    return decided, conflicts


def apply_rules(archive, record):
    """Let the rules set fields on record["data"]. A person's edit beats a rule."""
    d = record["data"]
    party = d["buyer"] if d.get("direction") == "out" else d["seller"]
    view = {"data": d, "counterparty": archive.resolve_counterparty(party, create=False),
            "entity": d.get("entity") or resolve_entity(archive.config, d)[0]}
    matches = match_rules(archive.rules, view, archive.text(record))
    edited = {e["field"] for e in record.get("edits", [])}
    decided, conflicts = decide(matches, edited)
    data = json.loads(json.dumps(d))
    log, rule_fields = [], {}
    for k, (value, rid) in sorted(decided.items()):
        rule_fields[k] = rid
        old = get_path(data, k)
        if k == "tags":
            value = sorted(set(old or []) | set(value))
        elif old not in (None, "", [], {}) and old != value:
            log.append({"field": k, "from": old, "to": value, "rule": rid})
        set_path(data, k, value)
    logged = {e["field"] for e in log}
    log += [e for e in record.get("rule_log", [])
            if e["field"] not in logged and rule_fields.get(e["field"]) == e["rule"]]
    record["rule_log"], record["rule_conflicts"] = log, conflicts
    record["rule_fields"] = rule_fields
    applied = set(rule_fields.values())
    if "tags" in rule_fields:
        applied |= {m["id"] for m in matches if "tags" in m["set"]}
    record["rules"] = sorted(applied)
    if rule_fields:
        record["data"] = normalize_proposal(data, archive.classes)


def check(record, archive):
    """All checks of one record. Returns [{id, severity, message}]."""
    d = record["data"]
    cfg = archive.config
    out = []

    def add(cid, sev, msg):
        out.append({"id": cid, "severity": sev, "message": msg})

    cls = archive.classes.get(d["doc_type"])
    if cls is None:
        add("class", "error", f"class {d['doc_type']} is not in config.json")
        cls = {"money": False, "sign": None, "required": [], "checks": []}

    text_doc = record["media"] in ("pdf-text", "xml") or record.get("source") == "xml"
    ev_sev = "error" if text_doc else "warning"
    full = squash(archive.text(record)) + squash(archive.text(record, "raw"))
    if record.get("source") != "xml":
        def present(label, value):
            if value and squash(value) not in full:
                add(f"evidence:{label}", ev_sev, f"{label} {value!r} does not appear in the document text")
        present("seller.name", d["seller"].get("name"))
        present("buyer.name", d["buyer"].get("name"))
        present("invoice_number", d.get("invoice_number"))
        for side in ("seller", "buyer"):
            vat = d[side].get("vat_id")
            if vat and norm_vat(vat).casefold() not in re.sub(r"[.\-]", "", full):
                add(f"evidence:{side}.vat_id", ev_sev, f"{side} VAT ID {vat} does not appear in the document text")
        for key, printed in d["evidence"].items():
            if squash(printed) not in full:
                add(f"evidence:{key}", ev_sev, f"evidence for {key} {printed!r} does not appear in the document text")
        for key in ("issue_date", "due_date", "service_date"):
            printed = d["evidence"].get(key)
            if printed and d.get(key) and dt.date.fromisoformat(d[key]) not in date_candidates(printed):
                add(f"evidence:{key}", "error", f"{key} {d[key]} is not what {printed!r} says")
        for key in ("gross", "net"):
            printed = d["evidence"].get(key)
            if printed and d.get(key) is not None:
                c = amount_candidates(printed)
                v = Decimal(d[key])
                if v not in c and not (cls["sign"] == "negative" and abs(v) in {abs(x) for x in c}):
                    add(f"evidence:{key}", "error", f"{key} {d[key]} is not what {printed!r} says")
            elif d.get(key) is not None and key == "gross" and cls["money"]:
                add("evidence:gross", "error", "evidence.gross (the total as printed) is missing")
        if d.get("issue_date") and "issue_date" not in d["evidence"]:
            add("evidence:issue_date", "error", "evidence.issue_date (the date as printed) is missing")

    for key in cls["required"]:
        cur = d
        for part in key.split("."):
            cur = (cur or {}).get(part)
        if cur in (None, "", []):
            add(f"required:{key}", "error", f"{key} is missing")

    entity, direction, problem = resolve_entity(cfg, d)
    record["entity"], record["direction"] = entity, direction
    if problem:
        add("entity", "error", problem)
    elif direction == "in" and entity:
        ent = next(e for e in cfg["entities"] if e["slug"] == entity)
        if ent.get("kind") == "private":
            for e in cfg["entities"]:
                if e.get("kind", "business") == "business" and any(
                        squash(a) and squash(a) in party_block(d["buyer"]) for a in e.get("addresses", [])):
                    add("entity:shared-address", "warning",
                        f"billed to a private person at the address of {e['slug']}: check that it is private")
                    break
        bv = norm_vat(d["buyer"].get("vat_id"))
        if bv and ent.get("vat_ids") and bv not in {norm_vat(v) for v in ent["vat_ids"]}:
            add("entity:vat", "warning", f"buyer VAT ID {bv} is not {entity}'s")
        if match_entities(cfg, d["seller"]):
            add("intercompany", "warning", f"issued by {', '.join(match_entities(cfg, d['seller']))} to {entity}")

    if d.get("currency"):
        if not re.fullmatch(r"[A-Z]{3}", d["currency"]):
            add("currency", "error", f"currency {d['currency']!r} is not an ISO 4217 code")
        elif d["currency"] not in CURRENCIES:
            add("currency", "warning", f"currency {d['currency']} is unusual")
        printed = d["evidence"].get("gross", "")
        symbols = {"€": "EUR", "£": "GBP"}
        for sym, code in symbols.items():
            if sym in printed and d["currency"] != code:
                add("currency", "error", f"the total is printed with {sym} but currency is {d['currency']}")
        for code in re.findall(r"\b[A-Z]{3}\b", printed):
            if code in CURRENCIES and code != d["currency"]:
                add("currency", "error", f"the total is printed in {code} but currency is {d['currency']}")
        if "$" in printed and d["currency"] in ("EUR", "GBP", "CHF"):
            add("currency", "error", f"the total is printed with $ but currency is {d['currency']}")

    tol = Decimal(cfg.get("tolerance", "0.01"))
    rate_tol = Decimal(cfg.get("rate_tolerance", "0.02"))
    gross = Decimal(d["gross"]) if d.get("gross") else None
    net = Decimal(d["net"]) if d.get("net") else None
    tax = d["tax"]
    if tax:
        tax_net = sum((Decimal(t["net"] or 0) for t in tax), Decimal(0))
        tax_sum = sum((Decimal(t["tax"] or 0) for t in tax), Decimal(0))
        if net is not None and abs(tax_net - net) > tol:
            add("sum:tax-net", "error", f"net per tax rate adds up to {money(tax_net)}, not {money(net)}")
        base = net if net is not None else tax_net
        if gross is not None and abs(base + tax_sum - gross) > tol:
            add("sum:gross", "error", f"net {money(base)} + tax {money(tax_sum)} is not gross {money(gross)}")
        for t in tax:
            if t["rate"] is None or t["net"] is None or t["tax"] is None:
                add("tax:incomplete", "error", "every tax entry needs rate, net and tax")
                continue
            expect = Decimal(t["net"]) * Decimal(t["rate"]) / 100
            lines_at_rate = max(1, sum(1 for li in d["lines"] if li.get("tax_rate") == t["rate"]))
            if abs(expect - Decimal(t["tax"])) > rate_tol * lines_at_rate:
                add("tax:rate", "error", f"{t['rate']} % of {t['net']} is {money(expect)}, not {t['tax']}")
            if Decimal(t["rate"]) == 0 and Decimal(t["net"]) != 0 and not d["reverse_charge"] \
                    and not re.search(r"steuerfrei|exempt|innergemeinschaftlich|intra-community|§\s*4|art\.?\s*7|"
                                      r"reverse|steuerschuldumkehr|kleinunternehmer|§\s*19", full):
                add("tax:zero", "warning", "0 % tax without an exemption or reverse-charge note in the text")
    elif cls["money"] and gross is not None:
        if net is not None and abs(net - gross) > tol:
            add("tax:missing", "error", f"net {money(net)} and gross {money(gross)} differ but no tax is given")
        else:
            add("tax:none", "warning", "no tax breakdown on the document")

    lines = d["lines"]
    status = "none"
    if lines:
        nets = [li["net"] for li in lines]
        grosses = [li["gross"] for li in lines]
        if all(n is not None for n in nets) and net is not None:
            total = sum((Decimal(n) for n in nets), Decimal(0))
            status = "complete" if abs(total - net) <= tol else "partial"
        elif all(g is not None for g in grosses) and gross is not None:
            total = sum((Decimal(g) for g in grosses), Decimal(0))
            status = "complete" if abs(total - gross) <= tol else "partial"
        elif all(n is not None for n in nets) and gross is not None and not tax:
            total = sum((Decimal(n) for n in nets), Decimal(0))
            status = "complete" if abs(total - gross) <= tol else "partial"
        else:
            status = "partial"
        if status == "partial":
            add("lines:sum", "warning", "the lines do not add up to the total")
        for i, li in enumerate(lines):
            if li["quantity"] and li["unit_price"] and li["net"]:
                expect = Decimal(li["quantity"]) * Decimal(li["unit_price"])
                if abs(expect - Decimal(li["net"])) > max(tol, abs(expect) * Decimal("0.001")):
                    add("lines:arithmetic", "warning", f"line {i + 1}: {li['quantity']} × {li['unit_price']} is not {li['net']}")
    record["lines_status"] = status

    if gross is not None:
        if cls["sign"] == "negative" and gross > 0:
            add("sign", "error", "a credit note has a negative total in this archive")
        if cls["sign"] == "positive" and gross < 0:
            add("sign", "error", "an invoice with a negative total: is it a credit note (cn)?")

    if d.get("issue_date"):
        issued = dt.date.fromisoformat(d["issue_date"])
        if issued.year < int(cfg.get("start_year", 2000)):
            add("date:range", "error", f"issued {issued} is before the archive's start year")
        ingested = dt.date.fromisoformat(record["ingested"])
        if issued > ingested:
            add("date:future", "error", f"issued {issued} is after the document arrived ({ingested})")
        if d.get("due_date") and dt.date.fromisoformat(d["due_date"]) < issued:
            add("date:due", "warning", "due before it was issued")

    for side in ("seller", "buyer"):
        ok = vat_ok(d[side].get("vat_id"))
        if ok is False:
            add(f"vat:{side}", "warning", f"{side} VAT ID {d[side]['vat_id']} is not valid")
    if d.get("iban") and iban_ok(d["iban"]) is False:
        add("iban", "warning", f"IBAN {d['iban']} fails its check digits")

    if direction == "in" and "ustg14" in cls["checks"]:
        seller_de = (d["seller"].get("country") == "DE"
                     or norm_vat(d["seller"].get("vat_id")).startswith("DE")
                     or bool(d["seller"].get("tax_number")))
        if seller_de:
            small = gross is not None and abs(gross) <= Decimal(cfg.get("small_invoice_limit", "250"))
            need = {"seller.address": bool(d["seller"]["address"]), "lines": bool(lines),
                    "tax rate": bool(tax) or d["reverse_charge"]}
            if not small:
                need.update({
                    "buyer.address": bool(d["buyer"]["address"]),
                    "seller VAT ID or tax number": bool(d["seller"].get("vat_id") or d["seller"].get("tax_number")),
                    "service date or period": bool(d.get("service_date") or d.get("service_period")),
                    "invoice number": bool(d.get("invoice_number")),
                })
            for item, present_ in need.items():
                if not present_:
                    add("ustg14", "warning", f"§14 UStG: {item} missing" + (" (§33 UStDV small invoice)" if small else ""))
    waived = {w["check"] for w in record.get("waived", [])}
    for c in out:
        if c["id"] in waived:
            c["severity"] = "waived"
    return out


def compute(record, archive):
    if not record.get("data"):
        record["checks"] = []
        record["entity"] = record["direction"] = record["counterparty"] = None
        return
    d = record["data"]
    record["checks"] = check(record, archive)
    party = d["seller"] if record["direction"] != "out" else d["buyer"]
    record["counterparty"] = archive.resolve_counterparty(party)
    v = archive.vendor(record["counterparty"]) if record["counterparty"] else None
    if v and v.get("category") and not d.get("category"):
        d["category"] = v["category"]
    if d.get("category") and d["category"] not in archive.config.get("categories", []):
        record["checks"].append({"id": "category", "severity": "warning",
                                 "message": f"category {d['category']!r} is not in config.json"})
    for msg in record.get("rule_conflicts", []):
        record["checks"].append({"id": "rule:conflict", "severity": "error", "message": msg})
    for entry in record.get("rule_log", []):
        record["checks"].append({"id": "rule:override", "severity": "warning",
                                 "message": f"rule {entry['rule']} changed {entry['field']} "
                                            f"from {entry['from']!r} to {entry['to']!r}"})
    if "entity" in record.get("rule_fields", {}):
        found = resolve_entity(archive.config, dict(d, entity=None))[0]
        if found and found != d.get("entity"):
            record["checks"].append({"id": "rule:entity", "severity": "error",
                                     "message": f"rule {record['rule_fields']['entity']} sets entity {d.get('entity')} "
                                                f"but the document is addressed to {found}"})
    cls = archive.classes.get(d["doc_type"])
    if cls and not any(c["severity"] == "error" for c in record["checks"]):
        problem = path_problem(record, archive, cls)
        if problem:
            record["checks"].append({"id": problem[0], "severity": "error", "message": problem[1]})


def status_of(record, archive=None):
    if record.get("unsupported"):
        return "review"
    if record.get("duplicate_of"):
        return "duplicate"
    if not record.get("data"):
        return "new"
    if any(c["severity"] == "error" for c in record.get("checks", [])):
        return "review"
    if archive is not None and record.get("path") == target_path(record, archive):
        return "filed"
    return "ok"


# ----------------------------------------------------------------------------------------------
# Names and paths


def placeholder_values(record, cls):
    d = record["data"]
    fields = d.get("fields") or {}
    issue = d.get("issue_date") or "0000-00-00"

    def val(v):
        return safe_number(str(v)) if v not in (None, "") else "-"

    values = {
        "issue_date": issue, "due_date": val(d.get("due_date")), "service_date": val(d.get("service_date")),
        "year": issue[:4] if issue[:4].isdigit() else "0000", "class": d["doc_type"],
        "counterparty": record.get("counterparty") or "unknown", "number": safe_number(d.get("invoice_number") or "-"),
        "amount": f"{d['gross']}{d['currency'] or ''}" if d.get("gross") is not None else "-",
        "id": record["id"][:8], "entity": val(record.get("entity")), "direction": val(record.get("direction")),
        "category": val(d.get("category")),
    }
    for name in cls.get("fields", {}):
        values[f"fields.{name}"] = val(fields.get(name))
    return values


def render(template, values):
    return HOLE.sub(lambda m: values[m.group(1)], template)


def canonical_name(record, cls, values=None):
    values = values or placeholder_values(record, cls)
    return render(cls["name"], values), MEDIA_EXT.get(record["kind"], "bin")


def folder_problem(record, folder):
    segments = folder.split("/")
    if any(s in ("", "-", ".", "..") or s.startswith("_") for s in segments):
        return f"folder {folder!r} has an empty, dotted or underscore segment"
    if segments[0] != record.get("entity"):
        return f"folder {folder!r} does not start with the entity {record.get('entity')!r}"
    return None


def rendered_path(record, archive, cls):
    """(folder, file name with extension), shortened to fit MAX_PATH where the values allow it."""
    values = placeholder_values(record, cls)

    def paths():
        stem, ext = canonical_name(record, cls, values)
        return render(cls["folder"], values), f"{stem}.{ext}"

    def over():
        return len(os.path.join(archive.root, *paths())) - MAX_PATH

    names = [h for h in HOLE.findall(cls["name"]) if h.startswith("fields.")]
    for key in ["number", "counterparty", *names]:
        if over() > 0:
            values[key] = values[key][: max(1, len(values[key]) - over())]
    return paths()


def path_problem(record, archive, cls):
    """The first reason the rendered path is unusable, as (check id, message), or None."""
    folder, name = rendered_path(record, archive, cls)
    problem = folder_problem(record, folder)
    if problem:
        return "path:folder", problem
    if len(os.path.join(archive.root, folder, name)) > MAX_PATH:
        return "path:length", f"the path is longer than {MAX_PATH} characters even after shortening"
    return None


def target_path(record, archive):
    st_dup = record.get("duplicate_of")
    ext = MEDIA_EXT.get(record["kind"], "bin")
    if st_dup:
        return f"{DUPLICATES}/{record['id'][:8]}_duplicate-of-{st_dup[:8]}.{ext}"
    if not record.get("data") and not record.get("unsupported"):
        return record.get("path")  # not read yet: it stays where it is
    cls = archive.classes.get(record["data"]["doc_type"]) if record.get("data") else None
    # path problems are re-checked here, never read from the (waivable) checks
    if (record.get("unsupported") or cls is None or path_problem(record, archive, cls)
            or any(c["severity"] == "error" for c in record.get("checks", []))):
        if record.get("path", "").startswith(INBOX + "/") or record.get("path", "").startswith(REVIEW + "/"):
            stem = safe_number(os.path.splitext(record.get("original_name") or "")[0], 60)
            return f"{REVIEW}/{record['id'][:8]}_{stem}.{ext}"
        return record.get("path")
    folder, name = rendered_path(record, archive, cls)
    return f"{folder}/{name}"


# ----------------------------------------------------------------------------------------------
# Duplicates


def doc_key(record):
    d = record.get("data") or {}
    if not d.get("invoice_number") or not record.get("entity"):
        return None
    return (record["entity"], record.get("counterparty"), d["doc_type"], safe_number(d["invoice_number"]).lower())


def assign_duplicates(archive):
    """Same document as different files: the best source stays, the others are duplicates."""
    groups = {}
    for r in archive.records.values():
        r.pop("duplicate_of", None)
        if r.get("data") and not any(c["severity"] == "error" for c in r.get("checks", [])):
            k = doc_key(r)
            if k:
                groups.setdefault(k, []).append(r)
    for rs in groups.values():
        if len(rs) < 2:
            continue
        grosses = {r["data"].get("gross") for r in rs}
        if len(grosses) > 1:
            for r in rs:
                r["checks"].append({"id": "duplicate:conflict", "severity": "error",
                                    "message": "another document has the same number but a different total: "
                                               + ", ".join(sorted(x["id"][:8] for x in rs if x is not r))})
            continue
        rs.sort(key=lambda r: (SOURCE_RANK.get(r["media"], 9), r["id"]))
        for r in rs[1:]:
            r["duplicate_of"] = rs[0]["id"]
    suspects = {}
    for r in archive.records.values():
        d = r.get("data")
        if not d or r.get("duplicate_of") or not d.get("gross") or not d.get("issue_date"):
            continue
        suspects.setdefault((r.get("counterparty"), d["issue_date"], d["gross"]), []).append(r)
    for rs in suspects.values():
        if len(rs) < 2:
            continue
        unnumbered = [r for r in rs if not r["data"].get("invoice_number")]
        if unnumbered:
            for r in unnumbered:
                if not any(c["id"] == "duplicate:suspected" for c in r["checks"]):
                    r["checks"].append({"id": "duplicate:suspected", "severity": "error",
                                        "message": "same counterparty, date and total as "
                                                   + ", ".join(sorted(x["id"][:8] for x in rs if x is not r))
                                                   + "; waive this check if it is a separate document"})
    waived_all(archive)


def waived_all(archive):
    for r in archive.records.values():
        waived = {w["check"] for w in r.get("waived", [])}
        for c in r.get("checks", []):
            if c["id"] in waived:
                c["severity"] = "waived"


def recompute_all(archive):
    for r in archive.records.values():
        compute(r, archive)
    assign_duplicates(archive)
    for r in archive.records.values():
        r["status"] = status_of(r, archive)


def save_all(archive):
    for r in archive.records.values():
        archive.save(r)
    archive.save_vendors()


# ----------------------------------------------------------------------------------------------
# Commands


def emit(obj):
    sys.stdout.write(dumps(obj))


def cmd_init(args):
    root = os.path.abspath(args.root)
    for d in (STATE, INBOX, REVIEW, DUPLICATES, EXPORTS, f"{STATE}/docs", f"{STATE}/derived",
              f"{STATE}/proposals", f"{STATE}/templates", f"{STATE}/plans"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    cfg = os.path.join(root, STATE, "config.json")
    created = False
    if not os.path.exists(cfg):
        write_state(cfg, dumps(default_config()))
        created = True
    if not os.path.exists(os.path.join(root, STATE, "vendors.json")):
        write_state(os.path.join(root, STATE, "vendors.json"), dumps({"vendors": []}))
    emit({"root": root, "config_created": created,
          "next": "add your entities to _paperwork/config.json (the setup skill asks for them)"})
    return EXIT_OK


def cmd_doctor(args):
    archive = Archive(args.root)
    versions = tool_versions()
    problems = []
    if not archive.config["entities"]:
        problems.append("no entities in config.json")
    for k in ("poppler", "tesseract"):
        if versions[k] == "missing":
            problems.append(f"{k} is missing")
    langs = tool(["tesseract", "--list-langs"], check=False)
    for lang in ("deu", "eng"):
        if not re.search(rf"^{lang}$", langs, re.M):
            problems.append(f"tesseract language {lang} is missing")
    locked = os.path.exists(archive.p(STATE, "lock"))
    emit({"root": archive.root, "tools": versions, "entities": [e["slug"] for e in archive.config["entities"]],
          "locked": locked, "problems": problems})
    return EXIT_CHECK if problems else EXIT_OK


def walk_files(archive, top, skip_top=()):
    base = archive.p(top) if top else archive.root
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        rel_dir = archive.rel(dirpath)
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".")
                             and not (rel_dir == "." and d in skip_top))
        for name in sorted(filenames):
            low = name.lower()
            if low in IGNORED_FILES or name.startswith(".") or name.startswith("~$") or low.endswith((".tmp", ".partial")):
                continue
            out.append(os.path.join(dirpath, name))
    return sorted(out, key=lambda p: archive.rel(p))


def ingest_file(archive, path, report):
    rel = archive.rel(path)
    try:
        sha = sha256_file(path)
    except OSError as e:
        report["unreadable"].append({"path": rel, "error": str(e)})
        return
    if sha in archive.records:
        r = archive.records[sha]
        if r["path"] == rel or any(c["path"] == rel for c in r.get("copies", [])):
            return
        if not os.path.exists(archive.p(r["path"])):
            archive.journal([{"op": "relink", "from": r["path"], "to": rel, "sha256": sha, "at": now()}])
            r["path"] = rel
            report["relinked"].append({"id": sha[:8], "path": rel})
            return
        r.setdefault("copies", []).append({"path": rel, "original_name": os.path.basename(path)})
        r["copies"].sort(key=lambda c: c["path"])
        report["exact_duplicates"].append({"id": sha[:8], "copy": rel, "of": r["path"]})
        return
    kind = sniff(path)
    record = {"id": sha, "path": rel, "original_name": os.path.basename(path), "first_seen": rel,
              "ingested": archive.today.isoformat(), "size": os.path.getsize(path), "kind": kind,
              "media": None, "pages": 0, "images": [], "einvoice": None, "source": None, "data": None,
              "checks": [], "waived": [], "edits": [], "copies": [], "tools": tool_versions()}
    archive.records[sha] = record
    if kind in ("unknown", "heic"):
        record["unsupported"] = f"cannot read {kind} files; convert it (e.g. to PDF or JPEG) and drop that in"
        record["media"] = kind
        report["unsupported"].append({"id": sha[:8], "path": rel, "kind": kind})
        return
    try:
        info = derive(archive, sha, path, kind)
    except (RuntimeError, OSError, ET.ParseError) as e:
        record["unsupported"] = f"could not read it: {e}"
        record["media"] = "unreadable"
        report["unsupported"].append({"id": sha[:8], "path": rel, "error": str(e)})
        return
    record.update({"media": info["media"], "pages": info["pages"], "images": info["images"],
                   "einvoice": info["einvoice"], "embedded_xml": info["embedded_xml"]})
    extract(archive, record, report)


def extract(archive, record, report):
    """The deterministic routes: the e-invoice XML, then a vendor template. Claude reads the rest."""
    record.pop("template_error", None)
    sha = record["id"]
    if record.get("embedded_xml"):
        xml_path = archive.p(record["embedded_xml"])
    elif record.get("einvoice"):
        xml_path = archive.p(record["path"])
    else:
        xml_path = None
    if xml_path:
        try:
            record["data"] = normalize_proposal(parse_einvoice(xml_path), archive.classes)
        except (Fail, Exception) as e:  # an unreadable e-invoice falls back to reading the text
            record["einvoice_error"] = str(e)
        else:
            apply_rules(archive, record)
            record["source"] = "xml"
            report["from_xml"].append(sha[:8])
            return
    text = archive.text(record)
    matches = [v for v in archive.vendors["vendors"] if v.get("template")
               and all(squash(m) in squash(text) for m in v["template"].get("match", []))]
    if len(matches) == 1:
        v = matches[0]
        try:
            record["data"] = normalize_proposal(apply_template(v["template"], text), archive.classes)
        except (Fail, ValueError, re.error, KeyError) as e:
            record["template_error"] = f"{v['slug']}: {e}"
            report["template_failed"].append({"id": sha[:8], "vendor": v["slug"], "error": str(e)})
        else:
            apply_rules(archive, record)
            record["source"] = f"template:{v['slug']}"
            report["from_template"].append({"id": sha[:8], "vendor": v["slug"]})


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def cmd_ingest(args):
    archive = Archive(args.root)
    if not archive.config["entities"]:
        raise Fail("config.json has no entities yet: add them first (the setup skill)")
    with archive.lock():
        report = {k: [] for k in ("new", "exact_duplicates", "relinked", "unsupported", "unreadable",
                                  "from_xml", "from_template", "template_failed")}
        before = set(archive.records)
        files = walk_files(archive, INBOX)
        if args.adopt:
            files += walk_files(archive, None, skip_top=MANAGED_TOP)
            files += walk_files(archive, REVIEW) + walk_files(archive, DUPLICATES)
        for f in sorted(set(files), key=lambda p: archive.rel(p)):
            ingest_file(archive, f, report)
        for r in sorted(archive.records.values(), key=lambda r: r["id"]):
            if r["id"] not in set(archive.records) - before and not r.get("data") and not r.get("unsupported"):
                extract(archive, r, report)
        report["new"] = sorted(i[:8] for i in set(archive.records) - before)
        recompute_all(archive)
        save_all(archive)
        report["status"] = summary(archive)
        emit(report)
    return EXIT_OK


def summary(archive):
    counts = {}
    for r in archive.records.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return dict(sorted(counts.items()))


def cmd_pending(args):
    archive = Archive(args.root)
    out = []
    for r in sorted(archive.records.values(), key=lambda r: r["id"]):
        if r["status"] != "new" or r.get("unsupported"):
            continue
        item = {"id": r["id"][:12], "media": r["media"], "pages": r["pages"],
                "text": archive.p(STATE, "derived", r["id"], "text.txt"),
                "images": [archive.p(i) for i in r["images"]],
                "proposal": archive.p(STATE, "proposals", r["id"][:12] + ".json")}
        if r["media"] in ("pdf-scan", "pdf-mixed", "image"):
            item["read_also"] = "the page images: OCR text can be wrong; the images are the truth"
        if r.get("template_error"):
            item["template_error"] = r["template_error"]
        out.append(item)
    emit({"pending": out, "count": len(out),
          "how": "write each proposal (`paperwork schema`) to its proposal path, then `paperwork record <id> <proposal>`"})
    return EXIT_OK


def cmd_schema(args):
    try:
        classes = Archive(args.root).classes
    except Fail:
        classes = BUILTIN_CLASSES
    schema = dict(SCHEMA, doc_type={k: c["label"] for k, c in classes.items()})
    schema["fields"] = {k: c["fields"] for k, c in classes.items() if c["fields"]}
    emit(schema)
    return EXIT_OK


def record_view(r, archive):
    return {"id": r["id"], "status": r["status"], "path": r["path"], "target": target_path(r, archive),
            "entity": r.get("entity"), "direction": r.get("direction"), "counterparty": r.get("counterparty"),
            "media": r["media"], "source": r.get("source"), "lines_status": r.get("lines_status"),
            "duplicate_of": r.get("duplicate_of"), "copies": r.get("copies"),
            "problems": [c for c in r.get("checks", []) if c["severity"] == "error"],
            "warnings": [c for c in r.get("checks", []) if c["severity"] == "warning"],
            "waived": r.get("waived", []), "unsupported": r.get("unsupported")}


def cmd_record(args):
    archive = Archive(args.root)
    with archive.lock():
        r = archive.find(args.id)
        if r.get("unsupported"):
            raise Fail(f"{r['id'][:8]} cannot be read: {r['unsupported']}")
        if r.get("source") == "xml" and not args.force:
            raise Fail("this document was read from its e-invoice XML; pass --force to replace that")
        with open(args.proposal, encoding="utf-8") as f:
            try:
                proposal = json.load(f)
            except json.JSONDecodeError as e:
                raise Fail(f"{args.proposal}: not valid JSON: {e}")
        if r.get("data") and r.get("source") in ("claude", "user") and not args.force:
            raise Fail("this document already has fields; use `paperwork set` to change them or --force to replace")
        r["data"] = normalize_proposal(proposal, archive.classes)
        apply_rules(archive, r)
        r["source"] = "claude" if not args.user else "user"
        recompute_all(archive)
        save_all(archive)
        view = record_view(r, archive)
        emit(view)
    return EXIT_REVIEW if view["status"] == "review" else EXIT_OK


def set_path(d, key, value):
    parts = key.split(".")
    cur = d
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def get_path(d, key):
    cur = d
    for part in key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def cmd_set(args):
    archive = Archive(args.root)
    with archive.lock():
        r = archive.find(args.id)
        if not r.get("data"):
            raise Fail("this document has no fields yet: record a proposal first")
        data = json.loads(json.dumps(r["data"]))
        changes = []
        for item in args.assignments:
            if "=" not in item:
                raise Fail(f"write assignments as field=value, got {item!r}")
            key, raw = item.split("=", 1)
            try:
                value = json.loads(raw)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    value = raw
            except json.JSONDecodeError:
                value = raw
            if value == "":
                value = None
            changes.append({"field": key, "old": get_path(data, key), "new": value})
            set_path(data, key, value)
        normalized = normalize_proposal(data, archive.classes)
        r["data"] = normalized
        r["edits"] = r.get("edits", []) + [dict(c, at=now()) for c in changes]
        apply_rules(archive, r)
        if r.get("source") == "claude" or (r.get("source") or "").startswith("template:"):
            r["source_before_edit"] = r.get("source_before_edit") or r["source"]
        r["source"] = "user"
        recompute_all(archive)
        save_all(archive)
        view = record_view(r, archive)
        emit(view)
    return EXIT_REVIEW if view["status"] == "review" else EXIT_OK


def cmd_accept(args):
    archive = Archive(args.root)
    with archive.lock():
        r = archive.find(args.id)
        ids = {c["id"] for c in r.get("checks", [])}
        if args.check not in ids:
            raise Fail(f"{r['id'][:8]} has no check {args.check!r}; it has: {', '.join(sorted(ids)) or 'none'}")
        if args.check.startswith("path:"):
            raise Fail(f"{args.check} cannot be accepted: fix the class templates or the document's fields")
        if not args.reason.strip():
            raise Fail("give a reason")
        r["waived"] = [w for w in r.get("waived", []) if w["check"] != args.check] + [
            {"check": args.check, "reason": args.reason.strip(), "at": now()}]
        recompute_all(archive)
        save_all(archive)
        view = record_view(r, archive)
        emit(view)
    return EXIT_REVIEW if view["status"] == "review" else EXIT_OK


def cmd_reextract(args):
    archive = Archive(args.root)
    with archive.lock():
        r = archive.find(args.id)
        if r.get("data"):
            r.setdefault("history", []).append({"source": r.get("source"), "data": r["data"], "at": now()})
        r["data"] = None
        r["source"] = None
        recompute_all(archive)
        save_all(archive)
        emit(record_view(r, archive))
    return EXIT_OK


def cmd_show(args):
    archive = Archive(args.root)
    r = archive.find(args.id)
    view = record_view(r, archive)
    view["data"] = r.get("data")
    view["text"] = archive.p(STATE, "derived", r["id"], "text.txt")
    view["images"] = [archive.p(i) for i in r.get("images", [])]
    view["original_name"] = r.get("original_name")
    emit(view)
    return EXIT_OK


def cmd_list(args):
    archive = Archive(args.root)
    rows = []
    for r in sorted(archive.records.values(), key=lambda r: ((r.get("data") or {}).get("issue_date") or "", r["id"])):
        if args.status and r["status"] != args.status:
            continue
        d = r.get("data") or {}
        rows.append({"id": r["id"][:12], "status": r["status"], "entity": r.get("entity"),
                     "date": d.get("issue_date"), "counterparty": r.get("counterparty"),
                     "type": d.get("doc_type"), "number": d.get("invoice_number"),
                     "gross": d.get("gross"), "currency": d.get("currency"), "path": r["path"],
                     "problems": [c["message"] for c in r.get("checks", []) if c["severity"] == "error"]
                     + ([r["unsupported"]] if r.get("unsupported") else [])})
    emit({"documents": rows, "count": len(rows)})
    return EXIT_OK


def cmd_status(args):
    archive = Archive(args.root)
    inbox = [archive.rel(p) for p in walk_files(archive, INBOX)]
    known = {r["path"] for r in archive.records.values()} | {
        c["path"] for r in archive.records.values() for c in r.get("copies", [])}
    unregistered = [p for p in inbox if p not in known]
    plan = build_plan(archive)
    emit({"root": archive.root, "documents": summary(archive), "inbox_unregistered": len(unregistered),
          "planned_moves": len(plan["ops"])})
    return EXIT_OK


# plan / apply / undo -----------------------------------------------------------------------------


def build_plan(archive):
    ops = []
    taken = {}
    for r in sorted(archive.records.values(), key=lambda r: r["id"]):
        target = target_path(r, archive)
        if target and target != r["path"]:
            ops.append({"op": "move", "id": r["id"], "from": r["path"], "to": target, "sha256": r["id"]})
        ext = MEDIA_EXT.get(r["kind"], "bin")
        for n, c in enumerate(r.get("copies", []), 1):
            want = f"{DUPLICATES}/{r['id'][:8]}_copy-{n}.{ext}"
            if c["path"] != want:
                ops.append({"op": "move", "id": r["id"], "copy": n, "from": c["path"], "to": want, "sha256": r["id"]})
    for op in ops:
        taken.setdefault(op["to"], []).append(op)
    conflicts = [t for t, o in taken.items() if len(o) > 1]
    ops = [o for o in ops if o["to"] not in conflicts]
    body = json.dumps(ops, sort_keys=True)
    return {"plan": hashlib.sha256(body.encode()).hexdigest()[:12], "ops": ops, "conflicts": sorted(conflicts)}


def cmd_plan(args):
    archive = Archive(args.root)
    plan = build_plan(archive)
    path = args.out or archive.p(STATE, "plans", plan["plan"] + ".json")
    write_state(path, dumps(plan))
    groups = {}
    for op in plan["ops"]:
        kind = op["to"].split("/")[0]
        groups.setdefault("to " + (kind if kind in (REVIEW, DUPLICATES) else "archive"), []).append(
            {"from": op["from"], "to": op["to"]})
    emit({"plan": plan["plan"], "file": path, "moves": len(plan["ops"]), "conflicts": plan["conflicts"],
          "by_destination": groups, "apply": f"paperwork apply {path}"})
    return EXIT_OK


def cmd_apply(args):
    archive = Archive(args.root)
    with archive.lock():
        plan = read_json(args.plan)
        done, skipped, entries = [], [], []
        for op in plan["ops"]:
            src, dst = archive.p(op["from"]), archive.p(op["to"])
            r = archive.records.get(op["id"])
            reason = None
            if r is None:
                reason = "the document is no longer in the archive"
            elif not os.path.exists(src):
                reason = "the source is gone"
            elif sha256_file(src) != op["sha256"]:
                reason = "the source changed since the plan was made"
            elif os.path.lexists(dst) and not os.path.samefile(src, dst):
                reason = "the target exists; nothing is overwritten"
            if reason:
                skipped.append({"from": op["from"], "to": op["to"], "reason": reason})
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            how = "move"
            try:
                os.rename(src, dst)
            except OSError as e:
                if e.errno != 18:  # EXDEV: another volume
                    raise
                shutil.copy2(src, dst)
                if sha256_file(dst) != op["sha256"]:
                    raise Fail(f"copy of {op['from']} does not match its hash", EXIT_CHECK)
                how = "copy"
            entries.append({"batch": plan["plan"], "op": how, "from": op["from"], "to": op["to"],
                            "sha256": op["sha256"], "at": now()})
            if "copy" in op:
                r["copies"][op["copy"] - 1]["path"] = op["to"]
            elif how == "move":
                r["path"] = op["to"]
            done.append({"from": op["from"], "to": op["to"], "op": how})
            archive.journal([entries[-1]])
        recompute_all(archive)
        save_all(archive)
        emit({"plan": plan["plan"], "applied": len(done), "skipped": skipped, "undo": f"paperwork undo {plan['plan']}",
              "status": summary(archive)})
    return EXIT_CHECK if skipped else EXIT_OK


def cmd_undo(args):
    archive = Archive(args.root)
    with archive.lock():
        entries = [e for e in archive.journal_entries() if e.get("batch") == args.batch and e["op"] == "move"]
        undone = {e.get("undoes") for e in archive.journal_entries() if e.get("undoes")}
        if not entries:
            raise Fail(f"no moves in batch {args.batch!r}")
        if args.batch in undone:
            raise Fail(f"batch {args.batch} was already undone")
        back, skipped = [], []
        for e in reversed(entries):
            src, dst = archive.p(e["to"]), archive.p(e["from"])
            if not os.path.exists(src) or sha256_file(src) != e["sha256"]:
                skipped.append({"path": e["to"], "reason": "not where the move put it, or changed"})
                continue
            if os.path.lexists(dst):
                skipped.append({"path": e["from"], "reason": "something is in the old place; nothing is overwritten"})
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
            r = archive.records.get(e["sha256"])
            if r:
                if r["path"] == e["to"]:
                    r["path"] = e["from"]
                for c in r.get("copies", []):
                    if c["path"] == e["to"]:
                        c["path"] = e["from"]
            archive.journal([{"batch": "undo-" + args.batch, "undoes": args.batch, "op": "move",
                              "from": e["to"], "to": e["from"], "sha256": e["sha256"], "at": now()}])
            back.append(e["from"])
        recompute_all(archive)
        save_all(archive)
        emit({"undone": len(back), "skipped": skipped})
    return EXIT_CHECK if skipped else EXIT_OK


# verify --------------------------------------------------------------------------------------------


def cmd_verify(args):
    archive = Archive(args.root)
    problems = []
    known = set()
    for r in sorted(archive.records.values(), key=lambda r: r["id"]):
        for path in [r["path"]] + [c["path"] for c in r.get("copies", [])]:
            known.add(path)
            full = archive.p(path)
            if not os.path.exists(full):
                problems.append({"id": r["id"][:8], "path": path, "problem": "missing"})
            elif sha256_file(full) != r["id"]:
                problems.append({"id": r["id"][:8], "path": path, "problem": "content changed"})
    for f in walk_files(archive, None, skip_top={STATE, EXPORTS}):
        rel = archive.rel(f)
        if rel not in known:
            problems.append({"path": rel, "problem": "not registered" + (" (in the inbox)" if rel.startswith(INBOX + "/") else "")})
    emit({"documents": len(archive.records), "problems": problems, "ok": not problems})
    return EXIT_CHECK if problems else EXIT_OK


# export ----------------------------------------------------------------------------------------------

DOC_COLUMNS = ["id", "entity", "direction", "doc_type", "issue_date", "service_date", "service_start",
               "service_end", "due_date", "counterparty", "seller_name", "seller_vat_id", "seller_tax_number",
               "seller_address", "seller_country", "buyer_name", "buyer_vat_id", "billing_address",
               "buyer_country", "invoice_number", "refers_to", "currency", "net", "tax", "gross", "tax_rates",
               "reverse_charge", "paid", "payment_method", "iban", "category", "tags", "lines_status", "status",
               "duplicate_of", "source", "media", "path", "original_name", "warnings"]
LINE_COLUMNS = ["id", "line", "entity", "direction", "issue_date", "counterparty", "invoice_number", "currency",
                "description", "quantity", "unit", "unit_price", "net", "tax_rate", "gross"]
VAT_COLUMNS = ["entity", "month", "direction", "currency", "rate", "reverse_charge", "documents", "net", "tax", "gross"]
VENDOR_COLUMNS = ["entity", "year", "counterparty", "name", "vat_ids", "currency", "documents", "net", "gross"]
ISSUE_COLUMNS = ["id", "entity", "status", "severity", "check", "message", "path"]
NUMERIC = {"net", "tax", "gross", "quantity", "unit_price", "rate", "tax_rate"}


def table_text(columns, rows, dialect):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";" if dialect == "de" else ",", lineterminator="\n")
    w.writerow(columns)
    for row in rows:
        out = []
        for c in columns:
            v = row.get(c)
            if v is None:
                v = ""
            elif isinstance(v, bool):
                v = "true" if v else "false"
            v = str(v)
            if dialect == "de" and c in NUMERIC and re.fullmatch(r"-?\d+(\.\d+)?", v):
                v = v.replace(".", ",")
            out.append(v)
        w.writerow(out)
    return ("﻿" if dialect == "de" else "") + buf.getvalue()


def export_rows(archive, records):
    docs, lines, issues = [], [], []
    vat, vendors = {}, {}
    classes = archive.classes
    for r in sorted(records, key=lambda r: (r.get("entity") or "", (r.get("data") or {}).get("issue_date") or "", r["id"])):
        d = r.get("data") or {}
        seller, buyer = d.get("seller") or {}, d.get("buyer") or {}
        sp = d.get("service_period") or {}
        tax = d.get("tax") or []
        docs.append({
            "id": r["id"], "entity": r.get("entity"), "direction": r.get("direction"), "doc_type": d.get("doc_type"),
            "issue_date": d.get("issue_date"), "service_date": d.get("service_date"), "service_start": sp.get("start"),
            "service_end": sp.get("end"), "due_date": d.get("due_date"), "counterparty": r.get("counterparty"),
            "seller_name": seller.get("name"), "seller_vat_id": seller.get("vat_id"),
            "seller_tax_number": seller.get("tax_number"), "seller_address": " | ".join(seller.get("address") or []),
            "seller_country": seller.get("country"), "buyer_name": buyer.get("name"), "buyer_vat_id": buyer.get("vat_id"),
            "billing_address": " | ".join(buyer.get("address") or []), "buyer_country": buyer.get("country"),
            "invoice_number": d.get("invoice_number"), "refers_to": " | ".join(d.get("refers_to") or []),
            "currency": d.get("currency"), "net": d.get("net"),
            "tax": money(sum((Decimal(t["tax"]) for t in tax if t.get("tax")), Decimal(0))) if tax else None,
            "gross": d.get("gross"), "tax_rates": " | ".join(f"{t['rate']}" for t in tax),
            "reverse_charge": d.get("reverse_charge") if d else None, "paid": d.get("paid"),
            "payment_method": d.get("payment_method"), "iban": d.get("iban"), "category": d.get("category"),
            "tags": " | ".join(d.get("tags") or []), "lines_status": r.get("lines_status"), "status": r["status"],
            "duplicate_of": r.get("duplicate_of"), "source": r.get("source"), "media": r.get("media"),
            "path": r["path"], "original_name": r.get("original_name"),
            "warnings": " | ".join(c["message"] for c in r.get("checks", []) if c["severity"] == "warning"),
        })
        for i, li in enumerate(d.get("lines") or [], 1):
            lines.append({"id": r["id"], "line": i, "entity": r.get("entity"), "direction": r.get("direction"),
                          "issue_date": d.get("issue_date"), "counterparty": r.get("counterparty"),
                          "invoice_number": d.get("invoice_number"), "currency": d.get("currency"), **li})
        for c in r.get("checks", []):
            if c["severity"] in ("error", "warning"):
                issues.append({"id": r["id"], "entity": r.get("entity"), "status": r["status"], "severity": c["severity"],
                               "check": c["id"], "message": c["message"], "path": r["path"]})
        if r.get("unsupported"):
            issues.append({"id": r["id"], "entity": None, "status": r["status"], "severity": "error",
                           "check": "unsupported", "message": r["unsupported"], "path": r["path"]})
        if r["status"] not in ("ok", "filed") or not classes.get(d.get("doc_type"), {}).get("money"):
            continue
        month = (d.get("issue_date") or "")[:7]
        for t in tax or [{"rate": "unknown", "net": None, "tax": None}]:
            k = (r["entity"], month, r["direction"], d.get("currency"), t["rate"], bool(d.get("reverse_charge")))
            acc = vat.setdefault(k, {"documents": set(), "net": Decimal(0), "tax": Decimal(0), "gross": Decimal(0)})
            acc["documents"].add(r["id"])
            if tax:
                acc["net"] += Decimal(t["net"] or 0)
                acc["tax"] += Decimal(t["tax"] or 0)
                acc["gross"] += Decimal(t["net"] or 0) + Decimal(t["tax"] or 0)
            else:
                acc["net"] = acc["tax"] = None  # the document states no tax: net and tax are unknown
                acc["gross"] += Decimal(d.get("gross") or 0)
        k = (r["entity"], (d.get("issue_date") or "")[:4], r.get("counterparty"), d.get("currency"))
        acc = vendors.setdefault(k, {"documents": 0, "net": Decimal(0), "gross": Decimal(0)})
        acc["documents"] += 1
        acc["net"] += Decimal(d.get("net") or d.get("gross") or 0)
        acc["gross"] += Decimal(d.get("gross") or 0)
    vat_rows = [{"entity": k[0], "month": k[1], "direction": k[2], "currency": k[3], "rate": k[4],
                 "reverse_charge": k[5], "documents": len(v["documents"]), "net": money(v["net"]),
                 "tax": money(v["tax"]), "gross": money(v["gross"])}
                for k, v in sorted(vat.items(), key=lambda kv: tuple(str(x) for x in kv[0]))]
    vendor_rows = []
    for k, v in sorted(vendors.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        reg = archive.vendor(k[2]) or {}
        vendor_rows.append({"entity": k[0], "year": k[1], "counterparty": k[2],
                            "name": " | ".join(reg.get("names", [])), "vat_ids": " | ".join(reg.get("vat_ids", [])),
                            "currency": k[3], "documents": v["documents"], "net": money(v["net"]),
                            "gross": money(v["gross"])})
    return {"documents.csv": (DOC_COLUMNS, docs), "lines.csv": (LINE_COLUMNS, lines),
            "vat_summary.csv": (VAT_COLUMNS, vat_rows), "vendors.csv": (VENDOR_COLUMNS, vendor_rows),
            "issues.csv": (ISSUE_COLUMNS, issues)}


def cmd_export(args):
    archive = Archive(args.root)
    with archive.lock():
        recompute_all(archive)
        save_all(archive)
        records = list(archive.records.values())
        written = []
        scopes = {"all": records}
        for e in archive.config["entities"]:
            scopes[e["slug"]] = [r for r in records if r.get("entity") == e["slug"]]
        for dialect in (["csv", "de"] if args.dialect == "both" else [args.dialect]):
            suffix = "" if dialect == "csv" else "-de"
            for scope, rs in scopes.items():
                for name, (cols, rows) in export_rows(archive, rs).items():
                    stem, ext = os.path.splitext(name)
                    path = archive.p(EXPORTS, scope, stem + suffix + ext)
                    if write_state(path, table_text(cols, rows, dialect)):
                        written.append(archive.rel(path))
        emit({"written": written, "unchanged": not written, "documents": summary(archive)})
    return EXIT_OK


# vendors and templates ---------------------------------------------------------------------------------


def cmd_vendors(args):
    archive = Archive(args.root)
    counts = {}
    for r in archive.records.values():
        if r.get("counterparty"):
            counts[r["counterparty"]] = counts.get(r["counterparty"], 0) + 1
    emit({"vendors": [{"slug": v["slug"], "names": v["names"], "vat_ids": v["vat_ids"], "category": v.get("category"),
                       "template": bool(v.get("template")), "documents": counts.get(v["slug"], 0)}
                      for v in sorted(archive.vendors["vendors"], key=lambda v: v["slug"])]})
    return EXIT_OK


def cmd_vendor(args):
    archive = Archive(args.root)
    with archive.lock():
        v = archive.vendor(args.slug)
        if v is None:
            raise Fail(f"no vendor {args.slug!r}")
        if args.action == "merge":
            into = archive.vendor(args.value)
            if into is None or into is v:
                raise Fail(f"no other vendor {args.value!r}")
            into["names"] = sorted(set(into["names"]) | set(v["names"]))
            into["vat_ids"] = sorted(set(into["vat_ids"]) | set(v["vat_ids"]))
            into["category"] = into.get("category") or v.get("category")
            archive.vendors["vendors"].remove(v)
        elif args.action == "rename":
            new = slugify(args.value)
            if not new or archive.vendor(new):
                raise Fail(f"{args.value!r} is not a free slug")
            v["slug"] = new
        elif args.action == "category":
            if args.value not in archive.config.get("categories", []):
                raise Fail(f"{args.value!r} is not a category in config.json")
            v["category"] = args.value
        elif args.action == "alias":
            v["names"] = sorted(set(v["names"]) | {args.value})
        archive.save_vendors()
        recompute_all(archive)
        save_all(archive)
        emit({"vendor": args.slug, args.action: args.value, "status": summary(archive)})
    return EXIT_OK


COMPARE = ["doc_type", "issue_date", "invoice_number", "currency", "net", "gross", "tax", "reverse_charge"]


def template_test(archive, slug, template):
    confirmed = [r for r in archive.records.values() if r.get("counterparty") == slug and r["status"] in ("ok", "filed")
                 and r.get("source") != f"template:{slug}" and r.get("data")]
    results = []
    for r in sorted(confirmed, key=lambda r: r["id"]):
        text = archive.text(r)
        res = {"id": r["id"][:12], "diffs": []}
        if not all(squash(m) in squash(text) for m in template.get("match", [])):
            res["diffs"].append({"field": "match", "error": "the match strings are not all in the text"})
        else:
            try:
                got = normalize_proposal(apply_template(template, text), archive.classes)
            except (Fail, ValueError, re.error, KeyError) as e:
                res["diffs"].append({"field": "template", "error": str(e)})
                got = None
            if got is not None:
                for k in COMPARE:
                    if got.get(k) != r["data"].get(k):
                        res["diffs"].append({"field": k, "expected": r["data"].get(k), "got": got.get(k)})
                ent = resolve_entity(archive.config, got)[0]
                if ent != r.get("entity"):
                    res["diffs"].append({"field": "entity", "expected": r.get("entity"), "got": ent})
        results.append(res)
    ok = bool(results) and all(not x["diffs"] for x in results)
    return ok, results


def cmd_template(args):
    archive = Archive(args.root)
    v = archive.vendor(args.slug)
    if v is None:
        raise Fail(f"no vendor {args.slug!r}")
    template = read_json(args.file) if args.file else v.get("template")
    if not template:
        raise Fail(f"{args.slug} has no template; give a template file")
    if not template.get("match"):
        raise Fail("a template needs match strings that only this vendor's documents contain")
    ok, results = template_test(archive, args.slug, template)
    out = {"vendor": args.slug, "tested_against": len(results), "pass": ok, "results": results}
    if not results:
        out["why"] = "no confirmed document of this vendor to test against: confirm one first"
    if args.action == "set":
        if not ok:
            out["saved"] = False
            emit(out)
            return EXIT_CHECK
        with archive.lock():
            v = archive.vendor(args.slug)
            v["template"] = template
            archive.save_vendors()
        out["saved"] = True
    emit(out)
    return EXIT_OK if ok else EXIT_CHECK


def cmd_unlock(args):
    archive = Archive(args.root)
    path = archive.p(STATE, "lock")
    if not os.path.exists(path):
        emit({"locked": False})
        return EXIT_OK
    with open(path, encoding="utf-8", errors="replace") as f:
        who = f.read().strip()
    os.remove(path)  # engine state, never a document
    emit({"unlocked": who})
    return EXIT_OK


# ----------------------------------------------------------------------------------------------


def parser():
    ap = argparse.ArgumentParser(prog="paperwork", description=__doc__.split("\n\n")[0])
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        if name != "init":
            sp.add_argument("--root", default=os.environ.get("PAPERWORK_ROOT", "."), help=argparse.SUPPRESS)
        return sp

    sp = add("init", cmd_init, "create the archive layout and config")
    sp.add_argument("root")
    add("doctor", cmd_doctor, "check tools, config and lock")
    sp = add("ingest", cmd_ingest, "register new files from _inbox (and with --adopt everything in the archive)")
    sp.add_argument("--adopt", action="store_true")
    add("pending", cmd_pending, "documents that need their fields read")
    add("schema", cmd_schema, "the proposal format")
    sp = add("record", cmd_record, "check a proposal and store it")
    sp.add_argument("id")
    sp.add_argument("proposal")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--user", action="store_true", help="the proposal was confirmed by the user")
    sp = add("set", cmd_set, "change fields: field=value (dotted: buyer.name=...)")
    sp.add_argument("id")
    sp.add_argument("assignments", nargs="+")
    sp = add("accept", cmd_accept, "waive one check with a reason")
    sp.add_argument("id")
    sp.add_argument("check")
    sp.add_argument("--reason", required=True)
    sp = add("reextract", cmd_reextract, "drop a document's fields so it is read again (kept in history)")
    sp.add_argument("id")
    sp = add("show", cmd_show, "one document")
    sp.add_argument("id")
    sp = add("list", cmd_list, "documents")
    sp.add_argument("--status")
    add("status", cmd_status, "counts")
    sp = add("plan", cmd_plan, "the moves and renames that would be made")
    sp.add_argument("--out")
    sp = add("apply", cmd_apply, "make a plan's moves, journaled")
    sp.add_argument("plan")
    sp = add("undo", cmd_undo, "move a batch back")
    sp.add_argument("batch")
    add("verify", cmd_verify, "every file present, every hash right, nothing unregistered")
    sp = add("export", cmd_export, "write the CSVs")
    sp.add_argument("--dialect", choices=["csv", "de", "both"], default="both")
    add("vendors", cmd_vendors, "the counterparty registry")
    sp = add("vendor", cmd_vendor, "change a counterparty: merge <into> | rename <slug> | category <c> | alias <name>")
    sp.add_argument("slug")
    sp.add_argument("action", choices=["merge", "rename", "category", "alias"])
    sp.add_argument("value")
    sp = add("template", cmd_template, "test or set a vendor's extraction template")
    sp.add_argument("action", choices=["test", "set"])
    sp.add_argument("slug")
    sp.add_argument("file", nargs="?")
    add("unlock", cmd_unlock, "remove a stale lock")
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return args.fn(args)
    except Fail as e:
        sys.stderr.write(f"paperwork: {e}\n")
        return e.code
    except FileNotFoundError as e:
        sys.stderr.write(f"paperwork: {e}\n")
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
