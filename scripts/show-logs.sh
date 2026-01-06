#!/usr/bin/env bash
#
# Agent-OS v3 Log Viewer
# Tails the orchestrator log file
# Exit 0 for success, 1 for failure

set -euo pipefail

LOG_FILE="/opt/agent-os-v3/logs/orchestrator.log"

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "ERROR: Log file not found at $LOG_FILE" >&2
    echo "The orchestrator may not have run yet." >&2
    exit 1
fi

# Tail the log file (follow mode)
tail -f "$LOG_FILE"
