"""
Agent-OS v3 Helper Functions

Common utility functions used across the system.
Following million-step methodology: explicit, no magic, pure functions.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional, Union


def get_timestamp(utc: bool = True) -> datetime:
    """
    Get current timestamp.
    
    Args:
        utc: If True, return UTC timestamp. If False, return local time.
    
    Returns:
        datetime object representing current time
    
    Examples:
        >>> ts = get_timestamp()
        >>> isinstance(ts, datetime)
        True
        >>> ts.tzinfo is not None  # Has timezone info
        True
    """
    if utc:
        return datetime.now(timezone.utc)
    return datetime.now()


def format_duration(seconds: Union[int, float]) -> str:
    """
    Format a duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds (int or float)
    
    Returns:
        Human-readable string like "2h 34m 15s" or "45.2s"
    
    Examples:
        >>> format_duration(45)
        '45s'
        >>> format_duration(125)
        '2m 5s'
        >>> format_duration(3665)
        '1h 1m 5s'
        >>> format_duration(0.234)
        '0.23s'
    """
    if seconds < 0:
        return "0s"
    
    # For sub-second durations, show 2 decimal places
    if seconds < 1:
        return f"{seconds:.2f}s"
    
    seconds = int(seconds)
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:  # Always show seconds if no other parts
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def parse_json(data: Union[str, dict, list, None], default: Any = None) -> Any:
    """
    Safely parse JSON data.
    
    Handles the case where psycopg2 returns JSONB fields already parsed as dicts/lists,
    or as strings that need parsing.
    
    Args:
        data: Input data - can be JSON string, already-parsed dict/list, or None
        default: Default value to return if parsing fails or data is None
    
    Returns:
        Parsed JSON object (dict, list, etc.) or default value
    
    Examples:
        >>> parse_json('{"key": "value"}')
        {'key': 'value'}
        >>> parse_json({'key': 'value'})  # Already parsed
        {'key': 'value'}
        >>> parse_json(None, default={})
        {}
        >>> parse_json('invalid json', default=[])
        []
    """
    # Already None
    if data is None:
        return default
    
    # Already parsed (psycopg2 returns JSONB as dict/list)
    if isinstance(data, (dict, list)):
        return data
    
    # Try to parse string
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return default
    
    # Unknown type
    return default
