---
type: llm
weight: 3
---

Status history is kept as a slowly changing dimension type 2 or snapshot table with validity columns (valid_from/valid_to or equivalent), built from each weekly load; and loads are idempotent (MERGE on tenant_id + booking_id, or a rebuild that gives the same result). Fail if history is not kept or the weekly load appends duplicates.
