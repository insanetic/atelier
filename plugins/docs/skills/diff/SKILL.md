---
name: diff
description: >-
  Use whenever someone asks what changed in a help center article or doc page, or wants two versions of
  one compared, before answering from git yourself: "was hat sich am Artikel geändert?", "what changed in
  the export article since it was published?", "what's different from last week", "compare with the live
  version", "is the live article still what we have in git?", "diff the published and the local version",
  "which translations are out of date?". Compares two commits, the working copy with the last published version, or the live help
  center with git (someone edited it in the hosted editor), and says what changed in meaning before
  showing the line diff. Reads only; changes nothing.
argument-hint: "<article> [<version> [<version>]] [live]"
---

# Comparing versions of an article

Read [PROCEDURE.md](../../PROCEDURE.md) (steps 1, 2 and 7). Rule IDs are [CONVENTION.md](../../CONVENTION.md)'s.

```
$ARGUMENTS
```

1. **The article.** Resolve the file (procedure step 1). A title or slug: search the articles; several fit:
   ask.
2. **The versions.** Run `docs history <file>`. Map what the user said onto it:
   - two commits or dates given: those;
   - one given: it against the working copy;
   - "what changed" with nothing given: the working copy against the last `published` or `pulled`
     version, else against the previous commit;
   - "live", "online", "in Productlane": the live help center against the last published or pulled
     version (drift), and against the working copy;
   - translations: each `<slug>.<lang>.md` against the source changes since its `source_commit`.
3. **Get both texts** into the scratchpad:
   - a commit: `docs render --at <commit> --target <target> <file> --out <tmp>`;
   - the working copy: the file itself;
   - live: read the article from the target (procedure step 2) and save its body. Nothing connected: say
     that the live side cannot be read and compare what can be.
4. **Compare** with `docs diff <old> <new>` (normalises formatting, so a body read back from the target
   compares to ours).
5. **Report**, for each pair:

   ```
   <file>: <old label> → <new label>
   In meaning:
   - <step 3 now says to select **Export** instead of **Download**>
   - <section "Good to know" added: export limit 10,000 rows>
   Diff: +<n> −<m> lines
   <the diff, or the first 60 lines and where the rest is>
   ```

   Lead with meaning: steps added, removed or reordered, labels renamed, limits, prerequisites and warnings
   changed, sections added or removed. Wording-only edits are summed up in one bullet. "Same after
   normalising formatting" is a valid result.
6. **Drift** (live differs from the last published or pulled version): say so plainly, show who could
   have changed it (the hosted editor), and offer [pull](../pull/SKILL.md) to bring the live text into git
   before anything else is published to it (DOC-072). A translation that is behind its source in meaning:
   name it and offer to update it with [guide](../guide/SKILL.md) or [devdoc](../devdoc/SKILL.md).
