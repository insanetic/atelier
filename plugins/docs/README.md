# docs

A [Claude Code](https://claude.com/claude-code) **plugin** for help center articles and developer
documentation: written with you as Markdown files in git, in your house style or a well-tested default
shape per type, compared and rolled back through git, and pushed live only after you have seen the change
and said yes. Part of the
[atelier](../../README.md) marketplace.

```bash
# In Claude Code:
/plugin marketplace add insanetic/atelier
/plugin install docs@atelier
```

It does not care where the articles end up: a hosted help center such as Productlane, Intercom or Zendesk
through whatever tool is connected, a docs repository such as Docusaurus through a pull request, or nowhere
yet, and then the result comes back ready to copy and paste. Start in the repository that holds your
articles with `/docs:setup`.

---

## The idea

- **Git is the source of truth.** Every article is a Markdown file; every change is a commit. A help center
  that keeps no versions gets them from git, and every push is a commit with a `Docs-Published:` trailer,
  so "what was live last Monday" is one `git log` away.
- **Nothing goes live by accident.** Only `/docs:push` writes outside the files, only from a committed
  article that passes the check, only after showing what changes against the live version, and only after
  your yes. A hook enforces it.
- **Your style, or a good default.** A help center that already has its own style keeps it: `/docs:setup`
  reads your articles and writes the house style down as numbered rules. Without one, the plugin's defaults
  apply. The rules that matter everywhere (only verified facts, nothing secret, plain language, accessible,
  links that resolve) hold either way.
- **Two readers, two skills.** Users get plain language, numbered steps and the UI's own words. Developers
  get exact signatures and examples that run, checked against the source. One convention holds what they
  share.

## The convention

[`CONVENTION.md`](CONVENTION.md) is the whole of it, readable without the plugin. Every rule is either
*universal* (holds everywhere) or a *default* (holds until your house style says otherwise). In short:

- **One reader per article** (`user` or `developer`), always. By default **one type**, each answering one
  kind of question:

  | Type | Reader | Sections after the first paragraph (required in bold) |
  |---|---|---|
  | `how-to` | user | Before you begin · **Steps** · If it doesn't work · Related articles |
  | `troubleshooting` | both | Cause · **Solution** · Still not working? · Related articles |
  | `overview` | user | **What you can do** · How it works · Good to know · Related articles |
  | `reference` | user | free sections · Related articles |
  | `quickstart` | developer | **Before you begin** · **Install** · free · **Check that it works** · **Next steps** |
  | `how-to` | developer | Before you begin · **Steps** · Check that it works · Next steps |
  | `reference` | developer | **Signature** · Parameters · Returns · Errors · **Example** · Related articles |
  | `concept` | developer | **How it works** · When to use it · free · Related articles |
  | `faq` | both | one `##` question each, in the reader's words · Related articles |

  German headings are defined too (`Voraussetzungen`, `Schritte`, `Falls es nicht klappt` …).
- **FAQ answers are short** (universal): at most three sentences, linking to the article that covers it
  when there is one; a question that needs steps gets its own how-to, which the FAQ points to.
- **Links resolve** (universal): links to other articles in your project's one form (relative `.md` paths
  for Docusaurus and the like, `[[Title]]` for Obsidian, or the target's own form), only to articles that
  exist. At push each one is looked up at the target, by ID or exact title, never built from a title,
  because renamed articles keep their old address.
- **The point first.** The title is what the reader searches for (a how-to starts with the verb, ≤ 60
  characters); the first one or two sentences say what they will achieve.
- **Plain language for users** (about CEFR B1, universal): sentences ≤ 25 words, no "simply" or
  "einfach", one action per step, at most seven steps, labels exactly as on screen and marked the same way
  everywhere (default: **bold**, menu paths as **Settings** > **Billing**), no code, `Sie` or `du` but
  never both.
- **Every section stands on its own** (universal): help tools and AI assistants retrieve single sections,
  and support sends single sections. No "see above", the thing named again, one fact in one place, the
  reader's own word mentioned once, nothing only in an image, tables without empty cells or ✓/✗.
- **Articles follow the product** (universal): updated or removed when the product changes; `docs stale`
  lists articles nobody touched for months.
- **Verified for developers:** every signature and default from the source, samples that were run and run
  as they stand, placeholders like `API_KEY` explained below the block, expected output where the reader
  checks it, `applies_to` versions, deprecations with their replacement. Endpoint references add
  authorization, request and response.
- **Files** (default): in a docs repository, its own layout. For a hosted help center,
  `helpcenter/<collection>/<slug>.md`, translations as `<slug>.de.md` next to the source, images in
  `images/<slug>-<what>.png`, the target's article ID in the frontmatter, nothing else about history in the
  file.

## The skills

| Skill | Use it to |
|---|---|
| `/docs:setup` | set up a repository: where the articles live and go, and your house style inferred from your articles, written to `.claude/rules/docs.md` |
| `/docs:guide` | write or revise an article for users: how-to, troubleshooting, overview, reference, FAQ |
| `/docs:devdoc` | write or revise developer docs: quickstart, how-to, reference, concept, troubleshooting, FAQ |
| `/docs:check` | check articles against the convention and your house style, and fix them when you say so |
| `/docs:diff` | compare two versions, the working copy with what is live, or the live help center with git, by meaning first |
| `/docs:push` | put one or more articles live (or as drafts), or open the docs repository's pull request |
| `/docs:rollback` | restore an earlier version as a new commit and push it |
| `/docs:pull` | bring an article or collection from a hosted help center into git, when needed, or take over edits made there |

Every skill follows [`PROCEDURE.md`](PROCEDURE.md): read the house style, find where the articles live, read what exists, ask for
missing facts once, draft, apply a writing-style skill if one is installed, check, show, commit when you
are happy, and for anything live: confirm, write, record.

### Docusaurus and other docs repositories

The skills work right inside the docs repository: they follow its folders, sidebar keys, i18n layout and
components, and add only `type` and `reader` to the frontmatter. Git there already holds the history and
the deployed branch is what is live, so `pull` is not needed and `push` opens a pull request.

### Setting up a repository: your house style

Run `/docs:setup` in the repository that holds the articles. It finds where they live and where they go,
reads three to five of your articles, and infers your house style: file names, whether there is
frontmatter, headings and sections, how buttons and menus are marked, callouts, FAQs, the link form,
images. It asks only what it cannot see (language and address, screenshot standards, which sources Claude
may use for facts, words to avoid), then writes `.claude/rules/docs.md` after your yes: numbered entries
`DOC-1xx` in the [rulebook](../rulebook) format. [`examples/docs.md`](examples/docs.md) shows what such a
file looks like.

- **The skills read it every time** and follow it in place of the defaults it names.
- **`DOC-100`** makes Claude use these skills whenever an article is written, so a plain "write a help
  article" does not bypass them.
- **The rulebook plugin** can enforce it separately: `rulebook check` keeps the file well-formed and
  `rulebook:review` reviews a change against its entries.
- **Facts from code:** looking into your product's code or running a mock server is not this plugin's job.
  If you want Claude to, name the place in a house-style entry; Claude then gathers the facts there and
  hands them to the writing skill.

The hook needs no setup: it is active while the plugin is enabled.

### A writing-style plugin

When a writing-style skill is installed (for example a tone plugin), every article's wording goes through
it before the check, written for an external reader. The convention and your house style win on structure,
headings and limits.
Nothing names another plugin; without one, nothing changes.

---

## Which skill when

### In what order

1. **Once per repository: `/docs:setup`.** Before anything else in a repository that holds articles. It
   writes the house style and where the articles go; without it the defaults apply. Run it again with
   `update` when the style changes.
2. **Write: `/docs:guide` (users) or `/docs:devdoc` (developers).** For a new article and for every
   change to one. You work on the text together until you are happy; it is committed then. Nothing goes
   live from here.
3. **Optional check: `/docs:check`.** To review one article or a whole folder against the rules, or to
   fix them. `push` runs the check itself, so this is not a required step.
4. **Go live: `/docs:push`.** Shows what changes against the live version and waits for your yes. In a
   docs repository (Docusaurus …) it opens a pull request instead.

Then, when needed:

- **What changed? Is the live article still ours?** `/docs:diff`.
- **The live article is wrong:** `/docs:diff <article> live` to see what is live, then `/docs:rollback`,
  which pushes the older version after your yes.
- **An article exists only in the hosted help center, or someone edited it there:** `/docs:pull`. The
  other skills call it for you when they need it.

### Which skill for what

| Situation | Skill |
|---|---|
| New repository, new team, or the style changed | `setup` |
| "Write / update an article on …" for users, including FAQs | `guide` |
| SDK, API, quickstart, reference, developer FAQ | `devdoc` |
| "Is this article ok?", "check the folder", fix findings | `check` |
| "What changed since …?", "is the live version still ours?", stale translations | `diff` |
| "Push it", "put it live", "update Productlane", "open the docs PR" | `push` |
| "Go back to last week's version", "undo the last change live" | `rollback` |
| "Get the article from Productlane", "someone edited it online, take that over", "import a collection" | `pull` |

### Which skill calls which

| Skill | Calls or hands over to | When |
|---|---|---|
| `setup` | `docs check --house-style` | at the end, on two existing articles, to prove the rules fit |
| `guide`, `devdoc` | `pull` | the article exists only in the hosted help center: pulled first, so the change starts from what is live |
| `guide`, `devdoc` | a writing-style skill (such as tone), `docs check`, `docs links` | every draft |
| `guide`, `devdoc` | → you call `push` | when the article should go live; they never push themselves |
| `check` | `rulebook:review` (optional) | to review a whole change against the house style entries |
| `diff` | `pull` (offered) | the live article differs from what was pushed last |
| `diff` | `guide` / `devdoc` (offered) | a translation is behind its source |
| `push` | `check` (offered) | the article has check errors: push stops |
| `push` | `pull` (offered) | someone changed the live article: push stops for it until it is pulled |
| `push` | `docs render`, the target's tools, the hook | every push |
| `rollback` | `diff` | before restoring: is the live article what we pushed? |
| `rollback` | `push` | to put the restored version live, with the usual confirmation |
| `pull` | → `guide`, `devdoc`, `check` | findings in the pulled article are reported as work for later; pull never changes the text |

Only `push` (and `pull`'s reads) talk to the help center; only `push` writes to it, and only after your
yes. Every skill can be called on its own; the calls above are what happens inside it.

---

## `docs`

On the `PATH` while the plugin is enabled. Python 3.9+, no dependencies, no network.

```bash
docs check [--json] [--lang en|de] [--house-style] [--reader user|developer] [--type T] <file|->...
docs links [--json] <file>                       # links to other articles and images, resolved locally
docs history [--json] <file>                     # every version, marked where it went live
docs stale [--json] [--months N] <folder>        # articles not changed for N months (default 12)
docs render [--target productlane|docusaurus|markdown|plain] [--at <commit>] [--draft] [--house-style]
            [--links <map.json>] [--assets <map.json>] [--out <file>] <file>
docs diff [--json] <old> <new>                   # normalised, so a body read back from a target compares
```

`check` decides, with the defaults: frontmatter, reader and type, title and description, the first paragraph, the sections and
their order per type with the fixed headings (synonyms and wrong language caught), heading levels, the step
count, sentence length, judging and filler words, `Sie` and `du` mixed, alt text, link text, missing link
targets, callouts, code in user articles and code blocks without a language, placeholders, secrets,
internal hosts, FAQ questions and answer length, and translations whose source changed. With
`--house-style` it checks only the universal rules (facts and placeholders, secrets and internal hosts,
sentence length and judging words, `Sie` and `du`, alt text and link text, links that resolve, steps per
procedure, code for users), and the shape is judged against your house style by the skills or
`rulebook:review`. Exit 0 without errors, 1 with errors, 2 on a usage error. It reports; it never rewrites.

`links` lists every link to another article (relative path or `[[Title]]`) and image, with the file it
resolves to and that article's IDs at targets; exit 1 when one does not resolve.

`render` produces the body to push from a **committed** version that passes the check: no frontmatter,
callouts as quotes for targets without them, links to other articles and images rewritten to the addresses
in `--links` and `--assets`, which `/docs:push` fills by looking each one up at the target. It refuses
uncommitted changes, check errors, links without an address and `status: draft` (unless `--draft`). `--at` renders a
past version for comparing.

## Nothing goes live without git and your yes

The skills show what changes and wait for your answer, but a model can skip that step. So the plugin ships a
hook that runs before any write to a hosted help center (an MCP tool of Productlane, Intercom, Zendesk, Help
Scout, Document360, GitBook, ReadMe, Mintlify and similar that creates, updates, deletes or publishes
articles, or a `curl`/`wget`/`httpie` call to one):

1. An article body that `docs render` did not produce from a committed, checked article is sent back
   unwritten. Editing the text between render and write, or writing straight into the help center, does
   not get through.
2. Otherwise Claude Code asks you, naming the article file and commit that goes live.
3. Writes without a body (delete, move, rename) are always asked.

Reads are not affected. In a docs repository, pushing is a pull request you merge yourself. To switch the
hook off, set `DOCS_CONFIRM_PUBLISH=0` under `env` in your settings.

---

## Layout

```text
plugins/docs/
├── .claude-plugin/plugin.json
├── CONVENTION.md                  # the Docs Convention, DOC-0xx
├── PROCEDURE.md                   # how every skill reads the house style, checks, confirms, pushes, records
├── bin/docs                       # runs lib/docs.py
├── hooks/publish_gate.py          # before every help center write: rendered from git, then ask
├── lib/docs.py                    # check, links, history, stale, render, diff
├── skills/{setup,guide,devdoc,check,diff,push,rollback,pull}/SKILL.md
├── examples/docs.md               # an example house style, as /docs:setup writes it
├── tests/test_docs.py             # also checks the script's tables against CONVENTION.md
├── tests/test_publish_gate.py     # which calls are help center writes, and when they are sent back
└── evals/                         # one case per scenario, without a help center
```

## Develop

```bash
python3 -m unittest discover -s plugins/docs/tests
claude plugin validate --strict plugins/docs
claude plugin eval plugins/docs --runs 2 --judge-model sonnet --scaffold --allow-tools Bash Write Edit
```

The cases that need a repository with history (push, rollback, pull, Docusaurus) are `case.yaml` files
with a `scaffold.sh` that builds a small help center repository; `--scaffold` runs it and `--allow-tools`
lets the article be written, checked and committed.
