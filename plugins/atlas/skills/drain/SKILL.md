---
name: drain
description: Works through what the atlas lint found in the user's personal brain, one finding at a time with the user - re-verify, supersede, archive, merge or fix.
disable-model-invocation: true
argument-hint: "[kind of finding to work on, e.g. overdue]"
---

# Draining the brain

The lint names what needs attention; the user decides what happens to it. You propose one action per finding and
carry it out only after they agree.

## Steps

1. Run `atlas check`. If it reports nothing, say so and stop.
2. Tell the user the counts per kind, then work through them in this order: `schema`, `duplicate`, `broken-link`,
   `supersede`, `expired`, `overdue`, `misplaced`, `orphan`, `inbox`. If they named a kind, do only that one.
3. For each finding, read the note (`atlas get "<title>"`), then propose the one action that fits and wait for a yes.
   When several findings of a kind call for the same action, offer them as one batch.
4. Run `atlas check` again at the end and report what is left.

## The action for each kind

| Kind | Ask | Then |
|---|---|---|
| `schema` | Nothing, unless a value has to be guessed | Fill the field with `atlas set`; add frontmatter to a bare file by hand |
| `duplicate` | Which note survives | Move the text worth keeping into the survivor, then `atlas merge "<dup>" --into "<survivor>"` |
| `broken-link` | Create the missing note, point at an existing one, or drop the link | `atlas new …`, or edit the link |
| `supersede` | Which note replaced it | `atlas set "<old>" "superseded_by=[[New]]"`, or `atlas supersede` if it was never closed |
| `expired` | Is it still true | Still true: `atlas set "<title>" valid_to=`. Changed: write the new note, then `atlas supersede`. Simply over: `atlas archive` |
| `overdue` | Is it still true | Yes: `atlas verify`. Changed: new note and `atlas supersede`. No longer matters: `atlas archive` |
| `misplaced` | Live or closed | Active in the archive: `atlas restore` if it should be live, else `atlas archive` to mark it. Closed in `notes/`: `atlas archive` |
| `orphan` | Where it belongs | Link it from a hub or a related note, or `atlas archive` if it is not worth keeping |
| `inbox` | Note, or nothing | Turn it into a note (`atlas new`, after `atlas find`), or delete the capture |

## Hold to

- **Never decide for the user** whether something is still true. Show the note's description and its `verified`
  date, and ask.
- **Never delete a note.** Archive it; git keeps the history either way. Inbox captures may be deleted once handled.
- **Supersede, do not rewrite,** when a fact changed.
- **Stop when the user stops.** A partly drained brain is fine; the next pass picks up the rest.
