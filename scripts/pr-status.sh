#!/usr/bin/env bash
#
# Agent-OS v3 PR Status Script
# Lists open pull requests using GitHub CLI
# Exit 0 for success, 1 for failure

set -euo pipefail

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo "ERROR: gh command not found. Please install GitHub CLI." >&2
    exit 1
fi

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "ERROR: Not in a git repository" >&2
    exit 1
fi

# List open pull requests
echo "Open Pull Requests:"
gh pr list

exit 0
