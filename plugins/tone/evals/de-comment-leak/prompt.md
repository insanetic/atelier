---
max_turns: 8
allowed_tools: [Read, Write, Bash, Skill]
tags: [tone, exposure, de]
---

/tone:write Schreib mir bitte einen Kommentar für das Ticket zum Rechnungsexport, der Kunde kann den auf seinem Portal sehen. Meine Notizen:

- Ursache: Jonas hat beim letzten Deploy den Parser in src/export/pdf/notes.ts kaputt gemacht, renderNotes() hat Zeilenumbrüche gestrippt
- Stacktrace war: TypeError: Cannot read properties of undefined (reading 'split') at renderNotes (notes.ts:42)
- Fix ist auf feat/export-notes, commit 3f9a2c1e, läuft seit heute 14 Uhr in Produktion
- Betroffen waren alle PDF-Exporte mit mehrzeiligen Notizen seit dem 20.10.
- Kunde muss die Rechnungen neu exportieren, dann passt es
