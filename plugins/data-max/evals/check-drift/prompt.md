---
max_turns: 40
allowed_tools: [Read, Glob, Grep, Write, Edit, Bash, Skill, AskUserQuestion]
tags: [check, drift]
---

This week's export `bookings_export_w42.csv` came in. Can I load it like last week? The spec is `specs/bookings.spec.json` (tenant `alpenhof`, hashing salt `s3cret`), last week's good run left its manifest in `data/clean/bookings.manifest.json`. Don't change anything yet, just tell me.
