---
type: llm
weight: 2
---

Money is recommended as an exact decimal type (NUMERIC/DECIMAL or exact integer minor units) together with a separate currency column, never a float, and the review warns against adding EUR and CHF together. Fail if it recommends FLOAT/FLOAT64, or ignores the currency mix.
