#!/bin/bash
cd /opt/agent-os-v3
PG_IP=$(docker inspect maestro-postgres | jq -r '.[0].NetworkSettings.Networks["n8n-maestro_maestro-internal"].IPAddress')
export DB_HOST="$PG_IP"
export DB_PORT="5432"
export DB_NAME="agent_os_v3"
export DB_USER="maestro"
export DB_PASSWORD="maestro_secret_2024"
export TELEGRAM_BOT_TOKEN="8225207052:AAHRPqVqUupJnIbTrhCyr12Ki7-oWWpsHT8"
export TELEGRAM_CHAT_ID="5476253866"
export ANTHROPIC_API_KEY=$(cat /root/.anthropic_api_key)
export PYTHONPATH="/opt/agent-os-v3/src"
echo "[$(date -Is)] Starting V3 orchestrator"
python3 src/orchestrator.py
