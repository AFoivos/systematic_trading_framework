#!/usr/bin/env sh
set -eu

REPO_ROOT="${MCP_REPO_ROOT:-/workspace}"

if ! git config --global --get-all safe.directory 2>/dev/null |
    grep -Fxq "$REPO_ROOT"; then
    git config --global --add safe.directory "$REPO_ROOT"
fi

exec python -m repo_mcp.server
