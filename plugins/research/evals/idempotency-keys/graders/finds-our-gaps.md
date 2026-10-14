---
type: llm
weight: 3
---

The answer reviews our implementation in `src/idempotency.ts` and names its concrete defects. There are four:
(1) No request fingerprint: the same key with a different request body silently returns the first response, where others reject it (for example 422 or 409).
(2) No handling of concurrent in-flight requests with one key: two retries arriving together both reach `charge`, so the card is charged twice. Others lock the key or answer 409.
(3) No expiry: keys live forever in an in-process Map, which also loses them on restart and is not shared across instances. Others keep keys for a bounded window, such as 24 hours, in shared storage.
(4) It caches the 502 error response, so a retry after a transient failure never reaches the acquirer again.
Pass if it names at least three of the four, each tied to our code. Fail if it reviews idempotency only in general without pointing at our code.
