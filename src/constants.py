"""Agent-OS v3 System Constants"""

VERSION = "3.0.0"
BUILD_NUMBER = 1
RELEASE_DATE = "2026-01-06"
APP_NAME = "AgentOS"
AUTHOR = "Ty Fisher"
LOG_LEVEL = "INFO"
PROJECT_NAME = "Agent-OS v3"
DESCRIPTION = "Agent-OS v3 Autonomous Development System"
GITHUB_REPO = "agent-os-v3"
HOMEPAGE = "https://github.com/tyfiero/agent-os-v3"

# Logging configuration
LOG_LEVEL = "INFO"

# Test constant for GitHub PR verification
TESTED = True

# Task statuses
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETE = "complete"
STATUS_FAILED = "failed"
STATUS_HALTED = "halted"

# Phases
PHASE_DRAFTING = "drafting"
PHASE_VERIFICATION = "verification"
PHASE_EXECUTION = "execution"

# Confidence thresholds
MIN_DRAFTER_CONFIDENCE = 0.85
MIN_VERIFIER_CONFIDENCE = 0.90

# Timeout settings (seconds)
DRAFT_TIMEOUT = 600
DEFAULT_TIMEOUT = 300
VERIFY_TIMEOUT = 300
EXECUTE_TIMEOUT = 300

# Error codes
ERROR_CODES = {
    "E001": "TASK_NOT_FOUND",
    "E002": "VALIDATION_FAILED",
    "E003": "EXECUTION_FAILED",
    "E004": "CHECKPOINT_ERROR"
