# Changelog

All notable changes to Agent-OS v3 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-01-06

### Added

#### Core Pipeline
- Multi-role task execution pipeline (Drafter → Verifier → Compliance → Executor)
- Task orchestrator with automatic queue processing (`src/orchestrator.py`)
- Role-based agents with clear authority boundaries:
  - Drafter: Proposal generation using Claude Sonnet 4
  - Verifier: Critical validation and security checks
  - Compliance: Policy and security review
  - Executor: Deterministic proposal execution

#### State Management
- Checkpoint system for full state recovery (`src/checkpoints.py`)
- Global sequence numbering for ordering guarantees
- Rollback capability for reversible operations
- IMR Pentagon validation for irreversible steps

#### Uncertainty Detection
- Confidence scoring with configurable thresholds (`src/uncertainty.py`)
- Regex-based uncertainty pattern detection (~1ms)
- Optional Groq LLM deep semantic analysis (~400ms)
- Automatic HALT on confidence below threshold (default 0.70)

#### Database Schema
- PostgreSQL database with complete task lifecycle tracking
- Tables: `tasks`, `checkpoints`, `api_usage`, `projects`
- JSONB fields for flexible state snapshots
- Foreign key relationships with cascade rules

#### Cost Optimization
- API usage tracking across providers (Anthropic, Groq, OpenAI) (`src/cost_tracker.py`)
- Groq integration for 85-99% cost reduction on validation tasks
- Per-operation token and cost metrics
- Project and task-level cost aggregation

#### Notifications
- Real-time Telegram progress updates with percentage tracking (`src/notifications.py`, `src/progress_bar.py`)
- Pushover alerts for high-priority events
- HALT notifications with uncertainty details
- Success/failure summaries

#### Developer Tools
- CLI status viewer (`scripts/status.py`)
- CLI queue management (`scripts/queue.py`)
- Cron integration script (`scripts/run-task.sh`)
- Health checker for system monitoring
- Audit logger for compliance tracking

### Technical Details

#### Architecture
- Million-step methodology: explicit checkpointing, no silent failures
- Separation of concerns: roles cannot approve their own work
- Fail-fast on uncertainty: system halts rather than guessing
- UTC timestamps with Mountain Time display conversion

#### Models
- Primary: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
- Validation: Groq Llama 3.3 70B and Llama 3.1 8B
- Schema validation: 99% cost reduction vs Claude
- Uncertainty detection: 85% cost reduction vs Claude

#### Integration
- Git operations with branch naming convention `aos/{task_type}/{task_id}`
- GitHub PR creation via `gh` CLI
- Configurable skip flags for git push and PR creation
- Environment variable configuration via `/opt/agent-os-v3/.env`

### Configuration

- Working directory: `/opt/agent-os-v3`
- Database: `maestro-postgres:5432/agent_os_v3`
- Confidence threshold: 0.70 (drafter), 0.90 (verifier)
- Context limits: 10 files max, 10,000 chars per file
- Notification bots: Telegram @q_pulse_bot, Pushover

### Documentation

- System prompt for Drafter role (`prompts/drafter_system.md`)
- README with architecture overview
- Inline documentation following million-step principles
- Database schema comments and conventions

[3.0.0]: https://github.com/tyleribs1976/agent-os/releases/tag/v3.0.0
