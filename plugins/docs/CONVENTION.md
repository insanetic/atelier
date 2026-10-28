# Docs Convention 0.3.0

A convention for help center articles and developer documentation: what an article looks like, where its
file lives, how it links to others, and how its versions are kept. It does not care whether the article
ends up in Productlane, Docusaurus, Obsidian, another docs tool or nowhere yet. Every rule has an ID that
tools and reviews cite.

Why: people open a help article in the middle of a task, scan it, do the next step and leave. Most read
only the title, the first sentence and the steps. A fixed shape per type puts what they came for where
they look, keeps every article findable by the words they search, and makes two versions of the same
article comparable line by line.

**Universal and default rules.** Rules marked *universal* hold for every article everywhere. Rules marked
*default* describe a good shape and format when a project has none; a project's house style (section 11)
may replace them. A help center that already has its own established style keeps it.

---

## 1. Readers and types

### DOC-001 One reader per article · universal

| Reader | Who | Writes for them |
|---|---|---|
| `user` | anyone using the product, often without technical knowledge | `docs:guide` |
| `developer` | someone building on the product: SDK, API, integrations | `docs:devdoc` |

An article never serves both. When both need the same topic, write two articles and link them.

### DOC-002 One type per article · default

| Type | Reader | Answers | Title |
|---|---|---|---|
| `how-to` | user, developer | How do I get this one thing done? | the task: verb and object, "Export invoices as CSV" |
| `troubleshooting` | user, developer | Something is wrong. How do I fix it? | the symptom as the reader sees it, or the exact error message |
| `overview` | user | What is this, and what can I do with it? | the thing's name, "Invoices" |
| `reference` | user, developer | What exactly are the options, values, limits? | the thing and the aspect, "Roles and permissions", `createInvoice()` |
| `faq` | user, developer | Short answers to questions people ask about one topic | the topic and "questions", "Billing questions" |
| `quickstart` | developer | How do I get from nothing to a first working result? | "Quickstart: <what you build>" or "Get started with <product>" |
| `concept` | developer | How does it work, and why is it built this way? | the idea, "How webhooks are delivered" |

There is no "misc", "notes" or "tips" type. The developer types follow Diátaxis (tutorial, how-to,
reference, explanation): a quickstart is the shortest tutorial, a concept the explanation.

### DOC-003 One job per article · default

One task, one problem, one thing explained. An article that needs "and" in its title, or more than one
`Steps` section, is two articles. Variants of the same task (desktop and mobile, two plans) stay in one
article as a short list or tabs.

### DOC-006 FAQ answers are short · universal

An FAQ, or a questions section inside another article, answers each question in at most three sentences,
and links to the article that covers it when one exists. A question whose answer needs steps or more than
three sentences gets its own article (a how-to, a troubleshooting article), and the FAQ answer points to it.

### DOC-007 Every section stands on its own · universal

Help tools and AI assistants retrieve single sections, not whole articles, and support sends single
sections as links. So each section makes sense read alone: it names the thing again instead of "it" or
"this", and never says "see above", "as mentioned earlier", "below" or "siehe oben". A developer code block
carries its own imports and setup.

### DOC-008 One fact, one place · universal

A fact (a limit, a price, a requirement, a default) is written in one article; others link to it instead of
restating it, so an update cannot leave two versions that contradict each other.

### DOC-009 The reader's words are findable · universal

When readers call a thing differently from the UI ("bill" for **Invoice**), their word appears once in the
description or the first paragraph; the rest of the article uses the UI's word (DOC-033).

## 2. Facts

### DOC-004 Only what is verified · universal

Every label, menu path, step, limit, value, signature, parameter, default and error message comes from:
the user, what the product shows (a screenshot, a recording, the running app), an existing article, the
product's official documentation, or a source a house-style rule names (for example the app's code or a
mock server). For developer documentation, the source code, API schema or generated reference is that
source. Nothing guessed, nothing from memory of a similar product. A missing fact is asked; it never
becomes a placeholder, "TODO", "TBD" or a vague sentence. Unreleased behaviour is not documented until it
ships.

### DOC-005 Never written · universal

- Secrets, real keys and tokens, signed links. Examples use obvious placeholders (`API_KEY`).
- Real customer data in text, examples or screenshots: names, emails, accounts, invoices.
- Internal hosts, internal tools, internal ticket IDs, who built what, and how the text was made.
- Open security weaknesses. Document the safe way, not the hole.

## 3. Title and description

### DOC-010 The title is what the reader searches for · default

At most 60 characters, in the reader's words, not the team's. Shapes per type are in DOC-002.

- No "How to" or "Wie", no question form, no trailing period, no product name unless the help center
  covers several products. (Question-form titles, "How do I reset my password?", are a valid house-style
  choice; some AI help tools match them well. Sources disagree; the default keeps the task form.) A reader's question becomes the task or the symptom: "Why is my export
  empty?" becomes "Invoice export is empty".
- A how-to starts with the verb in its plain form: "Export invoices", "Rechnungen exportieren", not
  "Exporting invoices" or "Invoice export".
- The title is the only H1. The body starts below it.

### DOC-011 The description is one sentence · default

At most 160 characters, saying what the reader can do or learn. It shows in search results and in lists
of articles. It does not repeat the title.

## 4. Shape

### DOC-020 Every article starts with its point · default

The first paragraph, before any heading, says in one or two sentences (developer: up to three) what the
reader will achieve or learn, and for whom or when it applies. No "In this article", no history, no
marketing.

### DOC-021 One shape per type · default

Sections in this order, as `##` headings spelled exactly as in DOC-080 in the article's language.
Required sections are bold, the rest are left out when empty. `*` means free headings of the writer's
choice may stand there.

| Reader / type | Sections after the first paragraph |
|---|---|
| user / `how-to` | Before you begin · **Steps** · If it doesn't work · Related articles |
| user / `troubleshooting` | Cause · **Solution** · Still not working? · Related articles |
| user / `overview` | **What you can do** · How it works · Good to know · Related articles |
| user / `reference` | **\*** · Related articles |
| user / `faq` | **\*** · Related articles |
| developer / `quickstart` | **Before you begin** · **Install** · **\*** · **Check that it works** · **Next steps** |
| developer / `how-to` | Before you begin · **Steps** · Check that it works · Next steps |
| developer / `reference` | **Signature** · Authorization · Parameters · Returns · Errors · **Example** · Related articles |
| developer / `concept` | **How it works** · When to use it · \* · Related articles |
| developer / `troubleshooting` | Cause · **Solution** · Still not working? · Related articles |
| developer / `faq` | **\*** · Related articles |

### DOC-022 What goes in each section · default

- **Before you begin:** a short list of what must be true first: role or permission, plan, what to have
  ready; for developers the versions, accounts and keys. Only what really blocks the task.
- **Steps:** a numbered list, one action per step (DOC-034). Developer steps may carry a code block under
  the step. Long developer procedures may use `### 1. …` subsections instead.
- **If it doesn't work:** the two or three likely failures, each a short bullet: the symptom, then the fix
  or a link to the troubleshooting article.
- **Cause:** one or two sentences, only when the cause is known and helps the reader.
- **Solution:** numbered steps. When there are several causes, one `###` subsection per cause, the most
  likely first, each headed with the condition ("If the export is empty").
- **Still not working?:** what to send to support so they can help at once (what you did, what you see,
  when). Never a support email that is not public.
- **What you can do:** bullets, each a thing the reader can do, linked to its how-to.
- **How it works:** the model the reader needs to predict the product's behaviour. No implementation detail
  for users.
- **Good to know:** limits, plan differences, what happens to existing data. Short bullets.
- **Install:** the one command or step per package manager, in tabs or one block each.
- **Check that it works:** what to run or look at, and the exact output the reader should see.
- **Next steps / Related articles:** two or three links (DOC-044), the most likely next one first.
- **Signature:** the function signature, or for an HTTP endpoint the method and path, in one code block.
- **Authorization:** for an endpoint, the credentials and scopes it needs.
- **Parameters:** a table: Name, Type, Required, Default, Description.
- **Returns / Errors:** what comes back (for an endpoint, the response schema) and every documented error
  or status code, with when it happens and what to do. Pagination, rate limits and idempotency are stated
  or linked from the API overview when they apply.
- **Example:** a complete, runnable example (DOC-051) with its output; for an endpoint, the request and the
  response.
- **Reference and guides link both ways:** a reference page links to the how-tos that use it, a how-to to
  the reference of each API it calls. A reference page gives no instructions.
- **FAQ questions:** one `##` heading per question, in the reader's words, ending with `?`; the answer below
  it follows DOC-006, at most 60 words.

### DOC-023 Length · default

One screen is the goal for users. Above these word counts (body, without code), look for a second article:

| Type | Words |
|---|---|
| user `how-to` | 600 |
| user `troubleshooting` | 500 |
| user `overview` | 500 |
| developer `quickstart` | 15 minutes of reading and doing, with all code |

### DOC-024 The first sentence names the subject · default

The first sentence under each fixed heading names the task or symptom it belongs to ("To export invoices as
CSV:", "If the export is empty:"), so a section found on its own still says what it is about (DOC-007).

## 5. Writing

### DOC-030 Talk to the reader · universal

Second person, active voice, present tense. Steps are instructions in the imperative ("Select **Export**";
German with Sie: "Wählen Sie **Exportieren**"; with du: "Wähle **Exportieren**"). German uses one form of
address for the whole help center, `Sie` unless a rule says `du`, and never mixes them in an article.

### DOC-031 Short sentences · universal

For users, plain language at about CEFR level B1: sentences of 15 to 20 words on average and never more
than 25. For developers, never more than 35. One idea per sentence; paragraphs of at most three sentences.

### DOC-032 Plain words · universal

- No words that judge the reader's task: "simply", "just", "easy", "obviously", "of course", "einfach",
  "lediglich", "natürlich", "kinderleicht", "offensichtlich".
- No jargon for users. A term the reader must know is explained the first time it appears, in a few
  words.
- No filler ("in order to", "please note that", "es ist zu beachten, dass").

### DOC-033 The same word for the same thing · universal

One term per thing across the whole help center, the term the product's UI uses. Labels of buttons,
menus, fields and pages are written exactly as on screen and marked the same way everywhere, in every
section. Default marking: buttons and labels in **bold** without quotes; a path through menus bolds each
step but not the separator: **Settings** > **Billing** > **Invoices**. A house style may mark them differently (for example menu entries as
inline code with `→`); then that marking is used everywhere.

### DOC-034 Steps are one action each · universal

- Where first, then what: "In **Settings**, select **Billing**."
- At most seven steps for users in one procedure; more means grouping or a second procedure.
- The result of a step is in the same step when the reader cannot see it at once ("The export starts.
  You get an email when it is ready.").
- An optional step starts with "Optional:".
- Use "select" for clicking, tapping and choosing unless the house style says "click", so the step works on
  every device. "Enter" for typing.

### DOC-035 Works for everyone · universal

No directions or colours as the only pointer ("the green button on the right"): name the label. Every
image has alt text that says what it shows. Link text names where it goes; never "here", "click here",
"hier" or "this link".

## 6. Formatting

### DOC-040 Headings · default

`##` for sections, `###` inside them, nothing deeper, no level skipped. No H1 in the body. No trailing
punctuation except the question mark of "Still not working?" and of FAQ questions.

### DOC-041 Lists and tables · universal

Numbered lists only for sequences; bullets for everything else; one level of nesting at most. Tables only
for comparing or for reference values, never for layout. Every column has a descriptive header, no cell is
empty, and cells hold words, not ✓, ✗, Y, N, dashes or icons. Limits, defaults and exact values are also
stated in a sentence when the reader needs them to act.

### DOC-042 Callouts · default

At most two per article, in the portable form `:::note`, `:::tip`, `:::info`, `:::warning`, `:::danger`
closed by `:::`. A warning stands before the step it concerns. Nothing the reader needs to finish the task
lives only in a callout. A target that cannot show callouts gets a quote that starts with a bold label
(`> **Note:**`), which `docs render` writes.

### DOC-043 Images · universal

Screenshots only where the UI is hard to find, at most one per step, cropped to the part that matters and
highlighting the element the step refers to, with no real customer data, placed right after the step they
show, never two in a row without text between them. An image never holds the only copy of something the
reader needs: AI help tools read the text, not the image. A GIF only for a movement or flow a still image
cannot show. Screenshots match the article's language; where they cannot, the step text alone is enough. A missing screenshot is named to the user (which one, where), never invented. Where images
are stored, their size, theme and the tools to make them are house style; by default they sit next to the
article (DOC-062).

### DOC-045 No code for users · universal

User articles contain no code blocks. A value the reader must type exactly is written in `inline code`.

### DOC-046 Portable Markdown · default

CommonMark with tables, the callouts of DOC-042, and tabs. No raw HTML except what a target keeps as is.
In a docs-tool repository (DOC-060) the tool's own components are allowed; elsewhere only the tags every
target here understands: `<Tabs>`, `<Tab title="…">`, `<CodeGroup>`.

## 7. Links

### DOC-044 Links between articles · universal

- Every link to another article of the same help center points to that article as a file in the
  repository, in the project's one link form:
  - a relative path, `[Download an invoice](download-invoice.md)` (default; Docusaurus, VitePress, MkDocs);
  - a wiki link by title, `[[Download an invoice]]` or `[[Download an invoice|download it]]` (Obsidian,
    and any repository whose house style says so);
  - the target's own form, when the house style says the files are kept in it (for example Productlane's
    links by title, `[Exact title](https://help.example.com/docs/<path>)`).
- Every link resolves: the file or the title exists. A link to an article that does not exist yet is not
  written; the gap is named to the user.
- The link text names the article or where it goes (DOC-035); when the target shows links as chips with the
  article's title, the sentence is built so the exact title fits.
- External pages are ordinary links. Never internal hosts (DOC-005).

### DOC-047 Links are resolved by the target, never guessed · universal

When an article is pushed, each link to another article becomes that article's address at the target,
looked up through the target itself (its search or list of articles, by the linked article's ID or exact
title). An address is never built from a title or a slug: articles that were renamed keep their old
address. A link that cannot be resolved stops the push for that article and is shown to the user.

## 8. Developer documentation

### DOC-050 Verified against the source · universal

Every signature, parameter, type, default and error comes from the source, the API schema or the existing
reference, and the article names the versions it applies to (`applies_to`). When the source is at hand, it
is read before writing; when it is not, the user is asked.

### DOC-051 Examples run as they are · universal

- A sentence before each sample says what it does. A code block has a language and contains everything
  needed to run it: imports, setup, the call.
- No `...` in parts the reader must have; an omission is a comment in the code's language. Placeholders are
  obvious and explained right after the block ("Replace `API_KEY` with …"); the default form is uppercase
  with underscores and no "your" (`API_KEY`, `CUSTOMER_ID`), as in Google's style guide.
- No names that look like product conventions but are not in the source: an environment variable, a config
  file, an import path. Credentials are read from what the SDK actually reads, never written as a literal
  key.
- No shell prompt (`$`) in blocks meant for copying; output goes in its own block.
- The expected output is shown where the reader checks or uses it, always under "Check that it works".
- Default: install commands and client setup name the version of `applies_to`; when a page covers several
  languages, each tab holds an equivalent, complete sample, in the same order on every page.

### DOC-052 Samples are run · universal

Every sample was run before it is pushed, or the article says it was not. Where the repository can test
samples (doc tests, samples in tested files, a CI job), they live there and the article includes them.

### DOC-053 Deprecations are stated · universal

A deprecated element's reference says since when it is deprecated, when it will be removed if that is
known, what replaces it, and links to the migration how-to. A breaking change gets a changelog entry.

## 9. Files

### DOC-060 Where articles live · default

- **In a docs-tool repository** (Docusaurus, VitePress, MkDocs, Starlight, Mintlify, Nextra, an Obsidian
  vault and the like): the tool's own folders, sidebar, i18n layout and frontmatter keys win. This
  convention adds only its frontmatter keys (DOC-063) and the shape of the text.
- **For a hosted help center** that does not keep versions (Productlane and the like): one folder in a git
  repository, `helpcenter/` unless a rule says otherwise, laid out as
  `helpcenter/<collection>/<slug>.md`, with `helpcenter/<product>/<collection>/<slug>.md` when the folder
  serves several products. A collection folder holds an `index.md` whose frontmatter has the collection's
  `title`, `description` and `order`.

### DOC-061 File names · default

- The slug: lowercase ASCII, words joined by `-`, at most five words, taken from the title in the source
  language, without articles, dates or version numbers: `export-invoices-csv.md`.
- A translation sits next to its source as `<slug>.<lang>.md` (`export-invoices-csv.de.md`); in a
  docs-tool repository it goes where the tool's i18n layout wants it, under the same slug.
- A published article's file name is never changed without updating every link to it (DOC-044) and, where
  the address depends on it, a redirect at the target.
- Order comes from frontmatter (`order`, or the tool's own key such as `sidebar_position`), never from
  number prefixes in file names.

### DOC-062 Images · default

In an `images/` folder next to the articles, named `<slug>-<what-it-shows>.<ext>`:
`images/export-invoices-csv-export-dialog.png`. Shared by translations unless the UI text in the image
differs; then `<slug>-<what>.<lang>.<ext>`.

### DOC-063 Frontmatter · default

| Key | Required | Value |
|---|---|---|
| `title` | yes | DOC-010 |
| `description` | yes | DOC-011 |
| `type` | yes | a type from DOC-002 |
| `reader` | yes | `user` or `developer` |
| `lang` | when the file name or folder does not show it | `en`, `de`, … |
| `order` | no | position in its collection; in a docs-tool repository its own key instead |
| `status` | no | `draft` (never published) or `ready`; absent means ready |
| `applies_to` | developer | the product or SDK versions, `">=2.3"` |
| `source`, `source_commit` | translations | the source file and the commit it was translated from |
| `<target>` | after the first push | the article's ID at that target, `productlane: art_12ab` |

Nothing else goes into frontmatter: no history, no publish dates, no authors. Git holds those (DOC-070).
A house style without frontmatter (the title is the file name) keeps the target's ID where its rule says.

## 10. Versions

### DOC-070 Git is the history · universal

Every change to an article is a commit that touches its file. Pushing to a hosted help center records a
commit with one trailer per article, so the version that went live is a `git log` away:

```
docs: push export-invoices-csv to productlane

Docs-Published: productlane helpcenter/billing/export-invoices-csv.md
```

The article's content at that commit is what went live. A hosted article brought into git from the live
help center is recorded the same way with `Docs-Pulled:` and counts as live at that commit too. In a
docs-tool repository the deployed branch is the published version and needs no trailer.

### DOC-071 Only forward · universal

History is never rewritten. A rollback restores an older version as a new commit and is then pushed like
any change. The live help center is changed only from a committed article (DOC-072).

### DOC-072 Nothing goes live that is not in git · universal

A hosted help center is written only with the rendered body of a committed article that passes the check,
after the user has seen what changes and said yes. A change made directly in the hosted editor is pulled
into git before anything else is pushed to that article.

### DOC-073 Translations follow their source · universal

A translation names the source commit it was made from (`source_commit`). When the source changes in
meaning after that commit, the translation is updated before or with the next push, or marked stale to
the user.

### DOC-074 Articles follow the product · universal

When the UI or behaviour an article describes changes, the article is updated or unpublished in the same
release; an outdated article is removed, not left up. `docs stale` lists articles whose file has not changed
in a given number of months, as a prompt to review them. New articles come from real questions where they
exist: support tickets, failed searches, an AI tool's content-gap report.

## 11. House style

### DOC-090 A project's house style replaces the defaults · universal

A project may set its own house style in `.claude/rules/docs.md` (written by `docs:setup` or by hand):
numbered entries `DOC-1xx` in the rulebook format, each one checkable rule. It may replace any *default*
rule: the types, the shapes and headings, the title and file name form, frontmatter, callouts, how labels
and menu paths are marked, image storage and standards, and the link form. It may add rules: where facts
come from (the app's code, a mock server, recordings), screenshot standards, words to use and avoid,
punctuation, required sections for some folders.

It never replaces a *universal* rule, except where that rule names what may vary (DOC-033, DOC-034,
DOC-043, DOC-044).

Precedence, highest first: an explicit instruction in the request, the house style, the defaults here.
Where a house-style entry and a default disagree, the entry wins and the default is not checked.

## 12. Terms

### DOC-080 The same headings, every time · default

Section headings are spelled exactly as here, in the article's language. A language without a column uses
the English headings until one is added here and to `lib/docs.py`.

| Section | en | de |
|---|---|---|
| before | Before you begin | Voraussetzungen |
| steps | Steps | Schritte |
| trouble | If it doesn't work | Falls es nicht klappt |
| related | Related articles | Verwandte Artikel |
| cause | Cause | Ursache |
| solution | Solution | Lösung |
| still | Still not working? | Weiterhin Probleme? |
| can_do | What you can do | Was möglich ist |
| how_works | How it works | So funktioniert es |
| good_to_know | Good to know | Gut zu wissen |
| install | Install | Installation |
| verify | Check that it works | Prüfen, ob es funktioniert |
| next | Next steps | Nächste Schritte |
| signature | Signature | Signatur |
| params | Parameters | Parameter |
| returns | Returns | Rückgabewert |
| errors | Errors | Fehler |
| example | Example | Beispiel |
| auth | Authorization | Autorisierung |
| when_to_use | When to use it | Wann es passt |

---

## Sources

The shape and the writing rules draw on, checked against current versions on 2026-10-28:

- Diátaxis (diataxis.fr) and The Good Docs Project templates (quickstart, troubleshooting, concept, API
  reference) for the types and shapes.
- The Google developer documentation style guide (procedures, code samples, placeholders, code syntax) and
  the Microsoft Writing Style Guide (step-by-step instructions, UI interactions, code examples).
- GOV.UK content design (titles, plain language, links, structure) and Nielsen Norman Group research on
  FAQs and information scent; WCAG 2.2 (1.3.3 sensory characteristics) for accessible instructions.
- KCS (Consortium for Service Innovation) for troubleshooting articles and content health.
- Guidance from help center and AI-answer vendors on content their assistants read well (Zendesk,
  Intercom Fin, Help Scout, Document360, GitBook, kapa.ai, Vercel): self-contained sections, text over
  images, tables without empty cells, one fact in one place. These are vendor opinions, not research.
- RFC 9745 (Deprecation header) for deprecation notices; Write the Docs on docs as code.

Publishing an `llms.txt` and Markdown copies of pages (llmstxt.org) belongs to the site that serves the
docs, not to articles; the evidence that it helps is weak so far (Vercel, Ahrefs 2026).
