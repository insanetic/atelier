---
name: setup
description: >-
  Use when docs or a help center should be set up for this plugin in a repository, or its house style
  written down or updated: "richte die Doku ein", "set up the help center here", "set up docs for this
  repo", "write down our help center style", "our articles look different, adapt to them", "update our
  docs rules". Finds where the articles live and where they go, reads existing articles to infer the house
  style (headings, file names, frontmatter, links, callouts, how labels and menus are marked), asks only
  what it cannot see, and writes `.claude/rules/docs.md` as numbered rulebook entries after a yes.
argument-hint: "[folder or repository] [update]"
---

# Setting up docs in a repository

Read [CONVENTION.md](../../CONVENTION.md) (above all DOC-090 and which rules are *universal* and which
*default*) and [PROCEDURE.md](../../PROCEDURE.md) (steps 0 to 2). The result is one rules file the other
skills read every time; the plugin itself installs nothing else. Its hook is already active while the
plugin is enabled.

```
$ARGUMENTS
```

1. **Where.** The repository that holds the articles (procedure step 1): a docs-tool repository, a
   `helpcenter/` folder, an Obsidian vault, or nothing yet (then ask where, offering `helpcenter/`). The
   target (procedure step 2): the docs tool's own deploy, or which hosted help center and workspace. Read
   the connected tool only; never write to it here.
2. **What is there.** An existing `.claude/rules/docs.md`: read it, this is an update; keep its IDs, change
   only what the user wants or what the articles now contradict, and never renumber. Other rules files that
   speak about docs or tone: note them, do not repeat them.
3. **Read the articles.** Take three to five representative existing articles from different folders (local
   files, or read from the target when nothing is local). Infer, each with one example from the articles:
   - file names and folders (slug, or the title as the file name; category folders);
   - title source (frontmatter, first heading, file name) and whether there is frontmatter at all;
   - the types in use and each one's sections, their order and heading form (`#` or `##`, questions or
     fixed words), separators (`* * *`), list markers;
   - how buttons, menus, menu paths, icons and field values are marked;
   - callouts, FAQ or Q&A sections, links to other articles (relative path, `[[Title]]`, the target's own
     links by title), images (in the repository or hosted at the target, size, theme);
   - language, form of address, punctuation habits.
   Where the articles follow the defaults, write no entry for it: the default applies. Where they agree on
   something else, that is the house style. Where they disagree with each other, ask which one is meant.
4. **Ask once** for what the articles cannot show, with your inference as the proposed answer: target and
   workspace, language(s) and address, whether FAQs are wanted, screenshot standards and how screenshots
   are made, which sources Claude may use for facts (for example the app's code at a path, a mock server,
   the vendor's API docs; the plugin uses them only because this file names them), words to use and to
   avoid, required sections for some folders, commit message form.
5. **Draft `.claude/rules/docs.md`** in the rulebook format, with a one-paragraph header saying that it is
   this project's house style for the docs plugin and wins over the plugin's defaults. Entries:
   - `DOC-100 [MUST]` help center articles and docs go through the docs skills (always);
   - `DOC-101 [MUST]` where the articles live and where they go, with the link and ID lookup at the target;
   - `DOC-102` language and address;
   - from `DOC-110` on, one entry per house-style rule: `### DOC-1nn [MUST|SHOULD] <the rule>`, one or two
     sentences, the default it replaces named in words ("Replaces the plugin's default sections and
     headings."; not by the plugin's IDs, which `rulebook check` does not know), then the lines in this order: `- Good:` and/or
     `- Bad:` taken from the real articles, `- Checked by: review` (or `docs check` for a universal rule it
     only sharpens), and for a SHOULD what outweighs it.
   One checkable rule per entry; a table only where the rule is a table (sections per type). Nothing that
   restates a universal rule unchanged.
6. **Show and write.** Show the whole file (for an update, the diff) and ask once. Write it after the yes.
   When the rulebook plugin is installed, run `rulebook check` and fix what it reports.
7. **Prove it.** Run `docs check --house-style --reader <reader>` on two of the articles read in step 3 and
   report what is left: universal findings in existing articles (missing alt text, links that do not
   resolve, placeholders) are work for later, not reasons to change the house style.
8. **Report**: the file, the entries in one line each, what the check found, and that the hook needs no
   setup (`DOCS_CONFIRM_PUBLISH=0` in settings switches it off). Commit the file only when the user says so.
