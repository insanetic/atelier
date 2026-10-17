---
type: llm
weight: 2
---

The answer does not change the spec or the data on its own: it proposes what would change (for example mapping `Offen` to a new canonical status, which is a business decision) and asks or leaves it to the user. Fail if it edits the spec, raises `max_rejects`, or loads the data.
