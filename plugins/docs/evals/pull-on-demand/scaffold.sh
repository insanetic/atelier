#!/bin/bash
# Workspace for this case: a help center repository with history.
set -e
git init -q -b main
git config user.email docs@acme.example
git config user.name "Acme Docs"
git config commit.gpgsign false
c() { d=$1; shift; GIT_AUTHOR_DATE=$d GIT_COMMITTER_DATE=$d git commit -q "$@"; }
mkdir -p helpcenter/billing
cat > helpcenter/billing/export-invoices-csv.md <<'EOF'
---
title: Export invoices as CSV
description: Download all invoices of a period as one CSV file for your accounting.
type: how-to
reader: user
productlane: art_7f3k
---

You can download all invoices of a period as one CSV file. Admins and accountants can do this.

## Before you begin

- You have the **Admin** or **Accounting** role.

## Steps

1. Select **Settings > Billing > Invoices**.
2. Choose the period.
3. Select **Download**. You get an email when the file is ready.

## If it doesn't work

- **The file is empty:** there are no invoices in this period. Choose another period.
EOF
git add -A
c 2026-10-19T10:00:00 -m "docs(export-invoices-csv): first version"
c 2026-10-19T11:00:00 --allow-empty -m "docs: publish export-invoices-csv to productlane" -m "Docs-Published: productlane helpcenter/billing/export-invoices-csv.md"
sed -i.bak -e "s/3. Select \*\*Download\*\*. You get an email when the file is ready./3. Select **Export CSV**. The file downloads at once./" -e "s/2. Choose the period./2. Choose the period, at most 12 months./" helpcenter/billing/export-invoices-csv.md && rm helpcenter/billing/export-invoices-csv.md.bak
c 2026-10-26T09:00:00 -am "docs(export-invoices-csv): new export button, 12-month limit"
c 2026-10-26T09:30:00 --allow-empty -m "docs: publish export-invoices-csv to productlane" -m "Docs-Published: productlane helpcenter/billing/export-invoices-csv.md"
