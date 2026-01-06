#!/usr/bin/env bash
#
# Agent-OS v3 Lint Script
# Runs ruff and mypy on the src directory
#
# Exit on any error
set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Agent-OS v3 Linting ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Run ruff
echo "[1/2] Running ruff..."
if command -v ruff &> /dev/null; then
    ruff check src/
    echo "✓ ruff passed"
else
    echo "✗ ruff not found. Install with: pip install ruff"
    exit 1
fi

echo ""

# Run mypy
echo "[2/2] Running mypy..."
if command -v mypy &> /dev/null; then
    mypy src/
    echo "✓ mypy passed"
else
    echo "✗ mypy not found. Install with: pip install mypy"
    exit 1
fi

echo ""
echo "=== All linting checks passed ==="
