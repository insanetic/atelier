---
name: check
description: >-
  Use when a help center article or developer doc should be checked or reviewed against the docs
  convention, without writing it from scratch: "prüf den Artikel", "is this article ok?", "check the docs
  folder", "lint the help center", "review this how-to", or before a publish. Runs the deterministic
  docs check, then judges what it cannot (facts, one job per article, plain language, the reader's
  words), and reports findings with rule IDs. Changes the file only when asked.
argument-hint: "<article file, folder or pasted text> [fix]"
---

# Checking an article

Read [CONVENTION.md](../../CONVENTION.md), and the project's house style when there is one
([PROCEDURE.md](../../PROCEDURE.md), step 0): its `DOC-1xx` entries replace the default rules they speak
about.

```
$ARGUMENTS
```

1. **Machine check.** Run `docs check --json <file>...`, with `--house-style --reader <reader>` when the
   project has a house style (a folder: every `.md`/`.mdx` article in it; pasted text: save it to the
   scratchpad first), and `docs links <file>` for links that do not resolve. Every `error` is a finding
   unless step 3 sets it aside.
2. **Judge** what the check cannot, citing the rule:
   1. Facts (DOC-004, DOC-050): labels, steps, signatures and limits that nothing in the context backs.
      Say what to verify; never "correct" a fact from memory.
   2. Exposure (DOC-005) in meaning: customer data in examples or screenshots, internal names.
   3. Reader and job (DOC-001 to DOC-003, DOC-006): written for the wrong reader, two jobs, an FAQ
      answer that needs steps or is longer than three sentences.
   4. House style: every `DOC-1xx` entry the article falls under (shape, headings, file name, marking,
      link form, screenshots, words). When the rulebook plugin is installed, `rulebook:review` can do this
      part for a whole change.
   5. Title and first paragraph (DOC-010, DOC-020, or the house style's form): the reader's words, the
      point first.
   6. Writing (DOC-007 to DOC-009, DOC-030 to DOC-035, DOC-043): sections that only make sense after the
      one above, a fact restated that another article holds, the reader's own word missing, something only
      an image shows, jargon, one action per step, labels exactly as on screen, one term per thing.
   7. Developer pages (DOC-051): would each example run as it stands?
3. **Set aside** a check finding only when a rule in context allows it or the match is plainly not what
   the rule means (a quoted error message that contains "just"). List each with its reason.
4. **Report**, most severe first, at most ten findings per article:

   ```
   <file> · <reader> <type> · ok | needs work
   - DOC-0xx or DOC-1xx · "quoted text" · the fix
   Set aside: DOC-0xx · "quoted text" · why
   ```

5. With `fix` in the request, or after the user says so: fix the findings in the file, re-run the check,
   and show the diff. Facts that are missing become questions, not text.
