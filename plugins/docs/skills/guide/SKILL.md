---
name: guide
description: >-
  Use whenever a help center article, user guide, how-to, FAQ answer, troubleshooting page or product
  documentation for end users is written, revised, restructured or translated: "schreib einen
  Hilfe-Artikel", "Anleitung für Kunden", "help article for X", "how do users do Y", "update the help
  center article", "mach daraus einen Helpcenter-Artikel", or a support answer that should become an
  article. For readers without technical knowledge. Works on a local Markdown file in git (a helpcenter/
  folder or a Docusaurus or other docs repository), never publishes. Not for SDK or API docs: that is
  devdoc.
argument-hint: "<topic, notes, support thread or article file>"
---

# An article for users

Read [CONVENTION.md](../../CONVENTION.md) and [PROCEDURE.md](../../PROCEDURE.md), and follow the procedure
around these steps. The reader is in the middle of a task, may have no technical knowledge, and scans.

```
$ARGUMENTS
```

1. **House style and place** (procedure steps 0 and 1). The house style, when there is one, decides the
   shape, headings, file name, marking and link form below, in place of the defaults. An existing article: read it, its neighbours and its history
   (`docs history <file>`). An article that exists only in the hosted help center: pull it first
   ([pull](../pull/SKILL.md)), so the change starts from what is live.
2. **Already covered?** Search the articles for the same task or symptom (titles, descriptions, the
   reader's words). If one covers it, change that one or link to it instead of writing a second.
3. **Type** (DOC-002, DOC-003, or the house style's types). A task is a `how-to`, a problem a
   `troubleshooting`, "what is X" an `overview`, lists of options or limits a `reference`, short answers
   to recurring questions a `faq`. An FAQ answers in at most three sentences and links to the article
   that covers a question when one exists; a question that needs steps gets its own how-to (DOC-006). Two jobs: propose two articles.
4. **Facts** (procedure step 4). The exact labels and menu path on screen, who may do it (role, plan),
   what the reader sees after each step, and what usually goes wrong. Ask once for what is missing.
   Never describe UI you have not seen or been told. Product code or a running app is a source only
   where the house style names it (procedure step 4).
5. **Title and description** (DOC-010, DOC-011, or the house style's form): the words the reader would
   search.
6. **Write** the shape of the type (the house style's, else DOC-020 to DOC-023) in plain language
   (DOC-030 to DOC-035): the point first, then the sections, steps of one action each, labels exactly as
   on screen and marked the same way in every section (DOC-033). Every section stands on its own: name the
   thing again, never "see above" (DOC-007, DOC-024); a fact that another article holds is linked, not
   restated (DOC-008); the reader's own word for the thing appears once near the top (DOC-009). Nothing the
   reader needs lives only in an image (DOC-043). Link the related articles in the project's link form,
   only to articles that exist (DOC-044).
   Screenshots only where the UI is hard to find; when one is needed and missing, say which and where,
   do not invent a file.
7. **File** (DOC-060 to DOC-063, or the house style): the file name, the folder, the frontmatter. A translation records `source`
   and `source_commit`.
8. **Style, check, show, commit** as the procedure's steps 5 to 7 say. Read the article once as the
   reader: someone who has never seen this screen, with the app open beside it. Whatever they would still
   ask goes in, or is asked now.
9. **Hand over**: the file path, the check result, and what the user can do next (`/docs:push` when
   it should go live). Never push from here.
