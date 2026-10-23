#!/usr/bin/env python3
"""tone check: the deterministic half of a tone review.

Reads a draft, a profile and an audience, and reports what a machine can decide: lengths,
formatting, banned phrases, secrets, personal data, technical internals in external text and mixed
forms of address. It never rewrites and never uses the network. Python 3.9+, standard library only.
"""

import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "skills" / "write" / "references"
PROFILES = REFS / "profiles"

# Findings are reported in this order: exposure first, then facts, language, length, style.
ORDER = ["TONE-010", "TONE-011", "TONE-014", "TONE-021", "TONE-020", "TONE-022", "TONE-001",
         "TONE-051", "TONE-060", "TONE-061", "TONE-062", "TONE-063", "TONE-064", "TONE-065",
         "TONE-066", "TONE-067", "TONE-068", "TONE-041", "TONE-042", "TONE-043"]

INTERNAL_SUFFIXES = (".local", ".internal", ".lan", ".corp", ".intranet", ".localhost")


# --- profile files -------------------------------------------------------------------------------

def _scalar(raw):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [_scalar(part) for part in inner.split(",")] if inner else []
    return raw


def parse_frontmatter(text):
    """A small YAML subset: `key: scalar`, `key: [a, b]`, and `key:` followed by `  - item` lines."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("frontmatter is not closed")
    data, key = {}, None
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"\s+-\s+(.*)$", line)
        if item and key is not None:
            data[key].append(_scalar(item.group(1)))
            continue
        pair = re.match(r"([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not pair:
            raise ValueError("unreadable frontmatter line: " + line)
        key, value = pair.group(1), pair.group(2)
        data[key] = _scalar(value) if value.strip() else []
    return data, text[end + 4:].lstrip("\n")


def load(name):
    path = PROFILES / (name + ".md")
    if not path.is_file():
        raise FileNotFoundError(name)
    profile, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    base, _ = parse_frontmatter((REFS / "base.md").read_text(encoding="utf-8"))
    return profile, base


def profile_names():
    return sorted(p.stem for p in PROFILES.glob("*.md"))


# --- text helpers --------------------------------------------------------------------------------

URL = re.compile(r"https?://[^\s<>()\[\]`\"']+")
FENCE = re.compile(r"^```.*?^```[ \t]*$", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]+`")

DE_WORDS = {"der", "die", "das", "und", "ist", "nicht", "mit", "für", "auf", "ein", "eine", "wird",
            "werden", "im", "den", "dem", "zu", "von", "sich", "auch", "es", "wir", "ich", "noch",
            "jetzt", "bei", "nach", "wurde", "sind", "kein", "keine"}
EN_WORDS = {"the", "and", "is", "not", "with", "for", "on", "a", "an", "will", "be", "to", "of",
            "it", "we", "this", "that", "are", "now", "was", "were", "no", "after", "when"}


def detect_language(text):
    words = re.findall(r"[a-zA-ZäöüÄÖÜß]+", text.lower())
    de = sum(w in DE_WORDS for w in words)
    en = sum(w in EN_WORDS for w in words)
    return "de" if de > en else "en"


def phrase_pattern(phrase):
    parts = [re.escape(p.strip()) for p in phrase.split("…")]
    body = r".{0,60}?".join(parts)
    if body.endswith(r"\*"):
        body = body[:-2] + r"\w*"
        tail = ""
    else:
        tail = r"(?!\w)"
    return re.compile(r"(?<!\w)" + body + tail, re.I)


def mask(secret):
    return secret[:4] + "…"


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


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
        out = []
        for f in sorted(self.items, key=key):
            f = dict(f)
            del f["_pos"]
            out.append(f)
        return out


# --- checks --------------------------------------------------------------------------------------

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
            report.add("TONE-010", "error", "line %d" % line_of(text, m.start()),
                       "looks like a secret; remove it entirely", mask(m.group(0)), m.start())
    for m in URL.finditer(text):
        if SIGNED_QUERY.search(m.group(0)):
            report.add("TONE-010", "error", "line %d" % line_of(text, m.start()),
                       "signed or token-bearing URL; remove it", mask(m.group(0)), m.start())


def check_personal(text, audience, report):
    severity = "error" if audience == "external" else "note"
    for m in EMAIL.finditer(text):
        report.add("TONE-011", severity, "line %d" % line_of(text, m.start()),
                   "email address; name the person by role unless the reader needs it",
                   m.group(0), m.start())
    for m in PHONE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 8 <= len(digits) <= 15:
            report.add("TONE-011", severity, "line %d" % line_of(text, m.start()),
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
            report.add("TONE-021", "error", where, "link to an internal host", url, m.start())
        else:
            report.add("TONE-022", "note", where,
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
    """Technical internals in external text (TONE-020) and internal hosts named without a URL."""
    def add(m, what, text=raw):
        report.add("TONE-020", "error", "line %d" % line_of(text, m.start()),
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
        report.add("TONE-021", "error", "line %d" % line_of(text, m.start()),
                   "internal host name", m.group(0), m.start())


def check_phrases(prose, base, profile, report):
    groups = [("TONE-001", "note", "guess", "hedge or guess; state only what is known"),
              ("TONE-041", "error", "filler", "filler; cut it"),
              ("TONE-042", "error", "tells", "reads as AI-written; rephrase plainly")]
    for rule, severity, name, message in groups:
        # Both languages' lists: a short draft is easy to misdetect, and a German filler word in
        # English text (or the reverse) is a finding either way.
        phrases = [p for code in ("de", "en")
                   for p in list(base.get(name + "_" + code, [])) + list(profile.get(name + "_" + code, []))]
        for phrase in phrases:
            for m in phrase_pattern(phrase).finditer(prose):
                report.add(rule, severity, "line %d" % line_of(prose, m.start()), message,
                           m.group(0), m.start())
    for phrase in base.get("made_by", []):
        for m in phrase_pattern(phrase).finditer(prose):
            report.add("TONE-014", "error", "line %d" % line_of(prose, m.start()),
                       "mentions how the text or work was made", m.group(0), m.start())
    for m in re.finditer(r"—|\s–\s|\s--\s", prose):
        report.add("TONE-042", "error", "line %d" % line_of(prose, m.start()),
                   "long dash; use a comma, colon, period or parentheses", m.group(0).strip(),
                   m.start())
    for m in re.finditer("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]", prose):
        report.add("TONE-042", "error", "line %d" % line_of(prose, m.start()), "emoji",
                   m.group(0), m.start())


INFORMAL = re.compile(r"(?<!\w)(?:du|dich|dir|dein\w*|euch|euer|eure\w*)(?!\w)", re.I)
FORMAL = re.compile(r"(?<!\w)(?:Sie|Ihnen|Ihr|Ihre\w*)(?!\w)")


def check_address(prose, report):
    informal = INFORMAL.search(prose)
    formal = None
    for m in FORMAL.finditer(prose):
        before = prose[:m.start()].rstrip()
        if not before or before[-1] in ".!?:\n-*" or re.search(r"(?:^|\n)\s*(?:[-*+]|\d+\.)$", before):
            continue  # sentence start: could be "sie" or "ihr"
        formal = m
        break
    if informal and formal:
        report.add("TONE-051", "error", "line %d" % line_of(prose, formal.start()),
                   "mixes du and Sie; use one form throughout",
                   "%s … %s" % (informal.group(0), formal.group(0)), formal.start())


def strip_code(text):
    return INLINE_CODE.sub(" ", FENCE.sub(" ", text))


def words(text):
    return re.findall(r"[\w'’-]+", text)


def is_checklist(line):
    return bool(re.match(r"\s*[-*+]\s+\[[ xX]\]", line))


def is_bullet(line):
    return bool(re.match(r"\s*(?:[-*+]|\d+[.)])\s+", line))


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


def check_shape(title, body, profile, report):
    if "title_max_chars" in profile:
        if title is None:
            report.add("TONE-060", "note", "title", "no `# ` title line; title not checked")
        else:
            if len(title) > profile["title_max_chars"]:
                report.add("TONE-060", "error", "title", "title is %d characters, limit %d"
                           % (len(title), profile["title_max_chars"]), title)
            m = TYPE_PREFIX.match(title)
            if m:
                report.add("TONE-061", "error", "title", "type prefix; labels carry the type",
                           m.group(0).strip())
            if title.rstrip().endswith("."):
                report.add("TONE-062", "error", "title", "trailing period", title[-20:])

    lines = body.splitlines()
    if "body_max_words" in profile:
        counted = [l for l in lines if not is_checklist(l) and not re.match(r"\s*#{1,6}\s", l)]
        n = len(words(strip_code("\n".join(counted))))
        if n > profile["body_max_words"]:
            report.add("TONE-063", "error", "body", "%d words, limit %d"
                       % (n, profile["body_max_words"]))
    if "max_sentences" in profile:
        prose = " ".join(l for l in lines if l.strip() and not is_bullet(l))
        n = count_sentences(strip_code(prose))
        if n > profile["max_sentences"]:
            report.add("TONE-064", "error", "body", "%d sentences, limit %d"
                       % (n, profile["max_sentences"]))
    if "max_bullets" in profile:
        n = sum(is_bullet(l) for l in lines)
        if n > profile["max_bullets"]:
            report.add("TONE-065", "error", "body", "%d bullets, limit %d" % (n, profile["max_bullets"]))
    if profile.get("single_line"):
        n = len([l for l in lines if l.strip()])
        if n > 1:
            report.add("TONE-066", "error", "body", "%d lines, must be one" % n)
    if "max_chars" in profile:
        n = len(body.strip())
        if n > profile["max_chars"]:
            report.add("TONE-067", "error", "body", "%d characters, limit %d" % (n, profile["max_chars"]))
    if profile.get("no_issue_ids"):
        for m in ISSUE_ID.finditer(body):
            report.add("TONE-068", "error", "body", "issue ID; customers cannot open it",
                       m.group(0), m.start())

    allowed = profile.get("heading_levels", [])
    for i, line in enumerate(lines, 1):
        m = re.match(r"\s*(#{1,6})\s", line)
        if m and len(m.group(1)) not in allowed:
            report.add("TONE-043", "error", "line %d" % i,
                       "heading level %d not allowed here" % len(m.group(1)), line.strip()[:60])
    if profile.get("tables") is False:
        for i, line in enumerate(lines, 1):
            if re.match(r"\s*\|.*\|", line):
                report.add("TONE-043", "error", "line %d" % i, "table not allowed here")
                break
    if "bold_max" in profile:
        prose = "\n".join(l for l in lines if not re.match(r"\s*#{1,6}\s", l))
        bold = re.findall(r"\*\*[^*\n]+\*\*|__[^_\n]+__", strip_code(prose))
        if len(bold) > profile["bold_max"]:
            report.add("TONE-043", "error", "body", "%d bold spans, limit %d"
                       % (len(bold), profile["bold_max"]), bold[0])


def split_title(draft, profile):
    if "title_max_chars" not in profile:
        return None, draft
    lines = draft.splitlines()
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = re.match(r"#\s+(.*)$", line)
        if m:
            return m.group(1).strip(), "\n".join(lines[i + 1:])
        break
    return None, draft


def check(draft, profile_name, audience=None, lang=None):
    profile, base = load(profile_name)
    audience = profile.get("audience_fixed") or audience or profile.get("audience_default", "external")
    lang = lang or detect_language(strip_code(URL.sub(" ", draft)))
    report = Report()

    title, body = split_title(draft, profile)
    prose = strip_code(draft)
    prose_no_urls = URL.sub(lambda m: " " * len(m.group(0)), prose)

    check_secrets(draft, report)
    check_personal(prose_no_urls, audience, report)
    if audience == "external":
        check_urls(prose, report)
        check_internals(draft, prose_no_urls, report)
    check_phrases(prose_no_urls, base, profile, report)
    if lang == "de":
        check_address(prose_no_urls, report)
    check_shape(title, body, profile, report)
    return {"profile": profile_name, "audience": audience, "language": lang,
            "findings": report.sorted()}


# --- CLI -----------------------------------------------------------------------------------------

def render(result):
    out = []
    for f in result["findings"]:
        line = "%-5s %s %s: %s" % (f["severity"], f["id"], f["where"], f["message"])
        if f["quote"]:
            line += ' · "%s"' % f["quote"]
        out.append(line)
    errors = sum(f["severity"] == "error" for f in result["findings"])
    notes = len(result["findings"]) - errors
    head = "%s, %s, %s" % (result["profile"], result["audience"], result["language"])
    if not result["findings"]:
        out.append("clean (%s)" % head)
    else:
        out.append("%d error%s, %d note%s (%s)" % (errors, "" if errors == 1 else "s",
                                                   notes, "" if notes == 1 else "s", head))
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tone", description="Deterministic checks of text for other people.")
    sub = parser.add_subparsers(dest="command")
    c = sub.add_parser("check", help="check a draft against a profile")
    c.add_argument("--profile", required=True)
    c.add_argument("--audience", choices=["internal", "external"])
    c.add_argument("--lang", choices=["de", "en"])
    c.add_argument("--json", action="store_true")
    c.add_argument("file", help="the draft, or - for stdin")
    sub.add_parser("profiles", help="list the profiles")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0

    if args.command == "profiles":
        print("\n".join(profile_names()))
        return 0
    if args.command != "check":
        parser.print_usage(sys.stderr)
        return 2
    if args.profile not in profile_names():
        print("tone: unknown profile %r (have: %s)" % (args.profile, ", ".join(profile_names())),
              file=sys.stderr)
        return 2
    try:
        draft = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    except OSError as e:
        print("tone: cannot read %s: %s" % (args.file, e.strerror), file=sys.stderr)
        return 2
    result = check(draft, args.profile, args.audience, args.lang)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    return 1 if any(f["severity"] == "error" for f in result["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
