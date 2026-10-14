---
name: atlas
description: Use when the user asks about a person, organisation, decision, source or topic they may have recorded ("who is my contact at X", "what did we decide about Y", "what do my notes say about Z"), or asks to remember, save or note a fact or a preference that holds beyond this project, in their personal brain (also called atlas, second brain or notes). Not for the current repository's code or docs, and not for tasks, mail or calendar.
user-invocable: true
argument-hint: "<what to recall, or what to remember>"
---

# Atlas: the user's personal brain

A folder of markdown notes in the user's home directory, the same in every project. You reach it with the `atlas`
command, which is on the PATH while this plugin is enabled. At session start you see only a hint and the user's
standing preferences; nothing else is in your context until you ask.

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
   and the notes that link to it. Run one `atlas` command per call, without `;`, `&&` or loops, so the allow rule
   covers it.
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
     --source "[[Kickoff call 2026-10-01]]" --body "Runs the data team at [[Acme GmbH]]." \
     --from "Acme warehouse migration"
   ```

   - `-d` is one line saying what the note holds. It is what a later search shows, so make it specific.
   - Link other notes with `[[Title]]` in the text. Create the linked note if it should exist.
   - `--from "<hub or note>"` links the new note from where it belongs, so it can be found by following links.
     Choose the topic's hub, else the closest related note, else `Home`. If `new` says nothing links to the note,
     run `atlas link "<hub>" "<title>"`.
   - `--set valid_from=2025-03-01` when the fact started on a known date.
   - `--source` says where it came from: a URL, or a `source` note. Say in the text what you concluded yourself.
3. **When a fact changed, keep what was true before.**
   - A note about something that lasts (a person, an organisation, a topic) is edited in place: change the fields
     with `atlas set`, say in the text what changed and when ("Head of data until 2026-09-30, then [[Kai Berg]]"),
     and `atlas verify` it. Its title and the links to it stay.
   - A note that is a claim at a point in time (a decision, a price, a plan) is replaced: write the new note, then
     `atlas supersede "<old>" --by "<new>"`.
4. **A preference** about how you should work with the user in every project ("short answers", "British spelling")
   is a `preference` note: the title names it, `-d` states it as an instruction. Its description is shown at the
   start of every session, so follow it from then on. A preference that holds only for one repository belongs in
   that repository's memory or CLAUDE.md, not here.
5. **Something not yet worth a note** goes to the inbox: `atlas capture "<one line>"`.
6. **Tell the user what you wrote:** the titles, in one line each.

## Maintain

- `atlas verify "<title>"` when the user confirms a note is still true.
- `atlas set "<title>" key=value` (repeat a key for a list; `key=` clears it), `atlas rename "<title>" "<new title>"`
  (rewrites every link), `atlas archive "<title>"`, `atlas link "<from>" "<to>"`.
- Edits you make in the brain with your edit tools are committed by the plugin's hook. `atlas commit` commits the
  user's own edits when they ask.
- `atlas check` lints the brain. To work through what it finds with the user, use the `drain` skill.

## Hold to

- **Only when the turn calls for it.** Search when the user asks about something they may have recorded; write only
  when they ask you to remember, save or note something.
- **Open few notes, through the command.** Never grep or read the folder wholesale; `atlas find` shows the
  descriptions so you do not have to, and it leaves out what was archived.
- **No secrets.** Do not store passwords, keys or tokens.
- **The files are the user's.** They also edit them in Obsidian, so change a note's text with a targeted edit, never
  by rewriting the whole file.
