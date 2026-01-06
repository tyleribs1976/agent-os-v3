#!/usr/bin/env bash
#
# Agent-OS v3 Code Formatter
# Runs ruff format on the src directory
#
# Usage:
#   ./scripts/format.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if ! command -v ruff &> /dev/null; then
    echo "Error: ruff is not installed"
    echo "Install with: pip install ruff"
    exit 1
fi

echo "Formatting Python files in src/ with ruff..."
ruff format src/

echo "✓ Formatting complete"
