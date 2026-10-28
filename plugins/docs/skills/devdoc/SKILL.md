---
name: devdoc
description: >-
  Use whenever developer documentation is written or revised: SDK or API docs, a quickstart or getting
  started guide, an integration how-to, a reference page for a function, class, endpoint or webhook, a
  concept page, or a developer troubleshooting page ("schreib die SDK-Doku", "document this endpoint",
  "quickstart für unser SDK", "update the API reference", "explain how webhooks work for developers").
  Verifies every signature and example against the source, never invents an API. Works on a local
  Markdown file in git (a docs repository such as Docusaurus, or a helpcenter/ folder), never publishes.
  Not for end-user help articles: that is guide.
argument-hint: "<topic, symbol, endpoint or article file> [source path]"
---

# Documentation for developers

Read [CONVENTION.md](../../CONVENTION.md) and [PROCEDURE.md](../../PROCEDURE.md), and follow the procedure
around these steps. The reader knows how to code, not our product; they copy the examples and expect them
to run.

```
$ARGUMENTS
```

1. **House style and place** (procedure steps 0 and 1). The house style, when there is one, decides
   the shape, headings, file name and link form, in place of the defaults. An existing page: read it, its neighbours and `docs history <file>`. Only
   in the hosted help center: [pull](../pull/SKILL.md) it first.
2. **Already covered?** Search the docs for the same symbol, endpoint or task. Change or link to what
   exists.
3. **Type** (DOC-002): from nothing to a first result is a `quickstart`, one task a `how-to`, one function,
   class or endpoint a `reference` (an endpoint adds Authorization, the request and the response, and
   states pagination, rate limits and idempotency or links them), how and why a `concept`, an error a `troubleshooting`, short answers
   to recurring questions a `faq` (DOC-006). A page mixing
   tutorial and reference becomes two.
4. **Source** (DOC-050). Read the source the user, the repository or the house style points to: the
   code of the SDK or API being documented, its schema (OpenAPI, GraphQL, protobuf) or its generated
   reference: signatures, types, defaults, errors, the version that introduced it. Do not go looking
   through other code bases on your own. The source is not at hand: ask for it or for the facts. Never document from memory, from a similar library, or from
   what the name suggests. Note `applies_to`.
5. **Examples** (DOC-051, DOC-052): a sentence before each sample saying what it does; complete and
   runnable, with imports and setup; placeholders like `API_KEY` explained right after the block; no shell
   prompt; the expected output in its own block where the reader checks it. Credentials come from what the
   SDK reads, never a literal key. Introduce no names that look like product
   conventions but are not in the source: an environment variable, a config file, an import path. When the environment allows, run the example
   (or the repository's tests for it) and paste the real output; say when it could not be run.
6. **Write** the type's shape (DOC-020 to DOC-022) with the fixed headings: first the point, then the
   sections. Parameters as a table with no empty cells; every documented error with when it happens and
   what to do. A deprecated element says since when, its replacement and the migration how-to (DOC-053).
   A reference links to the how-tos that use it, a how-to to the reference of each API it calls. Next
   steps and related articles link only to pages that exist; when there are none yet, ask which pages are
   planned rather than filling the section with more examples.
7. **File** (DOC-060 to DOC-063). In a docs-tool repository, its own layout, sidebar keys and components.
8. **Style, check, show, commit** as the procedure's steps 5 to 7 say. Read the page as the reader with
   an empty project: every step they would get stuck on is fixed or asked.
9. **Hand over**: the file, the check result, what was verified and how (read in the source, example run),
   and `/docs:push` when it should go live. Never push from here.
