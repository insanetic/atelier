---
max_turns: 60
allowed_tools: [Read, Glob, Grep, Write, Edit, Bash, Skill]
tags: [clean, overlap]
---

We download the Google Ads campaign report every week; the last two are in exports/. Load them into Snowflake so the table stays correct when weeks overlap and conversions get revised later. I'm offline for the next hours, so don't wait for me: make sensible assumptions and write them down.
