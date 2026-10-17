"""Engine tests. They run inside the tools image: `bin/paperwork __test`.

Every company, person, VAT ID and address here is made up.
"""

import contextlib
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))
import paperwork as pw  # noqa: E402
from pdfgen import image_pdf, text_pdf  # noqa: E402


def de_vat(eight):
    product = 10
    for ch in eight:
        total = (int(ch) + product) % 10 or 10
        product = (2 * total) % 11
    return f"DE{eight}{(11 - product) % 10}"


OWN_VAT = de_vat("31415926")
KRANICH_VAT = de_vat("27182818")
HOSTER_VAT = de_vat("16180339")

CONFIG_ENTITIES = [
    {"slug": "nordlicht", "name": "Nordlicht Digital GmbH", "names": ["Nordlicht Digital GmbH"],
     "vat_ids": [OWN_VAT], "addresses": ["Musterweg 1", "Am Hafen 7"], "kind": "business"},
    {"slug": "kranich", "name": "Kranich Data GmbH", "vat_ids": [KRANICH_VAT], "addresses": ["Industriestr. 9"]},
    {"slug": "privat", "name": "Erika Mustermann", "kind": "private"},
]


def hoster_invoice(number="RE-2026-0042", date="14.03.2026", buyer="Nordlicht Digital GmbH", net="100,00",
                   tax="19,00", gross="119,00", extra=()):
    return [
        "Muster Hosting GmbH, Serverstr. 5, 10115 Berlin",
        "Rechnung",
        f"Rechnungsnummer: {number}",
        f"Rechnungsdatum: {date}",
        "Leistungszeitraum: 01.02.2026 - 28.02.2026",
        "Rechnungsadresse:",
        buyer,
        "Erika Mustermann",
        "Musterweg 1",
        "12345 Musterstadt",
        "Lieferadresse: Kranich Data GmbH, Industriestr. 9, 12345 Musterstadt",
        f"USt-IdNr. Kunde: {OWN_VAT}",
        "Pos Beschreibung Menge Preis Netto",
        f"1 Cloud Server M 1 {net} € {net} €",
        f"Summe netto {net} €",
        f"19 % USt. {tax} €",
        f"Gesamtbetrag {gross} €",
        f"Muster Hosting GmbH - USt-IdNr. {HOSTER_VAT} - IBAN DE89 3704 0044 0532 0130 00",
        *extra,
    ]


def hoster_proposal(number="RE-2026-0042", date="2026-03-14", printed_date="14.03.2026", buyer="Nordlicht Digital GmbH",
                    net="100.00", tax="19.00", gross="119.00", printed_gross="119,00 €"):
    return {
        "doc_type": "inv", "language": "de", "issue_date": date,
        "service_period": {"start": "2026-02-01", "end": "2026-02-28"},
        "seller": {"name": "Muster Hosting GmbH", "address": ["Serverstr. 5", "10115 Berlin"], "vat_id": HOSTER_VAT,
                   "country": "DE"},
        "buyer": {"name": buyer, "address": ["Musterweg 1", "12345 Musterstadt"], "vat_id": OWN_VAT, "country": "DE"},
        "invoice_number": number, "currency": "EUR", "net": net, "gross": gross,
        "tax": [{"rate": "19", "net": net, "tax": tax}],
        "iban": "DE89370400440532013000",
        "lines": [{"description": "Cloud Server M", "quantity": "1", "unit_price": net, "net": net, "tax_rate": "19"}],
        "evidence": {"issue_date": printed_date, "gross": printed_gross},
    }


CII = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
 xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
 xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
 <rsm:ExchangedDocument><ram:ID>ZF-77</ram:ID><ram:TypeCode>{type}</ram:TypeCode>
  <ram:IssueDateTime><udt:DateTimeString format="102">20260402</udt:DateTimeString></ram:IssueDateTime></rsm:ExchangedDocument>
 <rsm:SupplyChainTradeTransaction>
  <ram:IncludedSupplyChainTradeLineItem>
   <ram:SpecifiedTradeProduct><ram:Name>Beratung</ram:Name></ram:SpecifiedTradeProduct>
   <ram:SpecifiedLineTradeAgreement><ram:NetPriceProductTradePrice><ram:ChargeAmount>500.00</ram:ChargeAmount></ram:NetPriceProductTradePrice></ram:SpecifiedLineTradeAgreement>
   <ram:SpecifiedLineTradeDelivery><ram:BilledQuantity unitCode="HUR">2</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
   <ram:SpecifiedLineTradeSettlement><ram:ApplicableTradeTax><ram:RateApplicablePercent>19</ram:RateApplicablePercent></ram:ApplicableTradeTax>
    <ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>1000.00</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation></ram:SpecifiedLineTradeSettlement>
  </ram:IncludedSupplyChainTradeLineItem>
  <ram:ApplicableHeaderTradeAgreement>
   <ram:SellerTradeParty><ram:Name>Beratung Becker GmbH</ram:Name>
    <ram:PostalTradeAddress><ram:PostcodeCode>20095</ram:PostcodeCode><ram:LineOne>Ufer 3</ram:LineOne><ram:CityName>Hamburg</ram:CityName><ram:CountryID>DE</ram:CountryID></ram:PostalTradeAddress>
    <ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">{seller_vat}</ram:ID></ram:SpecifiedTaxRegistration></ram:SellerTradeParty>
   <ram:BuyerTradeParty><ram:Name>Kranich Data GmbH</ram:Name>
    <ram:PostalTradeAddress><ram:PostcodeCode>12345</ram:PostcodeCode><ram:LineOne>Industriestr. 9</ram:LineOne><ram:CityName>Musterstadt</ram:CityName><ram:CountryID>DE</ram:CountryID></ram:PostalTradeAddress></ram:BuyerTradeParty>
  </ram:ApplicableHeaderTradeAgreement>
  <ram:ApplicableHeaderTradeDelivery/>
  <ram:ApplicableHeaderTradeSettlement><ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
   <ram:ApplicableTradeTax><ram:CalculatedAmount>190.00</ram:CalculatedAmount><ram:TypeCode>VAT</ram:TypeCode><ram:BasisAmount>1000.00</ram:BasisAmount><ram:CategoryCode>S</ram:CategoryCode><ram:RateApplicablePercent>19</ram:RateApplicablePercent></ram:ApplicableTradeTax>
   <ram:BillingSpecifiedPeriod><ram:StartDateTime><udt:DateTimeString format="102">20260301</udt:DateTimeString></ram:StartDateTime><ram:EndDateTime><udt:DateTimeString format="102">20260331</udt:DateTimeString></ram:EndDateTime></ram:BillingSpecifiedPeriod>
   <ram:SpecifiedTradePaymentTerms><ram:DueDateDateTime><udt:DateTimeString format="102">20260416</udt:DateTimeString></ram:DueDateDateTime></ram:SpecifiedTradePaymentTerms>
   <ram:SpecifiedTradeSettlementHeaderMonetarySummation><ram:LineTotalAmount>1000.00</ram:LineTotalAmount><ram:TaxBasisTotalAmount>1000.00</ram:TaxBasisTotalAmount>
    <ram:TaxTotalAmount currencyID="EUR">190.00</ram:TaxTotalAmount><ram:GrandTotalAmount>1190.00</ram:GrandTotalAmount><ram:DuePayableAmount>1190.00</ram:DuePayableAmount></ram:SpecifiedTradeSettlementHeaderMonetarySummation>
  </ram:ApplicableHeaderTradeSettlement>
 </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""

UBL = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
 <cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0</cbc:CustomizationID>
 <cbc:ID>XR-2026-9</cbc:ID><cbc:IssueDate>2026-05-05</cbc:IssueDate><cbc:DueDate>2026-05-19</cbc:DueDate>
 <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode><cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
 <cac:AccountingSupplierParty><cac:Party><cac:PostalAddress><cbc:StreetName>Kai 1</cbc:StreetName><cbc:CityName>Bremen</cbc:CityName><cbc:PostalZone>28195</cbc:PostalZone><cac:Country><cbc:IdentificationCode>DE</cbc:IdentificationCode></cac:Country></cac:PostalAddress>
  <cac:PartyTaxScheme><cbc:CompanyID>{seller_vat}</cbc:CompanyID><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:PartyTaxScheme>
  <cac:PartyLegalEntity><cbc:RegistrationName>Druckerei Weser GmbH</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingSupplierParty>
 <cac:AccountingCustomerParty><cac:Party><cac:PostalAddress><cbc:StreetName>Musterweg 1</cbc:StreetName><cbc:CityName>Musterstadt</cbc:CityName><cbc:PostalZone>12345</cbc:PostalZone><cac:Country><cbc:IdentificationCode>DE</cbc:IdentificationCode></cac:Country></cac:PostalAddress>
  <cac:PartyLegalEntity><cbc:RegistrationName>Nordlicht Digital GmbH</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingCustomerParty>
 <cac:TaxTotal><cbc:TaxAmount currencyID="EUR">7.00</cbc:TaxAmount>
  <cac:TaxSubtotal><cbc:TaxableAmount currencyID="EUR">100.00</cbc:TaxableAmount><cbc:TaxAmount currencyID="EUR">7.00</cbc:TaxAmount><cac:TaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>7</cbc:Percent><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>
 <cac:LegalMonetaryTotal><cbc:LineExtensionAmount currencyID="EUR">100.00</cbc:LineExtensionAmount><cbc:TaxExclusiveAmount currencyID="EUR">100.00</cbc:TaxExclusiveAmount><cbc:TaxInclusiveAmount currencyID="EUR">107.00</cbc:TaxInclusiveAmount><cbc:PayableAmount currencyID="EUR">107.00</cbc:PayableAmount></cac:LegalMonetaryTotal>
 <cac:InvoiceLine><cbc:ID>1</cbc:ID><cbc:InvoicedQuantity unitCode="C62">100</cbc:InvoicedQuantity><cbc:LineExtensionAmount currencyID="EUR">100.00</cbc:LineExtensionAmount>
  <cac:Item><cbc:Name>Flyer A5</cbc:Name><cac:ClassifiedTaxCategory><cbc:ID>S</cbc:ID><cbc:Percent>7</cbc:Percent><cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme></cac:ClassifiedTaxCategory></cac:Item>
  <cac:Price><cbc:PriceAmount currencyID="EUR">1.00</cbc:PriceAmount></cac:Price></cac:InvoiceLine>
</Invoice>
"""


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def doc_file(docs, prefix):
    return next(n for n in sorted(os.listdir(docs)) if n.startswith(prefix))


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = pw.main(list(args))
    text = out.getvalue()
    try:
        data = json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        data = text
    return code, data, err.getvalue()


def all_files(root):
    out = {}
    for dirpath, _, files in os.walk(root):
        if "/_paperwork" in dirpath + "/" and "_paperwork" in os.path.relpath(dirpath, root).split(os.sep)[0]:
            continue
        if os.path.relpath(dirpath, root).split(os.sep)[0] == "exports":
            continue
        for f in files:
            p = os.path.join(dirpath, f)
            out[os.path.relpath(p, root)] = pw.sha256_file(p)
    return out


class Units(unittest.TestCase):
    def test_render(self):
        self.assertEqual(pw.render("{a}_{b}", {"a": "x", "b": "y"}), "x_y")

    def test_builtin_classes(self):
        self.assertEqual(set(pw.BUILTIN_CLASSES),
                         {"inv", "cn", "rcpt", "rem", "notice", "oc", "quote", "contract", "other"})
        with self.assertRaises(pw.Fail):
            pw.normalize_proposal({"doc_type": "x"})

    def test_amounts(self):
        c = pw.amount_candidates
        self.assertEqual(c("1.250,60 €"), {Decimal("1250.60")})
        self.assertEqual(c("€20.42"), {Decimal("20.42")})
        self.assertEqual(c("(€20.42)"), {Decimal("-20.42")})
        self.assertEqual(c("-24,04 €"), {Decimal("-24.04")})
        self.assertEqual(c("71,4202 €"), {Decimal("71.4202")})
        self.assertEqual(c("1,234"), {Decimal("1.234"), Decimal("1234")})
        self.assertEqual(c("$1,234.50 USD"), {Decimal("1234.50")})
        self.assertEqual(c("1.000.000"), {Decimal("1000000")})
        self.assertEqual(c("62 ,00"), {Decimal("62.00")})

    def test_dates(self):
        c = pw.date_candidates
        d = pw.dt.date
        self.assertEqual(c("13. März 2024"), {d(2024, 3, 13)})
        self.assertEqual(c("07 Mai 2024"), {d(2024, 5, 7)})
        self.assertEqual(c("Jul 24, 2026"), {d(2026, 7, 24)})
        self.assertEqual(c("02nd June, 2024"), {d(2024, 6, 2)})
        self.assertEqual(c("24.05.2026"), {d(2026, 5, 24)})
        self.assertEqual(c("18/06/2026"), {d(2026, 6, 18)})
        self.assertEqual(c("04/06/2026"), {d(2026, 6, 4), d(2026, 4, 6)})
        self.assertEqual(c("2026-03-14"), {d(2026, 3, 14)})
        self.assertEqual(c("23.65.2024"), set())

    def test_ids(self):
        self.assertTrue(pw.vat_ok(OWN_VAT))
        self.assertFalse(pw.vat_ok(OWN_VAT[:-1] + str((int(OWN_VAT[-1]) + 1) % 10)))
        self.assertIsNone(pw.vat_ok("514440874"))
        self.assertTrue(pw.vat_ok("ATU12345678"))
        self.assertTrue(pw.iban_ok("DE89 3704 0044 0532 0130 00"))
        self.assertFalse(pw.iban_ok("DE89 3704 0044 0532 0130 01"))
        self.assertIsNone(pw.iban_ok("DE35***************429"))

    def test_names(self):
        self.assertEqual(pw.company_key("Amazon EU S.à r.l., Niederlassung Deutschland"), "amazon eu")
        self.assertEqual(pw.company_key("OpenAI, LLC"), "openai")
        self.assertEqual(pw.company_key("Kurz & Klein UG (haftungsbeschränkt)"), "kurz klein")
        self.assertEqual(pw.slugify("Müller Baustoffe"), "mueller-baustoffe")
        self.assertEqual(pw.safe_number("DE/2026_04 12"), "DE-2026-04-12")


class Archive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "Belege")
        code, _, err = run("init", self.root)
        self.assertEqual(code, 0, err)
        cfg_path = os.path.join(self.root, "_paperwork", "config.json")
        cfg = json.loads(read(cfg_path))
        cfg["entities"] = CONFIG_ENTITIES
        cfg["start_year"] = 2020
        write_json(cfg_path, cfg)

    def tearDown(self):
        self.tmp.cleanup()

    def pw(self, *args):
        return run(*args, "--root", self.root) if args[0] not in ("init",) else run(*args)

    def drop(self, name, data):
        path = os.path.join(self.root, "_inbox", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def propose(self, doc_id, proposal):
        path = os.path.join(self.root, "_paperwork", "proposals", doc_id + ".json")
        with open(path, "w") as f:
            json.dump(proposal, f)
        return self.pw("record", doc_id, path)

    def only_pending(self):
        code, data, err = self.pw("pending")
        self.assertEqual(code, 0, err)
        return data["pending"]

    def pending_id(self, needle):
        for item in self.only_pending():
            if needle in read(item["text"]):
                return item["id"]
        self.fail(f"no pending document contains {needle!r}")

    def file_all(self):
        code, plan, err = self.pw("plan")
        self.assertEqual(code, 0, err)
        code, res, err = self.pw("apply", plan["file"])
        self.assertEqual(code, 0, (res, err))
        return plan, res

    def csv_rows(self, scope, name):
        with open(os.path.join(self.root, "exports", scope, name), encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    # ------------------------------------------------------------------------------------------

    def write_config(self, **changes):
        path = os.path.join(self.root, "_paperwork", "config.json")
        cfg = json.loads(read(path))
        cfg.update(changes)
        write_json(path, cfg)

    def write_rules(self, rules, user=None):
        name = "rules.json" if not user else os.path.join("rules", user + ".json")
        path = os.path.join(self.root, "_paperwork", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        write_json(path, {"rules": rules})

    def test_claude_alone_is_unconfirmed_until_confirmed(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p["alternatives"] = {"doc_type": ["rcpt"]}
        code, view, err = self.propose(doc, p)
        self.assertEqual(code, 0, (view, err))
        self.assertEqual(view["status"], "unconfirmed")
        self.assertIn("counterparty:new", [c["id"] for c in view["warnings"]])
        self.assertEqual(view["alternatives"], {"doc_type": ["rcpt"]})
        self.file_all()
        self.assertEqual(self.pw("show", doc[:8])[1]["status"], "unconfirmed")
        self.assertEqual(len(self.pw("list", "--status", "unconfirmed")[1]["documents"]), 1)
        self.assertTrue(self.pw("vendors")[1]["vendors"][0]["proposed"])
        code, _, err = self.pw("confirm", doc[:8])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.pw("show", doc[:8])[1]["status"], "filed")
        self.assertFalse(self.pw("vendors")[1]["vendors"][0]["proposed"])

    def test_ruled_class_with_confirmed_vendor_needs_no_confirmation(self):
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]}, "set": {"doc_type": "inv"}}])
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        self.pw("confirm", doc[:8])  # confirms the new vendor once
        self.drop("b.pdf", text_pdf([hoster_invoice(number="RE-2")]))
        self.pw("ingest")
        code, view, _ = self.propose(self.only_pending()[0]["id"], hoster_proposal(number="RE-2"))
        self.assertEqual(view["status"], "ok")

    def test_alternatives_must_be_known(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        p = hoster_proposal()
        p["alternatives"] = {"doc_type": ["invoice"]}
        code, _, err = self.propose(self.only_pending()[0]["id"], p)
        self.assertEqual(code, 2)
        self.assertIn("alternatives", err)

    def test_records_from_before_the_outcome_stay_confirmed(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        path = os.path.join(self.root, "_paperwork", "docs", self.pw("show", doc[:8])[1]["id"] + ".json")
        rec = json.loads(read(path))
        del rec["recorded_by"]
        write_json(path, rec)
        self.pw("vendor", "muster-hosting", "alias", "Muster Hosting AG")  # any recompute
        self.assertEqual(self.pw("show", doc[:8])[1]["status"], "ok")

    def test_confirm_refuses_a_document_in_review_and_edits_confirm(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal(gross="191.00", tax="91.00", printed_gross="191,00 €"))
        code, _, err = self.pw("confirm", doc[:8])
        self.assertNotEqual(code, 0)
        self.assertIn("review", err)

    def test_set_confirms(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        code, view, err = self.pw("set", doc[:8], "notes=checked")
        self.assertEqual(code, 0, err)
        self.assertEqual(view["status"], "ok")

    def test_claude_proposal_in_review_is_not_confirmed(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        _, view, _ = self.propose(doc, hoster_proposal(gross="191.00", tax="91.00", printed_gross="191,00 €"))
        self.assertEqual(view["status"], "review")
        self.assertIs(self.pw("show", doc[:8])[1]["confirmed"], False)

    def test_archive_from_before_the_outcome_replans_with_zero_moves(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        self.pw("confirm", doc[:8])
        self.file_all()
        full = self.pw("show", doc[:8])[1]["id"]
        path = os.path.join(self.root, "_paperwork", "docs", full + ".json")
        rec = json.loads(read(path))
        for key in ("recorded_by", "confirmed", "vendor_proposed"):
            rec.pop(key, None)
        write_json(path, rec)
        vpath = os.path.join(self.root, "_paperwork", "vendors.json")
        vendors = json.loads(read(vpath))
        for v in vendors["vendors"]:
            v.pop("proposed", None)
        write_json(vpath, vendors)
        self.assertEqual(self.pw("plan")[1]["moves"], 0)
        view = self.pw("show", doc[:8])[1]
        self.assertEqual((view["status"], view["confirmed"]), ("filed", True))

    def test_alternatives_keep_three_per_key(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        p = hoster_proposal()
        p["alternatives"] = {"counterparty": [" A ", "B", "C", "D"], "entity": ["nordlicht"]}
        _, view, _ = self.propose(self.only_pending()[0]["id"], p)
        self.assertEqual(view["alternatives"], {"counterparty": ["A", "B", "C"], "entity": ["nordlicht"]})

    def test_confirm_takes_several_ids(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.drop("b.pdf", text_pdf([hoster_invoice(number="RE-2026-0043")]))
        self.pw("ingest")
        ids = []
        for item in self.only_pending():
            number = "RE-2026-0043" if "RE-2026-0043" in read(item["text"]) else "RE-2026-0042"
            self.propose(item["id"], hoster_proposal(number=number))
            ids.append(item["id"][:8])
        self.assertEqual(self.pw("status")[1]["documents"].get("unconfirmed"), 2)
        code, _, err = self.pw("confirm", *ids)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.pw("list", "--status", "unconfirmed")[1]["count"], 0)

    def test_reextract_clears_the_proposed_vendor_flag(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        self.pw("reextract", doc[:8])
        full = self.pw("show", doc[:8])[1]["id"]
        rec = json.loads(read(os.path.join(self.root, "_paperwork", "docs", full + ".json")))
        self.assertFalse(rec.get("vendor_proposed"))

    def test_rules_test_previews_without_writing(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        docs = os.path.join(self.root, "_paperwork", "docs")
        before = {n: read(os.path.join(docs, n)) for n in os.listdir(docs)}
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}}])
        code, out, err = self.pw("rules", "test")
        self.assertEqual(code, 0, err)
        self.assertEqual(out["changes"][0]["changes"][0]["to"], "hosting")
        self.assertEqual(before, {n: read(os.path.join(docs, n)) for n in os.listdir(docs)})
        code, out, _ = self.pw("rules", "apply")
        self.assertEqual(json.loads(read(os.path.join(docs, doc_file(docs, doc))))["data"]["category"], "hosting")

    def test_rules_test_file_must_be_valid(self):
        bad = os.path.join(self.root, "draft.json")
        write_json(bad, {"rules": [{"id": "x", "when": {"bogus": 1}, "set": {"category": "hosting"}}]})
        code, _, err = self.pw("rules", "test", "--file", bad)
        self.assertEqual(code, 1)
        self.assertIn("bogus", err)

    def ingest_hoster(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        return doc

    def draft(self, category):
        path = os.path.join(self.root, "draft.json")
        write_json(path, {"rules": [{"id": "draft", "when": {"text": ["Cloud Server"]}, "set": {"category": category}}]})
        return path

    def test_rules_test_file_replaces_archive_layer(self):
        self.ingest_hoster()
        self.write_rules([{"id": "disk", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}}])
        code, out, err = self.pw("rules", "test", "--file", self.draft("software"))
        self.assertEqual(code, 0, err)
        self.assertEqual(out["changes"][0]["changes"][0]["to"], "software")
        self.assertEqual(out["changes"][0]["rules"], ["draft"])

    def test_rules_test_file_repairs_broken_rules_json(self):
        self.ingest_hoster()
        with open(os.path.join(self.root, "_paperwork", "rules.json"), "w") as f:
            f.write("{broken")
        self.assertNotEqual(self.pw("status")[0], 0)
        code, out, err = self.pw("rules", "test", "--file", self.draft("software"))
        self.assertEqual(code, 0, err)
        self.assertEqual(out["changes"][0]["changes"][0]["to"], "software")
        self.assertNotEqual(self.pw("status")[0], 0)

    def test_rules_apply_rejects_file(self):
        code, _, err = self.pw("rules", "apply", "--file", self.draft("software"))
        self.assertEqual(code, 2)
        self.assertIn("--file", err)

    def test_rules_apply_leaves_user_records_and_unchanged_out(self):
        doc = self.ingest_hoster()
        self.pw("set", doc, "notes=mine")
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}}])
        docs = os.path.join(self.root, "_paperwork", "docs")
        before = read(os.path.join(docs, doc_file(docs, doc)))
        code, out, err = self.pw("rules", "apply")
        self.assertEqual((code, out["changes"]), (0, []), err)
        self.assertEqual(before, read(os.path.join(docs, doc_file(docs, doc))))

    def test_pending_carries_text_rule_hints(self):
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]}, "set": {"doc_type": "inv"}}])
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        self.assertEqual(self.only_pending()[0]["rule_hints"], {"doc_type": "inv"})

    def test_rule_sets_class_and_category(self):
        self.write_rules([{"id": "hoster", "when": {"text": ["Cloud Server"]},
                           "set": {"category": "hosting", "tags": ["server"]}}])
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        code, view, err = self.propose(doc, hoster_proposal())
        self.assertEqual(code, 0, (view, err))
        rec = json.loads(read(os.path.join(self.root, "_paperwork", "docs", view["id"] + ".json")))
        self.assertEqual(rec["data"]["category"], "hosting")
        self.assertEqual(rec["data"]["tags"], ["server"])
        self.assertEqual(rec["rules"], ["hoster"])
        self.assertEqual(rec["rule_fields"], {"category": "hoster", "tags": "hoster"})

    def test_rule_overrides_proposal_with_a_warning(self):
        self.write_rules([{"id": "is-receipt", "when": {"counterparty": "muster-hosting"}, "set": {"doc_type": "rcpt"}}])
        # first document creates the counterparty, second is ruled
        for n in ("A-1", "A-2"):
            self.drop(n + ".pdf", text_pdf([hoster_invoice(number=n)]))
        self.pw("ingest")
        a = self.pending_id("A-1")
        b = self.pending_id("A-2")
        self.propose(a, hoster_proposal(number="A-1"))
        code, view, _ = self.propose(b, hoster_proposal(number="A-2"))
        self.assertIn("rule:override", [c["id"] for c in view["warnings"]])

    def test_rule_conflict_goes_to_review(self):
        self.write_rules([{"id": "a", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}},
                          {"id": "b", "when": {"text": ["Gesamtbetrag"]}, "set": {"category": "software"}}])
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        code, view, _ = self.propose(self.only_pending()[0]["id"], hoster_proposal())
        self.assertEqual(code, 3)
        self.assertIn("rule:conflict", [c["id"] for c in view["problems"]])

    def test_user_rules_only_fill_gaps(self):
        self.write_rules([{"id": "arch", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}}])
        self.write_rules([{"id": "mine", "when": {"text": ["Cloud Server"]},
                           "set": {"category": "software", "tags": ["mine"]}}], user="erika")
        os.environ["PAPERWORK_USER"] = "erika"
        self.addCleanup(os.environ.pop, "PAPERWORK_USER", None)
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        code, view, _ = self.propose(self.only_pending()[0]["id"], hoster_proposal())
        rec = json.loads(read(os.path.join(self.root, "_paperwork", "docs", view["id"] + ".json")))
        self.assertEqual((rec["data"]["category"], rec["data"]["tags"]), ("hosting", ["mine"]))

    def ruled(self, rules, **proposal):
        self.write_rules(rules)
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        return self.propose(self.only_pending()[0]["id"], hoster_proposal(**proposal))

    def test_edit_clears_a_rule_conflict(self):
        code, view, _ = self.ruled([{"id": "a", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}},
                                    {"id": "b", "when": {"text": ["Gesamtbetrag"]}, "set": {"category": "software"}}])
        self.assertEqual(code, 3)
        code, view, err = self.pw("set", view["id"], "category=hosting")
        self.assertEqual(code, 0, (view, err))
        self.assertNotIn("rule:conflict", [c["id"] for c in view["problems"]])
        rec = json.loads(read(os.path.join(self.root, "_paperwork", "docs", view["id"] + ".json")))
        self.assertEqual(rec["data"]["category"], "hosting")

    def test_edit_beats_rule(self):
        code, view, _ = self.ruled([{"id": "a", "when": {"text": ["Cloud Server"]}, "set": {"category": "hosting"}}])
        self.pw("set", view["id"], "category=software")
        self.pw("set", view["id"], "notes=later")
        rec = json.loads(read(os.path.join(self.root, "_paperwork", "docs", view["id"] + ".json")))
        self.assertEqual(rec["data"]["category"], "software")

    def test_more_specific_rule_wins(self):
        code, view, err = self.ruled([
            {"id": "broad", "when": {"text": ["Cloud Server"]}, "set": {"category": "software"}},
            {"id": "narrow", "when": {"text": ["Cloud Server"], "regex": "Gesamtbetrag"}, "set": {"category": "hosting"}}])
        self.assertEqual(code, 0, (view, err))
        rec = json.loads(read(os.path.join(self.root, "_paperwork", "docs", view["id"] + ".json")))
        self.assertEqual(rec["data"]["category"], "hosting")

    def test_rule_entity_must_match_the_billed_party(self):
        code, view, _ = self.ruled([{"id": "wrong", "when": {"text": ["Cloud Server"]}, "set": {"entity": "kranich"}}])
        self.assertEqual(code, 3)
        self.assertIn("rule:entity", [c["id"] for c in view["problems"]])

    def test_override_warning_survives_a_later_set(self):
        code, view, _ = self.ruled([{"id": "is-receipt", "when": {"text": ["Cloud Server"]}, "set": {"doc_type": "rcpt"}}])
        self.assertIn("rule:override", [c["id"] for c in view["warnings"]])
        code, view, _ = self.pw("set", view["id"], "notes=later")
        self.assertIn("rule:override", [c["id"] for c in view["warnings"]])

    def test_rule_values_of_the_wrong_type_are_reported(self):
        self.write_rules([{"id": "listy", "when": {"text": ["x"]}, "set": {"doc_type": ["inv"], "entity": ["a"]}}])
        code, _, err = self.pw("status")
        self.assertNotEqual(code, 0)
        self.assertIn("rules[archive].listy", err)

    def test_bad_rules_fail_fast(self):
        self.write_rules([{"id": "broken", "when": {"regex": "("}, "set": {"category": "hosting"}}])
        code, _, err = self.pw("status")
        self.assertNotEqual(code, 0)
        self.assertIn("broken", err)
        self.write_rules([{"id": "noclass", "when": {"text": ["x"]}, "set": {"doc_type": "invoice"}}])
        self.assertIn("noclass", self.pw("status")[2])

    def test_upgrade_replans_zero_moves(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        self.propose(self.only_pending()[0]["id"], hoster_proposal())
        self.file_all()
        self.write_config(classes={})  # explicit empty: built-ins only
        self.assertEqual(self.pw("plan")[1]["moves"], 0)

    def test_folder_and_name_templates(self):
        self.write_config(classes={"inv": {"folder": "{entity}/{year}"},
                                   "contract": {"fields": {"start": {"type": "date"}},
                                                "folder": "{entity}/contracts/{counterparty}",
                                                "name": "{fields.start}_{class}_{counterparty}_{id}"}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.drop("b.pdf", text_pdf([hoster_invoice(number="V-1", extra=["Vertrag ab 01.01.2026"])]))
        self.pw("ingest")
        a = self.pending_id("RE-2026-0042")
        b = self.pending_id("V-1")
        self.propose(a, hoster_proposal())
        p = hoster_proposal(number="V-1")
        p.update(doc_type="contract", fields={"start": "2026-01-01"})
        self.propose(b, p)
        targets = sorted(m["to"] for m in self.pw("plan")[1]["by_destination"]["to archive"])
        self.assertIn(f"nordlicht/contracts/muster-hosting/2026-01-01_contract_muster-hosting_{b[:8]}.pdf", targets)
        self.assertTrue(any(t.startswith("nordlicht/2026/2026-03-14_inv_") for t in targets))

    def test_unsafe_folder_goes_to_review(self):
        self.write_config(classes={"contract": {"fields": {"area": {"type": "text"}},
                                                "folder": "{entity}/{fields.area}"}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p.update(doc_type="contract", fields={"area": ".."})
        code, view, _ = self.propose(doc, p)
        self.assertEqual(code, 3)
        self.assertIn("path:folder", [c["id"] for c in view["problems"]])
        self.assertTrue(view["target"].startswith("_review/"))
        code, _, err = self.pw("accept", doc, "path:folder", "--reason", "x")
        self.assertNotEqual(code, 0)
        self.assertIn("path:folder", err)
        self.assertTrue(self.pw("show", doc)[1]["target"].startswith("_review/"))

    def test_folder_templates_never_escape(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        for folder in ("{entity}/../x", "{entity}/_review/x", "{year}/{entity}", "{entity}//x"):
            self.write_config(classes={"inv": {"folder": folder}})
            if self.pw("status")[0] != 0:
                continue  # rejected at load: no move target either
            self.pw("export")  # recomputes and saves the checks
            self.assertEqual(self.pw("plan")[1]["by_destination"].get("to archive", []), [])
            view = self.pw("show", doc)[1]
            self.assertTrue(view["target"].startswith("_review/"), (folder, view["target"]))
            self.assertIn("path:folder", [c["id"] for c in view["problems"]])

    def test_long_path_goes_to_review(self):
        self.write_config(classes={"inv": {"folder": "{entity}/" + "x" * 240}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        _, view, _ = self.propose(doc, hoster_proposal())
        self.assertIn("path:length", [c["id"] for c in view["problems"]])
        self.assertTrue(view["target"].startswith("_review/"))

    def test_long_path_is_shortened_to_fit(self):
        self.write_config(classes={"inv": {"folder": "{entity}/pad"}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        _, view, _ = self.propose(doc, hoster_proposal())
        fit = pw.MAX_PATH - len(os.path.join(self.root, view["target"]))
        self.write_config(classes={"inv": {"folder": "{entity}/" + "x" * (3 + fit + 5)}})
        view = self.pw("show", doc)[1]
        self.assertTrue(view["target"].startswith("nordlicht/xxx"), view["target"])
        self.assertLessEqual(len(os.path.join(self.root, view["target"])), pw.MAX_PATH)

    def test_bad_template_fails(self):
        self.write_config(classes={"inv": {"name": "{issue_date}_{colour}"}})
        code, _, err = self.pw("status")
        self.assertNotEqual(code, 0)
        self.assertIn("colour", err)
        self.assertIn("inv", err)

    def test_class_fields_are_exported(self):
        self.write_config(classes={"contract": {"fields": {"start": {"type": "date"}, "notice": {"type": "text"}}}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p.update(doc_type="contract", fields={"start": "2026-01-01", "notice": "3 Monate"})
        self.propose(doc, p)
        self.pw("export")
        rows = self.csv_rows("all", "class-contract.csv")
        self.assertEqual((rows[0]["start"], rows[0]["notice"]), ("2026-01-01", "3 Monate"))
        self.assertEqual(list(rows[0])[:7], ["id", "entity", "counterparty", "issue_date", "status", "confirmed", "path"])
        self.assertTrue(self.pw("export")[1]["unchanged"])

    def test_config_adds_a_class_with_required_fields(self):
        self.write_config(classes={"policy": {"label": "insurance policy",
                                              "fields": {"policy_number": {"type": "text"},
                                                         "start": {"type": "date"}},
                                              "required": ["issue_date", "seller.name", "fields.policy_number"]}})
        self.drop("a.pdf", text_pdf([hoster_invoice(extra=["Versicherungsschein Nr. VS-77"])]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p["doc_type"] = "policy"
        code, view, _ = self.propose(doc, p)
        self.assertEqual(code, 3)
        self.assertIn("required:fields.policy_number", [c["id"] for c in view["problems"]])
        p["fields"] = {"policy_number": "VS-77", "start": "2026-01-01"}
        path = os.path.join(self.root, "_paperwork", "proposals", doc + ".json")
        write_json(path, p)
        code, view, err = self.pw("record", doc, path, "--force")
        self.assertEqual(code, 0, (view, err))

    def test_bad_class_config_fails(self):
        self.write_config(classes={"Bad Key": {}})
        code, _, err = self.pw("status")
        self.assertNotEqual(code, 0)
        self.assertIn("classes", err)
        self.write_config(classes={"policy": {"fields": {"x": {"type": "colour"}}}})
        code, _, err = self.pw("status")
        self.assertIn("policy", err)

    def test_removed_class_goes_to_review(self):
        self.write_config(classes={"policy": {}})
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p["doc_type"] = "policy"
        self.assertEqual(self.propose(doc, p)[0], 0)
        self.write_config(classes={})
        self.pw("ingest")  # any recompute
        view = self.pw("show", doc[:8])[1]
        self.assertEqual(view["status"], "review")
        self.assertIn("class", [c["id"] for c in view["problems"]])

    def test_inbox_to_archive_round_trip(self):
        # The file name lies: the content decides everything.
        self.drop("Telekom_Rechnung_Mai.pdf", text_pdf([hoster_invoice()]))
        code, rep, err = self.pw("ingest")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(rep["new"]), 1)
        pending = self.only_pending()
        self.assertEqual(len(pending), 1)
        self.assertNotIn("Telekom", json.dumps(pending))
        self.assertIn("Rechnungsnummer: RE-2026-0042", read(pending[0]["text"]))
        code, view, err = self.propose(pending[0]["id"], hoster_proposal())
        self.assertEqual(code, 0, (view, err))
        self.assertEqual(view["status"], "unconfirmed")
        self.assertEqual(self.pw("confirm", view["id"][:8])[0], 0)
        view = self.pw("show", view["id"][:8])[1]
        self.assertEqual(view["status"], "ok")
        self.assertEqual((view["entity"], view["direction"], view["counterparty"]), ("nordlicht", "in", "muster-hosting"))
        before = all_files(self.root)
        plan, res = self.file_all()
        doc = view["id"]
        expect = f"nordlicht/2026/in/2026-03-14_inv_muster-hosting_RE-2026-0042_119.00EUR_{doc[:8]}.pdf"
        self.assertEqual(plan["by_destination"]["to archive"][0]["to"], expect)
        after = all_files(self.root)
        self.assertEqual(sorted(before.values()), sorted(after.values()), "files moved, none lost or changed")
        self.assertEqual(self.pw("show", doc[:8])[1]["status"], "filed")
        code, v, _ = self.pw("verify")
        self.assertEqual(code, 0, v)

        code, ex, err = self.pw("export")
        self.assertEqual(code, 0, err)
        rows = self.csv_rows("all", "documents.csv")
        self.assertEqual(rows[0]["gross"], "119.00")
        self.assertEqual(rows[0]["billing_address"], "Musterweg 1 | 12345 Musterstadt")
        self.assertEqual(rows[0]["entity"], "nordlicht")
        lines = self.csv_rows("nordlicht", "lines.csv")
        self.assertEqual(lines[0]["description"], "Cloud Server M")
        vat = self.csv_rows("all", "vat_summary.csv")
        self.assertEqual((vat[0]["month"], vat[0]["rate"], vat[0]["tax"]), ("2026-03", "19", "19.00"))
        de = read(os.path.join(self.root, "exports", "all", "documents-de.csv"))
        self.assertTrue(de.startswith("﻿"))
        self.assertIn(";119,00;", de)
        code, ex2, _ = self.pw("export")
        self.assertTrue(ex2["unchanged"], "the same archive exports byte-identical files")

        code, u, err = self.pw("undo", plan["plan"])
        self.assertEqual(code, 0, (u, err))
        self.assertTrue(os.path.exists(os.path.join(self.root, "_inbox", "Telekom_Rechnung_Mai.pdf")))

    def test_evidence_must_match_the_text(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        code, view, _ = self.propose(doc, hoster_proposal(gross="191.00", tax="91.00", printed_gross="191,00 €"))
        self.assertEqual(code, pw.EXIT_REVIEW)
        ids = {p["id"] for p in view["problems"]}
        self.assertIn("evidence:gross", ids)
        self.assertIn("tax:rate", ids)

    def test_misread_date_is_caught(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        code, view, _ = self.propose(doc, hoster_proposal(date="2026-03-15"))
        self.assertEqual(code, pw.EXIT_REVIEW)
        self.assertIn("evidence:issue_date", {p["id"] for p in view["problems"]})

    def test_arithmetic(self):
        self.drop("a.pdf", text_pdf([hoster_invoice(gross="120,00")]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        code, view, _ = self.propose(doc, hoster_proposal(gross="120.00", printed_gross="120,00 €"))
        self.assertEqual(code, pw.EXIT_REVIEW)
        self.assertIn("sum:gross", {p["id"] for p in view["problems"]})

    def test_unknown_buyer_goes_to_review_and_can_be_set(self):
        self.drop("a.pdf", text_pdf([hoster_invoice(buyer="Fremdfirma AG")]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal(buyer="Fremdfirma AG")
        p["buyer"]["vat_id"] = None
        code, view, _ = self.propose(doc, p)
        self.assertEqual(code, pw.EXIT_REVIEW)
        self.assertIn("entity", {x["id"] for x in view["problems"]})
        plan, _ = self.file_all()
        self.assertTrue(plan["by_destination"]["to _review"][0]["to"].startswith("_review/"))
        code, view, err = self.pw("set", doc, "entity=kranich")
        self.assertEqual(code, 0, (view, err))
        self.assertEqual(view["target"].split("/")[:3], ["kranich", "2026", "in"])

    def test_private_buyer_at_a_business_address_is_flagged(self):
        lines = hoster_invoice(buyer="Erika Mustermann")
        self.drop("a.pdf", text_pdf([lines]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal(buyer="Erika Mustermann")
        p["buyer"]["vat_id"] = None
        code, view, _ = self.propose(doc, p)
        self.assertEqual(view["entity"], "privat")
        self.assertIn("entity:shared-address", {w["id"] for w in view["warnings"]})

    def test_exact_duplicate_is_kept_and_moved(self):
        data = text_pdf([hoster_invoice()])
        self.drop("rechnung.pdf", data)
        self.drop("06_Juni/rechnung (1).pdf", data)
        code, rep, _ = self.pw("ingest")
        self.assertEqual(len(rep["new"]), 1)
        self.assertEqual(len(rep["exact_duplicates"]), 1)
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        before = all_files(self.root)
        plan, res = self.file_all()
        after = all_files(self.root)
        self.assertEqual(len(before), len(after))
        self.assertEqual(len([p for p in after if p.startswith("_duplicates/")]), 1)
        self.assertEqual(self.pw("verify")[0], 0)

    def test_same_document_twice_and_separate_orders(self):
        self.drop("x.pdf", text_pdf([hoster_invoice()]))
        self.drop("y.pdf", text_pdf([hoster_invoice(extra=["Kopie"])]))
        self.drop("z.pdf", text_pdf([hoster_invoice(number="RE-2026-0043")]))
        self.pw("ingest")
        pend = self.only_pending()
        self.assertEqual(len(pend), 3)
        for item in pend:
            text = read(item["text"])
            number = "RE-2026-0043" if "RE-2026-0043" in text else "RE-2026-0042"
            self.propose(item["id"], hoster_proposal(number=number))
        _, listing, _ = self.pw("list")
        statuses = sorted((d["number"], d["status"]) for d in listing["documents"])
        self.assertEqual(statuses, [("RE-2026-0042", "duplicate"), ("RE-2026-0042", "unconfirmed"),
                                    ("RE-2026-0043", "unconfirmed")])

    def test_credit_note_sign(self):
        lines = [x.replace("Rechnung", "Gutschrift") for x in hoster_invoice(net="-100,00", tax="-19,00", gross="-119,00")]
        self.drop("a.pdf", text_pdf([lines]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal(net="100.00", tax="19.00", gross="119.00", printed_gross="-119,00 €")
        p["doc_type"] = "cn"
        code, view, _ = self.propose(doc, p)
        self.assertIn("sign", {x["id"] for x in view["problems"]})
        code, view, err = self.pw("set", doc, "gross=-119.00", "net=-100.00",
                                  'tax=[{"rate":"19","net":"-100.00","tax":"-19.00"}]',
                                  'lines=[{"description":"Cloud Server M","quantity":"1","unit_price":"-100.00","net":"-100.00","tax_rate":"19"}]')
        self.assertEqual(code, 0, (view, err))
        self.assertIn("_cn_", view["target"])
        self.assertIn("_-119.00EUR_", view["target"])

    def test_zugferd_pdf_is_read_from_its_xml(self):
        xml = CII.format(type="380", seller_vat=HOSTER_VAT).encode()
        self.drop("scan_irgendwas.pdf", text_pdf([["Rechnung ZF-77", "Beratung Becker GmbH"]], attachment=("factur-x.xml", xml)))
        code, rep, err = self.pw("ingest")
        self.assertEqual(len(rep["from_xml"]), 1, (rep, err))
        _, listing, _ = self.pw("list")
        d = listing["documents"][0]
        self.assertEqual((d["status"], d["entity"], d["gross"], d["number"]), ("ok", "kranich", "1190.00", "ZF-77"))
        self.assertEqual(self.only_pending(), [])

    def test_xrechnung_ubl_file(self):
        self.drop("invoice.bin", UBL.format(seller_vat=KRANICH_VAT.replace("DE", "DE")).encode())
        self.pw("ingest")
        _, listing, _ = self.pw("list")
        d = listing["documents"][0]
        self.assertEqual((d["entity"], d["gross"], d["type"]), ("nordlicht", "107.00", "inv"))
        plan, _ = self.file_all()
        self.assertTrue(plan["by_destination"]["to archive"][0]["to"].endswith(".xml"), "named by content, not by .bin")

    def test_cii_credit_note_is_negative(self):
        xml = CII.format(type="381", seller_vat=HOSTER_VAT).encode()
        self.drop("cn.xml", xml)
        self.pw("ingest")
        _, listing, _ = self.pw("list")
        d = listing["documents"][0]
        self.assertEqual((d["type"], d["gross"], d["status"]), ("cn", "-1190.00", "ok"))

    def test_scan_is_ocred(self):
        tmp = os.path.join(self.tmp.name, "page")
        with open(tmp + ".pdf", "wb") as f:
            f.write(text_pdf([hoster_invoice()]))
        subprocess.run(["pdftoppm", "-r", "200", "-gray", "-jpeg", "-singlefile", tmp + ".pdf", tmp], check=True)
        with open(tmp + ".jpg", "rb") as f:
            self.drop("scan0074.pdf", image_pdf(f.read()))
        self.pw("ingest")
        pend = self.only_pending()
        self.assertEqual(pend[0]["media"], "pdf-scan")
        self.assertEqual(len(pend[0]["images"]), 1)
        self.assertIn("read_also", pend[0])
        text = read(pend[0]["text"])
        self.assertIn("Muster Hosting", text)
        code, view, _ = self.propose(pend[0]["id"], hoster_proposal())
        self.assertIn(view["status"], ("unconfirmed", "review"))

    def test_template_learns_a_vendor(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        self.pw("confirm", doc[:8])  # a template is tested against confirmed documents only
        template = {
            "match": ["Muster Hosting GmbH", HOSTER_VAT],
            "fixed": {"doc_type": "inv", "currency": "EUR",
                      "seller": {"name": "Muster Hosting GmbH", "address": ["Serverstr. 5", "10115 Berlin"],
                                 "vat_id": HOSTER_VAT, "country": "DE"}},
            "fields": {
                "invoice_number": {"pattern": r"Rechnungsnummer:\s*(\S+)"},
                "issue_date": {"pattern": r"Rechnungsdatum:\s*(\d{2}\.\d{2}\.\d{4})", "type": "date"},
                "net": {"pattern": r"Summe netto\s+([\d.,]+ €)", "type": "amount", "decimal": ","},
                "gross": {"pattern": r"Gesamtbetrag\s+([\d.,]+ €)", "type": "amount", "decimal": ","},
                "tax": {"pattern": r"(\d+) % USt\.\s+([\d.,]+) €", "repeat": True, "type": "amount", "decimal": ",",
                        "groups": {"rate": 1, "tax": 2}},
                "buyer.name": {"pattern": r"Rechnungsadresse:\s*\n\s*(.+)"},
            },
        }
        tpath = os.path.join(self.root, "_paperwork", "templates", "muster-hosting.json")
        bad = json.loads(json.dumps(template))
        bad["fields"]["gross"]["pattern"] = r"Summe netto\s+([\d.,]+ €)"
        write_json(tpath, bad)
        code, res, _ = self.pw("template", "set", "muster-hosting", tpath)
        self.assertEqual(code, pw.EXIT_CHECK)
        self.assertFalse(res["saved"])
        # tax entries need their net too: a template that leaves it out fails the test
        template["fields"]["tax"] = {"pattern": r"(\d+) % USt\.\s+([\d.,]+) €", "repeat": True, "type": "amount",
                                     "decimal": ",", "groups": {"rate": 1, "tax": 2}}
        template["fields"]["tax"]["groups"] = {"rate": 1, "tax": 2}
        write_json(tpath, template)
        code, res, _ = self.pw("template", "test", "muster-hosting", tpath)
        self.assertEqual(code, pw.EXIT_CHECK)
        template["fields"]["tax"] = {
            "pattern": r"Summe netto\s+([\d.,]+) €\s*\n\s*(\d+) % USt\.\s+([\d.,]+) €", "repeat": True,
            "type": "amount", "decimal": ",", "groups": {"net": 1, "rate": 2, "tax": 3}}
        write_json(tpath, template)
        code, res, err = self.pw("template", "set", "muster-hosting", tpath)
        self.assertEqual(code, 0, (res, err))
        self.drop("b.pdf", text_pdf([hoster_invoice(number="RE-2026-0050", date="14.04.2026")]))
        code, rep, _ = self.pw("ingest")
        self.assertEqual(len(rep["from_template"]), 1, rep)
        _, listing, _ = self.pw("list")
        new = [d for d in listing["documents"] if d["number"] == "RE-2026-0050"][0]
        self.assertEqual((new["status"], new["date"], new["gross"]), ("ok", "2026-04-14", "119.00"))

    def test_untaxed_documents_have_unknown_net_in_the_vat_summary(self):
        lines = ["Example Software Inc., 1 Main St, Springfield", "Invoice US-9", "Date: Jul 24, 2026",
                 "Bill to: Nordlicht Digital GmbH, Musterweg 1, 12345 Musterstadt", "Total $49.00"]
        self.drop("a.pdf", text_pdf([lines]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        code, view, err = self.propose(doc, {
            "doc_type": "inv", "issue_date": "2026-07-24", "invoice_number": "US-9", "currency": "USD", "gross": "49.00",
            "seller": {"name": "Example Software Inc.", "country": "US"},
            "buyer": {"name": "Nordlicht Digital GmbH", "address": ["Musterweg 1", "12345 Musterstadt"]},
            "evidence": {"issue_date": "Jul 24, 2026", "gross": "$49.00"}})
        self.assertEqual(code, 0, (view, err))
        self.assertIn("tax:none", {w["id"] for w in view["warnings"]})
        self.pw("export")
        row = self.csv_rows("all", "vat_summary.csv")[0]
        self.assertEqual((row["rate"], row["net"], row["tax"], row["gross"]), ("unknown", "", "", "49.00"))

    def test_lock(self):
        with open(os.path.join(self.root, "_paperwork", "lock"), "w") as f:
            f.write("someone")
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        code, _, err = self.pw("ingest")
        self.assertEqual(code, pw.EXIT_LOCKED)
        self.assertIn("locked", err)

    def test_unsupported_file_goes_to_review(self):
        self.drop("notes.pdf", b"this is not a pdf at all")
        self.pw("ingest")
        plan, _ = self.file_all()
        self.assertTrue(plan["by_destination"]["to _review"][0]["to"].endswith(".bin"))

    def test_extension_comes_from_content(self):
        self.drop("photo.jpg", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        self.propose(self.only_pending()[0]["id"], hoster_proposal())
        plan, _ = self.file_all()
        self.assertTrue(plan["by_destination"]["to archive"][0]["to"].endswith(".pdf"))

    def test_manual_move_is_relinked(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        self.propose(doc, hoster_proposal())
        self.file_all()
        _, view, _ = self.pw("show", doc)
        moved = os.path.join(self.root, "somewhere", "else.pdf")
        os.makedirs(os.path.dirname(moved))
        os.rename(os.path.join(self.root, view["path"]), moved)
        self.assertEqual(self.pw("verify")[0], pw.EXIT_CHECK)
        code, rep, _ = self.pw("ingest", "--adopt")
        self.assertEqual(rep["relinked"][0]["path"], "somewhere/else.pdf")
        self.file_all()
        self.assertEqual(self.pw("verify")[0], 0)

    def test_apply_never_overwrites(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        self.propose(self.only_pending()[0]["id"], hoster_proposal())
        code, plan, _ = self.pw("plan")
        target = os.path.join(self.root, plan["by_destination"]["to archive"][0]["to"])
        os.makedirs(os.path.dirname(target))
        with open(target, "w") as f:
            f.write("already here")
        code, res, _ = self.pw("apply", plan["file"])
        self.assertEqual(code, pw.EXIT_CHECK)
        self.assertEqual(res["skipped"][0]["reason"], "the target exists; nothing is overwritten")
        self.assertEqual(read(target), "already here")

    def test_proposal_format_is_strict(self):
        self.drop("a.pdf", text_pdf([hoster_invoice()]))
        self.pw("ingest")
        doc = self.only_pending()[0]["id"]
        p = hoster_proposal()
        p["gross"] = "119,00"
        code, _, err = self.propose(doc, p)
        self.assertEqual(code, pw.EXIT_USAGE)
        self.assertIn("dot decimal", err)
        p = hoster_proposal()
        p["total"] = "1"
        self.assertEqual(self.propose(doc, p)[0], pw.EXIT_USAGE)


class Guard(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(HERE.parent / "hooks"))
        import guard
        self.g = guard
        self.root = "/data/Belege"

    def verdict(self, tool, tool_input, cwd="/home/u"):
        return self.g.decide({"tool_name": tool, "tool_input": tool_input, "cwd": cwd}, [self.root])

    def test_bash(self):
        deny = lambda c, cwd="/home/u": self.assertIsNotNone(self.verdict("Bash", {"command": c}, cwd), c)  # noqa: E731
        allow = lambda c, cwd="/home/u": self.assertIsNone(self.verdict("Bash", {"command": c}, cwd), c)  # noqa: E731
        deny("rm /data/Belege/nordlicht/2026/in/x.pdf")
        deny("rm -rf _inbox", cwd="/data/Belege")
        deny("mv /data/Belege/_inbox/a.pdf /tmp/")
        deny("echo hi > /data/Belege/_inbox/a.pdf")
        deny("find /data/Belege -name '*.pdf' -delete")
        deny("cd /data/Belege && rm x.pdf")
        deny("cp ~/Downloads/a.pdf /data/Belege/_inbox/")
        allow("cp -n ~/Downloads/a.pdf /data/Belege/_inbox/")
        allow("ls -la /data/Belege/_inbox")
        allow("paperwork ingest && paperwork plan", cwd="/data/Belege")
        allow("/opt/x/bin/paperwork apply /data/Belege/_paperwork/plans/abc.json")
        allow("rm /tmp/scratch.json")
        allow("cat /data/Belege/_paperwork/derived/abc/text.txt")
        deny("paperwork plan; rm /data/Belege/a.pdf")

    def test_edits(self):
        self.assertIsNotNone(self.verdict("Write", {"file_path": "/data/Belege/nordlicht/2026/in/a.pdf"}))
        self.assertIsNotNone(self.verdict("Edit", {"file_path": "/data/Belege/_paperwork/docs/abc.json"}))
        self.assertIsNone(self.verdict("Write", {"file_path": "/data/Belege/_paperwork/proposals/abc.json"}))
        self.assertIsNone(self.verdict("Edit", {"file_path": "/data/Belege/_paperwork/config.json"}))
        self.assertIsNone(self.verdict("Write", {"file_path": "/data/Belege/_paperwork/templates/x.json"}))
        self.assertIsNone(self.verdict("Write", {"file_path": "/data/Belege/_paperwork/rules.json"}))
        self.assertIsNone(self.verdict("Write", {"file_path": "/data/Belege/_paperwork/rules/erika.json"}))
        self.assertIsNotNone(self.verdict("Write", {"file_path": "/data/Belege/_paperwork/rules.json.bak"}))
        self.assertIsNotNone(self.verdict("Write", {"file_path": "/data/Belege/_paperwork/rules/../docs/x.json"}))
        self.assertIsNone(self.verdict("Write", {"file_path": "/tmp/a.json"}))


if __name__ == "__main__":
    unittest.main()
