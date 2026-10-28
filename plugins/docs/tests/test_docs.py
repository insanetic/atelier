"""Tests for `docs`. Run: python3 -m unittest discover -s plugins/docs/tests

Every product, name, host and token here is made up.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
sys.path.insert(0, str(PLUGIN / "lib"))
import docs  # noqa: E402

BIN = PLUGIN / "bin" / "docs"
CONVENTION = (PLUGIN / "CONVENTION.md").read_text(encoding="utf-8")


def article(meta, body):
    return "---\n" + "\n".join("%s: %s" % kv for kv in meta.items()) + "\n---\n\n" + body


def ids(text, severity=None, path=None, lang=None):
    return [f["id"] for f in docs.check(text, path, lang)["findings"] if severity in (None, f["severity"])]


USER = {"title": "Export invoices as CSV", "description": "Download all invoices of a period as one CSV file.",
        "type": "how-to", "reader": "user"}

HOWTO_EN = """You can download all invoices of a period as one CSV file. Admins and accountants can do this.

## Before you begin

- You have the **Admin** or **Accounting** role.

## Steps

1. Select **Settings > Billing > Invoices**.
2. Choose the period.
3. Select **Export**. You get an email when the file is ready.

## If it doesn't work

- **The file is empty:** there are no invoices in this period. Choose another period.
"""

HOWTO_DE = """Sie können alle Rechnungen eines Zeitraums als CSV-Datei herunterladen.

## Voraussetzungen

- Sie haben die Rolle **Admin**.

## Schritte

1. Wählen Sie **Einstellungen > Abrechnung > Rechnungen**.
2. Wählen Sie den Zeitraum.
3. Wählen Sie **Exportieren**. Sie bekommen eine E-Mail, sobald die Datei bereit ist.
"""

DE = {"title": "Rechnungen als CSV exportieren", "description": "Laden Sie alle Rechnungen eines Zeitraums "
      "als CSV-Datei herunter.", "type": "how-to", "reader": "user", "lang": "de"}

QUICKSTART = """Install the Acme SDK and send a first event. It takes about five minutes.

## Before you begin

- Node.js 18 or later

## Install

```bash
npm install @acme/sdk
```

## Send an event

```js
import { Acme } from "@acme/sdk";
const acme = new Acme({ apiKey: "YOUR_API_KEY" });
await acme.track("signup");
```

## Check that it works

```text
event sent: signup
```

## Next steps

- Read about [events](https://docs.acme.example/events).
"""

DEV = {"title": "Get started with the Acme SDK", "description": "Install the SDK and send a first event.",
       "type": "quickstart", "reader": "developer", "applies_to": "\">=2.0\""}


class Tables(unittest.TestCase):
    """The script's tables match CONVENTION.md."""

    def test_headings_match_doc_080(self):
        section = CONVENTION.split("### DOC-080")[1]
        rows = re.findall(r"^\| (\w+) \| ([^|]+?) \| ([^|]+?) \|$", section, re.M)
        table = {key: {"en": en, "de": de} for key, en, de in rows if key != "Section"}
        self.assertEqual(table, docs.HEADINGS)

    def test_shapes_match_doc_021(self):
        section = CONVENTION.split("### DOC-021")[1].split("### DOC-022")[0]
        rows = re.findall(r"^\| (user|developer) / `([\w-]+)` \| (.+?) \|$", section, re.M)
        self.assertEqual(len(rows), len(docs.SHAPES))
        by_name = {v["en"]: k for k, v in docs.HEADINGS.items()}
        for reader, kind, cells in rows:
            shape = []
            for cell in cells.split(" · "):
                required = cell.startswith("**")
                name = (cell.strip()[2:-2] if required else cell.strip()).replace("\\*", "*")
                shape.append(("*" if name == "*" else by_name[name], required))
            self.assertEqual(shape, docs.SHAPES[(reader, kind)], (reader, kind))

    def test_types_match_doc_002(self):
        section = CONVENTION.split("### DOC-002")[1].split("### DOC-003")[0]
        for kind, readers in re.findall(r"^\| `([\w-]+)` \| ([\w, ]+) \|", section, re.M):
            for reader in readers.split(", "):
                self.assertIn(kind, docs.TYPES[reader])


class Check(unittest.TestCase):
    def test_good_articles_pass(self):
        self.assertEqual(ids(article(USER, HOWTO_EN), "error"), [])
        self.assertEqual(ids(article(DE, HOWTO_DE), "error"), [])
        self.assertEqual(ids(article(DEV, QUICKSTART), "error"), [])

    def test_frontmatter(self):
        self.assertIn("DOC-063", ids(HOWTO_EN))
        self.assertIn("DOC-063", ids(article({"title": "Export invoices"}, HOWTO_EN)))
        self.assertIn("DOC-002", ids(article(dict(USER, type="tips"), HOWTO_EN)))
        self.assertIn("DOC-002", ids(article(dict(USER, type="quickstart"), HOWTO_EN)))
        self.assertIn("DOC-001", ids(article(dict(USER, reader="admin"), HOWTO_EN)))

    def test_title(self):
        for title in ("How to export invoices", "Export invoices.", "Export " + "x" * 60):
            self.assertIn("DOC-010", ids(article(dict(USER, title=title), HOWTO_EN), "error"), title)
        self.assertIn("DOC-010", ids(article(dict(USER, title="Exporting invoices"), HOWTO_EN), "note"))
        self.assertIn("DOC-010", ids(article(dict(DE, title="Wie exportiere ich Rechnungen"), HOWTO_DE)))
        self.assertIn("DOC-011", ids(article(dict(USER, description="Export invoices as CSV"), HOWTO_EN)))

    def test_h1_in_body(self):
        self.assertIn("DOC-010", ids(article(USER, "# Export\n\n" + HOWTO_EN)))

    def test_intro(self):
        self.assertIn("DOC-020", ids(article(USER, HOWTO_EN.split("\n", 1)[1])))
        self.assertIn("DOC-020", ids(article(USER, "In this article you learn it. " + HOWTO_EN)))
        long_intro = "One. Two. Three. " + HOWTO_EN
        self.assertIn("DOC-020", ids(article(USER, long_intro)))

    def test_synonym_and_language_of_headings(self):
        found = docs.check(article(USER, HOWTO_EN.replace("## Before you begin", "## Prerequisites")))
        self.assertTrue(any(f["id"] == "DOC-080" and "Before you begin" in f["message"] for f in found["findings"]))
        self.assertIn("DOC-080", ids(article(DE, HOWTO_DE.replace("## Schritte", "## Steps"))))
        self.assertIn("DOC-080", ids(article(USER, HOWTO_EN.replace("## Steps", "## steps"))))

    def test_shape(self):
        self.assertIn("DOC-021", ids(article(USER, HOWTO_EN.replace("## Steps", "## Something else"))))
        swapped = HOWTO_EN.replace("## Before you begin", "## TMP").replace("## Steps", "## Before you begin") \
            .replace("## TMP", "## Steps")
        self.assertIn("DOC-021", ids(article(USER, swapped)))
        self.assertIn("DOC-021", ids(article(dict(USER, type="overview"), HOWTO_EN)))
        no_verify = QUICKSTART.replace("## Check that it works", "## Output")
        self.assertIn("DOC-021", ids(article(DEV, no_verify)))  # free heading allowed, but verify missing

    def test_free_sections(self):
        ref = "Every role and what it may do.\n\n## Admin\n\nEverything.\n\n## Viewer\n\nRead only.\n"
        self.assertEqual(ids(article(dict(USER, type="reference", title="Roles and permissions"), ref), "error"), [])

    def test_steps(self):
        many = "\n".join("%d. Select **Item %d**." % (i, i) for i in range(1, 10))
        self.assertIn("DOC-034", ids(article(USER, HOWTO_EN.replace("1. Select **Settings > Billing > Invoices**.",
                                                                    many)), "error"))
        bullets = HOWTO_EN.replace("1. ", "- ").replace("2. ", "- ").replace("3. ", "- ")
        self.assertIn("DOC-022", ids(article(USER, bullets)))
        self.assertIn("DOC-034", ids(article(USER, HOWTO_EN.replace("Choose the period.",
                                                                    "Choose the period and then select **Apply**.")),
                                     "note"))

    def test_sentences_and_words(self):
        long = "Choose the period " + "and the account " * 10 + "you need."
        self.assertIn("DOC-031", ids(article(USER, HOWTO_EN.replace("Choose the period.", long))))
        self.assertIn("DOC-032", ids(article(USER, HOWTO_EN.replace("Choose the period.", "Simply choose it.")),
                                     "error"))
        self.assertIn("DOC-032", ids(article(DE, HOWTO_DE.replace("Wählen Sie den Zeitraum.",
                                                                  "Wählen Sie einfach den Zeitraum.")), "error"))

    def test_sie_and_du(self):
        mixed = HOWTO_DE.replace("2. Wählen Sie den Zeitraum.", "2. Wähle deinen Zeitraum.")
        self.assertIn("DOC-030", ids(article(DE, mixed)))

    def test_accessibility(self):
        self.assertIn("DOC-035", ids(article(USER, HOWTO_EN + "\n![](https://x.example/a.png)\n")))
        self.assertIn("DOC-035", ids(article(USER, HOWTO_EN + "\nSee [here](https://x.example).\n")))
        self.assertNotIn("DOC-035", ids(article(USER, HOWTO_EN + "\n![The export dialog](https://x.example/a.png)\n")))

    def test_code(self):
        self.assertIn("DOC-045", ids(article(USER, HOWTO_EN + "\n```\nexport\n```\n")))
        self.assertIn("DOC-051", ids(article(DEV, QUICKSTART.replace("```bash", "```"))))

    def test_exposure_and_placeholders(self):
        self.assertIn("DOC-005", ids(article(USER, HOWTO_EN + "\nOpen http://localhost:3000.\n")))
        self.assertIn("DOC-005", ids(article(DEV, QUICKSTART.replace("YOUR_API_KEY",
                                                                     "sk_live_abcdefghijklmnopqrstuv"))))
        self.assertIn("DOC-004", ids(article(USER, HOWTO_EN.replace("Choose the period.", "TODO which menu?"))))

    def test_callouts(self):
        self.assertIn("DOC-042", ids(article(USER, HOWTO_EN + "\n:::caution\nCareful.\n:::\n"), "error"))
        self.assertNotIn("DOC-042", ids(article(USER, HOWTO_EN + "\n:::note\nOnly for 2024.\n:::\n")))

    def test_code_is_not_prose(self):
        body = QUICKSTART.replace('await acme.track("signup");',
                                  'await acme.track("signup"); // simply ' + "word " * 40)
        self.assertEqual(ids(article(DEV, body), "error"), [])

    def test_faq(self):
        faq = dict(USER, type="faq", title="Billing questions")
        good = "Short answers about invoices and payments.\n\n## Can I change the invoice address?\n\nYes. See " \
               "[Change the address](https://help.acme.example/a).\n"
        self.assertEqual(ids(article(faq, good), "error"), [])
        self.assertIn("DOC-022", ids(article(faq, good.replace("address?", "address"))))
        long = good.replace("Yes.", "Yes. " + "word " * 70)
        self.assertIn("DOC-006", ids(article(faq, long)))

    def test_house_style_checks_only_universal_rules(self):
        indicate = ("# What is a widget?\n\nA widget shows one metric.\n\n* * *\n\n# How do I create a widget?\n\n"
                    "1.  Click **Add widget**.\n2.  Click **Save**.\n\n> **Note:** Widgets refresh hourly.\n")
        self.assertIn("DOC-063", ids(indicate))
        self.assertEqual(docs.check(indicate, house=True, reader="user")["findings"], [])
        self.assertIn("DOC-032", ids(indicate.replace("Click **Save**", "Simply click **Save**"), "error"))
        found = docs.check(indicate.replace("Click **Save**", "Simply click **Save**"), house=True, reader="user")
        self.assertEqual([f["id"] for f in found["findings"]], ["DOC-032"])
        many = "\n".join("%d.  Click **Item %d**." % (i, i) for i in range(1, 10))
        self.assertIn("DOC-034", [f["id"] for f in docs.check("Intro.\n\n" + many + "\n", house=True,
                                                              reader="user")["findings"]])
        self.assertIn("DOC-005", [f["id"] for f in docs.check("Open http://localhost:3000.\n", house=True)["findings"]])

    def test_sections_stand_alone(self):
        self.assertIn("DOC-007", ids(article(USER, HOWTO_EN.replace("Choose the period.", "Choose the period, see above."))))
        self.assertIn("DOC-007", ids(article(DE, HOWTO_DE.replace("Wählen Sie den Zeitraum.",
                                                                  "Wählen Sie den Zeitraum wie oben beschrieben."))))
        self.assertNotIn("DOC-007", ids(article(USER, HOWTO_EN)))

    def test_tables(self):
        ref = "Every role.\n\n## Roles\n\n| Role | Can export |\n|---|---|\n| Admin | yes |\n"
        meta = dict(USER, type="reference", title="Roles and permissions")
        self.assertEqual(ids(article(meta, ref), "error"), [])
        self.assertIn("DOC-041", ids(article(meta, ref.replace("| Admin | yes |", "| Admin | ✓ |"))))
        self.assertIn("DOC-041", ids(article(meta, ref.replace("| Admin | yes |", "| Admin |  |"))))

    def test_placeholder_form(self):
        self.assertIn("DOC-051", ids(article(DEV, QUICKSTART), "note"))
        self.assertNotIn("DOC-051", ids(article(DEV, QUICKSTART.replace("YOUR_API_KEY", "API_KEY")), "note"))

    def test_collection_index(self):
        index = "---\ntitle: Billing\ndescription: Invoices, payment methods and plans.\norder: 1\n---\n"
        result = docs.check(index, "helpcenter/billing/index.md")
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["type"], "collection")
        self.assertIn("DOC-060", ids("---\ntitle: Billing\n---\n", path="helpcenter/billing/index.md"))
        self.assertIn("DOC-063", ids(index, path="helpcenter/billing/overview.md"))

    def test_language_from_file_name(self):
        art = docs.Article(article({k: v for k, v in DE.items() if k != "lang"}, HOWTO_DE), "a/b/export.de.md")
        self.assertEqual(art.lang(), "de")
        self.assertEqual(docs.Article("x", "website/i18n/de/docusaurus-plugin-content-docs/current/a.md").lang(), "de")


def sh(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, input="", timeout=30)


class Git(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stamps = self.root / "stamps"
        os.environ["DOCS_STAMP_DIR"] = str(self.stamps)
        self.repo = self.root / "repo"
        (self.repo / "helpcenter" / "billing").mkdir(parents=True)
        for cmd in (["git", "init", "-q"], ["git", "config", "user.email", "t@example.com"],
                    ["git", "config", "user.name", "T"], ["git", "config", "commit.gpgsign", "false"]):
            sh(cmd, self.repo)
        self.rel = "helpcenter/billing/export-invoices-csv.md"
        self.file = self.repo / self.rel
        self.file.write_text(article(dict(USER, productlane="art_1"), HOWTO_EN + "\n:::note\nOnly for 2024.\n:::\n"),
                             encoding="utf-8")
        sh(["git", "add", "-A"], self.repo)
        sh(["git", "commit", "-qm", "docs(export-invoices-csv): first version"], self.repo)

    def tearDown(self):
        os.environ.pop("DOCS_STAMP_DIR", None)
        self.tmp.cleanup()

    def commit(self, message, *trailers, allow_empty=False):
        args = ["git", "commit", "-q", "-m", message] + [x for t in trailers for x in ("-m", t)]
        if allow_empty:
            args.append("--allow-empty")
        else:
            args.insert(2, "-a")
        sh(args, self.repo)

    def test_render_refuses_uncommitted(self):
        self.file.write_text(self.file.read_text() + "\nMore.\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as e:
            docs.render(str(self.file), "productlane")
        self.assertIn("uncommitted", str(e.exception))

    def test_render_refuses_check_errors_and_drafts(self):
        self.file.write_text(self.file.read_text().replace("Choose the period.", "TODO"), encoding="utf-8")
        self.commit("broken")
        with self.assertRaises(SystemExit) as e:
            docs.render(str(self.file), "productlane")
        self.assertIn("check error", str(e.exception))
        self.file.write_text(article(dict(USER, status="draft"), HOWTO_EN), encoding="utf-8")
        self.commit("draft")
        with self.assertRaises(SystemExit):
            docs.render(str(self.file), "productlane")
        body, _ = docs.render(str(self.file), "productlane", draft=True)
        self.assertNotIn("status:", body)

    def test_render_body_and_stamp(self):
        body, info = docs.render(str(self.file), "productlane")
        self.assertFalse(body.startswith("---"))
        self.assertIn("> **Note:**", body)
        self.assertNotIn(":::", body)
        self.assertEqual(info["file"], self.rel)
        self.assertEqual(len(list(self.stamps.iterdir())), 1)
        docusaurus, _ = docs.render(str(self.file), "docusaurus")
        self.assertIn(":::note", docusaurus)

    def test_render_rewrites_links_and_images(self):
        other = self.repo / "helpcenter" / "billing" / "download-invoice.md"
        other.write_text(article(dict(USER, title="Download an invoice", productlane="art_2"), HOWTO_EN))
        (self.repo / "helpcenter" / "billing" / "images").mkdir()
        (self.repo / "helpcenter" / "billing" / "images" / "export-invoices-csv-dialog.png").write_bytes(b"x")
        self.file.write_text(self.file.read_text() + "\n## Related articles\n\n- [Download an invoice]"
                             "(download-invoice.md)\n\n![The export dialog](images/export-invoices-csv-dialog.png)\n")
        sh(["git", "add", "-A"], self.repo)
        self.commit("links")
        with self.assertRaises(SystemExit) as e:
            docs.render(str(self.file), "productlane")
        self.assertIn("download-invoice.md", str(e.exception))
        body, _ = docs.render(str(self.file), "productlane",
                              links={"download-invoice.md": {"url": "https://help.acme.example/docs/billing/dl",
                                                             "title": "Download an invoice (PDF)"}},
                              assets={"images/export-invoices-csv-dialog.png": "https://cdn.acme.example/d.png"})
        self.assertIn("[Download an invoice (PDF)](https://help.acme.example/docs/billing/dl)", body)
        self.assertIn("(https://cdn.acme.example/d.png)", body)
        links = docs.internal_links(docs.Article(self.file.read_text(), str(self.file)))
        self.assertEqual([(l["form"], l.get("ids")) for l in links],
                         [("path", {"productlane": "art_2"}), ("image", None)])

    def test_wiki_links(self):
        other = self.repo / "helpcenter" / "billing" / "Download an invoice.md"
        other.write_text("A page.\n")
        self.file.write_text(self.file.read_text() + "\nSee [[Download an invoice]] and [[Missing page|this]].\n")
        art = docs.Article(self.file.read_text(), str(self.file))
        found = {l["target"]: l["file"] for l in docs.internal_links(art)}
        self.assertTrue(found["Download an invoice"].endswith("Download an invoice.md"))
        self.assertIsNone(found["Missing page"])
        self.assertIn("DOC-044", ids(self.file.read_text(), path=str(self.file)))
        body, unresolved = docs.rewrite_links("See [[Download an invoice]].", art,
                                              {"Download an invoice": "https://h.example/d"})
        self.assertEqual((body, unresolved), ("See [Download an invoice](https://h.example/d).", []))

    def test_history_marks_publishes(self):
        self.commit("docs: publish export-invoices-csv to productlane",
                    "Docs-Published: productlane " + self.rel, allow_empty=True)
        self.file.write_text(self.file.read_text().replace("Choose the period.", "Choose a period."))
        self.commit("docs(export-invoices-csv): wording")
        h = docs.history(str(self.file))
        self.assertEqual([v["subject"] for v in h["versions"]],
                         ["docs(export-invoices-csv): wording", "docs: publish export-invoices-csv to productlane",
                          "docs(export-invoices-csv): first version"])
        self.assertEqual(h["versions"][1]["live"], [{"event": "published", "target": "productlane"}])
        self.assertEqual(docs.last_live(h["versions"])["subject"], "docs: publish export-invoices-csv to productlane")
        self.assertFalse(h["uncommitted"])

    def test_history_with_spaces_in_path(self):
        spaced = self.repo / "Widgets" / "Create a widget.md"
        spaced.parent.mkdir()
        spaced.write_text("# What is a widget?\n\nA widget shows one metric.\n")
        sh(["git", "add", "-A"], self.repo)
        self.commit("Add article: Create a widget")
        self.commit("docs: push create-a-widget to productlane",
                    "Docs-Published: productlane Widgets/Create a widget.md", allow_empty=True)
        h = docs.history(str(spaced))
        self.assertEqual(h["versions"][0]["live"], [{"event": "published", "target": "productlane"}])

    def test_stale(self):
        old = self.repo / "helpcenter" / "billing" / "old-article.md"
        old.write_text("Old.\n")
        sh(["git", "add", "-A"], self.repo)
        env = dict(os.environ, GIT_AUTHOR_DATE="2024-01-01T10:00:00", GIT_COMMITTER_DATE="2024-01-01T10:00:00")
        subprocess.run(["git", "commit", "-qm", "old"], cwd=self.repo, env=env, capture_output=True, input="")
        found = docs.stale(str(self.repo / "helpcenter"), 12)
        self.assertEqual([e["file"] for e in found], ["billing/old-article.md"])

    def test_render_at_past_version_and_diff(self):
        old, _ = docs.render(str(self.file), "productlane")
        self.file.write_text(self.file.read_text().replace("Choose the period.", "Choose a period."))
        self.commit("wording")
        past, _ = docs.render(str(self.file), "productlane", at="HEAD~1")
        self.assertEqual(past, old)
        d = docs.diff(past, docs.render(str(self.file), "productlane")[0])
        self.assertEqual((d["added"], d["removed"]), (1, 1))

    def test_cli(self):
        res = sh([str(BIN), "check", "--json", self.rel], self.repo)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(json.loads(res.stdout)["ok"])
        res = sh([str(BIN), "history", self.rel], self.repo)
        self.assertIn("first version", res.stdout)
        res = sh([str(BIN), "check", "-"], self.repo)
        self.assertEqual(res.returncode, 1)


class Diff(unittest.TestCase):
    def test_formatting_only_is_same(self):
        a = "Intro.\n\n## Steps\n\n* Select __Export__.\n1) Then this.\n"
        b = "---\ntitle: x\n---\nIntro.\n\n\n## Steps  \n\n- Select **Export**.\n1. Then this.\n"
        self.assertTrue(docs.diff(a, b)["same"])

    def test_sections(self):
        d = docs.diff("Intro.\n\n## Steps\n\n1. A\n", "Intro.\n\n## Steps\n\n1. A\n\n## Good to know\n\n- B\n")
        self.assertEqual(d["sections_added"], ["Good to know"])


if __name__ == "__main__":
    unittest.main()
