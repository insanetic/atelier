---
max_turns: 12
allowed_tools: [Read, Write, Bash, Skill]
tags: [tracker, retro, findings, de]
---

Mach mir nachträglich die Tickets für heute. Ich habe den CSV-Export im Umsatz-Report repariert: Umlaute kamen kaputt an, jetzt ist es UTF-8 mit BOM, getestet und fertig. Dabei ist mir aufgefallen, dass der Excel-Export dasselbe Problem hat, das habe ich aber nicht angefasst. Außerdem haben wir entschieden, den Export-Dateinamen mit Datum erst später zu machen. Und im Code steht noch ein neues TODO: "Spaltenreihenfolge konfigurierbar machen". No tracker connected; paste-ready please. Labels Bug, Feature, Improvement, Chore; statuses Backlog, Todo, In Progress, In Review, Done.
