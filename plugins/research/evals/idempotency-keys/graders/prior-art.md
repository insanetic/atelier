---
type: llm
weight: 2
---

The answer shows how others solve it, naming at least three real, relevant references. Examples: the IETF HTTPAPI "Idempotency-Key HTTP Header Field" draft; Stripe's idempotent requests; another payment provider such as Adyen or PayPal; an open-source implementation or library; Brandur Leach's write-up on Stripe-like idempotency keys in Postgres. For each, it says what that reference does differently: key scope, fingerprinting, retention, concurrency or error caching. Fail if the references are vague ("many APIs…") or if fewer than three are named.
