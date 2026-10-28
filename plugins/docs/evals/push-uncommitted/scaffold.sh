#!/bin/bash
# Workspace for this case: a help center repository with history.
set -e
git init -q -b main
git config user.email docs@acme.example
git config user.name "Acme Docs"
git config commit.gpgsign false
c() { d=$1; shift; GIT_AUTHOR_DATE=$d GIT_COMMITTER_DATE=$d git commit -q "$@"; }
mkdir -p helpcenter/team
cat > helpcenter/team/invite-members.md <<'EOF'
---
title: Teammitglieder einladen
description: Laden Sie Kolleginnen und Kollegen per E-Mail in Ihren Workspace ein.
type: how-to
reader: user
lang: de
productlane: art_2m9q
---

Sie können Kolleginnen und Kollegen per E-Mail in Ihren Workspace einladen. Das können nur Admins.

## Voraussetzungen

- Sie haben die Rolle **Admin**.

## Schritte

1. Wählen Sie **Einstellungen > Team**.
2. Wählen Sie **Mitglied einladen**.
3. Geben Sie die E-Mail-Adresse ein und wählen Sie **Einladung senden**.

## Falls es nicht klappt

- **Die Einladung ist abgelaufen:** Einladungen gelten 7 Tage. Senden Sie eine neue.
EOF
git add -A
c 2026-10-20T10:00:00 -m "docs(invite-members): first version"
c 2026-10-20T11:00:00 --allow-empty -m "docs: publish invite-members to productlane" -m "Docs-Published: productlane helpcenter/team/invite-members.md"
sed -i.bak "s/3. Geben Sie die E-Mail-Adresse ein und wählen Sie \*\*Einladung senden\*\*./3. Geben Sie eine oder mehrere E-Mail-Adressen ein. Wählen Sie dann **Einladung senden**./" helpcenter/team/invite-members.md && rm helpcenter/team/invite-members.md.bak
