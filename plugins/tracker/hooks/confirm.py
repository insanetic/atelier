#!/usr/bin/env python3
"""PreToolUse hook: nothing reaches an issue tracker unless the user saw that exact text and answered.

The tracker skills show each write before making it (PROCEDURE.md, step 8), but that is an instruction the
model can skip. So for every tracker write through an MCP tool (Linear, Jira, GitHub issues and the like) or a
tracker CLI (gh issue, gh api …/issues, glab issue, acli jira, jira) this hook:

1. denies new text (a new issue or comment) that uses wrong fixed terms (CI-070: synonyms, misspelled
   headings, mixed languages), with the fix;
2. denies new text that was not shown in an assistant message the user then answered (read from the
   session transcript);
3. asks in every other case, edits of existing issues included: Claude Code's permission prompt shows what
   will be sent, for the final yes.

Edits are not checked for terms or compared: the convention covers what Claude writes new, not existing
issues or text people wrote themselves.

Reads pass untouched. Without a readable transcript only step 3 runs.
Set TRACKER_CONFIRM_WRITES=0 (for example under "env" in settings.json) to switch it off.
Standard library only, Python 3.9+. Never fails a tool call by crashing: on bad input it stays silent.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
try:
    import tracker  # noqa: E402  the checker, for the fixed terms
except Exception:  # without it the hook still asks
    tracker = None

TRACKERS = ("linear", "jira", "atlassian", "github", "gitlab", "trello", "asana", "clickup", "youtrack",
            "shortcut", "plane", "monday", "redmine", "azure")
# On code hosts only issue work counts; pull requests, files and repositories are not tracker writes.
CODE_HOSTS = ("github", "gitlab")
ISSUE_WORDS = {"issue", "issues", "label", "labels", "milestone", "subissue"}
WRITE_WORDS = {"create", "save", "update", "delete", "close", "add", "post", "transition", "edit", "set",
               "assign", "move", "archive", "comment", "reopen", "link", "unlink", "remove", "share", "unshare",
               "resolve", "retire", "restore", "merge", "mark", "bulk", "batch", "upsert", "write"}

CLI_WRITES = {
    ("gh", "issue"): {"create", "close", "comment", "edit", "reopen", "delete", "transfer", "lock", "unlock",
                      "pin", "unpin", "develop"},
    ("glab", "issue"): {"create", "close", "note", "update", "delete", "reopen"},
    ("jira", "issue"): {"create", "edit", "move", "comment", "assign", "delete", "link", "clone"},
}
ACLI_WRITES = {"create", "edit", "transition", "comment", "delete", "assign", "clone", "link"}
WRAPPERS = {"sudo", "command", "env", "nohup", "time", "exec"}
ASK = ("tracker: this writes to the issue tracker. It matches a draft shown in the chat that you answered; "
       "allow it only if your answer was yes to exactly this.")
ASK_UNVERIFIED = ("tracker: this writes to the issue tracker. Allow it only if you have seen this exact text "
                  "and said yes to it; otherwise deny and ask for the draft.")
NOT_SHOWN = ("tracker: not written. This text was not shown to the user before their last answer: %s. Show the "
             "draft in your message exactly as it will be posted (PROCEDURE.md, step 8), wait for the user's yes, "
             "then write exactly that text. Pass text literally or with --body-file, not through $(...).")
BAD_TERMS = ("tracker: not written. The text breaks the fixed terms (CONVENTION.md, CI-070): %s. Fix it, show "
             "the corrected draft to the user, and write it after their yes.")
TEXT_WORDS = {"title", "body", "description", "desc", "comment", "summary", "text", "content", "message", "note"}
CLI_TEXT_FLAGS = {"--title", "-t", "--body", "-b", "--comment", "-c", "--message", "-m", "--summary",
                  "--description", "-d"}
CLI_FILE_FLAGS = {"--body-file", "-F", "--description-file"}  # -F key=value is a gh api field


def words(name):
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return {w for w in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if w}


def is_mcp_write(name):
    parts = name.split("__")
    if len(parts) < 3 or parts[0] != "mcp":
        return False
    server, tool = parts[1].lower(), "__".join(parts[2:])
    host = next((t for t in TRACKERS if t in server), None)
    if host is None:
        return False
    ws = words(tool)
    if not ws & WRITE_WORDS:
        return False
    return host not in CODE_HOSTS or bool(ws & ISSUE_WORDS)


def tokens_of(segment):
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    while tokens and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[0]) or tokens[0] in WRAPPERS):
        tokens = tokens[1:]
    return tokens


def is_cli_write(command):
    for segment in re.split(r"&&|\|\||[;|\n]", command):
        t = tokens_of(segment)
        if len(t) >= 3 and t[2] in CLI_WRITES.get((t[0], t[1]), ()):
            return True
        if len(t) >= 4 and t[:3] == ["acli", "jira", "workitem"] and t[3] in ACLI_WRITES:
            return True
        if t[:2] == ["gh", "api"] and any(re.search(r"(^|/)issues(/|$)", x) for x in t[2:]):
            method = next((t[i + 1].upper() for i, x in enumerate(t[:-1]) if x in ("-X", "--method")), None)
            fields = any(x in ("-f", "-F", "--field", "--raw-field", "--input") for x in t)
            if method in ("POST", "PATCH", "PUT", "DELETE") or (method is None and fields):
                return True
    return False


def is_tracker_write(event):
    name = event.get("tool_name") or ""
    if name == "Bash":
        return is_cli_write((event.get("tool_input") or {}).get("command") or "")
    return is_mcp_write(name)


def is_text_key(key):
    return bool(words(str(key)) & TEXT_WORDS) or key == "name"  # a card's name; not projectName or teamName


def strings_under(value):
    """Every leaf string of a value."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings_under(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings_under(v)]
    return []


def input_texts(tool_input):
    """The text a tool input writes: its top-level title, body, description, comment ... fields, all the way down
    (Jira's description is a document tree). Nested keys such as a link's title do not count on their own."""
    if not isinstance(tool_input, dict):
        return []
    return [s for k, v in tool_input.items() if is_text_key(k) for s in strings_under(v)]


def cli_segments(command):
    """The command's simple commands as token lists; quoted text keeps its ; and | (TL;DR)."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    segments, current = [], []
    for token in lexer:
        if token and set(token) <= set("();<>|&"):
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    return segments


def cli_texts(command, cwd):
    texts = []
    for t in cli_segments(command):
        while t and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t[0]) or t[0] in WRAPPERS):
            t = t[1:]
        for i, token in enumerate(t[:-1]):
            value = t[i + 1]
            if token in CLI_TEXT_FLAGS:
                texts.append(value)
            elif token in ("-f", "-F", "--field", "--raw-field") and "=" in value:
                key, text = value.split("=", 1)
                if is_text_key(key) and not text.startswith("@"):
                    texts.append(text)
            elif token in CLI_FILE_FLAGS and not value.startswith("-"):
                path = Path(cwd or ".") / value
                try:
                    texts.append(path.read_text(encoding="utf-8")[:65536])
                except (OSError, UnicodeDecodeError):
                    pass
    return texts


def texts_of(event):
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") == "Bash":
        return [t for t in cli_texts(tool_input.get("command") or "", event.get("cwd")) if t.strip()]
    return [t for t in input_texts(tool_input) if len(t.strip()) >= 3]


def normal(text):
    return re.sub(r"\s+", " ", text.replace("\\n", "\n")).strip()


def is_human(entry):
    """A message the user typed (or answered through a question), not a tool result or a system note."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return False
    origin = entry.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return not content.lstrip().startswith(("<task-notification", "<local-command", "<system-reminder"))
    return isinstance(content, list) and any(b.get("type") == "text" for b in content if isinstance(b, dict))


def last_answered(transcript):
    """What the assistant showed in the turn the user answered last; None when it cannot be read."""
    try:
        lines = Path(transcript).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError, TypeError):
        return None
    shown, answered, questions = [], "", set()
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or entry.get("isSidechain"):
            continue
        content = (entry.get("message") or {}).get("content")
        blocks = content if isinstance(content, list) else []
        if entry.get("type") == "assistant":
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    shown.append(b.get("text") or "")
                elif b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
                    questions.add(b.get("id"))
                    shown.extend(strings_under(b.get("input")))
        elif entry.get("type") == "user":
            reply = any(isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in questions
                        and not b.get("is_error") for b in blocks)
            if reply or is_human(entry):
                if shown:
                    answered = normal("\n".join(shown))
                shown = []
    return answered


UPDATE_WORDS = {"update", "edit", "patch", "set", "transition", "move", "assign"}
CLI_UPDATES = {("gh", "issue", "edit"), ("glab", "issue", "update"), ("jira", "issue", "edit"),
               ("jira", "issue", "move"), ("jira", "issue", "assign")}


def is_edit(event):
    """A change to something that exists (an issue's description, status or fields), not new text."""
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") == "Bash":
        for t in cli_segments(tool_input.get("command") or ""):
            while t and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t[0]) or t[0] in WRAPPERS):
                t = t[1:]
            if tuple(t[:3]) in CLI_UPDATES or t[:4] in (["acli", "jira", "workitem", "edit"],
                                                        ["acli", "jira", "workitem", "transition"]):
                return True
            if t[:2] == ["gh", "api"] and any(x.upper() in ("PATCH", "PUT") for x in t):
                return True
        return False
    tool = "__".join((event.get("tool_name") or "").split("__")[2:])
    if words(tool) & UPDATE_WORDS:
        return True
    return isinstance(tool_input, dict) and bool(tool_input.get("id"))  # save_issue / save_comment with an id


def decide(event):
    """(decision, reason) for a tracker write."""
    try:
        if is_edit(event):
            return "ask", ASK_UNVERIFIED
    except ValueError:
        return "ask", ASK_UNVERIFIED
    try:
        texts = texts_of(event)
    except ValueError:  # a command shlex cannot read: nothing to compare, so only ask
        return "ask", ASK_UNVERIFIED
    errors = [f for t in texts for f in tracker.term_findings(t)] if tracker else []
    if errors:
        return "deny", BAD_TERMS % "; ".join(
            "%s %s (\"%s\")" % (f["id"], f["message"], f["quote"]) if f["quote"] else "%s %s" % (f["id"], f["message"])
            for f in errors[:5])
    answered = last_answered(event.get("transcript_path"))
    if answered is None or not texts:
        return "ask", ASK_UNVERIFIED
    missing = [t for t in texts if normal(t) not in answered]
    if missing:
        return "deny", NOT_SHOWN % "; ".join('"%s"' % normal(t)[:60] for t in missing[:3])
    return "ask", ASK


def main():
    if os.environ.get("TRACKER_CONFIRM_WRITES", "1").strip().lower() in ("0", "off", "false", "no"):
        return 0
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if isinstance(event, dict) and is_tracker_write(event):
        try:
            decision, reason = decide(event)
        except Exception:  # a bug here must never let a write through unasked
            decision, reason = "ask", ASK_UNVERIFIED
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                          "permissionDecisionReason": reason}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
