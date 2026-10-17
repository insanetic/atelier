---
type: llm
weight: 3
---

The answer states the grain of every table it proposes before or with the SQL, including a fact at one row per booking per stay night (or an equivalent nightly grain) for occupancy, distinguished from a booking-level fact. It handles the fan-out from bookings to nights deliberately (amount split per night or kept at booking grain, with the reason) and does not sum amounts across currencies. Fail if a grain is missing or revenue is summed across EUR and CHF.
