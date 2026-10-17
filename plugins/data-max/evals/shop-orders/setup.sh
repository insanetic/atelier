#!/usr/bin/env bash
# The workspace gets the fixture files: a raw export and, where the case needs one, its spec.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$here/fixture/." .
