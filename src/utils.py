"""Agent-OS v3 Utility Functions

Common helper functions used across the codebase.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


def format_timestamp(dt: datetime) -> str:
    """
    Format a datetime object as an ISO 8601 string.
    
    Args:
        dt: datetime object to format
    
    Returns:
        ISO 8601 formatted string (e.g., '2026-01-06T12:34:56.789012')
    
    Example:
        >>> format_timestamp(datetime(2026, 1, 6, 12, 34, 56))
        '2026-01-06T12:34:56'
    """
    return dt.isoformat()


def truncate_string(s: str, max_len: int = 100) -> str:
    """
    Truncate a string to a maximum length, adding ellipsis if truncated.
    
    Args:
        s: String to truncate
        max_len: Maximum length (default: 100)
    
    Returns:
        Truncated string with '...' appended if it exceeded max_len
    
    Example:
        >>> truncate_string('Hello World', 8)
        'Hello...'
        >>> truncate_string('Short', 10)
        'Short'
    """
    if len(s) <= max_len:
        return s
    return s[:max_len] + '...'


def safe_json_loads(s: Any) -> Dict[str, Any]:
    """
    Safely parse JSON string, returning empty dict on failure.
    
    Handles both string JSON and already-parsed dicts/lists (e.g., from psycopg2 JSONB).
    
    Args:
        s: JSON string, dict, list, or None
    
    Returns:
        Parsed dict, original value if already dict/list, or empty dict on failure
    
    Example:
        >>> safe_json_loads('{"key": "value"}')
        {'key': 'value'}
        >>> safe_json_loads('invalid json')
        {}
        >>> safe_json_loads(None)
        {}
        >>> safe_json_loads({'already': 'parsed'})
        {'already': 'parsed'}
    """
    if s is None:
        return {}
    
    if isinstance(s, dict):
        return s
    
    if isinstance(s, list):
        return s
    
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
