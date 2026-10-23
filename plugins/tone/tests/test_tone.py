"""Tests for `tone check`. Run: python3 -m unittest discover -s plugins/tone/tests

Every name, address, token and host here is made up.
"""

import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
import tone  # noqa: E402

BIN = HERE.parent / "bin" / "tone"


def ids(draft, profile="comment", audience=None, lang=None, severity=None):
    result = tone.check(draft, profile, audience, lang)
    return [f["id"] for f in result["findings"] if severity in (None, f["severity"])]


class Frontmatter(unittest.TestCase):
    def test_scalars_lists_and_blocks(self):
        data, body = tone.parse_frontmatter(
            '---\na: 3\nb: [2, 3]\nc: true\nd: "x y"\ne:\n  - "one"\n  - two\nf: []\n---\nbody\n')
        self.assertEqual(data, {"a": 3, "b": [2, 3], "c": True, "d": "x y", "e": ["one", "two"], "f": []})
        self.assertEqual(body, "body\n")

    def test_unclosed(self):
        with self.assertRaises(ValueError):
            tone.parse_frontmatter("---\na: 1\n")

    def test_shipped_profiles_load(self):
        self.assertEqual(tone.profile_names(), ["changelog", "comment", "issue"])
        for name in tone.profile_names():
            profile, base = tone.load(name)
            self.assertIn("audience_default", profile)
            self.assertTrue(base["filler_de"] and base["tells_en"] and base["made_by"])


class Clean(unittest.TestCase):
    def test_good_texts_are_clean(self):
        cases = [
            ("comment", "Behoben: Der Export enthält neue Rechnungen jetzt sofort, nicht erst nach einer Stunde."),
            ("comment", "Decision: we keep the hourly sync and add a manual \"Sync now\" button. "
                        "Hourly is enough for the reports; the button covers urgent cases."),
            ("issue", "# Zeilenumbrüche im Rechnungsexport erhalten\n\n## Problem\n"
                      "Mehrzeilige Notizen erscheinen im PDF-Export in einer Zeile.\n\n"
                      "## Fertig, wenn\n- [ ] Notizen behalten ihre Zeilenumbrüche\n"),
            ("changelog", "Exported invoices keep line breaks in notes."),
            ("changelog", "Die Synchronisierung läuft jetzt alle 15 Minuten statt stündlich."),
            ("comment", "Der Support ist 24/7 erreichbar, auch am 1.10.2026 und per Telefon und/oder Chat."),
        ]
        for profile, draft in cases:
            with self.subTest(draft=draft):
                self.assertEqual(tone.check(draft, profile)["findings"], [])


class Exposure(unittest.TestCase):
    def test_secrets_in_any_audience_are_masked(self):
        draft = "Use token ghp_abcdefghijklmnopqrstuvwx1234 for the import."
        result = tone.check(draft, "comment", "internal")
        secret = [f for f in result["findings"] if f["id"] == "TONE-010"]
        self.assertTrue(secret)
        self.assertNotIn("abcdefghij", json.dumps(result))

    def test_other_secret_shapes(self):
        for draft in ["password: hunter22", "postgres://app:s3cret@db.example.com/x",
                      "Key AKIAABCDEFGHIJKLMNOP", "-----BEGIN RSA PRIVATE KEY-----",
                      "https://files.example.com/a.pdf?X-Amz-Signature=abc"]:
            with self.subTest(draft=draft):
                self.assertIn("TONE-010", ids(draft, audience="internal"))

    def test_personal_data_error_external_note_internal(self):
        draft = "Bitte an max.muster@example.com oder +49 170 1234567 wenden."
        self.assertEqual(ids(draft, audience="external", severity="error").count("TONE-011"), 2)
        self.assertEqual(ids(draft, audience="internal", severity="note").count("TONE-011"), 2)
        self.assertEqual(ids(draft, audience="internal", severity="error"), [])

    def test_amounts_and_dates_are_not_phones(self):
        self.assertNotIn("TONE-011", ids("Betrag 1.234.567,00 EUR am 2026-10-23, Nr. 0815."))

    def test_made_by(self):
        self.assertIn("TONE-014", ids("Claude hat den Fehler gefunden und behoben."))
        self.assertIn("TONE-014", ids("This was AI-generated."))

    def test_internals_only_flagged_for_external(self):
        draft = ("Fixed in src/export/pdf.ts via renderNotes() on feat/export-notes, commit 3f9a2c1e. "
                 "Traceback (most recent call last) at 10.0.4.12.")
        external = ids(draft, audience="external")
        self.assertGreaterEqual(external.count("TONE-020"), 6)
        self.assertNotIn("TONE-020", ids(draft, audience="internal"))

    def test_code_is_internal(self):
        self.assertIn("TONE-020", ids("Run `make export` again.", audience="external"))
        self.assertIn("TONE-020", ids("Log:\n```\nboom\n```\n", audience="external"))

    def test_log_line(self):
        self.assertIn("TONE-020", ids("2026-10-23T08:12:01Z ERROR export failed", audience="external"))

    def test_urls(self):
        found = tone.check("See http://grafana.internal/d/1 and https://docs.example.com/x.", "comment")
        by_id = {f["id"]: f for f in found["findings"]}
        self.assertEqual(by_id["TONE-021"]["severity"], "error")
        self.assertEqual(by_id["TONE-022"]["severity"], "note")
        self.assertEqual(by_id["TONE-022"]["quote"], "https://docs.example.com/x")
        self.assertIn("TONE-021", ids("Läuft auf http://localhost:8080 und http://10.1.2.3/x."))
        self.assertNotIn("TONE-022", ids("See https://docs.example.com/x.", audience="internal"))

    def test_bare_internal_host(self):
        self.assertIn("TONE-021", ids("Der Job läuft auf billing.corp jede Nacht."))


class Style(unittest.TestCase):
    def test_filler_and_tells_both_languages(self):
        self.assertIn("TONE-041", ids("Grundsätzlich ist der Export wieder da. Viele Grüße"))
        self.assertIn("TONE-041", ids("Thanks for reporting! The export works again."))
        self.assertIn("TONE-042", ids("Der Export läuft jetzt nahtlos."))
        self.assertIn("TONE-042", ids("This is not just faster but also safer."))
        self.assertIn("TONE-042", ids("Der Export ist nicht nur schneller, sondern auch stabiler."))

    def test_dashes_and_emoji(self):
        self.assertIn("TONE-042", ids("The export works — finally."))
        self.assertIn("TONE-042", ids("Der Export läuft – endlich."))
        self.assertIn("TONE-042", ids("Export works again 🎉"))
        self.assertNotIn("TONE-042", ids("Seiten 10–20 sind betroffen."))

    def test_guesses_are_notes(self):
        found = ids("Das lag vermutlich am Cache und sollte jetzt behoben sein.")
        self.assertIn("TONE-001", found)
        self.assertNotIn("TONE-001", ids("Das lag vermutlich am Cache.", severity="error"))

    def test_word_boundaries(self):
        self.assertNotIn("TONE-001", ids("This is unlikely to matter."))
        self.assertNotIn("TONE-041", ids("Der Export ist eigenständig."))


class Address(unittest.TestCase):
    def test_mixed_du_and_sie(self):
        self.assertIn("TONE-051", ids("Kannst du den Export prüfen? Danach senden wir Ihnen die Datei."))

    def test_one_form_is_fine(self):
        self.assertNotIn("TONE-051", ids("Können Sie den Export prüfen? Wir senden Ihnen die Datei."))
        self.assertNotIn("TONE-051", ids("Kannst du den Export prüfen? Sie ist fertig."))

    def test_english_not_checked(self):
        self.assertNotIn("TONE-051", ids("You and Sie are names here, du too.", lang="en"))


class Shape(unittest.TestCase):
    def test_issue_title(self):
        found = ids("# [Bug] The dashboard does not load revenue widgets for accounts without currency.\n\nBody.",
                    profile="issue")
        for rule in ["TONE-060", "TONE-061", "TONE-062"]:
            self.assertIn(rule, found)
        self.assertIn("TONE-061", ids("# fix(export): keep line breaks\n", profile="issue"))

    def test_issue_without_title_is_a_note(self):
        result = tone.check("Only a body.", "issue")
        self.assertEqual([(f["id"], f["severity"]) for f in result["findings"]], [("TONE-060", "note")])

    def test_issue_body_words_skip_checklists(self):
        body = "# Keep notes\n\n" + "wort " * 110 + "\n" + "- [ ] " + "punkt " * 50 + "\n"
        self.assertNotIn("TONE-063", ids(body, profile="issue"))
        self.assertIn("TONE-063", ids("# Keep notes\n\n" + "wort " * 121, profile="issue"))

    def test_issue_headings_tables_bold(self):
        draft = "# Keep notes\n\n### Deep\n| a | b |\n**one** and **two**\n"
        self.assertEqual(ids(draft, profile="issue").count("TONE-043"), 3)

    def test_comment_limits(self):
        self.assertIn("TONE-064", ids("One. Two. Three. Four."))
        self.assertIn("TONE-065", ids("Status:\n- a\n- b\n- c\n- d\n- e\n"))
        self.assertIn("TONE-063", ids("wort " * 61))
        self.assertIn("TONE-043", ids("## Update\nDone."))
        self.assertIn("TONE-043", ids("Done **now**."))

    def test_sentences_skip_dates_and_abbreviations(self):
        cases = [("Die Auswertung ist da. Fehlende Buchungen vom 3. und 4.10. wurden nachgeladen.", 2),
                 ("Ab 1.11. gilt das. Tel. Hotline bleibt. Ca. 4 % mehr.", 3),
                 ("Kanal (z. B. Booking.com) und e.g. Expedia. Fertig", 2),
                 ("Wirklich? Ja!", 2), ("Am 3. Oktober live.", 1), ("", 0)]
        for text, n in cases:
            with self.subTest(text=text):
                self.assertEqual(tone.count_sentences(text), n)

    def test_changelog(self):
        self.assertIn("TONE-066", ids("One.\nTwo.", profile="changelog"))
        self.assertIn("TONE-067", ids("x" * 101, profile="changelog"))
        self.assertIn("TONE-068", ids("Fixed IND-412 export.", profile="changelog"))
        self.assertIn("TONE-068", ids("Fixed #42.", profile="changelog"))

    def test_changelog_is_always_external(self):
        result = tone.check("Fixed in src/export/pdf.ts.", "changelog", "internal")
        self.assertEqual(result["audience"], "external")
        self.assertIn("TONE-020", [f["id"] for f in result["findings"]])


class Order(unittest.TestCase):
    def test_exposure_before_style_errors_before_notes(self):
        result = tone.check("Grundsätzlich vermutlich ok, schreib an a.b@example.com.", "comment")
        got = [(f["severity"], f["id"]) for f in result["findings"]]
        self.assertEqual(got[0], ("error", "TONE-011"))
        self.assertEqual(got[-1], ("note", "TONE-001"))

    def test_deterministic(self):
        draft = "Kannst du `x()` prüfen — vermutlich src/a/b.ts. Ihnen danke ich."
        self.assertEqual(tone.check(draft, "comment"), tone.check(draft, "comment"))


class Language(unittest.TestCase):
    def test_detection(self):
        self.assertEqual(tone.check("Der Export ist wieder da und läuft.", "comment")["language"], "de")
        self.assertEqual(tone.check("The export is back and it works.", "comment")["language"], "en")


class Cli(unittest.TestCase):
    def run_cli(self, *args, stdin=""):
        return subprocess.run([str(BIN), *args], input=stdin, capture_output=True, text=True)

    def test_exit_codes(self):
        self.assertEqual(self.run_cli("check", "--profile", "comment", "-",
                                      stdin="Der Export ist wieder da.").returncode, 0)
        bad = self.run_cli("check", "--profile", "comment", "-", stdin="Grundsätzlich ok.")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("TONE-041", bad.stdout)
        self.assertEqual(self.run_cli("check", "--profile", "nope", "-").returncode, 2)
        self.assertEqual(self.run_cli("check", "-").returncode, 2)
        self.assertEqual(self.run_cli("check", "--profile", "comment", "/no/such/file").returncode, 2)

    def test_notes_only_exit_zero(self):
        out = self.run_cli("check", "--profile", "comment", "-", stdin="Das lag vermutlich am Cache.")
        self.assertEqual(out.returncode, 0)
        self.assertIn("1 note", out.stdout)

    def test_json_and_profiles(self):
        out = self.run_cli("check", "--profile", "issue", "--json", "-", stdin="# Keep notes\n")
        data = json.loads(out.stdout)
        self.assertEqual(data["profile"], "issue")
        self.assertEqual(self.run_cli("profiles").stdout.split(), ["changelog", "comment", "issue"])

    def test_main_in_process(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = tone.main(["profiles"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
