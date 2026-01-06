"""Agent-OS v3 Configuration Module

Centralized configuration management with environment variable loading and defaults.
Follows million-step methodology:
- All configuration is explicit
- No implicit defaults that hide behavior
- Environment variables override defaults
- Configuration is immutable after initialization
"""

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection configuration."""
    host: str
    port: int
    name: str
    user: str
    password: str
    min_pool_size: int
    max_pool_size: int


@dataclass(frozen=True)
class NotificationConfig:
    """Notification service configuration."""
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    pushover_api_token: Optional[str]
    pushover_user_key: Optional[str]


@dataclass(frozen=True)
class ModelConfig:
    """LLM model configuration."""
    drafter_model: str
    verifier_model: str
    groq_validator_model: str
    anthropic_api_key: Optional[str]
    groq_api_key: Optional[str]


@dataclass(frozen=True)
class SystemConfig:
    """System-level configuration."""
    work_dir: Path
    log_dir: Path
    confidence_threshold: float
    use_groq_validation: bool


@dataclass(frozen=True)
class Config:
    """Main configuration class for Agent-OS v3."""
    database: DatabaseConfig
    notifications: NotificationConfig
    models: ModelConfig
    system: SystemConfig
    
    @classmethod
    def from_env(cls) -> 'Config':
        """Load configuration from environment variables with defaults.
        
        Returns:
            Config instance with values from environment or defaults
        """
        # Database configuration
        database = DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            name=os.getenv('DB_NAME', 'agent_os_v3'),
            user=os.getenv('DB_USER', 'maestro'),
            password=os.getenv('DB_PASSWORD', 'maestro_secret_2024'),
            min_pool_size=int(os.getenv('DB_MIN_POOL_SIZE', '2')),
            max_pool_size=int(os.getenv('DB_MAX_POOL_SIZE', '10'))
        )
        
        # Notification configuration
        notifications = NotificationConfig(
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID'),
            pushover_api_token=os.getenv('PUSHOVER_API_TOKEN'),
            pushover_user_key=os.getenv('PUSHOVER_USER_KEY')
        )
        
        # Model configuration
        models = ModelConfig(
            drafter_model=os.getenv('DRAFTER_MODEL', 'claude-sonnet-4-20250514'),
            verifier_model=os.getenv('VERIFIER_MODEL', 'claude-sonnet-4-20250514'),
            groq_validator_model=os.getenv('GROQ_VALIDATOR_MODEL', 'llama-3.1-8b-instant'),
            anthropic_api_key=os.getenv('ANTHROPIC_API_KEY'),
            groq_api_key=os.getenv('GROQ_API_KEY')
        )
        
        # System configuration
        system = SystemConfig(
            work_dir=Path(os.getenv('AGENT_OS_WORK_DIR', '/opt/agent-os-v3')),
            log_dir=Path(os.getenv('AGENT_OS_LOG_DIR', '/opt/agent-os-v3/logs')),
            confidence_threshold=float(os.getenv('CONFIDENCE_THRESHOLD', '0.70')),
            use_groq_validation=os.getenv('USE_GROQ_VALIDATION', 'false').lower() == 'true'
        )
        
        return cls(
            database=database,
            notifications=notifications,
            models=models,
            system=system
        )
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary for serialization.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            'database': {
                'host': self.database.host,
                'port': self.database.port,
                'name': self.database.name,
                'user': self.database.user,
                'password': '***REDACTED***',
                'min_pool_size': self.database.min_pool_size,
                'max_pool_size': self.database.max_pool_size
            },
            'notifications': {
                'telegram_bot_token': '***REDACTED***' if self.notifications.telegram_bot_token else None,
                'telegram_chat_id': self.notifications.telegram_chat_id,
                'pushover_api_token': '***REDACTED***' if self.notifications.pushover_api_token else None,
                'pushover_user_key': '***REDACTED***' if self.notifications.pushover_user_key else None
            },
            'models': {
                'drafter_model': self.models.drafter_model,
                'verifier_model': self.models.verifier_model,
                'groq_validator_model': self.models.groq_validator_model,
                'anthropic_api_key': '***REDACTED***' if self.models.anthropic_api_key else None,
                'groq_api_key': '***REDACTED***' if self.models.groq_api_key else None
            },
            'system': {
                'work_dir': str(self.system.work_dir),
                'log_dir': str(self.system.log_dir),
                'confidence_threshold': self.system.confidence_threshold,
                'use_groq_validation': self.system.use_groq_validation
            }
        }


# Global configuration instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or initialize the global configuration instance.
    
    Returns:
        Config instance loaded from environment
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reload_config() -> Config:
    """Force reload configuration from environment.
    
    Useful for testing or when environment variables change.
    
    Returns:
        Newly loaded Config instance
    """
    global _config
    _config = Config.from_env()
    return _config
