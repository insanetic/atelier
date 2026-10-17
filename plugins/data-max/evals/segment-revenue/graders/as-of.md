---
type: llm
weight: 3
---

Revenue is attributed to the segment at order time via a snapshot plus an as-of join; the period before the first snapshot is backfilled (sample/README: c1 was silver until 2026-09-01) or labelled unknown. Fail if past orders get today's segment.
