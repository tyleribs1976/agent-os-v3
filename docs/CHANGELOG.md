# Changelog

All notable changes to Agent-OS v3 will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-01-06

### Added

#### Core Architecture
- **Five-Role System**: Implemented Drafter, Verifier, Compliance, Executor, and Auditor roles for separation of concerns
- **Checkpoint System**: Full state tracking with rollback capabilities via `CheckpointManager`
- **Uncertainty Detection**: Two-tier detection system (regex + Groq LLM) that enforces HALT on ambiguity
- **IMR Pentagon Framework**: Idempotence, Minimalism, Reversibility validation in execution pipeline

#### Database & Persistence
- PostgreSQL schema with `tasks`, `checkpoints`, `api_usage`, and `projects` tables
- Connection pooling via `psycopg2.pool.ThreadedConnectionPool`
- Transaction-safe operations with explicit commit/rollback
- JSONB storage for flexible state snapshots and error details

#### Task Management
- Priority-based task queue with dependency tracking
- Task types: implementation, architecture, documentation
- Task phases: preparation, drafting, verification, execution, confirmation
- Task statuses: pending, queued, running, complete, failed, halted

#### API & Cost Tracking
- Multi-provider support: Anthropic Claude, Groq, OpenAI
- Token usage and cost tracking in `api_usage` table
- Latency monitoring and success rate metrics

#### Notifications & Monitoring
- Telegram integration via `@q_pulse_bot`
- Pushover alerts for high-priority events
- Live progress tracking with `TelegramProgressBar`
- Timezone-aware notifications (UTC storage, MT display)

#### Developer Tools
- `scripts/status.py`: CLI status dashboard
- `scripts/queue.py`: Task queue management
- `scripts/run-task.sh`: Cron entry point
- Health checking via `HealthChecker`
- Retry logic via `RetryManager`
- Audit logging via `AuditLogger`

#### Core Modules
- `src/orchestrator.py`: Main task execution pipeline
- `src/db.py`: Database connection and query helpers
- `src/checkpoints.py`: State checkpoint management
- `src/uncertainty.py`: Uncertainty detection with Groq integration
- `src/validators.py`: Input validation (task_id, project_id, status)
- `src/helpers.py`: Utility functions (timestamps, duration formatting, JSON parsing)
- `src/utils.py`: Common helpers (JSON loading, string truncation)
- `src/models.py`: Dataclasses for Task, Project, Checkpoint
- `src/exceptions.py`: Custom exception hierarchy
- `src/constants.py`: System-wide constants and configuration

#### Roles Implementation
- `src/roles/drafter.py`: Proposal generation with confidence scoring
- `src/roles/verifier.py`: Independent proposal verification
- `src/roles/executor.py`: Safe execution with IMR Pentagon checks
- `src/roles/compliance.py`: Policy and constraint validation

#### Configuration
- Environment-based configuration via `.env`
- Project-level settings in `projects.config` JSONB field
- Configurable confidence thresholds (drafter: 0.85, verifier: 0.90)
- Configurable timeouts (draft: 600s, verify: 300s, execute: 300s)

### Changed
- Migrated from monolithic agent to multi-role pipeline architecture
- Replaced ad-hoc error handling with structured exception hierarchy
- Moved from implicit state to explicit checkpoint-based state management
- Shifted from single-LLM to multi-provider strategy for cost optimization

### Security
- Connection pooling prevents connection exhaustion attacks
- Input validation on all external inputs (task IDs, project IDs, statuses)
- Parameterized SQL queries prevent SQL injection
- Explicit transaction boundaries prevent partial state updates

### Performance
- 85% cost reduction for uncertainty detection via Groq Llama 3.3 70B
- Regex pre-filtering reduces LLM calls (~1ms vs ~400ms)
- Connection pooling reduces database connection overhead
- Context-aware file loading (max 10 files, 10KB per file) limits token usage

### Developer Experience
- Type hints throughout codebase for IDE support
- Docstrings with examples for all public functions
- Explicit error messages with context for debugging
- CLI tools for common operations

---

## [Unreleased]

### Planned
- Web dashboard for task monitoring
- GitHub Actions integration for CI/CD pipelines
- Multi-project parallel execution
- Historical analytics and trend reporting
- Custom role plugin system

---

**Note**: This is the initial release of Agent-OS v3. Previous versions (v1, v2) were experimental and not publicly released.

[3.0.0]: https://github.com/tyfiero/agent-os-v3/releases/tag/v3.0.0
