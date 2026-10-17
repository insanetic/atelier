#!/usr/bin/env python3
"""PreToolUse guard: nothing in a paperwork archive is deleted, moved or overwritten except by the engine.

Denies Bash commands that would remove, move, overwrite or rewrite files inside a registered archive
(the paperwork engine itself is allowed), and Write/Edit calls on anything there except the files
Claude is meant to write: _paperwork/config.json, _paperwork/rules.json, _paperwork/rules/, _paperwork/proposals/ and _paperwork/templates/.
Copying into _inbox/ is allowed with `cp -n` (never overwrite).

Archives: $PAPERWORK_HOME and the lines of ~/.config/paperwork/roots (written by `paperwork init`).
Runs on the host with the standard library only (Python 3.9+).
"""

import json
import os
import shlex
import sys

WRITABLE = ("_paperwork/proposals/", "_paperwork/templates/", "_paperwork/rules/")
WRITABLE_FILES = ("_paperwork/config.json", "_paperwork/rules.json")
DESTRUCTIVE = {"rm", "rmdir", "unlink", "shred", "truncate", "trash", "srm", "ln", "install", "dd", "tee",
               "touch", "chmod", "chown", "chflags", "xattr", "rename", "ditto", "unzip", "tar", "setfacl",
               "mkfile", "split", "patch"}
COPY_LIKE = {"cp", "mv", "rsync", "gcp", "gmv"}
WRAPPERS = {"sudo", "command", "env", "nohup", "time", "nice", "xargs", "doas", "builtin", "exec"}
SHELLS = {"sh", "bash", "zsh", "dash", "fish"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "|&"}


def roots():
    out = []
    home = os.environ.get("PAPERWORK_HOME")
    if home:
        out.append(home)
    conf = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "paperwork", "roots")
    try:
        with open(conf, encoding="utf-8") as f:
            out += [line.strip() for line in f if line.strip()]
    except OSError:
        pass
    return out


def resolve(path, cwd):
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    return os.path.realpath(path)


def inside(path, root):
    root = os.path.realpath(root)
    return path == root or path.startswith(root.rstrip("/") + "/")


def rel_in(path, rs):
    for r in rs:
        if inside(path, r):
            return os.path.relpath(path, os.path.realpath(r)).replace(os.sep, "/")
    return None


def segments(command):
    lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    lex.commenters = ""
    tokens = list(lex)
    seg = []
    for t in tokens:
        if t in SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def check_segment(tokens, cwd, rs):
    """(reason or None, new cwd)."""
    words, redirects = [], []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if set(t) <= set("<>&") and ">" in t:
            if not t.endswith("&") and i + 1 < len(tokens):
                redirects.append(tokens[i + 1])
            i += 2
            continue
        if t.isdigit() and i + 1 < len(tokens) and set(tokens[i + 1]) <= set("<>&") and ">" in tokens[i + 1]:
            i += 1
            continue
        if t in ("<", "<<", "<<<"):
            i += 2
            continue
        words.append(t)
        i += 1
    for target in redirects:
        if target != "/dev/null" and rel_in(resolve(target, cwd), rs) is not None:
            return f"writing into the archive with a redirect ({target})", cwd
    while words and ("=" in words[0] and not words[0].startswith("-") and words[0].split("=")[0].isidentifier()):
        words = words[1:]
    while words and os.path.basename(words[0]) in WRAPPERS:
        words = words[1:]
        while words and words[0].startswith("-"):
            words = words[1:]
    if not words:
        return None, cwd
    cmd = os.path.basename(words[0])
    args = words[1:]
    if cmd == "cd":
        return None, resolve(args[0], cwd) if args else os.path.expanduser("~")
    if cmd == "paperwork":
        return None, cwd
    if cmd in SHELLS and "-c" in args:
        inner = args[args.index("-c") + 1] if args.index("-c") + 1 < len(args) else ""
        return decide_command(inner, cwd, rs), cwd
    flags = [a for a in args if a.startswith("-")]
    paths = [resolve(a, cwd) for a in args if not a.startswith("-")]
    touched = [p for p in paths if rel_in(p, rs) is not None]
    cwd_in = rel_in(os.path.realpath(cwd), rs) is not None

    if cmd in DESTRUCTIVE and (touched or cwd_in):
        return f"`{cmd}` on files in the archive; only the paperwork engine moves or renames there", cwd
    if cmd in COPY_LIKE and (touched or cwd_in):
        if not paths:
            return None, cwd
        *sources, dest = paths
        dest_rel = rel_in(dest, rs)
        safe_flag = any(f in ("-n", "--no-clobber", "--ignore-existing") or (f.startswith("-") and not f.startswith("--") and "n" in f)
                        for f in flags) and not any("delete" in f or "remove-source" in f for f in flags)
        if cmd in ("cp", "gcp", "rsync") and dest_rel is not None and (dest_rel == "_inbox" or dest_rel.startswith("_inbox/")) \
                and sources and all(rel_in(s, rs) is None for s in sources) and safe_flag:
            return None, cwd
        return (f"`{cmd}` touching the archive. To add files, copy them into _inbox with `cp -n`; "
                "everything else goes through `paperwork plan` / `paperwork apply`"), cwd
    if cmd in ("sed", "gsed", "perl", "ruby") and any(f.startswith("-i") or (f.startswith("-") and "i" in f and cmd != "sed") for f in flags) \
            and (touched or cwd_in):
        return f"in-place edit with `{cmd}` in the archive", cwd
    if cmd == "find" and any(a in ("-delete", "-exec", "-execdir", "-ok", "-okdir") for a in args) and (touched or cwd_in):
        return "`find` with -delete/-exec in the archive", cwd
    if cmd == "git" and args and args[0] in ("clean", "rm", "mv", "checkout", "restore", "reset", "stash") and (touched or cwd_in):
        return f"`git {args[0]}` in the archive", cwd
    return None, cwd


def decide_command(command, cwd, rs):
    try:
        segs = list(segments(command))
    except ValueError:
        if any(rel_in(resolve(w, cwd), rs) is not None for w in command.split()) or rel_in(os.path.realpath(cwd), rs):
            return "a command touching the archive that could not be parsed"
        return None
    for seg in segs:
        reason, cwd = check_segment(seg, cwd, rs)
        if reason:
            return reason
    return None


def decide(event, rs):
    if not rs:
        return None
    tool = event.get("tool_name", "")
    inp = event.get("tool_input") or {}
    cwd = event.get("cwd") or os.getcwd()
    if tool == "Bash":
        return decide_command(inp.get("command", ""), cwd, rs)
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = inp.get("file_path") or inp.get("notebook_path")
        if not path:
            return None
        rel = rel_in(resolve(path, cwd), rs)
        if rel is None or rel in WRITABLE_FILES or rel.startswith(WRITABLE):
            return None
        return (f"{rel} is in the paperwork archive: documents and records change only through the engine "
                "(`paperwork set`, `record`, `plan`/`apply`)")
    return None


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    reason = decide(event, roots())
    if reason:
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                          "permissionDecisionReason": "paperwork guard: " + reason}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
