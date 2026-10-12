"""atlas: a personal brain of markdown notes. Standard library only, Python 3.9+.

The files are the truth. Every command scans them; nothing is cached.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

STATUSES = ("active", "superseded", "archived")
REQUIRED = ("id", "type", "description", "status", "created")
DATE_FIELDS = ("created", "verified", "valid_from", "valid_to")
FOLDERS = ("notes", "inbox", "archive")
ILLEGAL_IN_TITLE = '*"\\/<>:|?#^[]'

DEFAULT_CATALOG = {
    "version": 1,
    "inbox_max_age_days": 14,
    "git_autocommit": True,
    "types": {
        "note": {"about": "A concept, fact or lesson", "fields": {}, "required": [], "verify_after_days": 365},
        "person": {
            "about": "Someone you deal with",
            "fields": {"org": "link", "role": "text"},
            "required": [],
            "verify_after_days": 180,
        },
        "organisation": {"about": "A company, team or vendor", "fields": {}, "required": [], "verify_after_days": 365},
        "decision": {
            "about": "Something decided, with the reason",
            "fields": {"decided": "date"},
            "required": ["decided"],
            "verify_after_days": None,
        },
        "source": {
            "about": "An article, document or thread",
            "fields": {"url": "text", "author": "text"},
            "required": [],
            "verify_after_days": None,
        },
        "hub": {"about": "An entry point that links a topic's notes", "fields": {}, "required": [], "verify_after_days": None},
    },
}


class AtlasError(Exception):
    """A problem the user can act on; printed without a traceback."""


def today() -> dt.date:
    fixed = os.environ.get("ATLAS_TODAY")
    return dt.date.fromisoformat(fixed) if fixed else dt.date.today()


def parse_date(text: object) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(text))
    except ValueError:
        return None


# ── frontmatter: a flat subset of YAML ──────────────────────────────────────

KEY_LINE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")
LIST_ITEM = re.compile(r"^\s*-\s+(.*)$")
PLAIN_SCALAR = re.compile(r"^[A-Za-z0-9_./(][^#\n]*$")
RESERVED_SCALARS = {"true", "false", "null", "yes", "no", "on", "off", "~"}


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(raw) >= 2 and raw[0] == raw[-1] == "'":
        return raw[1:-1].replace("''", "'")
    return raw


def _split_inline_list(raw: str) -> list[str]:
    items, current, quote = [], "", ""
    for char in raw:
        if quote:
            current += char
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            current += char
        elif char == ",":
            items.append(current)
            current = ""
        else:
            current += char
    items.append(current)
    return [_unquote(item) for item in items if item.strip()]


def split_note(text: str) -> tuple[str | None, str]:
    """Returns the frontmatter block (None when there is none) and the body."""
    if not text.startswith("---"):
        return None, text
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return None, text


def parse_frontmatter(block: str) -> tuple[dict, list[str]]:
    """Parses `key: value` and list fields. Returns the fields and the lines it could not read."""
    fields: dict = {}
    unreadable: list[str] = []
    open_key: str | None = None
    for line in block.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = LIST_ITEM.match(line)
        if item and open_key is not None:
            if not isinstance(fields[open_key], list):
                fields[open_key] = []
            fields[open_key].append(_unquote(item.group(1)))
            continue
        key = KEY_LINE.match(line)
        if not key:
            unreadable.append(line)
            continue
        name, raw = key.group(1), key.group(2).strip()
        if raw == "":
            fields[name] = ""
            open_key = name
        elif raw.startswith("[") and raw.endswith("]") and not raw.startswith("[["):
            fields[name] = _split_inline_list(raw[1:-1])
            open_key = None
        else:
            fields[name] = _unquote(raw)
            open_key = None
    return fields, unreadable


def _scalar(value: object) -> str:
    text = str(value)
    plain = (
        PLAIN_SCALAR.match(text)
        and ": " not in text
        and not text.endswith(":")
        and text == text.strip()
        and text.lower() not in RESERVED_SCALARS
    )
    if plain:
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump_frontmatter(fields: dict) -> str:
    lines = []
    for key, value in fields.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {_scalar(item)}" for item in value)
        elif value == "" or value is None:
            lines.append(f"{key}:")
        else:
            lines.append(f"{key}: {_scalar(value)}")
    return "\n".join(lines)


# ── links ───────────────────────────────────────────────────────────────────

WIKILINK = re.compile(r"(!?\[\[)([^\]|#^]*)([#^][^\]|]*)?(\|[^\]]*)?(\]\])")
FENCED = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
INLINE_CODE = re.compile(r"`[^`\n]*`")


def link_targets(text: str) -> list[str]:
    """Link targets in order of appearance, without duplicates; code is skipped."""
    text = INLINE_CODE.sub("", FENCED.sub("", text))
    seen: dict[str, None] = {}
    for match in WIKILINK.finditer(text):
        target = match.group(2).strip()
        if target:
            seen.setdefault(target, None)
    return list(seen)


def retarget_links(text: str, old: str, new: str) -> str:
    def swap(match: re.Match) -> str:
        if match.group(2).strip().lower() != old.lower():
            return match.group(0)
        return f"{match.group(1)}{new}{match.group(3) or ''}{match.group(4) or ''}{match.group(5)}"

    return WIKILINK.sub(swap, text)


# ── the brain ───────────────────────────────────────────────────────────────


class Note:
    def __init__(self, path: Path, home: Path):
        self.path = path
        self.rel = path.relative_to(home).as_posix()
        self.folder = self.rel.split("/", 1)[0]
        self.title = path.stem
        self.text = path.read_text(encoding="utf-8")
        block, self.body = split_note(self.text)
        self.has_frontmatter = block is not None
        self.fields, self.unreadable = parse_frontmatter(block) if block is not None else ({}, [])

    def get(self, key: str, default: str = "") -> str:
        value = self.fields.get(key, default)
        return default if isinstance(value, list) else str(value)

    def list(self, key: str) -> list[str]:
        value = self.fields.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)] if value else []

    @property
    def names(self) -> list[str]:
        return [self.title, *self.list("aliases")]

    @property
    def links(self) -> list[str]:
        return link_targets(self.text)

    def save(self) -> None:
        self.text = f"---\n{dump_frontmatter(self.fields)}\n---\n{self.body}"
        self.path.write_text(self.text, encoding="utf-8")


class Brain:
    def __init__(self, home: Path):
        self.home = home
        catalog_file = home / "atlas.json"
        if not catalog_file.is_file():
            raise AtlasError(f"no brain at {home}; run `atlas init` (or set ATLAS_HOME)")
        try:
            self.catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as problem:
            raise AtlasError(f"atlas.json is not valid JSON: {problem}") from problem
        self.types: dict = self.catalog.get("types", {})
        self._notes: list[Note] | None = None

    def notes(self, folders: tuple[str, ...] = ("notes", "archive")) -> list[Note]:
        if self._notes is None:
            self._notes = [
                Note(path, self.home)
                for folder in ("notes", "archive")
                for path in sorted((self.home / folder).glob("*.md"))
            ]
        return [note for note in self._notes if note.folder in folders]

    def forget(self) -> None:
        self._notes = None

    def by_stem(self) -> dict[str, Note]:
        return {note.title.lower(): note for note in self.notes()}

    def resolve(self, ref: str) -> Note:
        """A note by path, id, title or alias."""
        notes = self.notes()
        wanted = ref.strip()
        if wanted.startswith("[[") and wanted.endswith("]]"):
            wanted = link_targets(wanted)[0] if link_targets(wanted) else wanted
        as_path = wanted[:-3] if wanted.endswith(".md") else wanted
        for note in notes:
            if note.rel[:-3] == as_path or str(note.path) == wanted:
                return note
        matches = [note for note in notes if note.get("id") == wanted]
        matches = matches or [note for note in notes if note.title.lower() == wanted.lower()]
        matches = matches or [note for note in notes if wanted.lower() in (alias.lower() for alias in note.list("aliases"))]
        if not matches:
            raise AtlasError(f"no note matches {ref!r}; try `atlas find --text`")
        if len(matches) > 1:
            listed = ", ".join(note.rel for note in matches)
            raise AtlasError(f"{ref!r} matches several notes: {listed}")
        return matches[0]

    def backlinks(self, target: Note) -> list[Note]:
        key = target.title.lower()
        return [note for note in self.notes() if note is not target and key in (link.lower() for link in note.links)]

    def _git(self, *args: str) -> str:
        done = subprocess.run(["git", *args], cwd=self.home, check=True, capture_output=True, text=True)
        return done.stdout.strip()

    def commit(self, message: str, paths: list[Path]) -> None:
        if not self.catalog.get("git_autocommit", True) or not (self.home / ".git").exists():
            return
        rels = sorted({path.relative_to(self.home).as_posix() for path in paths})
        try:
            rels = [rel for rel in rels if (self.home / rel).exists() or self._git("ls-files", "--", rel)]
            if not rels or not self._git("status", "--porcelain", "--", *rels):
                return
            subprocess.run(["git", "add", "-A", "--", *rels], cwd=self.home, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", f"atlas: {message}", "--", *rels],
                cwd=self.home,
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError):
            print("warning: the change is saved but could not be committed to git", file=sys.stderr)


def home_dir(arg: str | None) -> Path:
    return Path(arg or os.environ.get("ATLAS_HOME") or "~/atlas").expanduser().resolve()


def clean_title(title: str) -> str:
    cleaned = "".join(" " if char in ILLEGAL_IN_TITLE else char for char in title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    if not cleaned:
        raise AtlasError("the title is empty once the characters a file name cannot hold are removed")
    return cleaned


def new_id(brain: Brain) -> str:
    taken = {note.get("id") for note in brain.notes()}
    base = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    candidate, count = base, 1
    while candidate in taken:
        count += 1
        candidate = f"{base}-{count}"
    return candidate


def name_clashes(brain: Brain, names: list[str], ignore: Note | None = None) -> list[tuple[str, Note]]:
    wanted = {name.lower(): name for name in names}
    clashes = []
    for note in brain.notes():
        if note is ignore:
            continue
        for name in note.names:
            if name.lower() in wanted:
                clashes.append((name, note))
    return clashes


def parse_assignments(pairs: list[str]) -> dict:
    """`key=value` pairs. A repeated key, or a value with `;`, becomes a list. `key=` clears the field."""
    fields: dict = {}
    for pair in pairs:
        if "=" not in pair:
            raise AtlasError(f"expected key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        key = key.strip()
        if not KEY_LINE.match(f"{key}: x"):
            raise AtlasError(f"{key!r} is not a field name")
        value = value.strip()
        if value == "today":
            value = today().isoformat()
        if key in fields:
            previous = fields[key] if isinstance(fields[key], list) else [fields[key]]
            fields[key] = [*previous, value]
        elif ";" in value:
            fields[key] = [part.strip() for part in value.split(";") if part.strip()]
        else:
            fields[key] = value
    return fields


# ── find ────────────────────────────────────────────────────────────────────


def validity(note: Note) -> tuple[dt.date, dt.date]:
    start = parse_date(note.get("valid_from")) or dt.date.min
    end = parse_date(note.get("valid_to")) or dt.date.max
    return start, end


def text_score(note: Note, words: list[str]) -> int:
    """0 when a word is missing; otherwise higher for matches in the title than in the text."""
    title = note.title.lower()
    aliases = " ".join(note.list("aliases")).lower()
    description = note.get("description").lower()
    body = note.text.lower()
    score = 0
    for word in words:
        if word in title:
            score += 8
        elif word in aliases:
            score += 6
        elif word in description:
            score += 4
        elif word in body:
            score += 1
        else:
            return 0
    return score


def need_date(value: str | None, flag: str) -> dt.date | None:
    if value is None:
        return None
    if value == "today":
        return today()
    parsed = parse_date(value)
    if parsed is None:
        raise AtlasError(f"{flag} needs a date like 2026-10-12, got {value!r}")
    return parsed


def find(brain: Brain, args: argparse.Namespace) -> list[Note]:
    statuses = args.status or ([] if args.all else ["active"])
    everywhere = args.all or any(status != "active" for status in statuses)
    notes = brain.notes(("notes", "archive") if everywhere else ("notes",))
    valid_on = need_date(args.valid_on, "--valid-on")
    window_from = need_date(args.valid_from, "--valid-from")
    window_to = need_date(args.valid_to, "--valid-to")
    verified_before = need_date(args.verified_before, "--verified-before")
    links_to = brain.resolve(args.links_to) if args.links_to else None
    linked_from = brain.resolve(args.linked_from) if args.linked_from else None
    outgoing = {link.lower() for link in linked_from.links} if linked_from else set()
    wheres = parse_assignments(args.where or [])
    words = (args.text or "").lower().split()

    for kind in args.type or []:
        if kind not in brain.types:
            raise AtlasError(f"unknown type {kind!r}; `atlas types` lists them")

    scored = []
    for note in notes:
        if args.type and note.get("type") not in args.type:
            continue
        if statuses and note.get("status") not in statuses:
            continue
        start, end = validity(note)
        if valid_on and not (start <= valid_on < end):
            continue
        if (window_from or window_to) and not (
            start <= (window_to or dt.date.max) and (window_from or dt.date.min) < end
        ):
            continue
        if verified_before:
            verified = parse_date(note.get("verified")) or parse_date(note.get("created"))
            if verified and verified >= verified_before:
                continue
        if links_to and links_to.title.lower() not in (link.lower() for link in note.links):
            continue
        if linked_from and note.title.lower() not in outgoing:
            continue
        if any(not field_matches(brain, note, key, value) for key, value in wheres.items()):
            continue
        score = text_score(note, words) if words else 1
        if score:
            scored.append((score, note))
    scored.sort(key=lambda pair: (-pair[0], pair[1].title.lower()))
    return [note for _, note in scored]


def field_matches(brain: Brain, note: Note, key: str, wanted: object) -> bool:
    """A field equals the value, or a list holds it. A link matches by the note's title or any alias."""
    have = [value.lower() for value in note.list(key)]
    have += [target.lower() for value in note.list(key) for target in link_targets(value)]
    wanted_values = wanted if isinstance(wanted, list) else [wanted]
    for value in wanted_values:
        accepted = {str(value).lower()}
        try:
            accepted.add(brain.resolve(str(value)).title.lower())
        except AtlasError:
            pass
        if accepted == {""}:
            if have:
                return False
        elif not accepted & set(have):
            return False
    return True


def summary(note: Note) -> dict:
    return {
        "path": note.rel,
        "title": note.title,
        "id": note.get("id"),
        "type": note.get("type"),
        "status": note.get("status"),
        "description": note.get("description"),
        "valid_from": note.get("valid_from"),
        "valid_to": note.get("valid_to"),
        "verified": note.get("verified"),
    }


def line(note: Note) -> str:
    parts = [note.rel, note.get("type") or "?", note.get("description") or "(no description)"]
    if note.get("status") not in ("", "active"):
        parts.append(note.get("status"))
    if note.get("valid_to"):
        parts.append(f"valid to {note.get('valid_to')}")
    return " | ".join(parts)


# ── check ───────────────────────────────────────────────────────────────────

ERRORS = ("schema", "broken-link", "duplicate", "supersede")


def check(brain: Brain) -> list[dict]:
    findings: list[dict] = []

    def add(kind: str, note: Note | None, message: str, path: str = "") -> None:
        findings.append(
            {
                "kind": kind,
                "level": "error" if kind in ERRORS else "warning",
                "path": note.rel if note else path,
                "message": message,
            }
        )

    notes = brain.notes()
    stems = brain.by_stem()
    files = {path.name.lower() for path in brain.home.rglob("*") if path.is_file() and ".git" not in path.parts}
    inbound: dict[str, int] = {}
    now = today()

    for note in notes:
        if not note.has_frontmatter:
            add("schema", note, "no frontmatter")
            continue
        for bad in note.unreadable:
            add("schema", note, f"cannot read the frontmatter line {bad.strip()!r} (only `key: value` and lists)")
        kind = note.get("type")
        spec = brain.types.get(kind)
        for field in REQUIRED:
            if not note.get(field):
                add("schema", note, f"`{field}` is missing")
        if kind and spec is None:
            add("schema", note, f"unknown type {kind!r}")
        if note.get("status") and note.get("status") not in STATUSES:
            add("schema", note, f"status {note.get('status')!r} is not one of {', '.join(STATUSES)}")
        spec = spec or {}
        for field in spec.get("required", []):
            if not note.fields.get(field):
                add("schema", note, f"`{field}` is required for type {kind}")
        dated = [*DATE_FIELDS, *(name for name, sort in spec.get("fields", {}).items() if sort == "date")]
        for field in dated:
            if note.get(field) and parse_date(note.get(field)) is None:
                add("schema", note, f"`{field}` is not a date like 2026-10-12: {note.get(field)!r}")

        for target in note.links:
            key = target.lower()
            if key in stems:
                if stems[key] is not note:
                    inbound[key] = inbound.get(key, 0) + 1
            elif key not in files:
                add("broken-link", note, f"[[{target}]] points at nothing")

        status = note.get("status")
        if status == "superseded":
            replaced_by = link_targets(note.get("superseded_by"))
            if not replaced_by:
                add("supersede", note, "superseded, but `superseded_by` names no note")
            elif replaced_by[0].lower() not in stems:
                add("supersede", note, f"`superseded_by` points at [[{replaced_by[0]}]], which does not exist")
        if status == "active":
            end = parse_date(note.get("valid_to"))
            if end and end <= now:
                add("expired", note, f"valid to {end}, but still active")
            age_limit = spec.get("verify_after_days")
            checked = parse_date(note.get("verified")) or parse_date(note.get("created"))
            if age_limit and checked and (now - checked).days > age_limit:
                add("overdue", note, f"last verified {checked}, {(now - checked).days} days ago (limit {age_limit})")
        if (status == "active") != (note.folder == "notes") and status in STATUSES:
            add("misplaced", note, f"status is {status}, but the file is in {note.folder}/")

    seen: dict[str, Note] = {}
    for note in notes:
        for name in note.names if note.folder == "notes" else [note.title]:
            other = seen.setdefault(name.lower(), note)
            if other is not note:
                add("duplicate", note, f"the name {name!r} is also used by {other.rel}")

    for note in notes:
        if note.folder == "notes" and note.get("type") != "hub" and not inbound.get(note.title.lower()):
            add("orphan", note, "nothing links to it")

    max_age = brain.catalog.get("inbox_max_age_days", 14)
    for path in sorted((brain.home / "inbox").glob("*.md")):
        age = (now - dt.date.fromtimestamp(path.stat().st_mtime)).days
        if age > max_age:
            add("inbox", None, f"captured {age} days ago (limit {max_age})", path.relative_to(brain.home).as_posix())
    return findings


# ── commands ────────────────────────────────────────────────────────────────


def cmd_init(args: argparse.Namespace) -> int:
    home = home_dir(args.home)
    if (home / "atlas.json").exists():
        raise AtlasError(f"there is already a brain at {home}")
    for folder in FOLDERS:
        (home / folder).mkdir(parents=True, exist_ok=True)
        (home / folder / ".gitkeep").touch()
    (home / "atlas.json").write_text(json.dumps(DEFAULT_CATALOG, indent=2) + "\n", encoding="utf-8")
    (home / ".gitignore").write_text(".obsidian/workspace*.json\n.trash/\n.DS_Store\n", encoding="utf-8")
    brain = Brain(home)
    fields = {
        "id": new_id(brain),
        "type": "hub",
        "description": "Where to start: the topics this brain holds",
        "status": "active",
        "created": today().isoformat(),
    }
    (home / "notes" / "Home.md").write_text(
        f"---\n{dump_frontmatter(fields)}\n---\nLink the hub of each topic from here.\n", encoding="utf-8"
    )
    try:
        if not (home / ".git").exists():
            subprocess.run(["git", "init", "-q"], cwd=home, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=home, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "atlas: init"], cwd=home, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        print("note: git is not available or not configured; the brain works without history", file=sys.stderr)
    print(f"created the brain at {home}")
    print("open that folder in Obsidian as a vault to read and edit it by hand")
    print("to reach it from every project without prompts, add to ~/.claude/settings.json:")
    print(
        json.dumps(
            {"permissions": {"additionalDirectories": [str(home)], "allow": ["Bash(atlas:*)", f"Edit({home}/**)"]}},
            indent=2,
        )
    )
    return 0


def cmd_types(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    print("every note: " + ", ".join(REQUIRED) + " (required); aliases, verified, valid_from, valid_to, superseded_by, sources")
    for name, spec in brain.types.items():
        own = ", ".join(
            f"{field}{' (required)' if field in spec.get('required', []) else ''}" for field in spec.get("fields", {})
        )
        review = spec.get("verify_after_days")
        print(
            f"{name}: {spec.get('about', '')}"
            + (f" | fields: {own}" if own else "")
            + (f" | review after {review} days" if review else "")
        )
    return 0


def cmd_find(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    found = find(brain, args)
    shown = found[: args.limit] if args.limit else found
    if args.json:
        print(json.dumps([summary(note) for note in shown], indent=2))
    elif args.paths:
        for note in shown:
            print(note.rel)
    else:
        for note in shown:
            print(line(note))
        if not found:
            print("no matches")
        elif len(shown) < len(found):
            print(f"{len(shown)} of {len(found)} shown; narrow the filters or raise --limit")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    note = brain.resolve(args.ref)
    print(f"# {note.rel}")
    if args.meta:
        print(dump_frontmatter(note.fields))
    else:
        print(note.text.rstrip("\n"))
    linking = brain.backlinks(note)
    if linking:
        print("\n# linked from")
        for other in linking:
            print(line(other))
    return 0


def cmd_links(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    note = brain.resolve(args.ref)
    stems = brain.by_stem()
    print(f"# {note.rel} links to")
    for target in note.links:
        other = stems.get(target.lower())
        print(line(other) if other else f"[[{target}]] | missing")
    print("# linked from")
    for other in brain.backlinks(note):
        print(line(other))
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    if args.type not in brain.types:
        raise AtlasError(f"unknown type {args.type!r}; `atlas types` lists them")
    title = clean_title(args.title)
    extra = parse_assignments(args.set or [])
    aliases = [alias for alias in (args.alias or []) if alias.strip()]
    clashes = name_clashes(brain, [title, *aliases])
    if clashes:
        listed = "; ".join(f"{name!r} is {note.rel}" for name, note in clashes)
        raise AtlasError(f"that name is taken: {listed}. Extend that note, or choose another title")
    if not args.description:
        raise AtlasError("--description is required: one line saying what the note holds")
    spec = brain.types[args.type]
    missing = [field for field in spec.get("required", []) if not extra.get(field)]
    if missing:
        raise AtlasError(f"type {args.type} needs: " + ", ".join(f"--set {field}=…" for field in missing))

    now = today().isoformat()
    fields: dict = {"id": new_id(brain), "type": args.type, "description": args.description}
    if aliases:
        fields["aliases"] = aliases
    fields.update({"status": "active", "created": now, "verified": now})
    fields.update(extra)
    if args.source:
        fields["sources"] = list(args.source)
    body = sys.stdin.read() if args.body == "-" else (args.body or "")
    path = brain.home / "notes" / f"{title}.md"
    path.write_text(f"---\n{dump_frontmatter(fields)}\n---\n{body.strip()}\n", encoding="utf-8")
    brain.commit(f"new {args.type} {title}", [path])
    print(path.relative_to(brain.home).as_posix())
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    text = (sys.stdin.read() if args.text == "-" else args.text).strip()
    if not text:
        raise AtlasError("nothing to capture")
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H%M%S")
    words = clean_title(" ".join(text.split()[:6]))[:60]
    path = brain.home / "inbox" / f"{stamp} {words}.md"
    path.write_text(text + "\n", encoding="utf-8")
    brain.commit(f"capture {words}", [path])
    print(path.relative_to(brain.home).as_posix())
    return 0


def cmd_inbox(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    items = sorted((brain.home / "inbox").glob("*.md"))
    for path in items:
        age = (today() - dt.date.fromtimestamp(path.stat().st_mtime)).days
        first = path.read_text(encoding="utf-8").strip().split("\n", 1)[0][:100]
        print(f"{path.relative_to(brain.home).as_posix()} | {age}d | {first}")
    if not items:
        print("the inbox is empty")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    note = brain.resolve(args.ref)
    changes = parse_assignments(args.pairs)
    if "id" in changes:
        raise AtlasError("the id of a note never changes")
    if "type" in changes and changes["type"] not in brain.types:
        raise AtlasError(f"unknown type {changes['type']!r}")
    if "status" in changes and changes["status"] not in STATUSES:
        raise AtlasError(f"status must be one of {', '.join(STATUSES)}")
    for key, value in changes.items():
        if value == "":
            note.fields.pop(key, None)
        else:
            note.fields[key] = value
    note.save()
    brain.commit(f"set {', '.join(changes)} on {note.title}", [note.path])
    print(note.rel)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    note = brain.resolve(args.ref)
    note.fields["verified"] = today().isoformat()
    note.save()
    brain.commit(f"verify {note.title}", [note.path])
    print(f"{note.rel} | verified {note.fields['verified']}")
    return 0


def move_to_archive(brain: Brain, note: Note) -> list[Path]:
    if note.folder == "archive":
        note.save()
        return [note.path]
    target = brain.home / "archive" / note.path.name
    if target.exists():
        raise AtlasError(f"archive/{note.path.name} already exists; rename one of them first")
    old = note.path
    note.path = target
    note.save()
    old.unlink()
    return [old, target]


def cmd_supersede(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    old, new = brain.resolve(args.old), brain.resolve(args.by)
    if old is new:
        raise AtlasError("a note cannot supersede itself")
    day = today().isoformat()
    old.fields.update({"status": "superseded", "valid_to": old.get("valid_to") or day, "superseded_by": f"[[{new.title}]]"})
    touched = move_to_archive(brain, old)
    if not new.get("valid_from"):
        new.fields["valid_from"] = day
        new.save()
        touched.append(new.path)
    brain.commit(f"{new.title} supersedes {old.title}", touched)
    print(f"archive/{old.path.name} | superseded by {new.rel}")
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    note = brain.resolve(args.ref)
    if note.get("status") != "superseded":
        note.fields["status"] = "archived"
    touched = move_to_archive(brain, note)
    brain.commit(f"archive {note.title}", touched)
    print(f"archive/{note.path.name}")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    note = brain.resolve(args.ref)
    if note.folder != "archive":
        raise AtlasError(f"{note.rel} is not in the archive")
    target = brain.home / "notes" / note.path.name
    if target.exists():
        raise AtlasError(f"notes/{note.path.name} already exists; rename one of them first")
    old = note.path
    note.fields["status"] = "active"
    for field in ("superseded_by", "valid_to"):
        note.fields.pop(field, None)
    note.path = target
    note.save()
    old.unlink()
    brain.commit(f"restore {note.title}", [old, target])
    print(f"notes/{note.path.name}")
    return 0


def rewrite_links(brain: Brain, old: str, new: str, skip: Note | None = None) -> list[Path]:
    touched = []
    for note in brain.notes():
        if note is skip:
            continue
        rewritten = retarget_links(note.text, old, new)
        if rewritten != note.text:
            note.path.write_text(rewritten, encoding="utf-8")
            touched.append(note.path)
    return touched


def cmd_rename(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    note = brain.resolve(args.ref)
    title = clean_title(args.title)
    if title == note.title:
        raise AtlasError("that is already its title")
    clashes = name_clashes(brain, [title], ignore=note)
    if clashes and title.lower() != note.title.lower():
        raise AtlasError(f"{title!r} is taken by {clashes[0][1].rel}")
    old_title, old_path = note.title, note.path
    aliases = [alias for alias in note.list("aliases") if alias.lower() != title.lower()]
    if not args.drop_old and old_title.lower() not in (alias.lower() for alias in aliases):
        aliases.append(old_title)
    if aliases:
        note.fields["aliases"] = aliases
    else:
        note.fields.pop("aliases", None)
    note.body = retarget_links(note.body, old_title, title)
    note.path = old_path.with_name(f"{title}.md")
    old_path.rename(note.path)
    note.save()
    touched = [old_path, note.path, *rewrite_links(brain, old_title, title, skip=note)]
    brain.commit(f"rename {old_title} to {title}", touched)
    print(f"{note.path.relative_to(brain.home).as_posix()} | {len(touched) - 2} notes relinked")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    duplicate, survivor = brain.resolve(args.dup), brain.resolve(args.into)
    if duplicate is survivor:
        raise AtlasError("a note cannot be merged into itself")
    names = [name for name in survivor.list("aliases")]
    for name in duplicate.names:
        if name.lower() not in (known.lower() for known in [survivor.title, *names]):
            names.append(name)
    survivor.fields["aliases"] = names
    survivor.save()
    duplicate.fields.update({"status": "superseded", "superseded_by": f"[[{survivor.title}]]"})
    duplicate.fields.pop("aliases", None)
    duplicate.fields["valid_to"] = duplicate.get("valid_to") or today().isoformat()
    touched = [survivor.path, *rewrite_links(brain, duplicate.title, survivor.title, skip=duplicate)]
    if duplicate.folder == "notes":
        archived = brain.home / "archive" / f"{duplicate.title} (merged {duplicate.get('id')}).md"
        old = duplicate.path
        duplicate.path = archived
        duplicate.save()
        old.unlink()
        touched += [old, archived]
    else:
        duplicate.save()
        touched.append(duplicate.path)
    brain.commit(f"merge {duplicate.title} into {survivor.title}", touched)
    print(f"{survivor.rel} | took over the names and links of {duplicate.title}; move any text worth keeping by hand")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    brain = Brain(home_dir(args.home))
    findings = check(brain)
    errors = sum(1 for finding in findings if finding["level"] == "error")
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for finding in findings:
            print(f"{finding['level']} {finding['kind']} | {finding['path']} | {finding['message']}")
        notes = len(brain.notes(("notes",)))
        print(f"{notes} notes: {errors} errors, {len(findings) - errors} warnings")
    return 1 if errors else 0


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="atlas", description="A personal brain of markdown notes.")
    top.add_argument("--home", help="the brain's folder (default: $ATLAS_HOME, then ~/atlas)")
    sub = top.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the brain").set_defaults(run=cmd_init)
    sub.add_parser("types", help="print the catalog of note types").set_defaults(run=cmd_types)

    find_cmd = sub.add_parser("find", help="list notes that match the filters")
    find_cmd.add_argument("--type", action="append", help="repeatable")
    find_cmd.add_argument("--text", help="words that must all appear")
    find_cmd.add_argument("--status", action="append", choices=STATUSES, help="default: active")
    find_cmd.add_argument("--valid-on", metavar="DATE")
    find_cmd.add_argument("--valid-from", metavar="DATE")
    find_cmd.add_argument("--valid-to", metavar="DATE")
    find_cmd.add_argument("--verified-before", metavar="DATE")
    find_cmd.add_argument("--links-to", metavar="REF")
    find_cmd.add_argument("--linked-from", metavar="REF")
    find_cmd.add_argument("--where", action="append", metavar="KEY=VALUE")
    find_cmd.add_argument("--all", action="store_true", help="also search the archive")
    find_cmd.add_argument("--limit", type=int, default=30)
    find_cmd.add_argument("--json", action="store_true")
    find_cmd.add_argument("--paths", action="store_true")
    find_cmd.set_defaults(run=cmd_find)

    get_cmd = sub.add_parser("get", help="print one note and what links to it")
    get_cmd.add_argument("ref")
    get_cmd.add_argument("--meta", action="store_true", help="frontmatter only")
    get_cmd.set_defaults(run=cmd_get)

    links_cmd = sub.add_parser("links", help="print a note's links and backlinks")
    links_cmd.add_argument("ref")
    links_cmd.set_defaults(run=cmd_links)

    new_cmd = sub.add_parser("new", help="create a note")
    new_cmd.add_argument("title")
    new_cmd.add_argument("--type", default="note")
    new_cmd.add_argument("--description", "-d")
    new_cmd.add_argument("--alias", action="append")
    new_cmd.add_argument("--source", action="append", help='a URL or "[[Source note]]"; repeatable')
    new_cmd.add_argument("--set", action="append", metavar="KEY=VALUE")
    new_cmd.add_argument("--body", help='the text, or "-" to read it from stdin')
    new_cmd.set_defaults(run=cmd_new)

    capture_cmd = sub.add_parser("capture", help="drop a line into the inbox")
    capture_cmd.add_argument("text", help='the text, or "-" to read it from stdin')
    capture_cmd.set_defaults(run=cmd_capture)

    sub.add_parser("inbox", help="list the inbox").set_defaults(run=cmd_inbox)

    set_cmd = sub.add_parser("set", help="change frontmatter fields")
    set_cmd.add_argument("ref")
    set_cmd.add_argument("pairs", nargs="+", metavar="KEY=VALUE")
    set_cmd.set_defaults(run=cmd_set)

    verify_cmd = sub.add_parser("verify", help="mark a note as confirmed today")
    verify_cmd.add_argument("ref")
    verify_cmd.set_defaults(run=cmd_verify)

    supersede_cmd = sub.add_parser("supersede", help="close a note in favour of a newer one")
    supersede_cmd.add_argument("old")
    supersede_cmd.add_argument("--by", required=True, metavar="REF")
    supersede_cmd.set_defaults(run=cmd_supersede)

    archive_cmd = sub.add_parser("archive", help="move a note to the archive")
    archive_cmd.add_argument("ref")
    archive_cmd.set_defaults(run=cmd_archive)

    restore_cmd = sub.add_parser("restore", help="bring a note back from the archive as active")
    restore_cmd.add_argument("ref")
    restore_cmd.set_defaults(run=cmd_restore)

    rename_cmd = sub.add_parser("rename", help="rename a note and rewrite every link to it")
    rename_cmd.add_argument("ref")
    rename_cmd.add_argument("title")
    rename_cmd.add_argument("--drop-old", action="store_true", help="do not keep the old title as an alias")
    rename_cmd.set_defaults(run=cmd_rename)

    merge_cmd = sub.add_parser("merge", help="fold a duplicate's names and links into another note")
    merge_cmd.add_argument("dup")
    merge_cmd.add_argument("--into", required=True, metavar="REF")
    merge_cmd.set_defaults(run=cmd_merge)

    check_cmd = sub.add_parser("check", help="lint the brain")
    check_cmd.add_argument("--json", action="store_true")
    check_cmd.set_defaults(run=cmd_check)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        return args.run(args)
    except AtlasError as problem:
        print(f"atlas: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
