---
name: check
description: >-
  Use when the user wants an issue, ticket, task, comment or closing note checked against the convention
  before or after it is posted: "is this ticket ok?", "prüf das Issue", "check IND-12", "does this follow
  our issue conventions", or to clean up an existing issue. Runs the deterministic tracker check, judges
  facts, audience and shape, and returns findings with rule IDs and a corrected version. Writes nothing
  unless asked to apply the correction.
argument-hint: "<draft, file or issue ID>"
---

# Checking against the convention

Read [CONVENTION.md](../../CONVENTION.md) and [PROCEDURE.md](../../PROCEDURE.md).

```
$ARGUMENTS
```

1. **The text.** A draft or file as given; an issue ID is fetched (title, description, recent comments).
   Decide type, kind, purpose or result and audience from the text and its context; ask only if it is
   honestly unclear.
2. **Check.** Save it with its frontmatter (PROCEDURE.md, step 7) and run `tracker check --json <file>`.
3. **Judge** what the script cannot, in this order: exposure in meaning (CI-002, CI-003), facts and guesses
   (CI-004, CI-005), whether someone who was not there could finish the issue from it alone (CI-008: why,
   done when, who to ask, what the work needs; for an existing issue, its fields count too), the kind
   (CI-006), whether the title states the outcome (CI-012) and the TL;DR adds to it (CI-024), one purpose
   per comment (CI-030). A CI-008 gap is a question, not a guess.
4. **Report**, nothing around it:

   ```
   **Verdict:** ok | fix | needs input
   **Findings:**
   - CI-0xx · "quoted phrase" · the fix
   **Corrected:**
   <the corrected text in the convention's shape>
   **Questions:**
   - <a fact the shape needs that nobody gave>
   ```

   Leave out empty parts; at most 7 findings, most severe first. `ok` means no finding and no correction.
5. Apply the correction only when asked, through confirmation as the procedure says.
