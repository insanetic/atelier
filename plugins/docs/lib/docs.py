#!/usr/bin/env python3
"""docs: the deterministic part of the Docs Convention (CONVENTION.md next to this folder).

    docs check [--json] [--lang L] [--house-style] [--reader R] [--type T] <file|->...
                                                      an article against the convention
    docs links [--json] <file>                        its links to other articles, resolved locally
    docs history [--json] <file>                      its versions, and which went live where
    docs stale [--json] [--months N] <folder>         articles not changed for N months (default 12)
    docs render [--target NAME] [--at REV] [--draft] [--links MAP] [--assets MAP] [--house-style] <file>
                                                      the body to push, from a committed version
    docs diff [--json] <old> <new>                    two versions, normalised, line by line

With --house-style only the universal rules are checked: the project's house style (.claude/rules/docs.md)
replaces the default shape, headings, title form, frontmatter and callouts, and is judged by review.

It reports and never rewrites an article, and it never uses the network. Python 3.9+, standard library only.
Exit codes: 0 fine, 1 findings with errors (check) or a refusal (render), 2 usage error.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

VERSION = "0.3.0"

# --- the convention's tables -------------------------------------------------------------------------------

READERS = ("user", "developer")
TYPES = {
    "user": ("how-to", "troubleshooting", "overview", "reference", "faq"),
    "developer": ("quickstart", "how-to", "reference", "concept", "troubleshooting", "faq"),
}

# DOC-080
HEADINGS = {
    "before": {"en": "Before you begin", "de": "Voraussetzungen"},
    "steps": {"en": "Steps", "de": "Schritte"},
    "trouble": {"en": "If it doesn't work", "de": "Falls es nicht klappt"},
    "related": {"en": "Related articles", "de": "Verwandte Artikel"},
    "cause": {"en": "Cause", "de": "Ursache"},
    "solution": {"en": "Solution", "de": "Lösung"},
    "still": {"en": "Still not working?", "de": "Weiterhin Probleme?"},
    "can_do": {"en": "What you can do", "de": "Was möglich ist"},
    "how_works": {"en": "How it works", "de": "So funktioniert es"},
    "good_to_know": {"en": "Good to know", "de": "Gut zu wissen"},
    "install": {"en": "Install", "de": "Installation"},
    "verify": {"en": "Check that it works", "de": "Prüfen, ob es funktioniert"},
    "next": {"en": "Next steps", "de": "Nächste Schritte"},
    "signature": {"en": "Signature", "de": "Signatur"},
    "params": {"en": "Parameters", "de": "Parameter"},
    "returns": {"en": "Returns", "de": "Rückgabewert"},
    "errors": {"en": "Errors", "de": "Fehler"},
    "example": {"en": "Example", "de": "Beispiel"},
    "auth": {"en": "Authorization", "de": "Autorisierung"},
    "when_to_use": {"en": "When to use it", "de": "Wann es passt"},
}
LANGS = ("en", "de")

# Headings people write instead of the fixed ones.
SYNONYMS = {
    "prerequisites": "before", "requirements": "before", "before you start": "before",
    "bevor sie beginnen": "before", "bevor du beginnst": "before", "vorbereitung": "before",
    "anforderungen": "before",
    "instructions": "steps", "procedure": "steps", "how to": "steps", "anleitung": "steps",
    "vorgehen": "steps", "so geht's": "steps", "so gehts": "steps",
    "troubleshooting": "trouble", "problems": "trouble", "fehlerbehebung": "trouble",
    "probleme": "trouble",
    "see also": "related", "related": "related", "learn more": "related", "siehe auch": "related",
    "weitere artikel": "related", "mehr erfahren": "related", "related links": "related",
    "fix": "solution", "resolution": "solution", "workaround": "solution", "behebung": "solution",
    "abhilfe": "solution", "reason": "cause", "grund": "cause",
    "overview": "how_works", "überblick": "how_works", "notes": "good_to_know", "hinweise": "good_to_know",
    "limits": "good_to_know", "limitations": "good_to_know", "einschränkungen": "good_to_know",
    "installation": "install", "setup": "install", "verify": "verify", "verification": "verify",
    "test it": "verify", "testen": "verify", "what's next": "next", "wie geht es weiter": "next",
    "arguments": "params", "argumente": "params", "return value": "returns", "response": "returns",
    "antwort": "returns", "exceptions": "errors", "error codes": "errors", "fehlercodes": "errors",
    "authentication": "auth", "authentifizierung": "auth", "auth": "auth",
    "examples": "example", "beispiele": "example", "usage": "example", "verwendung": "example",
    "syntax": "signature", "request": "signature", "anfrage": "signature",
}

# DOC-021: (section, required); "*" is a slot for free headings.
SHAPES = {
    ("user", "how-to"): [("before", False), ("steps", True), ("trouble", False), ("related", False)],
    ("user", "troubleshooting"): [("cause", False), ("solution", True), ("still", False), ("related", False)],
    ("user", "overview"): [("can_do", True), ("how_works", False), ("good_to_know", False), ("related", False)],
    ("user", "reference"): [("*", True), ("related", False)],
    ("developer", "quickstart"): [("before", True), ("install", True), ("*", True), ("verify", True),
                                  ("next", True)],
    ("developer", "how-to"): [("before", False), ("steps", True), ("verify", False), ("next", False)],
    ("developer", "reference"): [("signature", True), ("auth", False), ("params", False), ("returns", False),
                                 ("errors", False), ("example", True), ("related", False)],
    ("developer", "concept"): [("how_works", True), ("when_to_use", False), ("*", False), ("related", False)],
    ("developer", "troubleshooting"): [("cause", False), ("solution", True), ("still", False),
                                       ("related", False)],
    ("user", "faq"): [("*", True), ("related", False)],
    ("developer", "faq"): [("*", True), ("related", False)],
}
MAX_FAQ_ANSWER = 60

WORD_LIMITS = {("user", "how-to"): 600, ("user", "troubleshooting"): 500, ("user", "overview"): 500}
MAX_USER_STEPS = 7
MAX_SENTENCE = {"user": 25, "developer": 35}
MAX_INTRO_SENTENCES = {"user": 2, "developer": 3}
TITLE_MAX, DESCRIPTION_MAX = 60, 160
CALLOUTS = ("note", "tip", "info", "warning", "danger")
PORTABLE_TAGS = {"Tabs", "Tab", "CodeGroup"}
FRONTMATTER_KEYS = {"title", "description", "type", "reader", "lang", "order", "status", "applies_to",
                    "source", "source_commit"}

# DOC-032. Errors judge the reader's task; notes are filler to look at.
JUDGING = {
    "en": [r"\bsimply\b", r"\beasy\b", r"\beasily\b", r"\bobviously\b", r"\bof course\b"],
    "de": [r"\beinfach\b", r"\blediglich\b", r"\bnatürlich\b", r"\bkinderleicht\b", r"\boffensichtlich\b",
           r"\bselbstverständlich\b", r"\bganz leicht\b"],
}
FILLER = {
    "en": [r"\bjust\b", r"\bin order to\b", r"\bplease note\b", r"\bbasically\b", r"\butili[sz]e\b", r"\bleverage\b",
           r"\bit is important to\b"],
    "de": [r"\bes ist zu beachten\b", r"\bbitte beachten sie\b", r"\bim prinzip\b", r"\bgrundsätzlich\b"],
}
BAD_LINK_TEXT = {"here", "click here", "this link", "link", "this", "more", "read more", "hier", "hier klicken",
                 "diesen link", "link", "mehr", "weiterlesen", "dieser link"}
BACKREFS = re.compile(r"(?i)\b(?:see|as (?:shown|described|mentioned|explained)) (?:above|below|earlier)\b|"
                      r"\bas mentioned (?:earlier|before)\b|\b(?:siehe|wie) (?:oben|unten)\b|"
                      r"\b(?:oben|weiter oben|weiter unten) (?:beschrieben|erwähnt|genannt|gezeigt)\b")
TABLE_GLYPHS = re.compile(r"^(?:✓|✔|✗|✘|❌|✅|Y|N|-|–|—|x|X)$")
PLACEHOLDERS = re.compile(r"\b(?:TODO|TBD|FIXME|XXX)\b|<!--\s*(?:ask|todo|tbd)|lorem ipsum|\?\?\?", re.I)
SECRETS = [
    re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_\w{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"),
]
SIGNED_QUERY = re.compile(r"(?i)[?&](?:x-amz-signature|signature|sig|token|access_token|api_key|key)=[^&\s]{8,}")
INTERNAL_HOST = re.compile(r"(?i)\b(?:https?://)?(?:localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|"
                           r"192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|"
                           r"[\w.-]+\.(?:internal|corp|intranet|lan))\b(?::\d+)?")
SIE = re.compile(r"(?<![.!?:]\s)(?<!^)\b(?:Sie|Ihnen|Ihr|Ihre|Ihren|Ihrem|Ihrer|Ihres)\b", re.M)
DU = re.compile(r"\b(?:du|dich|dir|dein|deine|deinen|deinem|deiner|deines|Du|Dich|Dir|Dein|Deine)\b")
GERMAN_HINTS = re.compile(r"\b(?:und|der|die|das|nicht|mit|für|ist|Sie|wählen|auf|eine|einen|werden)\b")
ENGLISH_HINTS = re.compile(r"\b(?:the|and|you|your|with|for|is|select|to|of|this|that)\b")

# --- reading an article -----------------------------------------------------------------------------------


class Article:
    def __init__(self, text, path=None):
        self.path = path
        self.raw = text.replace("\r\n", "\n")
        self.meta, self.meta_lines, self.body, self.body_start = split_frontmatter(self.raw)

    def lang(self, given=None):
        if given:
            return given
        if self.meta.get("lang"):
            return self.meta["lang"]
        if self.path:
            m = re.search(r"\.([a-z]{2})\.mdx?$", self.path)
            if m:
                return m.group(1)
            m = re.search(r"/i18n/([a-z]{2})(?:-[A-Za-z]+)?/", self.path)
            if m:
                return m.group(1)
        prose = strip_code(self.body)
        return "de" if len(GERMAN_HINTS.findall(prose)) > len(ENGLISH_HINTS.findall(prose)) else "en"


def split_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, 0, text, 1
    end = text.find("\n---", 4)
    if end < 0:
        return {}, 0, text, 1
    block = text[4:end]
    meta = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if m:
            value = m.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            meta[m.group(1)] = value
    rest = text[end + 4:]
    rest = rest[1:] if rest.startswith("\n") else rest
    return meta, block.count("\n") + 1, rest, block.count("\n") + 4


FENCE = re.compile(r"^(\s*)(```+|~~~+)(.*)$")


def lines_outside_code(body):
    """(line number in body, line, in_code) for every line; fences themselves count as code."""
    out, fence = [], None
    for i, line in enumerate(body.split("\n"), 1):
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(2)[0] * 3
            out.append((i, line, True))
        elif fence is not None:
            out.append((i, line, True))
            if line.strip().startswith(fence):
                fence = None
        else:
            out.append((i, line, False))
    return out


def strip_code(body):
    return "\n".join(line for _, line, code in lines_outside_code(body) if not code)


def code_blocks(body):
    """(line, info string) of every opening fence."""
    blocks, fence = [], None
    for i, line in enumerate(body.split("\n"), 1):
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(2)[0] * 3
            blocks.append((i, m.group(3).strip()))
        elif fence is not None and line.strip().startswith(fence):
            fence = None
    return blocks


def headings(body):
    out = []
    for i, line, code in lines_outside_code(body):
        if code:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            out.append((i, len(m.group(1)), m.group(2).strip()))
    return out


def plain(text):
    """Markdown inline syntax removed, for counting words and sentences."""
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"`[^`]*`", "x", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_~]{1,3}", "", text)
    return text


def prose_units(body):
    """Paragraph and list-item texts outside code, headings, tables, callout fences and HTML-only lines,
    each with its first line number."""
    units, current, start = [], [], 0

    def flush():
        if current:
            units.append((start, " ".join(current)))
        current.clear()

    for i, line, code in lines_outside_code(body):
        s = line.strip()
        if code or not s or s.startswith(("#", "|", ":::", "<", "![")) or re.match(r"^-{3,}$", s):
            flush()
            continue
        item = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*)$", s)
        if item:
            flush()
            start = i
            current.append(item.group(1))
            continue
        if not current:
            start = i
        current.append(re.sub(r"^>\s?", "", s))
    flush()
    return units


def sentences(text):
    text = plain(text)
    text = re.sub(r"\b(?:e\.g|i\.e|etc|z\.B|z\. B|d\.h|d\. h|bzw|ca|usw|vgl|Nr|Dr)\.", "abbr", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9\"'(*])", text.strip())
    return [p for p in parts if re.search(r"\w", p)]


def word_count(text):
    return len(re.findall(r"[\wÄÖÜäöüß'-]+", plain(text)))


# --- findings --------------------------------------------------------------------------------------------


class Report:
    def __init__(self):
        self.findings = []

    def add(self, rule, severity, line, message, quote=""):
        self.findings.append({"id": rule, "severity": severity, "line": line, "message": message,
                              "quote": quote[:80]})

    def errors(self):
        return [f for f in self.findings if f["severity"] == "error"]


def heading_key(text):
    """(key, language) when the text is a fixed heading spelled exactly; else (None, None)."""
    for key, names in HEADINGS.items():
        for lang, name in names.items():
            if text == name:
                return key, lang
    return None, None


def near_key(text):
    """The fixed heading a free heading was probably meant to be: wrong case, wrong language or a synonym."""
    low = text.lower().rstrip(":?.!").strip()
    for key, names in HEADINGS.items():
        for name in names.values():
            if low == name.lower().rstrip("?"):
                return key
    return SYNONYMS.get(low)


def check_frontmatter(art, report):
    meta = art.meta
    if not art.meta_lines:
        report.add("DOC-063", "error", 1, "no frontmatter; title, description, type and reader are required")
        return None, None
    for key in ("title", "description", "type", "reader"):
        if not meta.get(key):
            report.add("DOC-063", "error", 1, "frontmatter needs `%s`" % key)
    reader, kind = meta.get("reader"), meta.get("type")
    if reader and reader not in READERS:
        report.add("DOC-001", "error", 1, "reader must be user or developer", reader)
        reader = None
    if kind and reader and kind not in TYPES[reader]:
        report.add("DOC-002", "error", 1, "type for a %s is one of %s" % (reader, ", ".join(TYPES[reader])), kind)
        kind = None
    if meta.get("status") and meta["status"] not in ("draft", "ready"):
        report.add("DOC-063", "error", 1, "status is draft or ready", meta["status"])
    if reader == "developer" and not meta.get("applies_to"):
        report.add("DOC-050", "note", 1, "developer articles name the versions they apply to (`applies_to`)")
    if meta.get("source") and not meta.get("source_commit"):
        report.add("DOC-073", "error", 1, "a translation names the source commit it was made from "
                   "(`source_commit`)")
    return reader, kind


def check_title(art, kind, lang, report):
    title = art.meta.get("title", "")
    if not title:
        return
    if len(title) > TITLE_MAX:
        report.add("DOC-010", "error", 1, "title has %d characters, at most %d" % (len(title), TITLE_MAX), title)
    if re.match(r"(?i)^(how (to|do i|can i)|wie\b)", title):
        report.add("DOC-010", "error", 1, "no \"How to\" or \"Wie\": start with the task itself", title)
    if title.rstrip().endswith((".", "?", "!", ":")):
        report.add("DOC-010", "error", 1, "no punctuation at the end of the title", title)
    if kind == "how-to" and lang == "en" and re.match(r"^[A-Z][a-z]+ing\b", title):
        report.add("DOC-010", "note", 1, "a how-to starts with the verb's plain form (\"Export\", not "
                   "\"Exporting\")", title)
    description = art.meta.get("description", "")
    if len(description) > DESCRIPTION_MAX:
        report.add("DOC-011", "error", 1, "description has %d characters, at most %d"
                   % (len(description), DESCRIPTION_MAX), description)
    if description and title and description.strip().rstrip(".").lower() == title.strip().lower():
        report.add("DOC-011", "error", 1, "the description repeats the title", description)


def check_headings(art, reader, kind, lang, report):
    hs = headings(art.body)
    off = art.body_start - 1
    previous = 1
    for line, level, text in hs:
        if level == 1:
            report.add("DOC-010", "error", line + off, "no H1 in the body: the title comes from the frontmatter",
                       text)
        elif level > 3:
            report.add("DOC-040", "error", line + off, "no headings below ###", text)
        elif level > previous + 1:
            report.add("DOC-040", "error", line + off, "heading level skipped", text)
        if level > 1 and re.search(r"[.:;,!]$", text):
            report.add("DOC-040", "error", line + off, "no punctuation at the end of a heading", text)
        previous = max(level, 2)
    if not (reader and kind):
        return
    shape = SHAPES[(reader, kind)]
    known = {k for k, _ in shape if k != "*"}
    free_allowed = any(k == "*" for k, _ in shape)
    h2 = [(line, text) for line, level, text in hs if level == 2]
    seen, pos = [], 0
    for line, text in h2:
        key, hlang = heading_key(text)
        if key is not None and hlang != lang and HEADINGS[key].get(lang) != text:
            report.add("DOC-080", "error", line + off, "heading in the wrong language: \"%s\""
                       % HEADINGS[key].get(lang, HEADINGS[key]["en"]), text)
        if key is None:
            near = near_key(text)
            if near and (near in known or not free_allowed):
                fixed = HEADINGS[near].get(lang, HEADINGS[near]["en"])
                report.add("DOC-080", "error", line + off, "use the fixed heading \"%s\"" % fixed, text)
                key = near
        if key is not None and key not in known:
            if free_allowed:
                key = None  # a free heading that happens to match another type's section
            else:
                report.add("DOC-021", "error", line + off, "a %s %s has no \"%s\" section"
                           % (reader, kind, text), text)
                continue
        if key is None and not free_allowed:
            report.add("DOC-021", "error", line + off, "a %s %s has only these sections: %s"
                       % (reader, kind, ", ".join(HEADINGS[k].get(lang, HEADINGS[k]["en"]) for k in known)),
                       text)
            continue
        slot = key if key is not None else "*"
        idx = next((i for i in range(pos, len(shape)) if shape[i][0] == slot), None)
        if idx is None:
            if key is not None and key in seen:
                report.add("DOC-021", "error", line + off, "section appears twice", text)
            else:
                report.add("DOC-021", "error", line + off, "section out of order; the order is: %s"
                           % " · ".join(HEADINGS[k].get(lang, HEADINGS[k]["en"]) if k != "*" else "…"
                                        for k, _ in shape), text)
            continue
        pos = idx if slot == "*" else idx + 1  # free headings may repeat; fixed ones may not
        seen.append(slot)
    for key, required in shape:
        if required and key not in seen:
            name = HEADINGS[key].get(lang, HEADINGS[key]["en"]) if key != "*" else "at least one section"
            report.add("DOC-021", "error", 1 + off if not h2 else h2[0][0] + off,
                       "a %s %s needs %s" % (reader, kind, "\"%s\"" % name if key != "*" else name))


def section(body, key):
    """(first line, text) of the ## section whose heading is `key`'s, or a misspelling or synonym of it."""
    out, inside, first = [], False, None
    for i, line, code in lines_outside_code(body):
        if not code and re.match(r"^##\s+", line):
            text = re.sub(r"^##\s+", "", line).strip()
            inside = first is None and (heading_key(text)[0] or near_key(text)) == key
            if inside:
                first = i
            continue
        if inside:
            out.append(line)
    return first, "\n".join(out)


def check_intro(art, reader, report):
    first_heading = next((i for i, line, code in lines_outside_code(art.body)
                          if not code and re.match(r"^#{2,}\s", line)), None)
    lines = art.body.split("\n")[: (first_heading - 1) if first_heading else None]
    intro = " ".join(l.strip() for l in lines if l.strip() and not l.strip().startswith(("#", ":::", "!["))
                     and not l.strip().startswith("import "))
    off = art.body_start - 1
    if not intro:
        report.add("DOC-020", "error", 1 + off, "start with one or two sentences on what the reader will achieve")
        return
    if reader:
        n = len(sentences(intro))
        if n > MAX_INTRO_SENTENCES[reader]:
            report.add("DOC-020", "error", 1 + off, "the first paragraph has %d sentences, at most %d"
                       % (n, MAX_INTRO_SENTENCES[reader]), intro)
    if re.match(r"(?i)^(in this (article|guide)|this article|in diesem artikel|dieser artikel)", intro):
        report.add("DOC-020", "error", 1 + off, "start with the point, not with \"In this article\"", intro)


def check_steps(art, reader, kind, lang, report):
    if kind != "how-to":
        return
    first, text = section(art.body, "steps")
    if first is None:
        return
    items = [l for l in text.split("\n") if re.match(r"^\d+[.)]\s", l)]
    numbered_h3 = [l for l in text.split("\n") if re.match(r"^###\s+\d+[.)]?\s", l)]
    line = first + art.body_start - 1
    if not items and not (reader == "developer" and numbered_h3):
        report.add("DOC-022", "error", line, "steps are a numbered list")
    if reader == "user" and len(items) > MAX_USER_STEPS:
        report.add("DOC-034", "error", line, "%d steps; at most %d for users: group them or split the article"
                   % (len(items), MAX_USER_STEPS))
    for item in items:
        if re.search(r"(?i)\b(?:and then|, then|und dann|anschließend)\b", item):
            report.add("DOC-034", "note", line, "one action per step", item.strip())


def check_faq(art, reader, kind, lang, report):
    """FAQ questions end with ? and their answers are short (DOC-006, DOC-022)."""
    if kind != "faq":
        return
    related = HEADINGS["related"].get(lang, HEADINGS["related"]["en"])
    off = art.body_start - 1
    current, start, words = None, 0, 0

    def close():
        if current is not None and words > MAX_FAQ_ANSWER:
            report.add("DOC-006", "error", start + off, "answer of %d words, at most %d: link to the article that "
                       "covers it" % (words, MAX_FAQ_ANSWER), current)

    lines = lines_outside_code(art.body)
    for i, line, code in lines:
        m = None if code else re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            close()
            current, start, words = m.group(1), i, 0
            if current == related:
                current = None
            elif not current.endswith("?"):
                report.add("DOC-022", "error", i + off, "an FAQ question is the reader's question, ending with ?",
                           current)
            continue
        if current is not None and not code:
            words += word_count(line)
    close()


def check_procedures(art, reader, report):
    """House style: every numbered list for users has at most seven steps (DOC-034)."""
    if reader != "user":
        return
    run, start = 0, 0
    for i, line, code in lines_outside_code(art.body) + [(0, "", False)]:
        if not code and re.match(r"^\d+[.)]\s", line):
            run, start = run + 1, start or i
        elif line.strip() and not re.match(r"^\s", line) or (i == 0):
            if run > MAX_USER_STEPS:
                report.add("DOC-034", "error", start + art.body_start - 1, "%d steps; at most %d for users: group "
                           "them or split the procedure" % (run, MAX_USER_STEPS))
            run, start = 0, 0


def check_writing(art, reader, kind, lang, report):
    off = art.body_start - 1
    words = 0
    for line, unit in prose_units(art.body):
        words += word_count(unit)
        if reader:
            for s in sentences(unit):
                n = word_count(s)
                if n > MAX_SENTENCE[reader]:
                    report.add("DOC-031", "error", line + off, "sentence of %d words, at most %d"
                               % (n, MAX_SENTENCE[reader]), s)
        low = plain(unit).lower()
        m = BACKREFS.search(plain(unit))
        if m:
            report.add("DOC-007", "error", line + off, "each section stands on its own: name the thing instead of "
                       "pointing above or below", m.group(0))
        for pattern in JUDGING.get(lang, JUDGING["en"]):
            m = re.search(pattern, low)
            if m:
                report.add("DOC-032", "error", line + off, "no words that judge the reader's task", m.group(0))
        for pattern in FILLER.get(lang, FILLER["en"]):
            m = re.search(pattern, low)
            if m:
                report.add("DOC-032", "note", line + off, "filler", m.group(0))
        if re.search(r"(?i)\b(?:on the (?:left|right)|top right|bottom left|the (?:red|green|blue) button|"
                     r"oben rechts|unten links|links oben|rechts oben|der (?:rote|grüne|blaue)n? (?:knopf|button))",
                     unit):
            report.add("DOC-035", "note", line + off, "name the label, not only where it is or its colour", unit)
    limit = WORD_LIMITS.get((reader, kind))
    if limit and words > limit:
        report.add("DOC-023", "note", 1 + off, "%d words; above %d, look for a second article" % (words, limit))
    if lang == "de" and reader == "user":
        prose = plain(strip_code(art.body))
        sie = [m.group(0) for m in SIE.finditer(prose)]
        du = [m.group(0) for m in DU.finditer(prose)]
        if sie and du:
            report.add("DOC-030", "error", 1 + off, "Sie and du in one article", "%s / %s" % (sie[0], du[0]))


def check_format(art, reader, report, house=False):
    off = art.body_start - 1
    callouts = 0
    for i, line, code in lines_outside_code(art.body):
        if code:
            continue
        s = line.strip()
        m = None if house else re.match(r"^:::(\w+)", s)
        if m:
            callouts += 1
            if m.group(1) not in CALLOUTS:
                report.add("DOC-042", "error", i + off, "callouts are %s" % ", ".join(CALLOUTS), s)
        for m in re.finditer(r"!\[([^\]]*)\]\(([^)]*)\)", line):
            alt = m.group(1).strip().lower()
            if not alt or alt in ("image", "screenshot", "bild", "img", "picture", "foto"):
                report.add("DOC-035", "error", i + off, "image without alt text saying what it shows", m.group(0))
        for m in re.finditer(r"<img\b[^>]*>", line):
            if not re.search(r"\balt=\"[^\"]+\"", m.group(0)):
                report.add("DOC-035", "error", i + off, "image without alt text saying what it shows", m.group(0))
        for m in re.finditer(r"(?<!!)\[([^\]]+)\]\(([^)]*)\)", line):
            if plain(m.group(1)).strip().lower().rstrip(".") in BAD_LINK_TEXT:
                report.add("DOC-035", "error", i + off, "link text says where it goes, not \"%s\"" % m.group(1),
                           m.group(0))
        for m in re.finditer(r"</?([A-Z][A-Za-z]*)\b", line):
            if not house and m.group(1) not in PORTABLE_TAGS:
                report.add("DOC-046", "note", i + off, "component <%s> works only in a docs-tool repository "
                           "that has it" % m.group(1), m.group(0))
        if not house and re.match(r"^\s*import\s.+\sfrom\s", line):
            report.add("DOC-046", "note", i + off, "MDX import: only in a docs-tool repository", s)
    if callouts > 2:
        report.add("DOC-042", "note", 1 + off, "%d callouts; at most two" % callouts)
    for i, line, code in lines_outside_code(art.body):
        s = line.strip()
        if code or not s.startswith("|") or re.match(r"^\|[\s:|-]+\|?$", s):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if any(not c for c in cells):
            report.add("DOC-041", "error", i + off, "table cell is empty: every cell holds words", s)
        elif any(TABLE_GLYPHS.match(plain(c)) for c in cells):
            report.add("DOC-041", "error", i + off, "table cells hold words, not ✓, ✗, Y, N or dashes", s)
    if reader == "developer" and not house:
        for i, line, code in lines_outside_code(art.body):
            m = re.search(r"\bYOUR_[A-Z0-9_]+\b", line)
            if m:
                report.add("DOC-051", "note", i + off, "default placeholder form has no \"your\": %s"
                           % m.group(0)[5:], m.group(0))
                break
    blocks = code_blocks(art.body)
    if reader == "user" and blocks:
        report.add("DOC-045", "error", blocks[0][0] + off, "no code blocks for users; a value to type goes in "
                   "`inline code`")
    if reader == "developer":
        for line, info in blocks:
            if not info:
                report.add("DOC-051", "error", line + off, "code block without a language")
        for i, line, code in lines_outside_code(art.body):
            if code and re.match(r"^\s*\$ \S", line):
                report.add("DOC-051", "note", i + off, "no shell prompt in a block meant for copying", line.strip())


def check_exposure(art, report):
    off = art.body_start - 1
    for i, line in enumerate(art.body.split("\n"), 1):
        for pattern in SECRETS:
            for m in pattern.finditer(line):
                report.add("DOC-005", "error", i + off, "looks like a secret; use a placeholder", m.group(0)[:4] + "…")
        if SIGNED_QUERY.search(line):
            report.add("DOC-005", "error", i + off, "signed or token-bearing link", line.strip())
        for m in INTERNAL_HOST.finditer(line):
            report.add("DOC-005", "error", i + off, "internal host", m.group(0))
        m = PLACEHOLDERS.search(line)
        if m:
            report.add("DOC-004", "error", i + off, "placeholder: ask for the fact instead", m.group(0))


MD_LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
WIKI_LINK = re.compile(r"(!?)\[\[([^\]|#]+)(?:#([^\]|]*))?(?:\|([^\]]*))?\]\]")
SKIP_DIRS = {".git", "node_modules", ".docusaurus", "build", "dist", ".obsidian", "results", "__pycache__"}
_TITLES = {}


def docs_root(path):
    root = git(["rev-parse", "--show-toplevel"], cwd=Path(path).resolve().parent)
    return Path(root.strip()) if root else Path(path).resolve().parent


def titles(root):
    """{title or file stem, lowercased: path} for every article under root, for wiki links."""
    root = Path(root).resolve()
    if root in _TITLES:
        return _TITLES[root]
    found = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if not name.endswith((".md", ".mdx")):
                continue
            f = Path(dirpath) / name
            stem = re.sub(r"\.mdx?$", "", name)
            found.setdefault(stem.lower(), f)
            try:
                head = f.read_text(encoding="utf-8")[:2000]
            except (OSError, UnicodeDecodeError):
                continue
            title = split_frontmatter(head)[0].get("title")
            if title:
                found.setdefault(title.lower(), f)
    _TITLES[root] = found
    return found


def is_external(target):
    return bool(re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I)) or target.startswith(("/", "#"))


def internal_links(art):
    """Every link and image in the body that points into the repository, resolved locally."""
    out = []
    if not art.path:
        return out
    base = Path(art.path).resolve().parent
    root = None
    for i, line, code in lines_outside_code(art.body):
        if code:
            continue
        for m in MD_LINK.finditer(line):
            href = m.group(3)
            target, _, anchor = href.partition("#")
            if not target or is_external(target):
                continue
            f = (base / target)
            out.append({"line": i + art.body_start - 1, "form": "image" if m.group(1) else "path", "raw": href,
                        "target": target, "anchor": anchor, "text": m.group(2),
                        "file": str(f.resolve()) if f.exists() else None})
        for m in WIKI_LINK.finditer(line):
            root = root or docs_root(art.path)
            name = m.group(2).strip()
            f = titles(root).get(name.lower())
            out.append({"line": i + art.body_start - 1, "form": "image" if m.group(1) else "wiki", "raw": m.group(0),
                        "target": name, "anchor": m.group(3) or "", "text": m.group(4) or name,
                        "file": str(f) if f else None})
    for link in out:
        if link["file"] and link["file"].endswith((".md", ".mdx")):
            try:
                meta = split_frontmatter(Path(link["file"]).read_text(encoding="utf-8"))[0]
            except (OSError, UnicodeDecodeError):
                meta = {}
            link["title"] = meta.get("title") or re.sub(r"\.mdx?$", "", Path(link["file"]).name)
            link["ids"] = {k: v for k, v in meta.items() if k not in FRONTMATTER_KEYS and not k.startswith(
                ("sidebar", "slug", "id", "tags", "keywords", "hide", "pagination", "custom", "displayed"))}
    return out


def check_links(art, report):
    """Links to other articles and images in the repository must resolve (DOC-043, DOC-044)."""
    for link in internal_links(art):
        if link["file"] is None:
            rule = "DOC-043" if link["form"] == "image" else "DOC-044"
            report.add(rule, "error", link["line"], "link target not found", link["target"])


def check_translation(art, report):
    """A translation whose source changed after `source_commit` may be stale (DOC-073)."""
    source, commit = art.meta.get("source"), art.meta.get("source_commit")
    if not (art.path and source and commit):
        return
    src = (Path(art.path).parent / source)
    if not src.exists():
        report.add("DOC-073", "error", 1, "source file not found", source)
        return
    out = git(["log", "--format=%h", "%s..HEAD" % commit, "--", src.name], cwd=src.parent)
    if out is None:
        return
    changed = [l for l in out.splitlines() if l.strip()]
    if changed:
        report.add("DOC-073", "note", 1, "the source changed in %d commit(s) since this translation (%s); "
                   "check whether it changed in meaning" % (len(changed), ", ".join(changed[:5])))


def check_collection(art, report):
    """A collection's index.md (DOC-060): title, description and order, no article shape."""
    for key in ("title", "description"):
        if not art.meta.get(key):
            report.add("DOC-060", "error", 1, "a collection's index.md needs `%s`" % key)
    description = art.meta.get("description", "")
    if len(description) > DESCRIPTION_MAX:
        report.add("DOC-011", "error", 1, "description has %d characters, at most %d"
                   % (len(description), DESCRIPTION_MAX), description)


def is_collection_index(art):
    return bool(art.path) and Path(art.path).name in ("index.md", "index.mdx") and not art.meta.get("type")


def check(text, path=None, lang=None, house=False, reader=None, kind=None):
    """Findings for one article. house=True: a house style replaces the default rules; only the universal
    ones are checked, with reader and type from the arguments or the frontmatter when it has them."""
    art = Article(text, path)
    report = Report()
    if not house and is_collection_index(art):
        check_collection(art, report)
        return {"file": path or "-", "reader": None, "type": "collection", "lang": art.lang(lang),
                "findings": report.findings, "ok": not report.errors()}
    language = art.lang(lang)
    if house:
        reader = reader or (art.meta.get("reader") if art.meta.get("reader") in READERS else None)
        kind = kind or art.meta.get("type")
        check_procedures(art, reader, report)
    else:
        reader, kind = check_frontmatter(art, report)
        check_title(art, kind, language, report)
        check_intro(art, reader, report)
        check_headings(art, reader, kind, language, report)
        check_steps(art, reader, kind, language, report)
        check_faq(art, reader, kind, language, report)
    check_writing(art, reader, kind, language, report)
    check_format(art, reader, report, house)
    check_exposure(art, report)
    check_links(art, report)
    check_translation(art, report)
    report.findings.sort(key=lambda f: (f["severity"] != "error", f["line"]))
    return {"file": path or "-", "reader": reader, "type": kind, "lang": language, "house_style": house,
            "findings": report.findings, "ok": not report.errors()}


# --- git ------------------------------------------------------------------------------------------------


def git(args, cwd=None):
    try:
        res = subprocess.run(["git"] + args, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                             timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return res.stdout if res.returncode == 0 else None


def repo_path(path):
    """(repository root, path relative to it) or (None, None)."""
    p = Path(path).resolve()
    root = git(["rev-parse", "--show-toplevel"], cwd=p.parent)
    if not root:
        return None, None
    root = Path(root.strip()).resolve()
    return root, p.relative_to(root).as_posix()


TRAILER = re.compile(r"^Docs-(Published|Pulled):[ \t]*(\S+)[ \t]+(.+?)[ \t]*$", re.M)  # paths may hold spaces


def history(path):
    """Every commit that touched the article or recorded it as live, newest first."""
    root, rel = repo_path(path)
    if root is None:
        raise SystemExit("docs: %s is not in a git repository" % path)
    sep = "\x1e"
    touched = git(["log", "--follow", "--format=%H", "--", rel], cwd=root) or ""
    touched = set(touched.split())
    out = git(["log", "--format=%H%x1f%h%x1f%aI%x1f%an%x1f%s%x1f%B" + sep, "--grep", rel, "--fixed-strings",
               "HEAD"], cwd=root) or ""
    logged = git(["log", "--follow", "--format=%H%x1f%h%x1f%aI%x1f%an%x1f%s%x1f%B" + sep, "--", rel], cwd=root) or ""
    entries = {}
    for chunk in (logged + out).split(sep):
        parts = chunk.strip("\n").split("\x1f")
        if len(parts) < 6:
            continue
        full, short, date, author, subject, body = parts
        live = [{"event": m.group(1).lower(), "target": m.group(2)} for m in TRAILER.finditer(body)
                if m.group(3) == rel]
        if full not in touched and not live:
            continue
        entries[full] = {"commit": short, "full": full, "date": date, "author": author, "subject": subject,
                         "changed": full in touched, "live": live}
    order = (git(["log", "--format=%H", "HEAD"], cwd=root) or "").split()
    rank = {h: i for i, h in enumerate(order)}
    result = sorted(entries.values(), key=lambda e: rank.get(e["full"], 1 << 30))
    dirty = bool((git(["status", "--porcelain", "--", rel], cwd=root) or "").strip())
    return {"file": rel, "uncommitted": dirty, "versions": result}


def last_live(versions, target=None):
    for v in versions:
        for event in v["live"]:
            if target in (None, event["target"]):
                return v
    return None


# --- render ---------------------------------------------------------------------------------------------

CALLOUT_LABEL = {"en": {"note": "Note", "tip": "Tip", "info": "Info", "warning": "Warning", "danger": "Danger"},
                 "de": {"note": "Hinweis", "tip": "Tipp", "info": "Info", "warning": "Achtung", "danger": "Gefahr"}}


def render_body(text, target, lang):
    """The body as it goes to a target: no frontmatter; callouts as blockquotes unless the target is a
    docs tool that has them."""
    _, _, body, _ = split_frontmatter(text.replace("\r\n", "\n"))
    if target in ("docusaurus", "markdown"):
        return body.strip() + "\n"
    out, kind = [], None
    for _, line, code in lines_outside_code(body):
        s = line.strip()
        if not code and kind is None and re.match(r"^:::(\w+)", s):
            kind = re.match(r"^:::(\w+)", s).group(1)
            label = CALLOUT_LABEL.get(lang, CALLOUT_LABEL["en"]).get(kind, kind.title())
            title = s[3 + len(kind):].strip()
            out.append("> **%s:**%s" % (label, " " + title if title else ""))
            continue
        if not code and kind is not None:
            if s == ":::":
                kind = None
                continue
            out.append("> " + line if s else ">")
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def rewrite_links(body, art, links=None, assets=None):
    """Links to other articles become their address at the target, from `links`: a map from the link as
    written (a relative path, or a wiki link's title) to a URL or {"url": …, "title": …}. The push skill
    fills it by looking each article up at the target (DOC-047). Images become their URL in `assets`.
    Returns (body, unresolved)."""
    links, assets = links or {}, assets or {}
    unresolved = []

    def lookup(key):
        value = links.get(key) or links.get(os.path.normpath(key)) if key else None
        if isinstance(value, str):
            return value, None
        if isinstance(value, dict) and value.get("url"):
            return value["url"], value.get("title")
        return None, None

    def md(m):
        image, text, href = m.group(1), m.group(2), m.group(3)
        target, _, anchor = href.partition("#")
        if not target or is_external(target):
            return m.group(0)
        if image:
            url = assets.get(target) or assets.get(os.path.normpath(target))
            if not url:
                unresolved.append(target)
            return "![%s](%s)" % (text, url or href)
        url, title = lookup(target)
        if not url:
            unresolved.append(target)
            return m.group(0)
        return "[%s](%s%s)" % (title or text, url, "#" + anchor if anchor else "")

    def wiki(m):
        if m.group(1):
            url = assets.get(m.group(2).strip())
            if not url:
                unresolved.append(m.group(2).strip())
                return m.group(0)
            return "![%s](%s)" % (m.group(4) or m.group(2).strip(), url)
        name = m.group(2).strip()
        url, title = lookup(name)
        if not url:
            unresolved.append(name)
            return m.group(0)
        anchor = m.group(3)
        return "[%s](%s%s)" % (m.group(4) or title or name, url, "#" + anchor if anchor else "")

    out = []
    for _, line, code in lines_outside_code(body):
        out.append(line if code else WIKI_LINK.sub(wiki, MD_LINK.sub(md, line)))
    return "\n".join(out), unresolved


def normal(text):
    return re.sub(r"\s+", " ", text.replace("\\n", "\n")).strip()


def stamp_dir():
    base = os.environ.get("DOCS_STAMP_DIR") or os.path.join(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "docs-plugin", "rendered")
    return Path(base)


def stamp(body, info):
    """Remember that this body was rendered from a committed, checked article, for the publish hook."""
    digest = hashlib.sha256(normal(body).encode("utf-8")).hexdigest()
    try:
        d = stamp_dir()
        d.mkdir(parents=True, exist_ok=True)
        (d / digest).write_text(json.dumps(info), encoding="utf-8")
        cutoff = time.time() - 7 * 86400
        for old in d.iterdir():
            if old.stat().st_mtime < cutoff:
                old.unlink()
    except OSError:
        pass
    return digest


def render(path, target, at=None, draft=False, links=None, assets=None, house=False):
    """(body, info) or raises SystemExit with the reason. Warnings go to stderr."""
    root, rel = repo_path(path)
    if root is None:
        raise SystemExit("docs: not rendered. %s is not in a git repository; commit it first (DOC-072)" % path)
    rev = at or "HEAD"
    if at is None and (git(["status", "--porcelain", "--", rel], cwd=root) or "").strip():
        raise SystemExit("docs: not rendered. %s has uncommitted changes; commit them first (DOC-072)" % rel)
    text = git(["show", "%s:%s" % (rev, rel)], cwd=root)
    if text is None:
        raise SystemExit("docs: not rendered. %s does not exist at %s" % (rel, rev))
    commit = (git(["rev-parse", "--short", rev], cwd=root) or rev).strip()
    result = check(text, str(root / rel), house=house)
    if at is None and not result["ok"]:
        raise SystemExit("docs: not rendered. %s has %d check error(s); run `docs check %s` (DOC-072)"
                         % (rel, len([f for f in result["findings"] if f["severity"] == "error"]), rel))
    art = Article(text, str(root / rel))
    if at is None and art.meta.get("status") == "draft" and not draft:
        raise SystemExit("docs: not rendered. %s has status: draft; set it to ready, commit, then render, or "
                         "pass --draft to publish as a draft at the target" % rel)
    body = render_body(text, target, art.lang())
    if target not in ("docusaurus", "markdown"):
        body, unresolved = rewrite_links(body, art, links, assets)
        if unresolved and at is None:
            raise SystemExit("docs: not rendered. Links or images without an address at %s: %s. Look each "
                             "article up at the target and pass them with --links, upload the images and pass "
                             "--assets (DOC-047)" % (target, ", ".join(sorted(set(unresolved)))))
    info = {"file": rel, "commit": commit, "target": target, "at": at is not None, "time": int(time.time())}
    if at is None:
        stamp(body, info)
    return body, info


def stale(folder, months=12):
    """Articles under folder whose file has not changed in `months` months, oldest first (DOC-074)."""
    root = docs_root(Path(folder) / "x")
    cutoff = time.time() - months * 30.44 * 86400
    found = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if not name.endswith((".md", ".mdx")) or name in ("README.md", "CHANGELOG.md"):
                continue
            f = Path(dirpath) / name
            out = git(["log", "-1", "--format=%ct", "--", str(f.resolve())], cwd=root)
            if not out or not out.strip():
                continue
            when = int(out.strip())
            if when < cutoff:
                found.append({"file": os.path.relpath(f, folder), "last_change": time.strftime("%Y-%m-%d",
                              time.gmtime(when))})
    return sorted(found, key=lambda e: e["last_change"])


# --- diff -----------------------------------------------------------------------------------------------


def normalise(text):
    """Remove differences that are only formatting, so a body read back from a target compares to ours:
    frontmatter, trailing spaces, list markers, emphasis markers, blank-line runs, heading closers."""
    _, _, body, _ = split_frontmatter(text.replace("\r\n", "\n"))
    out = []
    for _, line, code in lines_outside_code(body):
        if code:
            out.append(line.rstrip())
            continue
        s = line.rstrip()
        s = re.sub(r"^(\s*)[*+](\s+)", r"\1-\2", s)
        s = re.sub(r"^(\s*)(\d+)\)(\s+)", r"\1\2.\3", s)
        s = re.sub(r"__(.+?)__", r"**\1**", s)
        s = re.sub(r"(?<![*\w])_(?!_)(.+?)(?<!_)_(?![*\w])", r"*\1*", s)
        s = re.sub(r"^(#{1,6}\s.*?)\s+#+$", r"\1", s)
        s = re.sub(r"[ \t]+", " ", s) if not s.startswith("    ") else s
        out.append(s)
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def diff(old_text, new_text, old_name="old", new_name="new"):
    a, b = normalise(old_text).splitlines(), normalise(new_text).splitlines()
    lines = list(difflib.unified_diff(a, b, old_name, new_name, lineterm="", n=2))
    added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
    old_h = [t for _, lvl, t in headings(normalise(old_text)) if lvl >= 2]
    new_h = [t for _, lvl, t in headings(normalise(new_text)) if lvl >= 2]
    return {"same": not lines, "added": added, "removed": removed,
            "sections_added": [h for h in new_h if h not in old_h],
            "sections_removed": [h for h in old_h if h not in new_h], "diff": "\n".join(lines)}


# --- command line ---------------------------------------------------------------------------------------


def read_input(name):
    if name == "-":
        return sys.stdin.read(), None
    p = Path(name)
    try:
        return p.read_text(encoding="utf-8"), str(p)
    except (OSError, UnicodeDecodeError) as e:
        raise SystemExit("docs: cannot read %s: %s" % (name, e))


def print_check(result):
    head = "%s · %s %s · %s" % (result["file"], result["reader"] or "?", result["type"] or "?", result["lang"])
    print(head)
    if not result["findings"]:
        print("  ok")
    for f in result["findings"]:
        quote = ' "%s"' % f["quote"] if f["quote"] else ""
        print("  %s %s line %d: %s%s" % (f["severity"], f["id"], f["line"], f["message"], quote))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="docs", description="The Docs Convention, checked.")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("check", help="check articles against the convention")
    p.add_argument("--json", action="store_true")
    p.add_argument("--lang")
    p.add_argument("--house-style", action="store_true", help="the project has a house style: check only the "
                   "universal rules")
    p.add_argument("--reader", choices=READERS)
    p.add_argument("--type")
    p.add_argument("files", nargs="+")
    p = sub.add_parser("links", help="links to other articles and images, resolved in the repository")
    p.add_argument("--json", action="store_true")
    p.add_argument("file")
    p = sub.add_parser("history", help="versions of an article and which went live")
    p.add_argument("--json", action="store_true")
    p.add_argument("file")
    p = sub.add_parser("render", help="the body to publish, from a committed version")
    p.add_argument("--target", default="plain", help="productlane, docusaurus, markdown, plain (default)")
    p.add_argument("--at", help="a past commit: render that version (for comparing, not publishing)")
    p.add_argument("--draft", action="store_true", help="allow status: draft")
    p.add_argument("--out", help="write the body to this file instead of stdout")
    p.add_argument("--links", help="JSON file mapping each link as written (path or wiki title) to its URL "
                   "at the target, or to {\"url\": …, \"title\": …}")
    p.add_argument("--assets", help="JSON file mapping relative image paths to their uploaded URLs")
    p.add_argument("--house-style", action="store_true")
    p.add_argument("file")
    p = sub.add_parser("stale", help="articles not changed for a number of months")
    p.add_argument("--json", action="store_true")
    p.add_argument("--months", type=int, default=12)
    p.add_argument("folder")
    p = sub.add_parser("diff", help="two versions, normalised")
    p.add_argument("--json", action="store_true")
    p.add_argument("old")
    p.add_argument("new")
    args = parser.parse_args(argv)

    if args.cmd == "check":
        results = []
        for name in args.files:
            text, path = read_input(name)
            results.append(check(text, path, args.lang, args.house_style, args.reader, args.type))
        if args.json:
            print(json.dumps(results if len(results) > 1 else results[0], indent=2, ensure_ascii=False))
        else:
            for r in results:
                print_check(r)
        return 0 if all(r["ok"] for r in results) else 1
    if args.cmd == "links":
        text, path = read_input(args.file)
        found = internal_links(Article(text, path))
        if args.json:
            print(json.dumps(found, indent=2, ensure_ascii=False))
        else:
            for link in found:
                where = link["file"] or "NOT FOUND"
                ids = ", ".join("%s %s" % kv for kv in (link.get("ids") or {}).items())
                print("line %d %s %s → %s%s" % (link["line"], link["form"], link["target"], where,
                                                 "  [%s]" % ids if ids else ""))
        return 0 if all(link["file"] for link in found) else 1
    if args.cmd == "stale":
        found = stale(args.folder, args.months)
        if args.json:
            print(json.dumps(found, indent=2, ensure_ascii=False))
        else:
            print("%d article(s) unchanged for %d months or more" % (len(found), args.months))
            for e in found:
                print("  %s  %s" % (e["last_change"], e["file"]))
        return 0
    if args.cmd == "history":
        h = history(args.file)
        if args.json:
            print(json.dumps(h, indent=2, ensure_ascii=False))
        else:
            print(h["file"] + ("  (uncommitted changes)" if h["uncommitted"] else ""))
            for v in h["versions"]:
                live = ", ".join("%s %s" % (e["event"], e["target"]) for e in v["live"])
                print("  %s %s %-12s %s%s" % (v["commit"], v["date"][:10], v["author"][:12], v["subject"],
                                              "  [%s]" % live if live else ""))
        return 0
    if args.cmd == "render":
        try:
            assets = json.loads(Path(args.assets).read_text(encoding="utf-8")) if args.assets else None
            links = json.loads(Path(args.links).read_text(encoding="utf-8")) if args.links else None
            body, info = render(args.file, args.target, args.at, args.draft, links, assets, args.house_style)
        except (OSError, ValueError) as e:
            print("docs: cannot read a map: %s" % e, file=sys.stderr)
            return 2
        except SystemExit as e:
            print(e, file=sys.stderr)
            return 1
        if args.out:
            Path(args.out).write_text(body, encoding="utf-8")
            print("docs: rendered %s at %s for %s → %s" % (info["file"], info["commit"], info["target"], args.out),
                  file=sys.stderr)
        else:
            sys.stdout.write(body)
        return 0
    if args.cmd == "diff":
        old, _ = read_input(args.old)
        new, _ = read_input(args.new)
        d = diff(old, new, args.old, args.new)
        if args.json:
            print(json.dumps(d, indent=2, ensure_ascii=False))
        else:
            if d["same"]:
                print("same (after normalising formatting)")
            else:
                print("+%d -%d lines" % (d["added"], d["removed"]))
                for h in d["sections_added"]:
                    print("  section added: " + h)
                for h in d["sections_removed"]:
                    print("  section removed: " + h)
                print(d["diff"])
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
