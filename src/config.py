#!/usr/bin/env python3
"""
Agent-OS v3 Configuration Module

Following million-step methodology:
- All configuration is explicit, never implicit
- Environment variables are the source of truth
- Defaults are documented and sensible
- No silent fallbacks that hide misconfiguration
"""

import os
from typing import Optional


class Config:
    """
    Central configuration class for Agent-OS v3.
    
    Loads settings from environment variables with sensible defaults.
    All configuration should flow through this class.
    
    Usage:
        config = Config()
        db_host = config.db_host
        model = config.default_model
    """
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        
        # Database configuration
        self.db_host: str = os.environ.get('DB_HOST', 'localhost')
        self.db_port: int = int(os.environ.get('DB_PORT', '5432'))
        self.db_name: str = os.environ.get('DB_NAME', 'agent_os_v3')
        self.db_user: str = os.environ.get('DB_USER', 'maestro')
        self.db_password: str = os.environ.get('DB_PASSWORD', 'maestro_secret_2024')
        
        # Connection pool settings
        self.db_pool_min: int = int(os.environ.get('DB_POOL_MIN', '2'))
        self.db_pool_max: int = int(os.environ.get('DB_POOL_MAX', '10'))
        
        # LLM configuration
        self.anthropic_api_key: Optional[str] = os.environ.get('ANTHROPIC_API_KEY')
        self.groq_api_key: Optional[str] = os.environ.get('GROQ_API_KEY')
        self.openai_api_key: Optional[str] = os.environ.get('OPENAI_API_KEY')
        
        # Model defaults
        self.default_model: str = os.environ.get('DEFAULT_MODEL', 'claude-sonnet-4-20250514')
        self.drafter_model: str = os.environ.get('DRAFTER_MODEL', 'claude-sonnet-4-20250514')
        self.verifier_model: str = os.environ.get('VERIFIER_MODEL', 'claude-sonnet-4-20250514')
        self.groq_model: str = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
        
        # Confidence thresholds
        self.drafter_confidence_threshold: float = float(os.environ.get('DRAFTER_CONFIDENCE_THRESHOLD', '0.70'))
        self.verifier_confidence_threshold: float = float(os.environ.get('VERIFIER_CONFIDENCE_THRESHOLD', '0.90'))
        
        # Feature flags
        self.use_groq_validation: bool = os.environ.get('USE_GROQ_VALIDATION', 'false').lower() == 'true'
        self.use_groq_uncertainty: bool = os.environ.get('USE_GROQ_UNCERTAINTY', 'true').lower() == 'true'
        self.skip_git_push: bool = os.environ.get('SKIP_GIT_PUSH', 'true').lower() == 'true'
        self.skip_pr_creation: bool = os.environ.get('SKIP_PR_CREATION', 'true').lower() == 'true'
        
        # Notification configuration
        self.telegram_bot_token: Optional[str] = os.environ.get('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id: Optional[str] = os.environ.get('TELEGRAM_CHAT_ID')
        self.pushover_token: Optional[str] = os.environ.get('PUSHOVER_TOKEN')
        self.pushover_user: Optional[str] = os.environ.get('PUSHOVER_USER')
        
        # Path configuration
        self.work_dir: str = os.environ.get('AGENT_OS_WORK_DIR', '/opt/agent-os-v3')
        self.log_dir: str = os.environ.get('AGENT_OS_LOG_DIR', '/opt/agent-os-v3/logs')
        self.prompts_dir: str = os.environ.get('AGENT_OS_PROMPTS_DIR', '/opt/agent-os-v3/prompts')
        self.data_dir: str = os.environ.get('AGENT_OS_DATA_DIR', '/opt/agent-os-v3/data')
        
        # Operational settings
        self.max_context_files: int = int(os.environ.get('MAX_CONTEXT_FILES', '10'))
        self.max_file_size: int = int(os.environ.get('MAX_FILE_SIZE', '10000'))
        self.checkpoint_retention_days: int = int(os.environ.get('CHECKPOINT_RETENTION_DAYS', '90'))
        
        # GitHub configuration
        self.github_token: Optional[str] = os.environ.get('GITHUB_TOKEN')
        self.github_repo: Optional[str] = os.environ.get('GITHUB_REPO')
        
        # Timezone
        self.timezone: str = os.environ.get('TZ', 'America/Denver')  # Mountain Time
        
        # Monitoring
        self.grafana_url: Optional[str] = os.environ.get('GRAFANA_URL')
        self.grafana_api_key: Optional[str] = os.environ.get('GRAFANA_API_KEY')
    
    def get_db_config(self) -> dict:
        """Return database configuration as a dict."""
        return {
            'host': self.db_host,
            'port': self.db_port,
            'name': self.db_name,
            'user': self.db_user,
            'password': self.db_password,
        }
    
    def get_pool_config(self) -> dict:
        """Return connection pool configuration."""
        return {
            'min_conn': self.db_pool_min,
            'max_conn': self.db_pool_max,
        }
    
    def validate(self) -> list[str]:
        """
        Validate configuration and return list of errors.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Check required API keys based on feature flags
        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is required")
        
        if self.use_groq_validation or self.use_groq_uncertainty:
            if not self.groq_api_key:
                errors.append("GROQ_API_KEY is required when Groq features are enabled")
        
        # Validate thresholds
        if not 0.0 <= self.drafter_confidence_threshold <= 1.0:
            errors.append(f"DRAFTER_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0, got {self.drafter_confidence_threshold}")
        
        if not 0.0 <= self.verifier_confidence_threshold <= 1.0:
            errors.append(f"VERIFIER_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0, got {self.verifier_confidence_threshold}")
        
        # Validate notification config (warn only)
        if not self.telegram_bot_token or not self.telegram_chat_id:
            errors.append("Warning: Telegram notifications not configured (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID missing)")
        
        return errors
    
    def __repr__(self) -> str:
        """Return string representation (masking sensitive values)."""
        return (
            f"Config("
            f"db_host={self.db_host}, "
            f"db_name={self.db_name}, "
            f"default_model={self.default_model}, "
            f"use_groq_validation={self.use_groq_validation}, "
            f"drafter_confidence_threshold={self.drafter_confidence_threshold}"
            f")"
        )


# Global config instance (singleton pattern)
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global config instance (singleton).
    
    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reload_config() -> Config:
    """
    Force reload of configuration from environment.
    
    Returns:
        New Config instance
    """
    global _config_instance
    _config_instance = Config()
    return _config_instance
