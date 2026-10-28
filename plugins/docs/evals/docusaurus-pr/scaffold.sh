#!/bin/bash
# Workspace for this case: a help center repository with history.
set -e
git init -q -b main
git config user.email docs@acme.example
git config user.name "Acme Docs"
git config commit.gpgsign false
c() { d=$1; shift; GIT_AUTHOR_DATE=$d GIT_COMMITTER_DATE=$d git commit -q "$@"; }
mkdir -p docs/guides
printf "export default { title: \"Acme Docs\", url: \"https://docs.acme.example\", baseUrl: \"/\" };\n" > docusaurus.config.ts
printf "{ \"name\": \"acme-docs\", \"private\": true }\n" > package.json
git add -A
c 2026-10-20T10:00:00 -m "chore: docusaurus site"
git init -q --bare ../origin.git && git remote add origin ../origin.git && git push -q origin main
cat > docs/guides/export-invoices.md <<'EOF'
---
title: Export invoices as CSV
description: Download all invoices of a period as one CSV file for your accounting.
type: how-to
reader: user
sidebar_position: 2
---

You can download all invoices of a period as one CSV file. Admins and accountants can do this.

## Steps

1. Select **Settings > Billing > Invoices**.
2. Choose the period, at most 12 months.
3. Select **Export CSV**. The file downloads at once.
EOF
git add -A
c 2026-10-27T10:00:00 -m "docs(export-invoices): first version"
