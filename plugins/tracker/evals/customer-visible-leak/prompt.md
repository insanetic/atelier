---
max_turns: 10
allowed_tools: [Read, Write, Bash, Skill]
tags: [tracker, issue, exposure, en]
---

File a bug: the revenue widgets are empty for Northwind and Contoso because CurrencyFormatter.format() in src/dashboard/currency.ts throws when currency is null (see https://github.com/acme/dash/pull/812, commit 4be91f0). Should show revenue in the tenant default currency. Reported by maria.lopez@northwind.example. Workspace (no tracker connected here, so just give me what to paste): labels Bug, Feature, Improvement, Chore, Tech debt, Docs, Wontfix, User error; statuses Backlog, Todo, In Progress, In Review, Done, Canceled, Duplicate.
