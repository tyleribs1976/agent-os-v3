# Agent-OS v3 System Context

## Database Schema (PostgreSQL)

### tasks table
```sql
id              UUID PRIMARY KEY
project_id      UUID REFERENCES projects(id)
title           VARCHAR(200)
description     TEXT
task_type       VARCHAR(50)  -- 'implementation', 'architecture', 'documentation'
status          VARCHAR(20)  -- 'pending', 'running', 'complete', 'failed', 'halted'
priority        INTEGER
current_phase   VARCHAR(50)  -- 'preparation', 'drafting', 'verification', 'execution', 'confirmation'
dependencies    JSONB
created_at      TIMESTAMP
updated_at      TIMESTAMP
started_at      TIMESTAMP
completed_at    TIMESTAMP
last_error      TEXT
```

### checkpoints table
```sql
id                      SERIAL PRIMARY KEY
checkpoint_uuid         UUID
global_sequence         BIGINT UNIQUE
project_id              UUID
task_id                 UUID
phase                   VARCHAR(50)
step_name               VARCHAR(100)
state_snapshot          JSONB
inputs_hash             VARCHAR(64)
outputs_hash            VARCHAR(64)
drafter_agent_id        VARCHAR(50)
verifier_agent_id       VARCHAR(50)
status                  VARCHAR(20)  -- 'created', 'complete', 'failed', 'rolled_back'
error_details           JSONB
previous_checkpoint_id  INTEGER
rollback_data           JSONB
created_at              TIMESTAMP
completed_at            TIMESTAMP
```

### api_usage table
```sql
id              SERIAL PRIMARY KEY
timestamp       TIMESTAMP DEFAULT NOW()
provider        VARCHAR(50)  -- 'anthropic', 'groq', 'openai'
model           VARCHAR(100)
operation       VARCHAR(100) -- 'draft', 'verify', 'schema_validate', 'uncertainty_detect'
input_tokens    INTEGER
output_tokens   INTEGER
total_tokens    INTEGER GENERATED
cost_usd        DECIMAL(10,8)
latency_ms      INTEGER
success         BOOLEAN
project_id      UUID
task_id         UUID
error_message   TEXT
metadata        JSONB
```

### projects table
```sql
id          UUID PRIMARY KEY
name        VARCHAR(100)
repo_url    TEXT
work_dir    TEXT
config      JSONB  -- {"skip_git_push": bool, "skip_pr_creation": bool}
created_at  TIMESTAMP
```

## File Structure
```
/opt/agent-os-v3/
├── src/
│   ├── orchestrator.py    # Main task orchestrator
│   ├── db.py              # Database helpers (query_one, query_all, insert_returning)
│   ├── checkpoints.py     # CheckpointManager class
│   ├── uncertainty.py     # UncertaintyDetector class
│   ├── groq_integration.py # Groq validators
│   ├── cost_tracker.py    # API cost tracking
│   ├── notifications.py   # Telegram/Pushover alerts
│   └── roles/
│       ├── drafter.py     # Drafter role
│       ├── verifier.py    # Verifier role
│       └── executor.py    # ExecutionController
├── scripts/
│   ├── run-task.sh        # Cron entry point
│   ├── status.py          # CLI status tool
│   └── queue.py           # CLI queue management
├── prompts/
│   └── drafter_system.md
├── logs/
│   └── orchestrator.log
└── .env                   # Environment variables
```

## Environment & Conventions

### Timezone
- Server runs in UTC
- User is in Mountain Time (UTC-7 MST, UTC-6 MDT)
- All database timestamps are UTC
- Display times should convert to MT for notifications

### Cron
- Cron files go in /etc/cron.d/
- Use full paths in cron entries
- Source /opt/agent-os-v3/.env for environment

### Notifications
- Telegram bot: @q_pulse_bot
- Pushover for high-priority alerts
- Use notifications.py: notify_halt(), notify_progress(), notify_success()

### Database Connection
```python
from db import query_one, query_all, insert_returning, execute
# Connection via environment: host=maestro-postgres, db=agent_os_v3, user=maestro
```

### Error Handling
- All errors logged to checkpoints.error_details as JSONB
- Format: {"reason": "...", "error": "...", "signals": [...]}

### Git Operations
- Branch naming: aos/{task_type}/{task_id[:8]}
- Currently skip_git_push=true, skip_pr_creation=true
- Work directory: /opt/agent-os-v3
