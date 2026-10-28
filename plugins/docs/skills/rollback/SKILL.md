---
name: rollback
description: >-
  Use when a help center article or doc page should go back to an earlier version: "roll das zurück",
  "stell die alte Version wieder her", "undo the last change to this article", "the live article is wrong,
  go back to last week's", "revert the help center article to what was published on Monday". Finds the
  version in git (published, pulled or any commit), restores it as a new commit without rewriting history,
  shows what changes against the live version, and then publishes it through the publish skill, after a
  yes. Also restores only locally when that is all that is asked.
argument-hint: "<article> [<version, date or 'last published'>]"
---

# Rolling back an article

Read [CONVENTION.md](../../CONVENTION.md) (DOC-070 to DOC-072) and [PROCEDURE.md](../../PROCEDURE.md).

```
$ARGUMENTS
```

1. **The article and the versions.** Resolve the file (procedure step 1) and run `docs history <file>`.
2. **Which version.** From what the user said: a commit, a date ("Monday's" means the version live then:
   the last `published` or `pulled` entry on or before that date), "the previous one" (the version before
   the last publish when the bad version is live, else the previous commit). Several fit or none: show the
   candidates from the history, newest first, with their subjects, and ask. Show the chosen version's
   text summary before going on.
3. **Live first.** For a hosted target, compare the live article with the last published version
   ([diff](../diff/SKILL.md)). If someone changed it in the hosted editor, say so: the rollback would also
   remove that change; ask before going on.
4. **Restore as a new commit** (DOC-071). Take the old content with `git show <commit>:<path>`, keep today's
   target IDs and `source_commit` keys in the frontmatter (an ID must not go back to an older or missing
   one), write it to the file, run `docs check` (an old version may break a newer rule: report it, fix only
   with a yes), show `docs diff` against the current version, and commit as
   `docs(<slug>): roll back to <short commit> (<date>)`. Never `git reset`, `git revert` of unrelated
   files, force-push or a history rewrite. Translations of the article: name them; they are rolled back
   only when the user says so.
5. **Live.** When the user wants it live (the usual reason for a rollback), continue with
   [push](../push/SKILL.md) from its step 2 for this article; its confirmation shows the change
   against the live version. Only local was asked: stop after the commit and say the help center still
   shows the newer version.
6. **Report**: the version restored, the commit, and the live link or that it is not live yet.
