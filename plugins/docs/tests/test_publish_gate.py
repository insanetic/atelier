"""Tests for the publish hook. Run: python3 -m unittest discover -s plugins/docs/tests

Every host, ID and key here is made up.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
sys.path.insert(0, str(PLUGIN / "lib"))
sys.path.insert(0, str(PLUGIN / "hooks"))
import docs  # noqa: E402
import publish_gate as gate  # noqa: E402

HOOK = PLUGIN / "hooks" / "publish_gate.py"
BODY = "You can download all invoices of a period as one CSV file.\n\n## Steps\n\n1. Select **Export**.\n"


def mcp(tool, **tool_input):
    return {"tool_name": tool, "tool_input": tool_input}


def bash(command, cwd=None):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


class Detect(unittest.TestCase):
    def test_mcp_writes(self):
        for name in ("mcp__productlane__docs_update_article", "mcp__productlane__docs_create_article",
                     "mcp__productlane__docs_create_draft", "mcp__claude_ai_Intercom__createArticle",
                     "mcp__zendesk__update_help_center_article", "mcp__gitbook__update_page"):
            self.assertTrue(gate.is_write(mcp(name)), name)

    def test_not_writes(self):
        for name in ("mcp__productlane__docs_list_articles", "mcp__productlane__docs_get_article",
                     "mcp__productlane__threads_create_thread", "mcp__zendesk__update_ticket",
                     "mcp__notion__create_page", "mcp__plugin_linear_linear__save_document", "Write", "Read"):
            self.assertFalse(gate.is_write(mcp(name)), name)

    def test_http(self):
        self.assertTrue(gate.is_write(bash("curl -X PATCH https://productlane.com/api/v2/docs/articles/a1 -d '{}'")))
        self.assertTrue(gate.is_write(bash("curl https://productlane.com/api/v2/docs/articles --json @b.json")))
        self.assertTrue(gate.is_write(bash("http PATCH https://api.intercom.io/articles/1 body=x")))
        self.assertFalse(gate.is_write(bash("curl https://productlane.com/api/v2/docs/articles/a1")))
        self.assertFalse(gate.is_write(bash("curl -X POST https://api.example.com/docs -d x")))
        self.assertFalse(gate.is_write(bash("curl -X POST https://productlane.com/api/v2/threads -d x")))
        self.assertFalse(gate.is_write(bash("git push origin docs/export")))


class Decide(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DOCS_STAMP_DIR"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("DOCS_STAMP_DIR", None)
        self.tmp.cleanup()

    def stamp(self, body=BODY):
        docs.stamp(body, {"file": "helpcenter/billing/export.md", "commit": "abc1234", "target": "productlane"})

    def test_rendered_body_is_asked(self):
        self.stamp()
        decision, reason = gate.decide(mcp("mcp__productlane__docs_update_article", id="a1", content=BODY))
        self.assertEqual(decision, "ask")
        self.assertIn("export.md at abc1234", reason)

    def test_escaped_newlines_still_match(self):
        self.stamp()
        escaped = BODY.replace("\n", "\\n")
        self.assertEqual(gate.decide(mcp("mcp__productlane__docs_update_article", id="a1", content=escaped))[0], "ask")

    def test_unrendered_or_edited_body_is_denied(self):
        self.assertEqual(gate.decide(mcp("mcp__productlane__docs_update_article", id="a1", content=BODY))[0], "deny")
        self.stamp()
        edited = BODY.replace("Export", "Download")
        self.assertEqual(gate.decide(mcp("mcp__productlane__docs_update_article", id="a1", content=edited))[0], "deny")

    def test_without_body_is_asked(self):
        decision, reason = gate.decide(mcp("mcp__productlane__docs_delete_article", id="a1"))
        self.assertEqual(decision, "ask")
        self.assertIn("without an article body", reason)

    def test_http_payload_file(self):
        self.stamp()
        with tempfile.TemporaryDirectory() as cwd:
            Path(cwd, "b.json").write_text(json.dumps({"title": "Export", "content": BODY}))
            event = bash("curl -X PATCH https://productlane.com/api/v2/docs/articles/a1 --json @b.json", cwd)
            self.assertEqual(gate.decide(event)[0], "ask")
            Path(cwd, "b.json").write_text(json.dumps({"content": BODY + "\nHand edit."}))
            self.assertEqual(gate.decide(event)[0], "deny")

    def test_command_substitution_cannot_be_read(self):
        event = bash('curl -X PATCH https://productlane.com/api/v2/docs/articles/a1 -d "$(docs render a.md)"')
        self.assertEqual(gate.decide(event)[0], "ask")


class Main(unittest.TestCase):
    def run_hook(self, event, env=None):
        res = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True,
                             env=dict(os.environ, **(env or {})), timeout=30)
        return json.loads(res.stdout) if res.stdout.strip() else None

    def test_switch_off(self):
        event = mcp("mcp__productlane__docs_update_article", id="a1", content=BODY)
        self.assertIsNone(self.run_hook(event, {"DOCS_CONFIRM_PUBLISH": "0"}))
        with tempfile.TemporaryDirectory() as stamps:
            out = self.run_hook(event, {"DOCS_STAMP_DIR": stamps})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_reads_are_silent(self):
        self.assertIsNone(self.run_hook(mcp("mcp__productlane__docs_list_articles")))

    def test_bad_input_is_silent(self):
        res = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True, timeout=30)
        self.assertEqual((res.returncode, res.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
