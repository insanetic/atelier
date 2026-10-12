---
name: atlas
description: Use when the user asks to recall, look up, remember, save or note something in their personal brain (also called atlas, second brain or notes), or asks what they know about a person, organisation, decision or topic they recorded earlier. Not for the current repository's code or docs, not for tasks, mail or calendar, and not on your own initiative.
user-invocable: true
argument-hint: "<what to recall, or what to remember>"
---

# Atlas: the user's personal brain

A folder of markdown notes in the user's home directory, the same in every project. You reach it with the `atlas`
command, which is on the PATH while this plugin is enabled. Nothing from it is in your context until you ask.

If a command says there is no brain, tell the user to run `atlas init` and stop.

## Recall

1. **Search first, with filters.** One line comes back per note: path, type, description.

   ```bash
   atlas find --text "acme warehouse"                    # every word must appear; title matches first
   atlas find --type person --where "org=Acme GmbH"
   atlas find --type decision --valid-on today
   atlas find --links-to "Jane Doe"
   atlas find --text pricing --all                       # also the archive
   ```

2. **Choose from the descriptions,** then open only what the question needs: `atlas get "<title>"` prints the note
   and the notes that link to it.
3. **Follow links** when the answer is one step away: `atlas links "<title>"`.
4. **Answer from what you read,** and name the notes you used. If the brain has nothing, say so; do not fill the
   gap from memory as if it were recorded.

A note with `valid_to` in the past or status `superseded` is history: say so, and follow `superseded_by` for the
current state.

## Remember

1. **Look before writing.** Search by name and by topic. If a note already covers it, extend that note with your
   edit tools; do not create a second one.
2. **One idea per note,** titled as a person would name it. `atlas types` lists the note types and their fields.

   ```bash
   atlas new "Jane Doe" --type person -d "Head of data at Acme; contact for the warehouse migration" \
     --alias "J. Doe" --set "org=[[Acme GmbH]]" --set "role=Head of data" \
     --source "[[Kickoff call 2026-10-01]]" --body "Runs the data team at [[Acme GmbH]]."
   ```

   - `-d` is one line saying what the note holds. It is what a later search shows, so make it specific.
   - Link other notes with `[[Title]]` in the text. Create the linked note if it should exist.
   - `--set valid_from=2025-03-01` when the fact started on a known date.
   - `--source` says where it came from: a URL, or a `source` note. Say in the text what you concluded yourself.
3. **A fact that changed is never overwritten.** Write the new note, then `atlas supersede "<old>" --by "<new>"`.
4. **Something not yet worth a note** goes to the inbox: `atlas capture "<one line>"`.
5. **Tell the user what you wrote:** the titles, in one line each.

## Maintain

- `atlas verify "<title>"` when the user confirms a note is still true.
- `atlas set "<title>" key=value`, `atlas rename "<title>" "<new title>"` (rewrites every link), `atlas archive "<title>"`.
- `atlas check` lints the brain. To work through what it finds with the user, use the `drain` skill.

## Hold to

- **Only when asked.** Do not search or write the brain unless the user asked for it in this turn.
- **Open few notes.** Never read the folder wholesale; the descriptions exist so you do not have to.
- **No secrets.** Do not store passwords, keys or tokens.
- **The files are the user's.** They also edit them in Obsidian, so change a note's text with a targeted edit, never
  by rewriting the whole file.
