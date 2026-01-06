# Agent-OS v3

Agent-OS v3 is an autonomous task execution system that follows the million-step methodology for reliable, checkpointed software development operations.

## Overview

Agent-OS v3 implements a multi-role pipeline (Drafter → Verifier → Compliance → Executor) that ensures quality and safety through:

- **Checkpointed execution**: Every state change is recorded for rollback capability
- **Uncertainty detection**: System halts on any ambiguity or low confidence
- **Role separation**: Draft proposals, verification, compliance checks, and execution are distinct phases
- **Cost tracking**: API usage is monitored across Anthropic, Groq, and OpenAI providers
- **Progress notifications**: Real-time updates via Telegram and Pushover

## Architecture

The system consists of:

- **Orchestrator** (`src/orchestrator.py`): Main task queue processor
- **Drafter** (`src/roles/drafter.py`): Generates proposals using Claude
- **Verifier** (`src/roles/verifier.py`): Validates drafts for correctness and safety
- **Compliance** (`src/roles/compliance.py`): Security and policy checks
- **Executor** (`src/roles/executor.py`): Deterministic proposal execution
- **Checkpoint Manager** (`src/checkpoints.py`): State management and recovery
- **Uncertainty Detector** (`src/uncertainty.py`): Confidence scoring and halt logic

## Database

PostgreSQL database with:
- `tasks`: Task queue and status tracking
- `checkpoints`: State snapshots for recovery
- `api_usage`: Cost and performance metrics
- `projects`: Repository and configuration data

## Requirements

- Python 3.9+
- PostgreSQL 12+
- Claude CLI or Anthropic API key
- Optional: Groq API for validation (cost optimization)

## License

Proprietary - Tyler Iverson 2024-2026
