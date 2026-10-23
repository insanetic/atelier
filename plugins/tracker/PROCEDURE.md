# How every tracker skill works

The steps every skill of this plugin follows around its own job. `CONVENTION.md` (next to this file) says
what the text looks like; this file says how it gets into the tracker. Rule IDs are the convention's.

## 1. The tracker

- Use whatever tracker tool is connected in this session: an MCP server or a CLI for issues and tasks.
  Find it by what it offers (find issues, create issue, add comment, list labels or statuses).
- **None connected:** do everything up to step 6, then hand the result over to copy and paste (see
  **Copy and paste**). Say once that nothing was written.
- **More than one:** a rule in context decides; otherwise ask which one.

## 2. The target

- Team or board, and project or list, from the request, the issue being worked on, and rules files in
  context (for example "this repository goes to team X, project Y"). Ask when it is not plain; never take a
  default you happened to see earlier in the session.
- For an existing issue, fetch it by its ID and confirm it is the one meant, not a same-named neighbour.

## 3. Live discovery and mapping

- Look up what the target has, only as far as the job needs: labels, statuses, users, link types.
- Map the convention's kind, result or handoff onto them by meaning, using the workspace's spelling
  (see the convention's **Mapping onto a tracker**). A rule in context may fix a mapping.
- No counterpart for a label: go on without it and say so, or offer to create it, and create only after a
  yes. No counterpart for a needed status: ask.

## 4. Audience and language

- **Audience** is `external` (CI-001) unless the user says the text is internal, or a rule in context marks
  the team or project as internal-only.
- **Language:** the language the issue or thread already uses. New issues: a rule's default language,
  else the language of the user's request.
- **Address** (German and any language with a formal you): as the thread does, as the reporter wrote, or as
  the user said. Nothing to go on: `Sie` for external, `du` for internal. One form throughout.

## 5. Facts

Only what the user, the conversation or the work shows (CI-004). Collect what the shape needs and the
context lacks, and ask for all of it in one question, with concrete options where there are some. Optional
facts that are missing mean the section is left out (CI-005).

## 6. Draft and check

1. Write the draft in the convention's shape.
2. If a writing-style skill is available in this session, apply it to the wording now. The convention wins
   on structure: sections, leads, results and limits stay as they are.
3. Save the draft with its frontmatter to a file in the scratchpad and run `tracker check <file>` (the
   `tracker` command is on the PATH while this plugin is enabled):

   ```
   ---
   type: issue | comment
   kind: bug | feature | improvement | task                              # issue
   purpose: progress | decision | question | blocker | handoff | close   # comment
   result: done | wont-do | works-as-intended | duplicate | cant-reproduce | obsolete   # close
   audience: external | internal
   ---
   ```

4. Fix every `error` and check again. A finding may be set aside only when a rule in context allows it
   (for example a longer comment limit) or the match is plainly not what the rule means; list it under
   **Dismissed** in the confirmation with the reason. A `note` is for judgement.

## 7. Confirm

Show every write in one message, exactly as it will be posted, and ask once (a question with the options,
not a wall of text):

```
<ID or "new issue"> · <team / project>
Kind: <kind> → label <label>   Status: <status>   Assignee: <person>
<title>
<body or comment>
```

Several writes in one flow (issues, comments, status changes) are confirmed together; the user may pick
some and drop others. Nothing is written before the yes. A rule in context may waive confirmation for a
named action; nothing else does.

## 8. Write and report

Write in this order: issue, then fields (kind label, status, assignee, links), then comment. Fetch the
result back to see it landed. Report one line per write: ID, link, target, and what was set. If a write
fails, stop, say what was and was not written, and do not retry blindly.

## Copy and paste

With no tracker connected, hand over each item like this, nothing else around it but one line saying
nothing was written:

````
**Title**
```
<title>
```
**Description**
```
<body>
```
**Set:** kind label `<kind>`, status `<status>`, assignee `<person>`, link to `<ID>`
````

A comment goes in a single code block, with the status to set under it.
