#!/bin/sh
# Bundles core and the CLI into dist/, which is committed: an installed plugin has no node_modules.
set -e
cd "$(dirname "$0")"
esbuild core/index.ts --bundle --format=esm --platform=neutral --main-fields=module,main --outfile=dist/core.js --log-level=warning
esbuild cli/bin.ts --bundle --format=esm --platform=neutral --main-fields=module,main '--external:node:*' --target=node24 '--banner:js=#!/usr/bin/env node' --outfile=dist/cli.js --log-level=warning
chmod +x dist/cli.js
