# How every docs skill works

The steps every skill of this plugin follows around its own job. `CONVENTION.md` (next to this file) says
what an article looks like and where it lives; this file says how the skills find it, change it and get it
live. Rule IDs are the convention's.

## 0. The house style

Before anything else, look for the project's house style: a rules file about docs in context
(`.claude/rules/docs.md` of the repository that holds the articles, or `~/.claude/rules/docs.md`), with
entries `DOC-1xx` (DOC-090).

- **There is one:** its entries replace the convention's *default* rules they speak about; the universal
  rules still hold. Run the check as `docs check --house-style --reader <user|developer> <file>`, and judge
  the article's shape, headings, file name, frontmatter, link form and formatting against the entries, not
  against the defaults. When the rulebook plugin is installed, `rulebook:review` can review a change against
  the same entries.
- **There is none, but the repository already has articles in a clearly different style** (other headings,
  no frontmatter, title as file name): do not rewrite them into the defaults. Follow the existing articles
  for this task, say so, and recommend `/docs:setup` once, so the house style is written down.
- **There is none and nothing to follow:** the defaults apply; `docs check <file>`.

## 1. Where the articles are

Work this list down and stop at the first answer:

1. A rule in context names the place ("articles for the Acme help center live in `helpcenter/` of this
   repository and go to Productlane").
2. The user named a file or folder.
3. **A docs-tool repository:** this repository (or the one the user points to) has a `docusaurus.config.*`,
   `.vitepress/`, `mkdocs.yml`, `astro.config.*` with Starlight, `mint.json`/`docs.json`, `theme.config.*`,
   an `.obsidian/` vault or similar. The articles are where the tool keeps them; follow the tool's layout,
   sidebar and i18n (DOC-060). Pushing there means the repository's own flow: a branch and a pull request.
4. **A hosted help center folder:** a `helpcenter/` folder in this repository, or one the user names. The
   target is the hosted help center (step 2).
5. Nothing yet: ask once where articles should live, offering `helpcenter/` in this repository, and
   recommend `/docs:setup`, which writes it down for next time.

Never create a docs folder in a repository where the user did not ask for one.

## 2. The target

Only `push`, `pull` and the live comparisons of `diff` and `rollback` need it.

- **Docs-tool repository:** the target is the repository itself. Nothing is sent anywhere; pushing is a
  pull request.
- **Hosted help center:** whatever tool is connected for it in this session: an MCP server (Productlane,
  Intercom, Zendesk …), a CLI, or its HTTP API with a key the user has set up. Find it by what it offers
  (list, search, get, create, update articles). A rule may name it. More than one: ask.
- **None connected:** do everything up to the confirmation, then hand the rendered body over to copy and
  paste, and say once that nothing went live. The article stays the version in git.
- The article's ID at the target is its frontmatter key named after the target (`productlane: art_12ab`),
  or where the house style keeps it. No ID: it is a new article there; search the target by title first so
  it is not created twice.
- Look up what the target has (collections, languages, draft support) only as far as the job needs, and map
  the article's folder to a collection by name. No match: ask; never create a collection without a yes.

## 3. The reader, the type, the language

- **Reader:** `user` unless the request, the folder or the article says developer (SDK, API, code). Never
  both (DOC-001). `docs:guide` writes for users, `docs:devdoc` for developers.
- **Type:** from what the reader needs, not from the words of the request (DOC-002, or the house style's
  types). Two fit honestly: ask. Two jobs: offer two articles (DOC-003), unless the house style keeps them
  in one.
- **Language:** the article's, or for a new one a rule's default, else the language of the request. German
  uses `Sie` unless a rule says `du` (DOC-030). Default headings come from that language's column (DOC-080).

## 4. Facts

Only what DOC-004 allows. Read before writing:

- the existing article and its neighbours in the same collection, for terms, marking and links;
- for users, the UI's own labels: from the user, screenshots or recordings, existing articles;
- for developers, the source, the API schema or the generated reference (DOC-050);
- any further source the house style names (the app's code, a mock server, the vendor's API docs). Looking
  into a product's code or running it is not this plugin's job: do it only where a rule names the source,
  gather the facts there, and hand them to the writing step; otherwise ask the user.

Ask for everything missing in one question, with concrete options where there are some. Never write a
placeholder.

## 5. Draft and check

1. Write the article in its shape (the house style's, else the default), as a file in its place (step 1),
   not only in the chat.
2. Links to other articles in the project's one link form (DOC-044), only to articles that exist. Run
   `docs links <file>`: every link must resolve.
3. If a writing-style skill is available in this session, apply it to the wording now, for an external
   reader. The convention and the house style win on structure, headings, terms and limits.
4. Run the check (step 0 says which form; the `docs` command is on the PATH while this plugin is enabled).
   Fix every `error` and check again. A finding may be set aside only when a rule in context allows it or
   the match is plainly not what the rule means; tell the user which and why. A `note` is for judgement.
5. Show the user the article (or for a change, the diff, step 7) and work on it with them until they are
   happy. Nothing goes live from a writing skill.

## 6. Commit

An article is versioned by committing its file (DOC-070). Commit when the user is happy with a version or
asks, with a message naming the article: `docs(<slug>): <what changed>`, or the house style's form. Never
commit other files with it, never amend or rewrite a commit that touched an article (DOC-071), and never
`git push` unless asked. In a docs-tool repository, work on a branch unless the user says otherwise.

## 7. Showing a change

A change is shown as `docs diff <old> <new>` against what matters: the last live version for a push, the
previous commit for an edit. Lead with what changed in meaning, in a few bullets (a step added, a label
renamed, a limit changed), then the diff. Formatting-only differences are not changes.

## 8. Confirm

Before anything goes live, show in one message, and ask once:

```
<article path> → <target> (<new | update ID>, <collection>, <draft | live>)
Version: <commit> "<subject>"   Live now: <commit of the last push or pull | not published>
Changes: <the meaning bullets>
<the diff against the live version, or the full body for a new article>
Also: <images to upload, links resolved and to what, translations that may be stale>
```

Several articles in one go are confirmed together; the user may drop some. A request to push is not the
yes: "push it", "stell das live" ask for this confirmation. A rule in context may waive it for a named
case; nothing else does.

The plugin's hook enforces the core of this for hosted help centers: a body that `docs render` did not
produce from a committed, checked article is sent back unwritten, and every write is asked once more.
`DOCS_CONFIRM_PUBLISH=0` switches it off.

## 9. Record

After a hosted push or pull succeeded, record it as a commit (DOC-070), including a new remote ID in the
frontmatter when there is one:

```
docs: push <slug> to <target>

Docs-Published: <target> <path from the repository root>
```

`Docs-Pulled:` for a pull. One trailer line per article; `git commit --allow-empty` when only the trailer is
new. Then report the link to the live article. When the write failed, say so and record nothing.

## Copy and paste

With no target connected, the result of a push is the rendered body (`docs render --out`), the collection
and the title, ready to paste, and nothing is recorded: the live help center does not have it until
someone pastes it. After they confirm it was pasted, record it as in step 9.
