---
max_turns: 8
allowed_tools: [Read, Write, Bash, Skill]
tags: [tone, internal, audience]
---

/tone:write Internal note for our team's Linear issue (only engineers see this project). Tighten it but keep what the next dev needs:

"Hey team, so basically I looked into this and it's worth noting that the dedup in the GA4 loader was keying on session_id only. I changed it to (session_id, event_ts) in ga4/dedup.py, commit 8c1d0e7. Hope this helps! Let me know if you have questions."
