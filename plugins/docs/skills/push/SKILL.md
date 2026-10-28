---
name: push
description: >-
  Use when one or more help center articles or doc pages should go live, be pushed or updated online, or
  be put up as a draft at the target: "push the article", "push it to Productlane", "veröffentliche den
  Artikel", "stell das online", "publish to the help center", "update the live version", "open the docs
  PR". The counterpart of pull, and the only docs skill that writes anywhere outside the local files.
  Pushes only a committed, checked version, checks that nobody changed the live article in the meantime,
  shows exactly what changes, waits for a yes, then writes and records the push in git. Any help center
  with a connected tool (Productlane, Intercom, Zendesk …), a docs repository (Docusaurus …) through a
  pull request, or none: then copy and paste. Not for a plain git push of code or commits.
argument-hint: "<article file(s) or folder> [draft]"
---

# Pushing articles live

Read [CONVENTION.md](../../CONVENTION.md) (DOC-070 to DOC-073) and [PROCEDURE.md](../../PROCEDURE.md), and
follow the procedure around these steps. Pushing changes what customers see; nothing here is guessed.

```
$ARGUMENTS
```

1. **What and where.** Resolve the articles (procedure step 1) and the target (step 2). A folder means its
   articles that changed since their last push (`docs history`), confirmed as a list first.
2. **Ready?** For each article:
   - the check (procedure step 0: with `--house-style` when the project has one) has no errors; otherwise
     stop and offer [check](../check/SKILL.md);
   - every link resolves (`docs links <file>`);
   - no uncommitted changes: show them and ask whether to commit them (procedure step 6) or push the last
     commit as it is;
   - `status: draft` goes live only when the user says so; otherwise push it as a draft at the target, if
     the target has drafts, or ask;
   - translations with a stale `source_commit` (DOC-073) are named.
3. **Docs-tool repository** (the target is the repository): pushing is its pull request. Commit on a
   branch, push it and open a pull request after the confirmation in step 7, with the diff summary as its
   description. Never push to the default branch or merge unless the user says so. Then report the link
   and stop.
4. **Hosted help center: drift.** For an article that has an ID at the target, read the live body and
   compare it with the last pushed or pulled version (`docs history`, `docs render --at`, `docs diff`).
   Different: stop for that article, show the difference, and offer [pull](../pull/SKILL.md) first
   (DOC-072). Never overwrite a change made in the hosted editor without the user seeing it.
5. **Resolve links and images** (DOC-047). Run `docs links --json <file>`. For each link to another
   article, look that article up **at the target**: by its ID at the target when its file has one, else by
   its exact title through the target's search or list of articles. Take the address the target gives
   (and its current title, where the target shows links by title), never one built from a title or slug:
   renamed articles keep their old address. Write them to a JSON map from the link as written to
   `{"url": …, "title": …}`. A linked article that is not live yet: push it first, or ask. Images the
   target hosts: upload them (each upload is part of the confirmation) and map them the same way, unless
   the house style keeps images hosted already.
6. **Render** each article:
   `docs render --target <target> [--house-style] --links <map> [--assets <map>] --out <tmp> <file>`.
   Render refuses uncommitted or failing articles and links without an address; do not work around it.
7. **Confirm** as the procedure's step 8: per article the target, new or update, collection, draft or
   live, the version, what changes in meaning, and the diff against the live version (or the whole body for
   a new one). One question for all of them.
8. **Write** exactly the rendered body, unchanged, through the target's tool: update by ID, or create in the
   collection (search by title first so it is not created twice). Pass it literally or from the rendered
   file; the hook compares it with what `docs render` produced and sends anything else back. Nothing
   connected: hand over the body to copy and paste (procedure, **Copy and paste**).
9. **Record and report** (procedure step 9): the new ID into the frontmatter, the `Docs-Published:`
   commit, the live link. A failed write is reported with the error, and nothing is recorded for it.
