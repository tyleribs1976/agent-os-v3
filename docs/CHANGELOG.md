# Changelog

All notable changes to Agent-OS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-01-06

### Added

#### Core Architecture
- **Multi-agent orchestration system** with role-based separation (Drafter, Verifier, Compliance, Executor)
- **Checkpoint-based state management** with full rollback capability via `CheckpointManager`
- **Uncertainty detection system** using regex patterns and optional Groq LLM analysis
- **IMR Pentagon validation** for irreversible operations (git push, PR creation)
- **PostgreSQL database** for tasks, checkpoints, projects, and API usage tracking

#### Agent Roles
- **Drafter**: Generates proposals with confidence scoring and uncertainty flags
- **Verifier**: Critically evaluates drafts with security and correctness checks
- **Compliance**: Reviews risk flags and enforces security policies
- **Executor**: Deterministic execution controller (non-LLM)

#### Infrastructure
- **Telegram progress tracking** with real-time phase updates via `TelegramProgressBar`
- **Cost tracking** for Anthropic Claude and Groq API usage in `api_usage` table
- **Notification system** supporting Telegram and Pushover (halt/success/error alerts)
- **Health checking** and audit logging for production monitoring
- **Retry management** with exponential backoff for transient failures

#### Database Schema
- `tasks` table with status tracking and phase management
- `checkpoints` table with global sequencing and rollback data
- `api_usage` table for cost and latency monitoring
- `projects` table with configuration support

#### Tooling
- `scripts/status.py`: CLI tool for task and checkpoint status
- `scripts/queue.py`: CLI tool for task queue management
- `scripts/run-task.sh`: Cron-compatible task runner
- `scripts/create_grafana_dashboard.py`: Monitoring dashboard setup

#### Integration
- **Groq integration** for cost-effective schema validation (99% cost reduction)
- **Grafana monitoring** with PostgreSQL datasource
- **Git operations** with branch naming convention `aos/{task_type}/{task_id}`

### Changed
- Migrated from v2 monolithic architecture to role-based agent system
- Replaced implicit state management with explicit checkpoint system
- Centralized error handling through checkpoint error_details JSONB field

### Architecture Principles
- **Million-step methodology**: Every state change is checkpointed
- **Uncertainty escalation**: HALT on any ambiguity or low confidence
- **Role separation**: No agent can approve its own work
- **Explicit over implicit**: All state serialized, no hidden assumptions
- **Rollback capability**: Reversible steps can always be undone

### Technical Details
- **Python 3.10+** with psycopg2 for PostgreSQL connectivity
- **Claude Sonnet 4** for drafting and verification (configurable)
- **Groq Llama 3.3 70B** for uncertainty detection (optional)
- **Groq Llama 3.1 8B** for schema validation (optional)
- **UTC timestamps** with Mountain Time display in notifications
- **Connection pooling** via `psycopg2.pool.ThreadedConnectionPool`

### Configuration
- Environment: `/opt/agent-os-v3/.env`
- Work directory: `/opt/agent-os-v3`
- Database: `maestro-postgres:5432/agent_os_v3`
- Cron integration: `/etc/cron.d/`

[3.0.0]: https://github.com/tyleribs1976/agent-os/releases/tag/v3.0.0
