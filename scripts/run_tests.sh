#!/usr/bin/env bash
#
# Agent-OS v3 Test Runner
# Runs pytest on the tests directory with proper configuration
#

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Load environment if available
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "Error: pytest not found. Install with: pip install pytest" >&2
    exit 1
fi

# Run pytest with common options
echo "Running tests in $PROJECT_ROOT/tests/"
pytest tests/ \
    --verbose \
    --tb=short \
    --color=yes \
    "$@"

exit_code=$?

if [[ $exit_code -eq 0 ]]; then
    echo "✓ All tests passed"
else
    echo "✗ Tests failed with exit code $exit_code" >&2
fi

exit $exit_code
