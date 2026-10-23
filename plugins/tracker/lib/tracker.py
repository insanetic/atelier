#!/usr/bin/env python3
"""tracker check: lint an issue, comment, handoff or close draft against Conventional Issues.

Deterministic, no network, no tracker. Reports; never rewrites. Python 3.9+, standard library only.
The rule IDs are those of CONVENTION.md.
"""

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

KINDS = ("bug", "feature", "improvement", "task")
PURPOSES = ("progress", "decision", "question", "blocker", "handoff", "close")
RESULTS = ("done", "wont-do", "works-as-intended", "duplicate", "cant-reproduce", "obsolete")

# Section: (English, German). Required and optional per kind, in order.
SECTIONS = {
    "problem": ("Problem", "Problem"), "expected": ("Expected", "Erwartet"),
    "steps": ("Steps", "Schritte"), "done": ("Done when", "Fertig, wenn"),
    "need": ("Need", "Bedarf"), "excluded": ("Not included", "Nicht enthalten"),
    "today": ("Today", "Heute"), "better": ("Better", "Besser"),
    "what": ("What", "Was"), "why": ("Why", "Warum"),
}
SHAPES = {
    "bug": [("problem", True), ("expected", True), ("steps", False), ("done", True)],
    "feature": [("need", True), ("done", True), ("excluded", False)],
    "improvement": [("today", True), ("better", True), ("done", True)],
    "task": [("what", True), ("why", True), ("done", True)],
}
TLDR = "TL;DR:"  # lead of the body's first line, in every language
LEADS = {
    "progress": [r"Status:", r"Stand:"],
    "decision": [r"Decision:", r"Entscheidung:"],
    "question": [r"Question for [^:\n]+:", r"Frage an [^:\n]+:"],
    "blocker": [r"Blocked:", r"Blockiert:"],
}
HANDOFF = [  # (lines that may start it, required)
    ([r"Ready for review:", r"Handed to [^:\n]+:", r"Bereit zur Prüfung:", r"Übergabe an [^:\n]+:"], True),
    ([r"To check:", r"Zu prüfen:"], False),
    ([r"Open:", r"Offen:"], False),
]
CLOSE_LEADS = {
    "done": [r"Done:", r"Erledigt:"],
    "wont-do": [r"Not doing:", r"Nicht umgesetzt:"],
    "works-as-intended": [r"Works as intended:", r"Funktioniert wie vorgesehen:"],
    "duplicate": [r"Duplicate of\b", r"Duplikat von\b"],
    "cant-reproduce": [r"Not reproducible:", r"Nicht reproduzierbar:"],
    "obsolete": [r"No longer relevant:", r"Nicht mehr relevant:"],
}
HEDGES = ["probably", "presumably", "seems to", "should now work", "should be fixed", "might be",
          "I think", "I believe", "vermutlich", "wahrscheinlich", "scheint", "sollte jetzt",
          "sollte nun", "eventuell", "möglicherweise", "ich denke", "ich glaube"]
PLACEHOLDERS = re.compile(r"(?<!\w)(?:TBD|TODO|unknown|unbekannt|n/a|\?\?\?|<[^>\n]*>)(?!\w)", re.I)
GREETINGS = re.compile(r"(?i)^(?:hi|hello|hey|hallo|moin|liebe|lieber|dear)\b|(?:viele|liebe|beste|freundliche)"
                       r" grüße|best regards|kind regards|thanks for (?:reporting|reaching out)|danke für"
                       r" (?:die|deine|ihre) meldung|sorry for|entschuldigen sie")

TITLE_MAX, BODY_MAX, COMMENT_MAX, CLOSE_SENTENCES, TLDR_MAX = 70, 120, 60, 2, 25

ORDER = ["CI-002", "CI-003", "CI-004", "CI-005", "CI-006", "CI-010", "CI-011", "CI-012", "CI-020",
         "CI-021", "CI-022", "CI-024", "CI-030", "CI-031", "CI-040", "CI-050", "CI-051", "CI-000"]
INTERNAL_SUFFIXES = (".local", ".internal", ".lan", ".corp", ".intranet", ".localhost")


class Report:
    def __init__(self):
        self.items = []

    def add(self, rule, severity, where, message, quote=None, pos=0):
        self.items.append({"id": rule, "severity": severity, "where": where, "message": message,
                           "quote": quote, "_pos": pos})

    def sorted(self):
        def key(f):
            rank = ORDER.index(f["id"]) if f["id"] in ORDER else len(ORDER)
            return (f["severity"] != "error", rank, f["_pos"])
        return [{k: v for k, v in f.items() if k != "_pos"} for f in sorted(self.items, key=key)]


def parse_frontmatter(text):
    """`key: value` lines between `---` fences. Values are plain strings."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("frontmatter is not closed")
    data = {}
    for line in text[4:end].splitlines():
        line = line.split("#", 1)[0].strip() if not line.strip().startswith("#") else ""
        if not line:
            continue
        m = re.match(r"([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            raise ValueError("unreadable frontmatter line: " + line)
        data[m.group(1)] = m.group(2).strip().strip("\"'")
    return data, text[end + 4:].lstrip("\n")


# --- exposure (same checks as the tone plugin's, copied so neither depends on the other) ---

URL = re.compile(r"https?://[^\s<>()\[\]`\"']+")
FENCE = re.compile(r"^```.*?^```[ \t]*$", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]+`")
def mask(secret):
    return secret[:4] + "…"


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


SECRETS = [
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_\w{20,}"),
    re.compile(r"\bxox[abprs]-[\w-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\blin_(?:api|oauth)_\w{20,}"),
    re.compile(r"\beyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b[a-z][\w+.-]*://[^\s:/@]+:[^\s@/]+@"),
    re.compile(r"(?i)\b(?:password|passwort|kennwort|pwd|secret|api[_-]?key|access[_-]?token|token)"
               r"\s*[:=]\s*\S+"),
]
SIGNED_QUERY = re.compile(r"(?i)[?&](?:x-amz-signature|signature|sig|token|access_token|api_key|key)=")
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-zA-Z]{2,}\b")
PHONE = re.compile(r"(?<![\w+/.,-])(?:\+\d{1,3}[\s./-]?|0)\(?\d{2,5}\)?(?:[\s./-]?\d{2,}){1,4}(?![\w.,/-]?\d)")


def check_secrets(text, report):
    for pattern in SECRETS:
        for m in pattern.finditer(text):
            report.add("CI-002", "error", "line %d" % line_of(text, m.start()),
                       "looks like a secret; remove it entirely", mask(m.group(0)), m.start())
    for m in URL.finditer(text):
        if SIGNED_QUERY.search(m.group(0)):
            report.add("CI-002", "error", "line %d" % line_of(text, m.start()),
                       "signed or token-bearing URL; remove it", mask(m.group(0)), m.start())


def check_personal(text, audience, report):
    severity = "error" if audience == "external" else "note"
    for m in EMAIL.finditer(text):
        report.add("CI-002", severity, "line %d" % line_of(text, m.start()),
                   "email address; name the person by role unless the reader needs it",
                   m.group(0), m.start())
    for m in PHONE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 8 <= len(digits) <= 15:
            report.add("CI-002", severity, "line %d" % line_of(text, m.start()),
                       "phone number", m.group(0), m.start())


def host_is_internal(host):
    host = (host or "").lower().rstrip(".")
    if not host or host == "localhost" or "." not in host:
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    return host.endswith(INTERNAL_SUFFIXES)


def check_urls(text, report):
    for m in URL.finditer(text):
        url = m.group(0).rstrip(".,;:!?")
        where = "line %d" % line_of(text, m.start())
        if host_is_internal(urlsplit(url).hostname):
            report.add("CI-003", "error", where, "link to an internal host", url, m.start())
        else:
            report.add("CI-003", "note", where,
                       "link in external text: keep only if the reader can open it", url, m.start())


PATH = re.compile(r"(?<![\w@:/.-])(?:[A-Za-z]:\\[\w\\. -]+|(?:~|\.{1,2})?/?(?:[\w.-]+/)+[\w.-]+)")
EXTENSION = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,4}$")
CALL = re.compile(r"(?<![\w.])[A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)*\(\)")
DOTTED_CALL = re.compile(r"(?<![\w.])[A-Za-z_]\w*\.[A-Za-z_]\w*\(")
STACK = [
    re.compile(r"^\s*at [\w.$<>]+\(.*\)\s*$", re.M),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"File \"[^\"]+\", line \d+"),
    re.compile(r"\b[A-Z]\w*(?:Error|Exception)\b:"),
]
LOG_LINE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*\s+\[?(?:TRACE|DEBUG|INFO|WARN|WARNING|ERROR|FATAL)\b")
COMMIT = re.compile(r"(?<![\w#/-])[0-9a-f]{7,40}(?![\w-])")
BRANCH = re.compile(r"(?<![\w/])(?:feat|feature|fix|bugfix|hotfix|chore|release|refactor)/[\w./-]+")
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\w|\.\d)")
BARE_HOST = re.compile(r"(?<![\w./@-])[\w-]+(?:\.[\w-]+)*\.(?:internal|local|lan|corp|intranet)\b", re.I)


def is_path(token):
    stripped = token.lstrip("~.")
    segments = [s for s in stripped.split("/") if s]
    if re.match(r"[A-Za-z]:\\", token):
        return True
    if len(segments) < 2:
        return False
    if any(re.fullmatch(r"\d+", s) for s in segments):
        return False  # 24/7, 1/2, dates
    leading = token.startswith(("/", "./", "../", "~/"))
    return leading or bool(EXTENSION.search(segments[-1])) or len(segments) >= 3


def check_internals(raw, prose_no_urls, report):
    """Technical internals in external text and internal hosts named without a URL (CI-003)."""
    def add(m, what, text=raw):
        report.add("CI-003", "error", "line %d" % line_of(text, m.start()),
                   what + "; describe the effect for the reader instead", m.group(0)[:80], m.start())

    for m in FENCE.finditer(raw):
        add(m, "code block")
    for m in INLINE_CODE.finditer(raw):
        add(m, "code span")
    text = prose_no_urls
    for m in PATH.finditer(text):
        if is_path(m.group(0).rstrip(".,;:")):
            add(m, "file path", text)
    for m in CALL.finditer(text):
        add(m, "function name", text)
    for m in DOTTED_CALL.finditer(text):
        add(m, "function name", text)
    for pattern in STACK:
        for m in pattern.finditer(text):
            add(m, "stack trace", text)
    for m in LOG_LINE.finditer(text):
        add(m, "log line", text)
    for m in COMMIT.finditer(text):
        token = m.group(0)
        if re.search(r"\d", token) and re.search(r"[a-f]", token):
            add(m, "commit hash", text)
    for m in BRANCH.finditer(text):
        add(m, "branch name", text)
    for m in IPV4.finditer(text):
        if all(int(part) <= 255 for part in m.group(0).split(".")):
            add(m, "IP address", text)
    for m in BARE_HOST.finditer(text):
        report.add("CI-003", "error", "line %d" % line_of(text, m.start()),
                   "internal host name", m.group(0), m.start())


def strip_code(text):
    return INLINE_CODE.sub(" ", FENCE.sub(" ", text))


ABBREVIATIONS = {"ca", "bzw", "tel", "nr", "usw", "vgl", "inkl", "ggf", "evtl", "zb", "dh", "ua",
                 "eg", "ie", "etc", "vs", "dr", "hr", "fr", "mr", "mrs", "ms", "abs", "st", "bspw", "max", "min"}


def count_sentences(text):
    """Sentence ends are . ! ? before whitespace or the end, except after a number (dates, ordinals),
    a single letter (z. B., initials) or a known abbreviation (ca., e.g., Tel.)."""
    text = text.strip()
    if not text:
        return 0
    count = 0
    for m in re.finditer(r"[.!?]+(?=\s|$)", text):
        before = text[:m.start()]
        word = re.sub(r"[^a-zäöü]", "", re.split(r"\s", before.lower())[-1])
        if m.group(0) == "." and (re.search(r"\d$", before) or len(word) == 1
                                  or word in ABBREVIATIONS):
            continue
        count += 1
    if not re.search(r"[.!?]\s*$", text):
        count += 1
    return count


TYPE_PREFIX = re.compile(r"^\s*(?:\[[^\]]+\]|(?:feat|fix|bug|bugfix|chore|docs|refactor|feature|"
                         r"hotfix|improvement|task)(?:\([^)]*\))?\s*:)", re.I)
ISSUE_ID = re.compile(r"(?<![\w-])[A-Z][A-Z0-9]{1,9}-\d+\b|(?<![\w&])#\d+\b")




# --- structure -----------------------------------------------------------------------------------

def words(text):
    return re.findall(r"[\w'’-]+", text)


def is_checklist(line):
    return bool(re.match(r"\s*[-*+]\s+\[[ xX]\]\s", line))


def section_key(heading):
    name = heading.strip().rstrip(":").strip().lower().replace(",", "")
    for key, names in SECTIONS.items():
        if name in (n.lower().replace(",", "") for n in names):
            return key
    return None


def starts_with(text, patterns):
    return any(re.match(p, text) for p in patterns)


def check_hedges(prose, report):
    for phrase in HEDGES:
        for m in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", prose, re.I):
            report.add("CI-004", "note", "line %d" % line_of(prose, m.start()),
                       "hedge or guess; state only what is known", m.group(0), m.start())
    for m in PLACEHOLDERS.finditer(prose):
        report.add("CI-005", "error", "line %d" % line_of(prose, m.start()),
                   "placeholder; ask for the fact or leave the section out", m.group(0), m.start())


def check_issue(meta, body, report):
    kind = meta.get("kind")
    if kind not in KINDS:
        report.add("CI-006", "error", "frontmatter", "kind must be one of: " + ", ".join(KINDS),
                   kind or None)
    lines = body.splitlines()
    title, start = None, 0
    for i, line in enumerate(lines):
        if line.strip():
            m = re.match(r"#\s+(.*)$", line)
            if m:
                title, start = m.group(1).strip(), i + 1
            break
    if title is None:
        report.add("CI-010", "error", "title", "the draft must start with `# <title>`")
    else:
        if len(title) > TITLE_MAX:
            report.add("CI-010", "error", "title", "%d characters, limit %d" % (len(title), TITLE_MAX), title)
        if title.endswith("."):
            report.add("CI-010", "error", "title", "trailing period", title[-20:])
        m = TYPE_PREFIX.match(title) or re.match(r"\s*[A-Z][A-Z0-9]{1,9}-\d+\b", title)
        if m:
            report.add("CI-011", "error", "title", "prefix; the kind is a label", m.group(0).strip())
        if re.search(r"\b(?:bug|fehler|issue|ticket|problem)\b", title, re.I) and kind == "bug":
            report.add("CI-012", "note", "title", "a bug's title names the correct behaviour, not the symptom",
                       title)

    rest = lines[start:]
    counted = [l for l in rest if not is_checklist(l) and not re.match(r"\s*#{1,6}\s", l)]
    n = len(words(strip_code("\n".join(counted))))
    if n > BODY_MAX:
        report.add("CI-020", "error", "body", "%d words, limit %d (checklists not counted)" % (n, BODY_MAX))

    first = next((i for i, l in enumerate(rest) if l.strip()), None)
    tldr = first if first is not None and rest[first].lstrip().startswith(TLDR) else None
    if tldr is None:
        report.add("CI-024", "error", "body", "the body starts with one `%s` sentence, in every language, "
                   "before the first section" % TLDR)
    else:
        text = rest[tldr].strip().split(":", 1)[1]
        if count_sentences(text) > 1:
            report.add("CI-024", "error", "line %d" % (start + tldr + 1), "TL;DR is one sentence", text.strip()[:60])
        if len(words(text)) > TLDR_MAX:
            report.add("CI-024", "error", "line %d" % (start + tldr + 1),
                       "TL;DR is %d words, limit %d" % (len(words(text)), TLDR_MAX))

    found, current, content = [], None, {}
    for i, line in enumerate(rest, start + 1):
        if i - start - 1 == tldr:
            continue
        m = re.match(r"\s*(#{1,6})\s+(.*)$", line)
        if m:
            key = section_key(m.group(2))
            if len(m.group(1)) != 2 or key is None:
                report.add("CI-021", "error", "line %d" % i, "not a section of this convention", line.strip()[:60])
                current = None
                continue
            found.append(key)
            current = key
            content[key] = []
        elif current:
            content[current].append(line)
        elif line.strip():
            if line.lstrip().startswith(TLDR):
                report.add("CI-024", "error", "line %d" % i, "the TL;DR comes first, before any section")
            report.add("CI-021", "error", "line %d" % i, "text outside a section", line.strip()[:60])
    if kind in SHAPES:
        shape = [k for k, _ in SHAPES[kind]]
        for key, required in SHAPES[kind]:
            if required and key not in found:
                report.add("CI-021", "error", "body", "missing required section: %s" % SECTIONS[key][0])
        for key in found:
            if key not in shape:
                report.add("CI-021", "error", "body", "section not part of a %s: %s" % (kind, SECTIONS[key][0]))
        known = [k for k in found if k in shape]
        if known != sorted(known, key=shape.index):
            report.add("CI-021", "error", "body", "sections out of order; expected " +
                       ", ".join(SECTIONS[k][0] for k in shape))
        if len(set(found)) != len(found):
            report.add("CI-021", "error", "body", "a section appears twice")
    for key, text in content.items():
        filled = [l for l in text if l.strip()]
        if not filled:
            report.add("CI-005", "error", "body", "empty section: %s; fill it or leave it out" % SECTIONS[key][0])
        elif key == "done" and not all(is_checklist(l) for l in filled):
            report.add("CI-022", "error", "body", "Done when holds only checklist lines (`- [ ] ...`)")
        elif key == "steps" and not all(re.match(r"\s*\d+[.)]\s", l) for l in filled):
            report.add("CI-022", "error", "body", "Steps is a numbered list")


def check_comment(meta, body, report):
    purpose = meta.get("purpose")
    text = body.strip()
    if purpose not in PURPOSES:
        report.add("CI-030", "error", "frontmatter", "purpose must be one of: " + ", ".join(PURPOSES),
                   purpose or None)
        return
    n = len(words(strip_code(text)))
    if n > COMMENT_MAX:
        report.add("CI-030", "error", "body", "%d words, limit %d" % (n, COMMENT_MAX))
    if re.search(r"^\s*#{1,6}\s", text, re.M):
        report.add("CI-030", "error", "body", "no headings in a comment")
    for m in GREETINGS.finditer(text):
        report.add("CI-030", "error", "line %d" % line_of(text, m.start()),
                   "greeting, sign-off, thanks or apology", m.group(0), m.start())

    if purpose in LEADS:
        if not starts_with(text, LEADS[purpose]):
            report.add("CI-030", "error", "lead", "a %s comment starts with %s" % (purpose, " or ".join(
                p.replace(r"[^:\n]+", "<person>").replace("\\b", "") for p in LEADS[purpose])), text[:30])
    elif purpose == "handoff":
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        slots = []
        for line in lines:
            slot = next((i for i, (pats, _) in enumerate(HANDOFF) if starts_with(line, pats)), None)
            if slot is None:
                report.add("CI-040", "error", "body", "every handoff line starts with its label", line[:40])
            else:
                slots.append(slot)
        if not slots or slots[0] != 0:
            report.add("CI-040", "error", "body",
                       "the first line is `Ready for review:` / `Handed to <person>:` (de: `Bereit zur Prüfung:` / `Übergabe an <person>:`)")
        if slots != sorted(set(slots)) or len(slots) != len(set(slots)):
            report.add("CI-040", "error", "body", "lines in order, each once: done, to check, open")
    elif purpose == "close":
        result = meta.get("result")
        if result not in RESULTS:
            report.add("CI-050", "error", "frontmatter", "result must be one of: " + ", ".join(RESULTS),
                       result or None)
        else:
            if not starts_with(text, CLOSE_LEADS[result]):
                report.add("CI-050", "error", "lead", "a %s close starts with %s" % (result, " or ".join(
                    p.replace("\\b", "") for p in CLOSE_LEADS[result])), text[:30])
            n = count_sentences(strip_code(text))
            if n > CLOSE_SENTENCES:
                report.add("CI-050", "error", "body", "%d sentences, limit %d" % (n, CLOSE_SENTENCES))


MENTION = re.compile(r"(?<![\w.@/+-])@([A-Za-z0-9](?:[\w.-]*\w)?)(/[\w.-]+)?")
GROUP_HANDLES = {"team", "channel", "here", "all", "everyone", "everybody", "group", "alle"}
MENTION_PURPOSES = ("question", "blocker", "handoff")


def check_mentions(meta, prose, report):
    """CI-031: a mention notifies, so only someone who must act is mentioned, and only in a comment."""
    found = list(MENTION.finditer(prose))
    if not found:
        return
    for m in found:
        if m.group(1).lower() in GROUP_HANDLES or m.group(2):
            report.add("CI-031", "error", "line %d" % line_of(prose, m.start()),
                       "group or team mention notifies everyone; name the one person who must act",
                       m.group(0), m.start())
    where = "line %d" % line_of(prose, found[0].start())
    if meta.get("type") == "issue":
        report.add("CI-031", "error", where, "no mentions in a description; people go into the assignee or "
                   "subscriber fields (CI-008)", found[0].group(0), found[0].start())
    elif meta.get("purpose") in PURPOSES and meta.get("purpose") not in MENTION_PURPOSES:
        report.add("CI-031", "error", where, "mention only someone who must act: in a question, blocker or "
                   "handoff; others follow as subscribers", found[0].group(0), found[0].start())
    elif len({m.group(1).lower() for m in found}) > 1:
        report.add("CI-031", "note", where, "several people mentioned; mention only those who must act, "
                   "normally one", found[0].group(0), found[0].start())


def check(draft):
    meta, body = parse_frontmatter(draft)
    report = Report()
    kind = meta.get("type")
    audience = meta.get("audience", "external")
    if kind not in ("issue", "comment"):
        report.add("CI-000", "error", "frontmatter", "type must be issue or comment", kind or None)
    if audience not in ("internal", "external"):
        report.add("CI-000", "error", "frontmatter", "audience must be internal or external", audience)
        audience = "external"
    prose = strip_code(body)
    prose_no_urls = URL.sub(lambda m: " " * len(m.group(0)), prose)
    check_secrets(body, report)
    check_personal(prose_no_urls, audience, report)
    if audience == "external":
        check_urls(prose, report)
        check_internals(body, prose_no_urls, report)
    check_hedges(prose_no_urls, report)
    check_mentions({**meta, "type": kind}, prose_no_urls, report)
    if kind == "issue":
        check_issue(meta, body, report)
    elif kind == "comment":
        check_comment(meta, body, report)
    return {"type": kind, "audience": audience, "findings": report.sorted()}


def render(result):
    out = []
    for f in result["findings"]:
        line = "%-5s %s %s: %s" % (f["severity"], f["id"], f["where"], f["message"])
        if f["quote"]:
            line += ' · "%s"' % f["quote"]
        out.append(line)
    errors = sum(f["severity"] == "error" for f in result["findings"])
    notes = len(result["findings"]) - errors
    head = "%s, %s" % (result["type"], result["audience"])
    out.append("clean (%s)" % head if not result["findings"] else "%d error%s, %d note%s (%s)" % (
        errors, "" if errors == 1 else "s", notes, "" if notes == 1 else "s", head))
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tracker", description="Lint drafts against Conventional Issues.")
    sub = parser.add_subparsers(dest="command")
    c = sub.add_parser("check", help="check a draft")
    c.add_argument("--json", action="store_true")
    c.add_argument("file", help="the draft, or - for stdin")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if args.command != "check":
        parser.print_usage(sys.stderr)
        return 2
    try:
        draft = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        result = check(draft)
    except OSError as e:
        print("tracker: cannot read %s: %s" % (args.file, e.strerror), file=sys.stderr)
        return 2
    except ValueError as e:
        print("tracker: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 1 if any(f["severity"] == "error" for f in result["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
