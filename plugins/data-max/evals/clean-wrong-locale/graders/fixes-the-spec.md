---
type: llm
weight: 3
---

The first run fails because the spec declares `.` as the decimal separator while the file uses German numbers (`1.234,50 €`). The answer fixes this in the spec (decimal `,`, thousands `.`) and reruns, instead of editing the data file, writing a one-off script, or raising `max_rejects` to let the bad rows through. Pass if the spec's locale is corrected and the clean output comes from the engine run. Fail if data was hand-edited, rows were dropped to make it pass, or the amounts were parsed with the wrong separator.
