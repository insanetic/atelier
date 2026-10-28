"""Tests for the confirm hook. Run: python3 -m unittest discover -s plugins/tracker/tests"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
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



COMMENT = "Stand: Der Import läuft wieder. Als Nächstes prüfen wir die Oktober-Daten."
ISSUE_TITLE = "Mietvertrag Büro Leipzig verlängern"
ISSUE_BODY = ("TL;DR: Der Mietvertrag für das Büro Leipzig soll vor dem Ablauf verlängert werden.\n\n"
              "## Aufgabe\nDen Mietvertrag um zwei Jahre verlängern.\n\n## Warum\nEr läuft am 31.12. aus.\n\n"
              "## Akzeptanzkriterien\n- [ ] Verlängerung unterschrieben\n")


def say(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def human(text):
    return {"type": "user", "message": {"role": "user", "content": text}, "origin": {"kind": "human"}}


def ask_question(id_, question):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": id_, "name": "AskUserQuestion",
         "input": {"questions": [{"question": question, "options": [{"label": "Post it"}, {"label": "Change"}]}]}}]}}


def answer(id_):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": id_, "content": "Post it"}]}}


def tool_result(text="ok"):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_x", "content": text}]}}


class Shown(unittest.TestCase):
    """A write goes on to the permission prompt only if its text was shown and the user answered after that."""

    def decide(self, entries, tool_input, name="mcp__plugin_linear_linear__save_comment"):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(json.dumps(e) for e in entries))
        self.addCleanup(os.unlink, f.name)
        return confirm.decide({"tool_name": name, "tool_input": tool_input, "transcript_path": f.name})[0]

    def test_shown_and_answered_asks(self):
        entries = [human("kommentier das"), say("Kommentar zu IND-12:\n\n```\n" + COMMENT + "\n```\n\nSo posten?"),
                   human("ja")]
        self.assertEqual(self.decide(entries, {"issueId": "IND-12", "body": COMMENT}), "ask")

    def test_answered_through_a_question(self):
        entries = [human("kommentier das"), say("Entwurf:\n" + COMMENT), ask_question("q1", "So posten?"),
                   answer("q1")]
        self.assertEqual(self.decide(entries, {"issueId": "IND-12", "body": COMMENT}), "ask")
        entries = [human("leg ein Ticket an"), ask_question("q2", "So anlegen?\n" + ISSUE_TITLE + "\n" + ISSUE_BODY),
                   answer("q2")]
        self.assertEqual(self.decide(entries, {"title": ISSUE_TITLE, "description": ISSUE_BODY, "team": "Ops"},
                                     "mcp__plugin_linear_linear__save_issue"), "ask")

    def test_not_shown_is_denied(self):
        self.assertEqual(self.decide([human("kommentier IND-12: Import läuft wieder")],
                                     {"issueId": "IND-12", "body": COMMENT}), "deny")

    def test_shown_but_not_answered_is_denied(self):
        entries = [human("kommentier das"), say("Ich poste jetzt:\n" + COMMENT)]
        self.assertEqual(self.decide(entries, {"issueId": "IND-12", "body": COMMENT}), "deny")

    def test_text_changed_after_the_yes_is_denied(self):
        entries = [human("kommentier das"), say("Entwurf:\n" + COMMENT), human("ja")]
        changed = COMMENT.replace("Oktober", "November")
        self.assertEqual(self.decide(entries, {"issueId": "IND-12", "body": changed}), "deny")

    def test_only_the_last_answer_counts(self):
        entries = [human("kommentier das"), say("Entwurf:\n" + COMMENT), human("ja"), say("Erledigt."),
                   human("und jetzt noch IND-13"), say("Mache ich.")]
        self.assertEqual(self.decide(entries, {"issueId": "IND-13", "body": COMMENT}), "deny")

    def test_tool_results_and_system_notes_are_not_answers(self):
        note = {"type": "user", "isMeta": True, "message": {"role": "user", "content": "skill text"}}
        task = {"type": "user", "message": {"role": "user", "content": "<task-notification>done</task-notification>"},
                "origin": {"kind": "task-notification"}}
        for entry in (tool_result(), note, task):
            with self.subTest(entry=entry):
                entries = [human("kommentier das"), say("Entwurf:\n" + COMMENT), entry]
                self.assertEqual(self.decide(entries, {"issueId": "IND-12", "body": COMMENT}), "deny")

    def test_several_writes_after_one_yes(self):
        entries = [human("leg es an"), say("Neu:\n" + ISSUE_TITLE + "\n" + ISSUE_BODY + "\nDann kommentieren:\n" +
                                           COMMENT), human("ja"), say("Lege an."), tool_result("IND-14")]
        self.assertEqual(self.decide(entries, {"title": ISSUE_TITLE, "description": ISSUE_BODY},
                                     "mcp__plugin_linear_linear__save_issue"), "ask")
        self.assertEqual(self.decide(entries, {"issueId": "IND-14", "body": COMMENT}), "ask")

    def test_cli_text_is_compared_too(self):
        entries = [human("kommentier das"), say("Entwurf:\n" + COMMENT), human("ja")]
        command = "gh issue comment 12 --body %s" % shlex.quote(COMMENT)
        self.assertEqual(self.decide(entries, {"command": command}, "Bash"), "ask")
        heredoc = "gh issue comment 12 --body \"$(cat <<'EOF'\n%s\nEOF\n)\"" % COMMENT
        self.assertEqual(self.decide(entries, {"command": heredoc}, "Bash"), "deny")
        tldr = "gh issue create --title %s --body %s" % (shlex.quote(ISSUE_TITLE), shlex.quote(ISSUE_BODY))
        shown = [human("leg es an"), say(ISSUE_TITLE + "\n" + ISSUE_BODY), human("ja")]
        self.assertEqual(self.decide(shown, {"command": tldr}, "Bash"), "ask")

    def test_writes_without_text_and_unreadable_transcripts_ask(self):
        self.assertEqual(self.decide([human("schließ IND-12")], {"id": "IND-12", "state": "Done"},
                                     "mcp__plugin_linear_linear__save_issue"), "ask")
        event = {"tool_name": "mcp__linear__save_comment", "tool_input": {"body": COMMENT},
                 "transcript_path": "/no/such/transcript.jsonl"}
        self.assertEqual(confirm.decide(event)[0], "ask")


class Edits(unittest.TestCase):
    """Edits of existing issues are not checked for terms or compared, only asked: old issues and text people
    wrote themselves stay as they are."""

    OLD = "## Acceptance Criteria\n- [x] export works\n## Notes\nwritten by hand"

    def test_edits_only_ask(self):
        for name, tool_input in [
                ("mcp__plugin_linear_linear__save_issue", {"id": "IND-12", "description": self.OLD}),
                ("mcp__github__update_issue", {"issue_number": 12, "body": self.OLD}),
                ("mcp__atlassian__editJiraIssue", {"issueIdOrKey": "IND-12", "description": self.OLD}),
                ("Bash", {"command": "gh issue edit 12 --body %s" % shlex.quote(self.OLD)}),
                ("Bash", {"command": "gh api repos/o/r/issues/12 -X PATCH -f body=%s" % shlex.quote(self.OLD)})]:
            with self.subTest(name=name):
                event = {"tool_name": name, "tool_input": tool_input, "transcript_path": "/no/such.jsonl"}
                self.assertEqual(confirm.decide(event)[0], "ask")

    def test_new_text_is_not_an_edit(self):
        for name, tool_input in [("mcp__plugin_linear_linear__save_issue", {"title": "x", "team": "Ops"}),
                                 ("mcp__plugin_linear_linear__save_comment", {"issueId": "IND-12", "body": "x"}),
                                 ("mcp__github__add_issue_comment", {"issue_number": 12, "body": "x"}),
                                 ("Bash", {"command": "gh issue create --title x --body y"}),
                                 ("Bash", {"command": "gh issue close 12 -c 'Done: x.'"})]:
            with self.subTest(name=name):
                self.assertFalse(confirm.is_edit({"tool_name": name, "tool_input": tool_input}))


class Terms(unittest.TestCase):
    """Wrong fixed terms are sent back with the fix, before anything else (CI-070)."""

    def test_wrong_terms_are_denied(self):
        for body in [ISSUE_BODY.replace("## Warum", "## Hintergrund"), ISSUE_BODY.replace("## Warum", "## Why"),
                     ISSUE_BODY.replace("Akzeptanzkriterien", "Fertig, wenn")]:
            with self.subTest(body=body):
                decision, reason = confirm.decide({"tool_name": "mcp__linear__save_issue",
                                                   "tool_input": {"title": ISSUE_TITLE, "description": body}})
                self.assertEqual(decision, "deny")
                self.assertIn("CI-0", reason)
        decision, _ = confirm.decide({"tool_name": "mcp__linear__save_comment",
                                      "tool_input": {"body": "Status: Der Import läuft wieder und wir prüfen jetzt."}})
        self.assertEqual(decision, "deny")

    def test_right_terms_pass_on(self):
        decision, _ = confirm.decide({"tool_name": "mcp__linear__save_issue",
                                      "tool_input": {"title": ISSUE_TITLE, "description": ISSUE_BODY}})
        self.assertEqual(decision, "ask")

if __name__ == "__main__":
    unittest.main()
