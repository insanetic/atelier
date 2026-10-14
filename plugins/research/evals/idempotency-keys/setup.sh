#!/usr/bin/env bash
# The workspace becomes a small committed repo: the study must find our idempotency layer and cite it at HEAD.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$here/fixture/." .
git init -q
git add -A
git -c user.name=eval -c user.email=eval@example.com commit -qm "pay-api"
