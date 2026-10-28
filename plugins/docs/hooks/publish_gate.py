#!/usr/bin/env python3
"""PreToolUse hook: nothing goes live in a hosted help center unless it came from git and the user said yes.

The docs skills publish only a committed, checked article, rendered by `docs render`, after showing the user
what changes (PROCEDURE.md). A model can skip those steps, so for every write to a hosted help center
through an MCP tool (Productlane, Intercom, Zendesk, Help Scout, Document360, GitBook, ReadMe, Mintlify …)
or an HTTP call to one (curl, wget, httpie), this hook:

1. denies it when the article body was not rendered by `docs render` from a committed article that passed
   `docs check` (DOC-072): `docs render` leaves a fingerprint of every body it produced, and the body sent
   must match one;
2. otherwise asks: Claude Code's permission prompt names the article and the commit, for the final yes.

Writes without a body (delete, move, rename, unpublish) are always asked. Reads pass untouched.
Set DOCS_CONFIRM_PUBLISH=0 (for example under "env" in settings.json) to switch it off.
Standard library only, Python 3.9+. Never fails a tool call by crashing: on bad input it stays silent.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import docs  # noqa: E402

HOSTS = ("productlane", "intercom", "zendesk", "helpscout", "help-scout", "freshdesk", "document360",
         "gitbook", "readme", "mintlify", "archbee", "helpjuice", "crisp", "gorgias", "helpcenter",
         "help-center", "knowledge")
# General wikis (Notion, Confluence) are left out: their page writes are not help center publishes.
DOC_WORDS = {"doc", "docs", "article", "articles", "collection", "collections", "category", "categories",
             "section", "sections", "knowledge", "kb", "helpcenter", "help", "guide", "guides", "page", "pages"}
WRITE_WORDS = {"create", "update", "delete", "publish", "unpublish", "patch", "put", "post", "save", "set",
               "edit", "move", "archive", "unarchive", "restore", "remove", "replace", "upsert", "write",
               "draft", "add", "rename", "translate", "bulk", "batch"}
BODY_WORDS = {"body", "content", "markdown", "md", "html", "text"}
HTTP_TOOLS = {"curl", "wget", "http", "https", "xh", "httpie"}
WRAPPERS = {"sudo", "command", "env", "nohup", "time", "exec"}

ASK = ("docs: this publishes to the live help center: %s. It matches the committed, checked version. Allow it "
       "only if you have seen what changes and said yes.")
ASK_OTHER = ("docs: this changes the live help center without an article body (delete, move, rename or "
             "unpublish). Allow it only if you asked for exactly this.")
ASK_UNREADABLE = ("docs: this writes to the live help center and its content could not be read. Allow it only "
                  "if you have seen what changes and said yes.")
NOT_RENDERED = ("docs: not published. The article body was not produced by `docs render` from a committed "
                "article that passes `docs check` (DOC-072). Commit the article, run `docs render --target "
                "<target> --out <file> <article>`, send exactly that body, and show the user what changes "
                "first. Use /docs:push. Body starts: \"%s\"")


def words(name):
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return {w for w in re.split(r"[^A-Za-z0-9]+", spaced.lower()) if w}


def is_mcp_write(name):
    parts = name.split("__")
    if len(parts) < 3 or parts[0] != "mcp":
        return False
    server = parts[1].lower()
    if not any(h in server for h in HOSTS):
        return False
    ws = words("__".join(parts[2:]))
    return bool(ws & WRITE_WORDS) and bool(ws & DOC_WORDS)


def segments(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    out, current = [], []
    for token in lexer:
        if token and set(token) <= set("();<>|&"):
            out.append(current)
            current = []
        else:
            current.append(token)
    out.append(current)
    return out


def http_calls(command):
    """(tokens, url, method, payloads) for every HTTP call to a help center host in a shell command."""
    calls = []
    for t in segments(command):
        while t and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t[0]) or t[0] in WRAPPERS):
            t = t[1:]
        if not t or Path(t[0]).name not in HTTP_TOOLS:
            continue
        urls = [x for x in t if re.match(r"^https?://", x) or re.match(r"^[\w.-]+\.\w+/", x)]
        url = next((u for u in urls if any(h in u.lower() for h in HOSTS)), None)
        if not url or not (words(url) & DOC_WORDS):
            continue
        method, payloads = None, []
        for i, x in enumerate(t):
            nxt = t[i + 1] if i + 1 < len(t) else ""
            if x in ("-X", "--request", "--method"):
                method = nxt.upper()
            elif x.startswith("-X") and len(x) > 2:
                method = x[2:].upper()
            elif x in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--json",
                       "--post-data", "--body-data", "--body-file", "--post-file"):
                payloads.append(("@" + nxt) if x in ("--body-file", "--post-file") else nxt)
            elif Path(t[0]).name in ("http", "https", "xh") and i == 1 and x.upper() in (
                    "POST", "PUT", "PATCH", "DELETE"):
                method = x.upper()
        if method is None and payloads:
            method = "POST"
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            calls.append((t, url, method, payloads))
    return calls


def is_write(event):
    name = event.get("tool_name") or ""
    if name == "Bash":
        try:
            return bool(http_calls((event.get("tool_input") or {}).get("command") or ""))
        except ValueError:
            return False
    return is_mcp_write(name)


def strings_under(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in strings_under(v)]
    if isinstance(value, list):
        return [s for v in value for s in strings_under(v)]
    return []


def bodies_in(value):
    """Article bodies in a tool input or a JSON payload: strings under body, content, markdown … keys."""
    if isinstance(value, dict):
        out = []
        for k, v in value.items():
            if words(str(k)) & BODY_WORDS:
                out.extend(s for s in strings_under(v) if len(s.strip()) >= 20)
            else:
                out.extend(bodies_in(v))
        return out
    if isinstance(value, list):
        return [s for v in value for s in bodies_in(v)]
    return []


def payload_bodies(payload, cwd):
    if payload.startswith("@"):
        try:
            payload = (Path(cwd or ".") / payload[1:]).read_text(encoding="utf-8")[:1048576]
        except (OSError, UnicodeDecodeError):
            return None
    try:
        data = json.loads(payload)
    except ValueError:
        return [payload] if len(payload.strip()) >= 20 else []
    return bodies_in(data)


def texts_of(event):
    """The bodies a write sends; None when they cannot be read."""
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") != "Bash":
        return bodies_in(tool_input)
    out = []
    for _, _, _, payloads in http_calls(tool_input.get("command") or ""):
        for p in payloads:
            if "$(" in p or "`" in p:
                return None
            got = payload_bodies(p, event.get("cwd"))
            if got is None:
                return None
            out.extend(got)
    return out


def rendered(body):
    """The stamp `docs render` left for this body, or None."""
    digest = docs.hashlib.sha256(docs.normal(body).encode("utf-8")).hexdigest()
    try:
        return json.loads((docs.stamp_dir() / digest).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def decide(event):
    try:
        texts = texts_of(event)
    except ValueError:
        return "ask", ASK_UNREADABLE
    if texts is None:
        return "ask", ASK_UNREADABLE
    if not texts:
        return "ask", ASK_OTHER
    found = []
    for t in texts:
        info = rendered(t)
        if info is None:
            return "deny", NOT_RENDERED % docs.normal(t)[:60]
        found.append("%s at %s" % (info.get("file", "?"), info.get("commit", "?")))
    return "ask", ASK % "; ".join(found)


def main():
    if os.environ.get("DOCS_CONFIRM_PUBLISH", "1").strip().lower() in ("0", "off", "false", "no"):
        return 0
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    if isinstance(event, dict) and is_write(event):
        try:
            decision, reason = decide(event)
        except Exception:  # a bug here must never let a write through unasked
            decision, reason = "ask", ASK_UNREADABLE
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                          "permissionDecisionReason": reason}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
