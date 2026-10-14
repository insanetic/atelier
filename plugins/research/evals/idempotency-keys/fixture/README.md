# pay-api

A small payments API. `POST /v1/charges` charges a card. Clients retry on timeouts and send an `Idempotency-Key` header so a retry never charges twice.
