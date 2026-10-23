"""Tests for `tracker check`. Run: python3 -m unittest discover -s plugins/tracker/tests

Every name, address, token and host here is made up.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
sys.path.insert(0, str(PLUGIN / "lib"))
import tracker  # noqa: E402

BIN = PLUGIN / "bin" / "tracker"


def draft(meta, body):
    return "---\n" + "\n".join("%s: %s" % kv for kv in meta.items()) + "\n---\n" + body


def ids(meta, body, severity=None):
    return [f["id"] for f in tracker.check(draft(meta, body))["findings"] if severity in (None, f["severity"])]


BUG_DE = """# Zeilenumbrüche im Rechnungsexport erhalten

Kurz: Mehrzeilige Notizen landen im PDF-Export in einer Zeile und sollen ihre Umbrüche behalten.

## Problem
Seit dem 20.10. erscheinen mehrzeilige Notizen im PDF-Export in einer Zeile.

## Erwartet
Notizen behalten ihre Zeilenumbrüche.

## Schritte
1. Rechnung mit mehrzeiliger Notiz anlegen
2. Als PDF exportieren

## Fertig, wenn
- [ ] Notizen behalten ihre Zeilenumbrüche
"""

FEATURE_EN = """# Filter the revenue report by booking channel

TL;DR: Revenue managers want to compare booking channels inside the revenue report.

## Need
Revenue managers need to compare channels without exporting to a spreadsheet.

## Done when
- [ ] The report has a channel filter
- [ ] The filter is kept when the report is shared

## Not included
Channel costs and commissions.
"""

TASK_DE = """# Mietvertrag Büro Leipzig verlängern

Kurz: Der Mietvertrag für das Büro Leipzig soll vor dem Ablauf um zwei Jahre verlängert werden.

## Was
Den Mietvertrag um zwei Jahre verlängern.

## Warum
Er läuft am 31.12. aus.

## Fertig, wenn
- [ ] Verlängerung unterschrieben
- [ ] Kopie in der Buchhaltung abgelegt
"""

IMPROVEMENT_EN = """# Show sync progress while bookings import

TL;DR: Users cannot tell whether a booking import is still running.

## Today
The import shows nothing until it finishes, which takes up to ten minutes.

## Better
A progress bar shows how many bookings are imported.

## Done when
- [ ] The import shows how many bookings are done and how many are left
"""


class Issues(unittest.TestCase):
    def test_good_issues_are_clean(self):
        for kind, body in [("bug", BUG_DE), ("feature", FEATURE_EN), ("task", TASK_DE),
                           ("improvement", IMPROVEMENT_EN)]:
            with self.subTest(kind=kind):
                self.assertEqual(tracker.check(draft({"type": "issue", "kind": kind}, body))["findings"], [])

    def test_kind_required(self):
        self.assertIn("CI-006", ids({"type": "issue"}, FEATURE_EN))
        self.assertIn("CI-006", ids({"type": "issue", "kind": "chore"}, FEATURE_EN))

    def test_title_rules(self):
        found = ids({"type": "issue", "kind": "feature"},
                    FEATURE_EN.replace("# Filter the revenue report by booking channel",
                                       "# [Feature] Filter the revenue report by booking channel and by the "
                                       "property it belongs to."))
        self.assertEqual(found.count("CI-010"), 2)
        self.assertIn("CI-011", found)
        for title in ["fix(export): keep notes", "IND-12 Keep notes", "Bug: keep notes"]:
            with self.subTest(title=title):
                self.assertIn("CI-011", ids({"type": "issue", "kind": "task"}, TASK_DE.replace(
                    "# Mietvertrag Büro Leipzig verlängern", "# " + title)))

    def test_missing_title(self):
        self.assertIn("CI-010", ids({"type": "issue", "kind": "task"}, TASK_DE.split("\n", 2)[2]))

    def test_bug_title_naming_the_symptom_is_a_note(self):
        found = tracker.check(draft({"type": "issue", "kind": "bug"},
                                    BUG_DE.replace("# Zeilenumbrüche im Rechnungsexport erhalten",
                                                   "# Fehler im Rechnungsexport")))["findings"]
        self.assertEqual([(f["id"], f["severity"]) for f in found], [("CI-012", "note")])

    def test_required_sections(self):
        found = ids({"type": "issue", "kind": "bug"}, "# Keep notes\n\n## Problem\nNotes lose line breaks.\n")
        self.assertIn("CI-021", found)

    def test_foreign_unknown_and_misordered_sections(self):
        self.assertIn("CI-021", ids({"type": "issue", "kind": "feature"}, FEATURE_EN + "\n## Steps\n1. a\n"))
        self.assertIn("CI-021", ids({"type": "issue", "kind": "feature"}, FEATURE_EN + "\n## Context\nText.\n"))
        self.assertIn("CI-021", ids({"type": "issue", "kind": "feature"}, FEATURE_EN + "\n### Detail\nText.\n"))
        self.assertIn("CI-021", ids({"type": "issue", "kind": "task"},
                                    "# Vertrag verlängern\n\nKurz: Vertrag verlängern.\n\n## Fertig, wenn\n- [ ] Unterschrieben\n\n"
                                    "## Was\nVerlängern.\n\n## Warum\nLäuft aus.\n"))

    def test_every_kind_says_why_and_done_when(self):
        self.assertIn("CI-021", ids({"type": "issue", "kind": "task"}, TASK_DE.replace(
            "## Warum\nEr läuft am 31.12. aus.\n\n", "")))
        self.assertIn("CI-021", ids({"type": "issue", "kind": "bug"}, BUG_DE.split("## Fertig, wenn")[0]))
        self.assertIn("CI-021", ids({"type": "issue", "kind": "improvement"},
                                    IMPROVEMENT_EN.split("## Done when")[0]))

    def test_tldr(self):
        lead = "TL;DR: Revenue managers want to compare booking channels inside the revenue report.\n\n"
        cases = {
            "missing": FEATURE_EN.replace(lead, ""),
            "no lead": FEATURE_EN.replace("TL;DR: ", ""),
            "two sentences": FEATURE_EN.replace("report.\n\n## Need", "report. They ask weekly.\n\n## Need"),
            "too long": FEATURE_EN.replace("inside the revenue report", "inside " + "the report " * 12),
            "after a section": FEATURE_EN.replace(lead, "").replace("## Done when", lead + "## Done when"),
        }
        for name, body in cases.items():
            with self.subTest(case=name):
                self.assertIn("CI-024", ids({"type": "issue", "kind": "feature"}, body))
        self.assertNotIn("CI-024", ids({"type": "issue", "kind": "bug"}, BUG_DE))

    def test_text_outside_sections(self):
        self.assertIn("CI-021", ids({"type": "issue", "kind": "task"}, TASK_DE.replace(
            "## Was", "Kurz vorab.\n\n## Was")))

    def test_section_contents(self):
        self.assertIn("CI-022", ids({"type": "issue", "kind": "task"}, TASK_DE.replace(
            "- [ ] Verlängerung unterschrieben", "Verlängerung unterschrieben")))
        self.assertIn("CI-022", ids({"type": "issue", "kind": "bug"}, BUG_DE.replace(
            "1. Rechnung", "- Rechnung")))
        self.assertIn("CI-005", ids({"type": "issue", "kind": "bug"}, BUG_DE.replace(
            "Notizen behalten ihre Zeilenumbrüche.\n", "")))

    def test_placeholders(self):
        for word in ["TBD", "unknown", "unbekannt", "<name>"]:
            with self.subTest(word=word):
                self.assertIn("CI-005", ids({"type": "issue", "kind": "task"}, TASK_DE.replace(
                    "zwei Jahre", word)))

    def test_body_words_skip_checklists(self):
        body = "# Keep notes\n\n## What\n" + "word " * 110 + "\n\n## Done when\n" + "- [ ] item\n" * 30
        self.assertNotIn("CI-020", ids({"type": "issue", "kind": "task"}, body))
        self.assertIn("CI-020", ids({"type": "issue", "kind": "task"},
                                    "# Keep notes\n\n## What\n" + "word " * 121 + "\n\n## Done when\n- [ ] a\n"))


class Comments(unittest.TestCase):
    def test_leads(self):
        good = [("progress", "Stand: Der Import läuft wieder. Als Nächstes prüfen wir die Oktober-Daten."),
                ("decision", "Decision: we keep the hourly sync, because the reports need no more."),
                ("question", "Frage an Lena: Sollen Stornos im Umsatz erscheinen?"),
                ("question", "Question for @maria: which properties are affected?"),
                ("blocker", "Blockiert: Zugang zum Channel-Manager fehlt. Braucht Freigabe vom Kunden.")]
        for purpose, text in good:
            with self.subTest(text=text):
                self.assertEqual(ids({"type": "comment", "purpose": purpose}, text), [])
        self.assertIn("CI-030", ids({"type": "comment", "purpose": "decision"}, "We keep the hourly sync."))
        self.assertIn("CI-030", ids({"type": "comment", "purpose": "talk"}, "Status: ok."))

    def test_length_headings_greetings(self):
        self.assertIn("CI-030", ids({"type": "comment", "purpose": "progress"}, "Status: " + "word " * 60))
        self.assertIn("CI-030", ids({"type": "comment", "purpose": "progress"}, "Status: ok.\n## More\nx"))
        for text in ["Hallo zusammen, Stand: ok.", "Status: ok. Best regards", "Stand: ok. Viele Grüße"]:
            with self.subTest(text=text):
                self.assertIn("CI-030", ids({"type": "comment", "purpose": "progress"}, text))

    def test_handoff(self):
        ok = ("Ready for review: exported invoices keep line breaks in notes.\n"
              "To check: export an invoice with multi-line notes.\nOpen: none.")
        self.assertEqual(ids({"type": "comment", "purpose": "handoff"}, ok), [])
        self.assertEqual(ids({"type": "comment", "purpose": "handoff"}, "Übergabe an Swen: Vertrag liegt bereit."), [])
        self.assertIn("CI-040", ids({"type": "comment", "purpose": "handoff"}, "Open: none.\nReady for review: x."))
        self.assertIn("CI-040", ids({"type": "comment", "purpose": "handoff"}, "Please review this."))
        self.assertIn("CI-040", ids({"type": "comment", "purpose": "handoff"},
                                    "Ready for review: x.\nAlso a note.\nOpen: none."))

    def test_close(self):
        good = [("done", "Erledigt: Exportierte Rechnungen behalten Zeilenumbrüche. Folgeaufgabe: IND-88."),
                ("wont-do", "Not doing: the export is replaced by the new report in November."),
                ("works-as-intended", "Funktioniert wie vorgesehen: Stornos zählen nicht zum Umsatz. "
                                      "Sie stehen im Storno-Report."),
                ("duplicate", "Duplikat von IND-42."),
                ("cant-reproduce", "Not reproducible: exports with multi-line notes work on all tested accounts. "
                                   "Reopen with an example invoice."),
                ("obsolete", "Nicht mehr relevant: Der alte Export wurde abgeschaltet.")]
        for result, text in good:
            with self.subTest(result=result):
                self.assertEqual(ids({"type": "comment", "purpose": "close", "result": result}, text), [])
        self.assertIn("CI-050", ids({"type": "comment", "purpose": "close", "result": "done"}, "Fixed it."))
        self.assertIn("CI-050", ids({"type": "comment", "purpose": "close", "result": "maybe"}, "Done: x."))
        self.assertIn("CI-050", ids({"type": "comment", "purpose": "close", "result": "done"},
                                    "Done: one. Two. Three."))


class Exposure(unittest.TestCase):
    def test_external_by_default(self):
        text = "Status: fixed in src/export/pdf.ts, commit 3f9a2c1e."
        self.assertIn("CI-003", ids({"type": "comment", "purpose": "progress"}, text))
        self.assertNotIn("CI-003", ids({"type": "comment", "purpose": "progress", "audience": "internal"}, text))

    def test_secrets_and_personal_data(self):
        self.assertIn("CI-002", ids({"type": "comment", "purpose": "progress", "audience": "internal"},
                                    "Status: token ghp_abcdefghijklmnopqrstuvwx1234 rotated."))
        self.assertIn("CI-002", ids({"type": "comment", "purpose": "progress"}, "Status: wrote to max@example.com."))
        result = tracker.check(draft({"type": "comment", "purpose": "progress"},
                                     "Status: key sk-abcdefghijklmnopqrstuvwxyz rotated."))
        self.assertNotIn("abcdefghij", json.dumps(result))

    def test_hedges_are_notes(self):
        found = tracker.check(draft({"type": "comment", "purpose": "progress"},
                                    "Stand: Das lag vermutlich am Cache."))["findings"]
        self.assertEqual([(f["id"], f["severity"]) for f in found], [("CI-004", "note")])


class Frontmatter(unittest.TestCase):
    def test_type_and_audience(self):
        self.assertIn("CI-000", ids({"kind": "bug"}, BUG_DE))
        self.assertIn("CI-000", ids({"type": "issue", "kind": "bug", "audience": "team"}, BUG_DE))
        with self.assertRaises(ValueError):
            tracker.check("---\ntype: issue\n")


class Convention(unittest.TestCase):
    """The script's tables are the convention's tables."""

    text = (PLUGIN / "CONVENTION.md").read_text(encoding="utf-8")

    def test_section_names(self):
        for english, german in tracker.SECTIONS.values():
            self.assertIn("| %s | %s |" % (english, german), self.text)

    def test_shapes(self):
        for kind, shape in tracker.SHAPES.items():
            required = ", ".join(tracker.SECTIONS[k][0] for k, r in shape if r)
            optional = ", ".join(tracker.SECTIONS[k][0] for k, r in shape if not r) or "—"
            self.assertIn("| `%s` | %s | %s |" % (kind, required, optional), self.text)
            self.assertIn("`%s` %s." % (kind, ", ".join(tracker.SECTIONS[k][0] for k, _ in shape)), self.text)

    def test_close_leads_and_limits(self):
        for result, (en, de) in tracker.CLOSE_LEADS.items():
            row = "| `%s` | `%s` | `%s` |" % (result, en.replace("\\b", ""), de.replace("\\b", ""))
            self.assertIn(row, self.text)
        self.assertIn("At most %d characters" % tracker.TITLE_MAX, self.text)
        self.assertIn("At most %d words, not counting checklist lines" % tracker.BODY_MAX, self.text)
        self.assertIn("At most %d words and one purpose" % tracker.COMMENT_MAX, self.text)
        self.assertIn("at most %d words, led by `%s` (German `%s`)" % (tracker.TLDR_MAX, *tracker.TLDR), self.text)

    def test_rule_ids_exist(self):
        cited = set(re.findall(r"CI-\d{3}", (PLUGIN / "lib" / "tracker.py").read_text()))
        defined = set(re.findall(r"### (CI-\d{3})", self.text)) | {"CI-000"}
        self.assertLessEqual(cited, defined)


class Cli(unittest.TestCase):
    def run_cli(self, *args, stdin=""):
        return subprocess.run([str(BIN), *args], input=stdin, capture_output=True, text=True)

    def test_exit_codes(self):
        good = draft({"type": "issue", "kind": "task"}, TASK_DE)
        self.assertEqual(self.run_cli("check", "-", stdin=good).returncode, 0)
        bad = self.run_cli("check", "-", stdin=good.replace("verlängern\n", "verlängern.\n", 1))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("CI-010", bad.stdout)
        self.assertEqual(self.run_cli("check", "-", stdin="---\ntype: issue\n").returncode, 2)
        self.assertEqual(self.run_cli("check", "/no/such/file").returncode, 2)
        self.assertEqual(self.run_cli().returncode, 2)

    def test_json(self):
        out = self.run_cli("check", "--json", "-", stdin=draft({"type": "comment", "purpose": "progress"}, "Status: ok."))
        self.assertEqual(json.loads(out.stdout)["findings"], [])


if __name__ == "__main__":
    unittest.main()
