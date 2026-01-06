#!/usr/bin/env bash
#
# Agent-OS v3 Cleanup Script
# Removes Python cache files and directories
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "[clean.sh] Cleaning Python cache files in $PROJECT_ROOT..."

# Remove __pycache__ directories
find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Remove .pyc files
find "$PROJECT_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true

# Remove .pyo files
find "$PROJECT_ROOT" -type f -name "*.pyo" -delete 2>/dev/null || true

echo "[clean.sh] Cleanup complete."
