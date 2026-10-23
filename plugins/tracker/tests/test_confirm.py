"""Tests for the confirm hook. Run: python3 -m unittest discover -s plugins/tracker/tests"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN / "hooks"))
import confirm  # noqa: E402

HOOK = PLUGIN / "hooks" / "confirm.py"


def mcp(name):
    return {"tool_name": name, "tool_input": {}}


def bash(command):
    return {"tool_name": "Bash", "tool_input": {"command": command}}


class Writes(unittest.TestCase):
    def test_tracker_mcp_writes_ask(self):
        for name in ["mcp__plugin_linear_linear__save_issue", "mcp__plugin_linear_linear__save_comment",
                     "mcp__linear__create_issue", "mcp__atlassian__createJiraIssue",
                     "mcp__jira__transition_issue", "mcp__github__create_issue",
                     "mcp__github__add_issue_comment", "mcp__github__update_issue",
                     "mcp__trello__add_card", "mcp__plugin_linear_linear__create_issue_label"]:
            with self.subTest(name=name):
                self.assertTrue(confirm.is_tracker_write(mcp(name)))

    def test_reads_and_other_tools_pass(self):
        for name in ["mcp__plugin_linear_linear__get_issue", "mcp__plugin_linear_linear__list_issues",
                     "mcp__atlassian__searchJiraIssuesUsingJql", "mcp__github__get_issue",
                     "mcp__github__create_pull_request", "mcp__github__push_files",
                     "mcp__claude_ai_Context7__query-docs", "mcp__slack__post_message", "Read", "Edit"]:
            with self.subTest(name=name):
                self.assertFalse(confirm.is_tracker_write(mcp(name)))

    def test_cli_writes_ask(self):
        for command in ["gh issue create --title x --body y", "cd repo && gh issue close 12 -c 'Done: x.'",
                        "gh issue comment 12 --body-file c.md", "gh api repos/o/r/issues/12 -X PATCH -f state=closed",
                        "gh api repos/o/r/issues -f title=x", "glab issue note 3 -m hi",
                        "acli jira workitem create --summary x", "jira issue move IND-1 Done"]:
            with self.subTest(command=command):
                self.assertTrue(confirm.is_tracker_write(bash(command)))

    def test_cli_reads_pass(self):
        for command in ["gh issue view 12", "gh issue list --label bug", "gh api repos/o/r/issues/12",
                        "gh pr create --title x", "git commit -m 'gh issue close'", "echo gh issue create"]:
            with self.subTest(command=command):
                self.assertFalse(confirm.is_tracker_write(bash(command)))


class Hook(unittest.TestCase):
    def run_hook(self, event, env=None):
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True,
                              text=True, env={**os.environ, **(env or {})})

    def test_asks_for_a_write(self):
        out = json.loads(self.run_hook(mcp("mcp__linear__save_issue")).stdout)["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "ask")
        self.assertIn("tracker", out["permissionDecisionReason"])

    def test_silent_for_a_read_and_bad_input(self):
        self.assertEqual(self.run_hook(mcp("mcp__linear__get_issue")).stdout, "")
        bad = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True)
        self.assertEqual((bad.returncode, bad.stdout), (0, ""))

    def test_switch_off(self):
        self.assertEqual(self.run_hook(mcp("mcp__linear__save_issue"), {"TRACKER_CONFIRM_WRITES": "0"}).stdout, "")


if __name__ == "__main__":
    unittest.main()
