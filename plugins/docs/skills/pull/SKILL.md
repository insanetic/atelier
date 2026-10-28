---
name: pull
description: >-
  Use when an article from a hosted help center (Productlane, Intercom, Zendesk …) should be brought into
  git, or when the live version was edited outside git: "hol den Artikel aus Productlane", "pull the help
  center article so I can edit it", "import our existing articles", "someone changed it online, take that
  over". Fetches the live article (one, several or a collection, on demand), writes it as a local Markdown
  file in the convention's layout with its target ID, and records it as live in git. Never changes the
  live help center. Not needed for docs that already live in a repository (Docusaurus …).
argument-hint: "<article title, ID, link or collection>"
---

# Pulling articles from a hosted help center

Read [CONVENTION.md](../../CONVENTION.md) (DOC-060 to DOC-063, DOC-070) and [PROCEDURE.md](../../PROCEDURE.md).
Articles are pulled when they are needed, not all at once: when one is to be changed, compared or rolled
back, or when the user asks for a collection.

```
$ARGUMENTS
```

1. **Where and from where.** The local folder (procedure step 1, a hosted help center folder) and the target
   (step 2). A docs-tool repository needs no pull: say so and stop.
2. **Which articles.** By ID, link, title or collection, read from the target (its list and get tools).
   Several match a title: ask. A collection: list its articles first and confirm the list.
3. **Already local?** Find the file by its target ID in the frontmatter, then by slug.
   - Not local: new file at `<folder>/<collection>/<slug>.md` (DOC-060, DOC-061), slug from the title.
   - Local and the live text differs from the last published or pulled version (drift): show the
     [diff](../diff/SKILL.md) and ask whether the live text replaces the local one. Uncommitted local
     changes are never overwritten: ask to commit or set them aside first.
4. **Convert, do not rewrite.** Body as the target returns it in Markdown (keep its tabs, code groups and
   raw HTML as they are); frontmatter from what the target knows: `title`, `description` (only if the
   target has one), `type` and `reader` (from the content; ask when unclear), `lang`, `order`, and the
   target ID (`productlane: <id>`). Images: download them into `images/` with the convention's names only
   when the user wants local copies; otherwise keep their URLs. Do not fix the text while pulling: the
   pulled file must be what is live.
5. **Check, do not fix.** Run `docs check` and report the findings as work for later
   ([guide](../guide/SKILL.md), [devdoc](../devdoc/SKILL.md) or [check](../check/SKILL.md) with fix).
6. **Record** (procedure step 9) with a `Docs-Pulled:` trailer per article, in one commit:
   `docs: pull <slug or collection> from <target>`. Show the commit before making it when it replaces local
   text; a first pull of new files is committed after saying what will be committed.
7. **Report**: the files, their check results, and the next step the user asked for.
