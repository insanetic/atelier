#!/usr/bin/env python3
"""PreToolUse hook: every write to an issue tracker waits for the user's yes.

The tracker skills show each write before making it (PROCEDURE.md, step 8), but that is an instruction the
model can skip. This hook makes Claude Code itself ask: a tracker write through an MCP tool (Linear, Jira,
GitHub issues and the like) or a tracker CLI (gh issue, gh api …/issues, glab issue, acli jira, jira) gets
the permission prompt, which shows exactly what will be sent. Reads pass untouched.

Set TRACKER_CONFIRM_WRITES=0 (for example under "env" in settings.json) to switch it off.
Standard library only, Python 3.9+. Never fails a tool call: on bad input it stays silent.
"""

import json
import os
import re
import shlex
import sys

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
REASON = ("tracker: this writes to the issue tracker. Allow it only if you have seen this exact text and said "
          "yes to it; otherwise deny and ask for the draft.")


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


def main():
    if os.environ.get("TRACKER_CONFIRM_WRITES", "1").strip().lower() in ("0", "off", "false", "no"):
        return 0
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if isinstance(event, dict) and is_tracker_write(event):
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                          "permissionDecisionReason": REASON}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
