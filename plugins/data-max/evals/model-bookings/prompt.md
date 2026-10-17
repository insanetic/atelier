---
max_turns: 40
allowed_tools: [Read, Glob, Grep, Write, Edit, Bash, Skill, AskUserQuestion]
tags: [model]
---

Our hotel bookings land in BigQuery as `raw.bookings` exactly as described by `specs/bookings.spec.json`, merged weekly. Management wants nightly occupancy and revenue per hotel, and we must be able to see how a booking's status changed over time. We use plain SQL in BigQuery, no dbt. Design the models and write the SQL. Don't ask me anything; state what you assume.
