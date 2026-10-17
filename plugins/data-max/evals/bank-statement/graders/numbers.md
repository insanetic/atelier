---
type: llm
weight: 3
---

The clean output holds all 32 transactions, amounts sum to 4554.90 with negatives from the trailing-minus format (`1.250,00-` → -1250.00), and dates are ISO. Fail if any row is missing or a sign or decimal is wrong.
