#!/bin/bash
set -e
git init -q -b main
git config user.email docs@acme.example
git config user.name "Acme Docs"
git config commit.gpgsign false
mkdir -p "Widgets" "Data Sources" "Account Management"
cat > "Widgets/Create a widget.md" <<'EOF'
# What is a widget?

A widget shows one metric on a dashboard. For example, a line chart of sessions from Google Analytics 4.

* * *

# How do I create a widget?

Open a dashboard in `Projects & Dashboards`.

1.  Click **Add widget**.
2.  Pick the metric.
3.  Click **Save**.

> **Note:** Widgets refresh every hour.

* * *

# Troubleshooting

**The widget is empty**

*   Check the date range. See [Add a data source](https://support.acme.example/docs/data-management/add-a-data-source).
EOF
cat > "Data Sources/Google Analytics 4.md" <<'EOF'
# What is the Google Analytics 4 connection?

It brings your GA4 sessions, users and conversions into Acme.

* * *

# How do I connect Google Analytics 4?

The connection uses OAuth.

> **Before you start**
> You need the Admin role in Acme and Viewer access to the GA4 property.

1.  Go to `Data sources` → `Marketplace`.
2.  Click **Google Analytics 4**.
3.  Click **Connect** and sign in with Google.

See [Add a data source](https://support.acme.example/docs/data-management/add-a-data-source).

* * *

# Troubleshooting

**The property is not listed**

*   Check that your Google account has Viewer access to it.
EOF
cat > "Account Management/Invite a team member.md" <<'EOF'
# What is a team member?

A team member is a person with access to your space.

* * *

# How do I invite a team member?

Open `Settings` → `Team`.

1.  Click **Invite**.
2.  Enter the email address.
3.  Click **Send invite**.

* * *

# Troubleshooting

**The invite did not arrive**

*   Check the spam folder. Invites expire after 7 days.
EOF
git add -A
git commit -qm "Add articles"
