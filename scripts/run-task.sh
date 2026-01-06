#!/bin/bash
# Agent-OS v3 Task Runner

# Load environment from .env
set -a
source /opt/agent-os-v3/.env
set +a

export PYTHONPATH=/opt/agent-os-v3/src

LOG_FILE="/opt/agent-os-v3/logs/orchestrator.log"

log() {
    echo "[$(date -Iseconds)] $1" >> "$LOG_FILE"
}

# Check if already running
LOCK_FILE="/tmp/agent-os-v3-runner.lock"
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log "Already running (PID $PID)"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log "Starting V3 orchestrator"
cd /opt/agent-os-v3/src
python3 orchestrator.py >> "$LOG_FILE" 2>&1
