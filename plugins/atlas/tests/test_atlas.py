import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import atlas  # noqa: E402


class BrainCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve() / "brain"
        os.environ["ATLAS_HOME"] = str(self.home)
        os.environ["ATLAS_TODAY"] = "2026-10-12"
        self.run_ok("init")

    def tearDown(self):
        os.environ.pop("ATLAS_HOME", None)
        os.environ.pop("ATLAS_TODAY", None)
        self.tmp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = atlas.main(list(args))
        return code, out.getvalue(), err.getvalue()

    def run_ok(self, *args):
        code, out, err = self.run_cli(*args)
        self.assertEqual(code, 0, f"{args}: {err}{out}")
        return out

    def new(self, title, kind="note", *extra, body="", description=None):
        return self.run_ok("new", title, "--type", kind, "-d", description or f"About {title}", "--body", body, *extra)

    def read(self, rel):
        return (self.home / rel).read_text(encoding="utf-8")

    def findings(self):
        code, out, _ = self.run_cli("check", "--json")
        return code, json.loads(out)

    def kinds(self):
        return sorted({finding["kind"] for finding in self.findings()[1]})


class Frontmatter(unittest.TestCase):
    def test_reads_scalars_block_lists_and_inline_lists(self):
        fields, unreadable = atlas.parse_frontmatter(
            'id: 20261012T143055\norg: "[[Acme GmbH]]"\naliases:\n  - J. Doe\n  - "Doe, Jane"\ntags: [a, "b, c"]\nrole:'
        )
        self.assertEqual(unreadable, [])
        self.assertEqual(fields["org"], "[[Acme GmbH]]")
        self.assertEqual(fields["aliases"], ["J. Doe", "Doe, Jane"])
        self.assertEqual(fields["tags"], ["a", "b, c"])
        self.assertEqual(fields["role"], "")

    def test_reports_lines_it_cannot_read(self):
        _, unreadable = atlas.parse_frontmatter("id: 1\n  nested: no\n")
        self.assertEqual(unreadable, ["  nested: no"])

    def test_what_it_writes_it_reads_back(self):
        fields = {
            "description": "Head of data: our contact",
            "org": "[[Acme GmbH]]",
            "aliases": ["J. Doe", "yes"],
            "created": "2026-10-12",
            "note": 'said "hi" # once',
        }
        again, unreadable = atlas.parse_frontmatter(atlas.dump_frontmatter(fields))
        self.assertEqual(unreadable, [])
        self.assertEqual(again, fields)

    def test_dates_stay_unquoted_so_obsidian_reads_them_as_dates(self):
        self.assertEqual(atlas.dump_frontmatter({"created": "2026-10-12"}), "created: 2026-10-12")


class Links(unittest.TestCase):
    def test_finds_targets_and_skips_code(self):
        text = "See [[Jane Doe]], [[Acme GmbH|Acme]], [[Plan#Risks]] and ![[chart.png]].\n`[[not a link]]`\n```\n[[nor this]]\n```\n"
        self.assertEqual(atlas.link_targets(text), ["Jane Doe", "Acme GmbH", "Plan", "chart.png"])

    def test_retarget_keeps_heading_and_shown_text(self):
        text = "[[Old]] [[old#Part|the part]] [[Older]]"
        self.assertEqual(atlas.retarget_links(text, "Old", "New"), "[[New]] [[New#Part|the part]] [[Older]]")


class NewAndFind(BrainCase):
    def test_init_creates_a_clean_brain_under_git(self):
        self.assertTrue((self.home / "atlas.json").is_file())
        self.assertTrue((self.home / "notes" / "Home.md").is_file())
        self.assertEqual(self.findings(), (0, []))
        if (self.home / ".git").exists():
            log = subprocess.run(["git", "log", "--oneline"], cwd=self.home, capture_output=True, text=True).stdout
            self.assertIn("atlas: init", log)

    def test_new_writes_a_note_obsidian_can_read(self):
        out = self.new("Jane Doe", "person", "--alias", "J. Doe", "--set", "org=[[Acme GmbH]]", "--set", "role=Head of data")
        self.assertEqual(out.strip(), "notes/Jane Doe.md")
        text = self.read("notes/Jane Doe.md")
        self.assertTrue(text.startswith("---\nid: "))
        self.assertIn('org: "[[Acme GmbH]]"', text)
        self.assertIn("aliases:\n  - J. Doe", text)
        self.assertIn("verified: 2026-10-12", text)

    def test_new_refuses_a_taken_title_or_alias(self):
        self.new("Jane Doe", "person", "--alias", "J. Doe")
        for title in ("jane doe", "J. Doe"):
            code, _, err = self.run_cli("new", title, "-d", "x")
            self.assertEqual(code, 2)
            self.assertIn("notes/Jane Doe.md", err)

    def test_new_needs_a_description_a_known_type_and_required_fields(self):
        self.assertEqual(self.run_cli("new", "A")[0], 2)
        self.assertEqual(self.run_cli("new", "A", "-d", "x", "--type", "ghost")[0], 2)
        code, _, err = self.run_cli("new", "Use DuckDB", "-d", "x", "--type", "decision")
        self.assertEqual(code, 2)
        self.assertIn("decided", err)
        self.run_ok("new", "Use DuckDB", "-d", "x", "--type", "decision", "--set", "decided=today")
        self.assertIn("decided: 2026-10-12", self.read("notes/Use DuckDB.md"))

    def test_new_drops_characters_a_file_name_cannot_hold(self):
        out = self.new("Q3: plan / review?")
        self.assertEqual(out.strip(), "notes/Q3 plan review.md")

    def test_find_filters_by_type_text_and_field(self):
        self.new("Jane Doe", "person", "--set", "org=[[Acme GmbH]]", description="Head of data at Acme")
        self.new("Acme GmbH", "organisation", description="Warehouse vendor")
        self.new("Warehouse notes", body="Jane Doe mentioned the warehouse.")
        people = self.run_ok("find", "--type", "person")
        self.assertEqual(people.strip(), "notes/Jane Doe.md | person | Head of data at Acme")
        ranked = self.run_ok("find", "--text", "warehouse").strip().split("\n")
        self.assertEqual([row.split(" | ")[0] for row in ranked], ["notes/Warehouse notes.md", "notes/Acme GmbH.md"])
        self.assertIn("notes/Jane Doe.md", self.run_ok("find", "--where", "org=Acme GmbH"))
        self.run_ok("set", "Acme GmbH", "aliases=Acme")
        self.assertIn("notes/Jane Doe.md", self.run_ok("find", "--where", "org=acme"))
        self.assertEqual(self.run_ok("find", "--where", "org=Other Inc").strip(), "no matches")
        self.assertIn("notes/Acme GmbH.md", self.run_ok("find", "--type", "organisation", "--where", "org="))
        self.assertEqual(self.run_ok("find", "--text", "nothing-here").strip(), "no matches")

    def test_find_by_validity(self):
        self.new("Old role", "note", "--set", "valid_from=2024-01-01", "--set", "valid_to=2025-06-01")
        self.new("New role", "note", "--set", "valid_from=2025-06-01")
        self.new("Timeless")

        def titles(*args):
            return sorted(json.loads(self.run_ok("find", "--json", "--type", "note", *args)), key=lambda n: n["title"])

        self.assertEqual([n["title"] for n in titles("--valid-on", "2025-01-01")], ["Old role", "Timeless"])
        self.assertEqual([n["title"] for n in titles("--valid-on", "2025-06-01")], ["New role", "Timeless"])
        overlap = titles("--valid-from", "2025-01-01", "--valid-to", "2025-12-31")
        self.assertEqual([n["title"] for n in overlap], ["New role", "Old role", "Timeless"])
        self.assertEqual(self.run_cli("find", "--valid-on", "soon")[0], 2)

    def test_find_by_links_and_verification_age(self):
        self.new("Acme GmbH", "organisation")
        self.new("Jane Doe", "person", body="Works at [[Acme GmbH]].")
        self.assertIn("notes/Jane Doe.md", self.run_ok("find", "--links-to", "Acme GmbH"))
        self.assertIn("notes/Acme GmbH.md", self.run_ok("find", "--linked-from", "Jane Doe"))
        self.run_ok("set", "Jane Doe", "verified=2026-01-01")
        stale = self.run_ok("find", "--verified-before", "2026-06-01", "--paths")
        self.assertEqual(stale.strip(), "notes/Jane Doe.md")

    def test_text_search_reads_values_and_text_not_field_names(self):
        self.new("Jane Doe", "person", "--set", "role=Head of data", description="Contact at Acme")
        self.new("Müller GmbH", "organisation", body="A start-up we met.")
        self.assertEqual(self.run_ok("find", "--text", "active").strip(), "no matches")
        self.assertEqual(self.run_ok("find", "--text", "person").strip(), "no matches")
        self.assertIn("notes/Jane Doe.md", self.run_ok("find", "--text", "head data"))
        self.assertIn("notes/Müller GmbH.md", self.run_ok("find", "--text", "muller"))
        self.assertEqual(self.run_ok("find", "--text", "art").strip(), "no matches")
        self.assertIn("notes/Müller GmbH.md", self.run_ok("find", "--text", "start"))

    def test_an_active_note_wins_over_an_archived_one(self):
        self.new("Acme", "organisation", "--alias", "Acme Corp")
        self.new("Acme 2026", "organisation")
        self.run_ok("supersede", "Acme", "--by", "Acme 2026")
        self.run_ok("set", "Acme 2026", "aliases=Acme")
        self.assertTrue(self.run_ok("get", "acme").startswith("# notes/Acme 2026.md\n"))
        self.assertIn('# archive/Acme.md | superseded | superseded by "[[Acme 2026]]"'.replace('"', ""), self.run_ok("get", "archive/Acme.md"))
        self.assertNotIn("duplicate", self.kinds())
        self.run_ok("new", "Acme Corp", "--type", "organisation", "-d", "an archived alias is free again")
        self.assertEqual(self.run_cli("new", "acme", "-d", "an archived title is not")[0], 2)

    def test_values_are_kept_on_one_line(self):
        self.run_ok("new", "Two lines", "-d", "first\nsecond", "--set", "role=a\n b")
        text = self.read("notes/Two lines.md")
        self.assertIn("description: first second\n", text)
        self.assertIn("role: a b\n", text)
        self.assertNotIn("schema", self.kinds())

    def test_new_links_from_a_hub_or_says_nothing_links_to_it(self):
        self.new("Acme", "hub", body="Topics:\n\n- [[Home]]")
        code, out, err = self.run_cli("new", "Billing", "-d", "x", "--from", "Acme")
        self.assertEqual((code, out.strip(), err), (0, "notes/Billing.md", ""))
        self.assertTrue(self.read("notes/Acme.md").endswith("- [[Home]]\n- [[Billing]]\n"))
        _, _, err = self.run_cli("new", "Loose", "-d", "x")
        self.assertIn('atlas link "<hub>" "Loose"', err)
        self.assertIn("linked Loose", self.run_ok("link", "Home", "Loose"))
        self.assertIn("already links", self.run_ok("link", "Home", "Loose"))
        self.assertNotIn("orphan", self.kinds())

    def test_get_resolves_title_alias_id_and_path_and_shows_backlinks(self):
        self.new("Acme GmbH", "organisation", "--alias", "Acme")
        self.new("Jane Doe", "person", body="Works at [[Acme GmbH]].")
        note_id = json.loads(self.run_ok("find", "--json", "--type", "organisation"))[0]["id"]
        for ref in ("acme gmbh", "Acme", note_id, "notes/Acme GmbH.md"):
            out = self.run_ok("get", ref)
            self.assertIn("# notes/Acme GmbH.md", out)
            self.assertIn("notes/Jane Doe.md | person", out)
        self.assertEqual(self.run_cli("get", "nobody")[0], 2)


class Lifecycle(BrainCase):
    def test_set_changes_and_clears_fields_and_keeps_the_text(self):
        self.new("Jane Doe", "person", body="Some text.\n\n- a list item")
        self.run_ok("set", "Jane Doe", "role=CTO", "aliases=JD", "aliases=Janie")
        text = self.read("notes/Jane Doe.md")
        self.assertIn("role: CTO", text)
        self.assertIn("aliases:\n  - JD\n  - Janie", text)
        self.assertTrue(text.endswith("---\nSome text.\n\n- a list item\n"))
        self.run_ok("set", "Jane Doe", "role=")
        self.assertNotIn("role", self.read("notes/Jane Doe.md"))
        self.assertEqual(self.run_cli("set", "Jane Doe", "id=other")[0], 2)
        self.assertEqual(self.run_cli("set", "Jane Doe", "status=gone")[0], 2)

    def test_a_semicolon_stays_in_the_value(self):
        self.new("Jane Doe", "person", "--set", "role=Head of data; platform")
        self.run_ok("set", "Jane Doe", "description=Head of data at Acme; contact")
        text = self.read("notes/Jane Doe.md")
        self.assertIn("description: Head of data at Acme; contact", text)
        self.assertIn("role: Head of data; platform", text)
        self.assertNotIn("schema", self.kinds())

    def test_saving_keeps_comments_nested_lines_and_untouched_fields(self):
        hand = (
            "---\nid: 9\ntype: note\ndescription: by hand\n# keep me\nstatus: active\ncreated: 2026-10-01\n"
            "tags: [a, b]\nmeta:\n  nested: 1\nverified: 2026-01-01\n---\nbody\n"
        )
        (self.home / "notes" / "Hand.md").write_text(hand, encoding="utf-8")
        self.run_ok("verify", "Hand")
        self.run_ok("set", "Hand", "role=x")
        self.assertEqual(
            self.read("notes/Hand.md"),
            hand.replace("verified: 2026-01-01", "verified: 2026-10-12").replace("\n---\nbody", "\nrole: x\n---\nbody"),
        )
        self.run_ok("archive", "Hand")
        archived = self.read("archive/Hand.md")
        self.assertIn("# keep me\n", archived)
        self.assertIn("meta:\n  nested: 1\n", archived)
        self.assertIn("status: archived", archived)

    def test_supersede_closes_the_old_note_and_archives_it(self):
        self.new("Pricing 2025", body="Flat fee.")
        self.new("Pricing 2026", body="Usage based. Replaces [[Pricing 2025]].")
        self.run_ok("supersede", "Pricing 2025", "--by", "Pricing 2026")
        old = self.read("archive/Pricing 2025.md")
        self.assertFalse((self.home / "notes" / "Pricing 2025.md").exists())
        self.assertIn("status: superseded", old)
        self.assertIn("valid_to: 2026-10-12", old)
        self.assertIn('superseded_by: "[[Pricing 2026]]"', old)
        self.assertIn("valid_from: 2026-10-12", self.read("notes/Pricing 2026.md"))
        self.assertNotIn("Pricing 2025", self.run_ok("find", "--text", "pricing"))
        self.assertIn("archive/Pricing 2025.md", self.run_ok("find", "--status", "superseded"))
        self.assertNotIn("supersede", self.kinds())
        self.assertNotIn("broken-link", self.kinds())

    def test_archive_moves_the_note_and_marks_it(self):
        self.new("Old idea")
        self.run_ok("archive", "Old idea")
        self.assertIn("status: archived", self.read("archive/Old idea.md"))
        self.assertNotIn("misplaced", self.kinds())

    def test_restore_brings_an_archived_note_back(self):
        self.new("Old idea")
        self.run_ok("archive", "Old idea")
        self.run_ok("restore", "Old idea")
        self.assertIn("status: active", self.read("notes/Old idea.md"))
        self.assertFalse((self.home / "archive" / "Old idea.md").exists())
        self.assertEqual(self.run_cli("restore", "Old idea")[0], 2)

    def test_rename_rewrites_links_and_keeps_the_old_title_as_alias(self):
        self.new("Acme", "organisation")
        self.new("Jane Doe", "person", "--set", "org=[[Acme]]", body="At [[Acme]] and [[acme|the vendor]].")
        out = self.run_ok("rename", "Acme", "Acme GmbH")
        self.assertIn("1 notes relinked", out)
        jane = self.read("notes/Jane Doe.md")
        self.assertIn('org: "[[Acme GmbH]]"', jane)
        self.assertIn("At [[Acme GmbH]] and [[Acme GmbH|the vendor]].", jane)
        self.assertIn("aliases:\n  - Acme", self.read("notes/Acme GmbH.md"))
        self.assertIn("# notes/Acme GmbH.md", self.run_ok("get", "Acme"))
        self.assertNotIn("broken-link", self.kinds())

    def test_merge_moves_names_and_links_to_the_survivor(self):
        self.new("Jane Doe", "person")
        self.run_ok("new", "Jane D", "--type", "person", "-d", "dup", "--alias", "JD")
        self.new("Meeting", body="Spoke with [[Jane D]].")
        self.run_ok("merge", "Jane D", "--into", "Jane Doe")
        self.assertIn("Spoke with [[Jane Doe]].", self.read("notes/Meeting.md"))
        self.assertIn("aliases:\n  - Jane D\n  - JD", self.read("notes/Jane Doe.md"))
        self.assertFalse((self.home / "notes" / "Jane D.md").exists())
        self.assertEqual(len(list((self.home / "archive").glob("Jane D (merged *.md"))), 1)
        code, found = self.findings()
        self.assertNotIn("duplicate", {f["kind"] for f in found})
        self.assertNotIn("supersede", {f["kind"] for f in found})

    def test_capture_and_inbox(self):
        out = self.run_ok("capture", "Jane moved to the platform team: check her role")
        self.assertTrue(out.startswith("inbox/2"))
        self.assertIn("0d | Jane moved to the platform team", self.run_ok("inbox"))
        self.assertEqual(self.run_cli("capture", "  ")[0], 2)
        for _ in range(3):
            self.run_ok("capture", "same words")
        self.assertEqual(len(list((self.home / "inbox").glob("* same words*.md"))), 3)

    def test_changes_are_committed_one_by_one(self):
        if not (self.home / ".git").exists():
            self.skipTest("git is not available")
        self.new("Acme", "organisation")
        self.run_ok("rename", "Acme", "Acme GmbH")
        self.run_ok("verify", "Acme GmbH")
        git = lambda *args: subprocess.run(["git", *args], cwd=self.home, capture_output=True, text=True).stdout
        subjects = git("log", "--format=%s").strip().split("\n")
        self.assertEqual(subjects[:2], ["atlas: rename Acme to Acme GmbH", "atlas: new organisation Acme"])
        self.assertEqual(git("status", "--porcelain").strip(), "")


class Commits(BrainCase):
    def setUp(self):
        super().setUp()
        if not (self.home / ".git").exists():
            self.skipTest("git is not available")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.home, capture_output=True, text=True).stdout.strip()

    def hook(self, payload):
        stdin = sys.stdin
        sys.stdin = io.StringIO(payload)
        try:
            return self.run_cli("commit", "--hook")
        finally:
            sys.stdin = stdin

    def test_the_hook_commits_an_edit_in_the_brain_and_nothing_else(self):
        path = self.home / "notes" / "Home.md"
        path.write_text(path.read_text() + "edited\n")
        self.assertEqual(self.hook(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})), (0, "", ""))
        self.assertEqual(self.git("log", "-1", "--format=%s"), "atlas: edit Home (by Claude)")
        self.assertEqual(self.git("status", "--porcelain"), "")
        outside = Path(self.tmp.name) / "elsewhere.md"
        outside.write_text("x")
        for payload in (json.dumps({"tool_input": {"file_path": str(outside)}}), "not json", "{}"):
            self.assertEqual(self.hook(payload), (0, "", ""))
        self.assertEqual(self.git("log", "-1", "--format=%s"), "atlas: edit Home (by Claude)")

    def test_commit_takes_refs_paths_or_everything_changed(self):
        self.new("Acme", "organisation")
        for name in ("Acme.md", "Home.md"):
            (self.home / "notes" / name).write_text(self.read(f"notes/{name}") + "more\n")
        self.run_ok("commit", "Acme", "-m", "tidy Acme")
        self.assertEqual(self.git("log", "-1", "--format=%s"), "atlas: tidy Acme")
        self.assertEqual(self.git("status", "--porcelain"), "M notes/Home.md")
        self.run_ok("commit")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertEqual(self.run_ok("commit").strip(), "nothing to commit")


class Check(BrainCase):
    def write(self, rel, text):
        (self.home / rel).write_text(text, encoding="utf-8")

    def test_a_linked_brain_is_clean(self):
        self.new("Acme GmbH", "organisation")
        self.new("Jane Doe", "person", body="At [[Acme GmbH]].")
        self.run_ok("set", "Home", "sources=")
        self.write("notes/Home.md", self.read("notes/Home.md") + "[[Jane Doe]]\n")
        if (self.home / ".git").exists():
            self.assertIn("uncommitted", self.kinds())
            self.assertEqual(self.run_ok("commit").strip(), "notes/Home.md")
        self.assertEqual(self.findings(), (0, []))

    def test_schema_errors(self):
        self.write("notes/Bare.md", "just text\n")
        self.write("notes/Odd.md", "---\nid: 1\ntype: ghost\nstatus: maybe\ncreated: soon\n  nested: x\n---\n")
        code, found = self.findings()
        self.assertEqual(code, 1)
        messages = " / ".join(f["message"] for f in found if f["kind"] == "schema")
        for expected in ("no frontmatter", "`description` is missing", "unknown type 'ghost'", "status 'maybe'", "`created` is not a date", "nested: x"):
            self.assertIn(expected, messages)

    def test_broken_link_and_orphan(self):
        self.new("Jane Doe", "person", body="At [[Nowhere Inc]] and ![[chart.png]].")
        (self.home / "notes" / "chart.png").write_bytes(b"")
        code, found = self.findings()
        self.assertEqual(code, 1)
        broken = [f["message"] for f in found if f["kind"] == "broken-link"]
        self.assertEqual(broken, ["[[Nowhere Inc]] points at nothing"])
        self.assertEqual([f["path"] for f in found if f["kind"] == "orphan"], ["notes/Jane Doe.md"])

    def test_duplicate_names_written_by_hand(self):
        self.new("Jane Doe", "person")
        self.write("notes/JD.md", self.read("notes/Jane Doe.md").replace("status: active", "aliases:\n  - jane doe\nstatus: active"))
        self.assertIn("duplicate", self.kinds())

    def test_overdue_expired_and_misplaced(self):
        self.new("Jane Doe", "person")
        self.new("Use DuckDB", "decision", "--set", "decided=2024-01-01")
        self.run_ok("set", "Jane Doe", "verified=2026-01-01", "valid_to=2026-09-01")
        self.run_ok("set", "Use DuckDB", "verified=2024-01-01", "status=archived")
        found = {f["kind"]: f for f in self.findings()[1]}
        self.assertIn("284 days ago (limit 180)", found["overdue"]["message"])
        self.assertEqual(found["overdue"]["path"], "notes/Jane Doe.md")
        self.assertIn("valid to 2026-09-01", found["expired"]["message"])
        self.assertEqual(found["misplaced"]["path"], "notes/Use DuckDB.md")

    def test_supersede_without_a_target(self):
        self.new("Old")
        self.run_ok("set", "Old", "status=superseded")
        messages = [f["message"] for f in self.findings()[1] if f["kind"] == "supersede"]
        self.assertEqual(messages, ["superseded, but `superseded_by` names no note"])
        self.run_ok("set", "Old", "superseded_by=[[Gone]]")
        messages = [f["message"] for f in self.findings()[1] if f["kind"] == "supersede"]
        self.assertEqual(messages, ["`superseded_by` points at [[Gone]], which does not exist"])

    def test_old_inbox_items(self):
        self.run_ok("capture", "something to sort")
        item = next((self.home / "inbox").glob("*.md"))
        self.assertTrue(item.name.startswith("2026-10-12 "))
        item.rename(item.with_name("2026-09-01" + item.name[10:]))
        found = [f for f in self.findings()[1] if f["kind"] == "inbox"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["level"], "warning")


class Hint(BrainCase):
    def test_names_the_brain_and_lists_the_standing_preferences(self):
        self.new("Short answers", "preference", description="Answer briefly, in prose, without bullet lists")
        self.new("Old style", "preference")
        self.run_ok("archive", "Old style")
        out = self.run_ok("hint")
        self.assertIn("personal brain, atlas: 2 markdown notes", out)
        self.assertIn("- Short answers: Answer briefly, in prose, without bullet lists", out)
        self.assertNotIn("Old style", out)
        self.assertNotIn("orphan", self.kinds())

    def test_is_silent_without_a_brain(self):
        os.environ["ATLAS_HOME"] = str(self.home.parent / "none")
        self.assertEqual(self.run_cli("hint"), (0, "", ""))


class Wrapper(unittest.TestCase):
    def test_the_command_on_the_path_runs(self):
        script = Path(__file__).resolve().parents[1] / "bin" / "atlas"
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "ATLAS_HOME": str(Path(tmp) / "brain")}
            done = subprocess.run([str(script), "check"], env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
            self.assertEqual(done.returncode, 2)
            self.assertIn("run `atlas init`", done.stderr)


if __name__ == "__main__":
    unittest.main()
