# Docs house style

An example of what `/docs:setup` writes to `.claude/rules/docs.md` in the repository that holds the
articles: this project's house style for the docs plugin. Its entries replace the plugin's *default* rules
they speak about; the plugin's universal rules still hold. Replace the example names with yours, or let
`/docs:setup` infer the entries from your existing articles. The format is the [rulebook](../../rulebook)
one, so `rulebook check` accepts it and `rulebook:review` can review a change against it.

### DOC-100 [MUST] Help center articles and docs go through the docs skills

Every help center article or developer doc that is written, changed, compared, pushed, rolled back or
brought in from a help center uses the matching docs skill: docs:guide, docs:devdoc, docs:check, docs:diff,
docs:push, docs:rollback, docs:pull. Load it before drafting.

- Bad: an article written straight into the Productlane editor through its tools.
- Checked by: review

### DOC-101 [MUST] Where the articles live and where they go

The articles live in the category folders at the root of this repository and go to Productlane, workspace
"Acme". Links to other articles and their addresses are looked up with `docs_search_articles` or
`docs_list_articles`, never built from a title.

- Bad: a link to `https://help.acme.example/docs/connections` because the article is called Connections,
  when Productlane keeps it at `data-management/my-data-sources`.
- Checked by: review

### DOC-102 [MUST] English, addressed as you

Articles are written in English and address the reader as "you".

- Good: "Click **Add widget**."
- Checked by: review

### DOC-110 [MUST] The file name is the title

Each article is `<Category>/<Title>.md`, the title written as it appears in the help center, with no
frontmatter and no title heading in the file. Replaces the plugin's default title, file name and
frontmatter.

- Good: `Widgets/Create a widget.md`
- Bad: `widgets/create-widget.md` with `title:` in frontmatter
- Checked by: review

### DOC-111 [MUST] What, why, how, troubleshooting

An article answers, each under its own `#` heading phrased as the reader asks it, in this order: "What is
<topic>?" (2 to 4 sentences), "Why do I need it?" (only for complex topics, 1 to 3 bullets), one "How do I
…?" per task, then "Troubleshooting". Sections are separated by `* * *`. Each section opens with where to
go, so it can be sent on its own. Replaces the plugin's default types, sections and headings.

- Good: `# How do I delete a filter?` followed by "Open the dashboard and select `Filters`." and the steps
- Bad: a `## Steps` section that only makes sense after reading the section above it
- Checked by: review

### DOC-112 [MUST] Data sources say how to connect

Every article in `Data Sources/` has a `# How do I connect <source>?` section with what is needed first
(as a `> **Before you start**` quote), the steps in the source system too, and a link to "Add a data
source". Requirements come from the vendor's official API documentation.

- Bad: a data source article that explains the metrics but not the connection
- Checked by: review

### DOC-113 [MUST] Menus as code, buttons in bold

Sidebar and menu entries are inline code, also on their own; menu paths join them with `→`; the icons
`⋮`, `i` and `x` are inline code; buttons are bold. Replaces the plugin's default marking of labels.

- Good: "Go to `Data sources` → `Connections` and click **Add**."
- Bad: "Go to **Data sources > Connections**."
- Checked by: review

### DOC-114 [MUST] Notes as quotes, at most two

Notes and tips are a `> **Note:** …` quote right after the section they belong to, at most two per
article. Replaces the plugin's default callouts.

- Good: `> **Note:** Widgets refresh every hour.`
- Checked by: review

### DOC-115 [MUST] Screenshots are hosted, 1200 × 627, dark mode

Images are uploaded to Productlane by a person and linked by their absolute URL; they are not stored in
the repository. Screenshots are 1200 × 627 px from a retina capture, in the app's dark mode, cropped to the
part that matters, from an empty test workspace. A missing screenshot is named to the user, never
invented. Replaces the plugin's default image storage.

- Bad: `![](images/widget.png)` in the repository
- Checked by: review

### DOC-116 [SHOULD] Facts from the app

For how a feature works, Claude may read the frontend code in `../acme-web` and start its mock server with
working mock data to look or take screenshots. Outweighed when the user describes the behaviour.

- Bad: steps written from a guess while the frontend code was at hand
- Checked by: review

### DOC-117 [MUST] No em dashes

No em dash (—) anywhere in an article; use a colon, a comma or a new sentence.

- Bad: "Widgets — the building blocks of a dashboard"
- Checked by: review

### DOC-118 [MUST] One commit per article

After each finished article, commit only its file with an English message, `Add article: <title>` or
`Update <title>: <what changed>`. Replaces the commit form of the procedure, step 6.

- Good: `Update Metrics: add troubleshooting for empty values`
- Checked by: review
