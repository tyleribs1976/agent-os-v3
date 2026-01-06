#!/usr/bin/env bash
#
# Agent-OS v3 Health Check Script
# Checks if postgres container is running
# Exit 0 for success, 1 for failure

set -euo pipefail

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: docker command not found" >&2
    exit 1
fi

# Check if maestro-postgres container exists and is running
if docker ps --filter "name=maestro-postgres" --filter "status=running" --format "{{.Names}}" | grep -q "maestro-postgres"; then
    echo "OK: maestro-postgres container is running"
    exit 0
else
    echo "ERROR: maestro-postgres container is not running" >&2
    exit 1
fi
