---
type: llm
weight: 3
---

The review handles the decisions the data cannot answer explicitly instead of silently: the key (tenant plus booking number), the timezone of `Erstellt am` (stated as an assumption to confirm, not presented as fact), what to do with guest names and emails (personal data in a shared multi-tenant table), and that weekly overlapping exports of a 6-month window must be merged on the key rather than appended. Pass if all four are addressed with a reason. Fail if a timezone or PII choice is applied without saying it is an assumption.
