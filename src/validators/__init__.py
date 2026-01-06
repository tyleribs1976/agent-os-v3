"""
Agent-OS v3 Input Validation Module

Following million-step methodology:
- Validate all inputs at system boundaries
- Explicit error messages for validation failures
- No silent fallbacks or coercion
"""

import re
from typing import Optional, List
from uuid import UUID


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_uuid(value: str, field_name: str = "id") -> str:
    """
    Validate that a string is a valid UUID.
    
    Args:
        value: The string to validate
        field_name: Name of the field being validated (for error messages)
    
    Returns:
        The validated UUID string (normalized to lowercase)
    
    Raises:
        ValidationError: If the value is not a valid UUID
    
    Examples:
        >>> validate_uuid("123e4567-e89b-12d3-a456-426614174000")
        '123e4567-e89b-12d3-a456-426614174000'
        >>> validate_uuid("invalid")
        ValidationError: Invalid UUID for field 'id': invalid
    """
    if not value:
        raise ValidationError(f"Missing required field: {field_name}")
    
    if not isinstance(value, str):
        raise ValidationError(
            f"Invalid type for {field_name}: expected string, got {type(value).__name__}"
        )
    
    try:
        # Use UUID constructor for validation
        uuid_obj = UUID(value)
        # Return normalized lowercase string representation
        return str(uuid_obj)
    except (ValueError, AttributeError) as e:
        raise ValidationError(
            f"Invalid UUID for field '{field_name}': {value}"
        ) from e


def validate_task_type(value: str) -> str:
    """
    Validate that a string is a valid task type.
    
    Valid task types:
    - implementation: Code implementation tasks
    - architecture: Architecture design tasks
    - documentation: Documentation tasks
    
    Args:
        value: The task type string to validate
    
    Returns:
        The validated task type (normalized to lowercase)
    
    Raises:
        ValidationError: If the value is not a valid task type
    
    Examples:
        >>> validate_task_type("implementation")
        'implementation'
        >>> validate_task_type("ARCHITECTURE")
        'architecture'
        >>> validate_task_type("invalid")
        ValidationError: Invalid task_type: 'invalid'. Must be one of: implementation, architecture, documentation
    """
    VALID_TASK_TYPES = {'implementation', 'architecture', 'documentation'}
    
    if not value:
        raise ValidationError("Missing required field: task_type")
    
    if not isinstance(value, str):
        raise ValidationError(
            f"Invalid type for task_type: expected string, got {type(value).__name__}"
        )
    
    normalized = value.lower().strip()
    
    if normalized not in VALID_TASK_TYPES:
        raise ValidationError(
            f"Invalid task_type: '{value}'. Must be one of: {', '.join(sorted(VALID_TASK_TYPES))}"
        )
    
    return normalized


def validate_status(value: str) -> str:
    """
    Validate that a string is a valid task status.
    
    Valid statuses: pending, queued, running, complete, failed, halted
    
    Args:
        value: The status string to validate
    
    Returns:
        The validated status (normalized to lowercase)
    
    Raises:
        ValidationError: If the value is not a valid status
    """
    VALID_STATUSES = {'pending', 'queued', 'running', 'complete', 'failed', 'halted'}
    
    if not value:
        raise ValidationError("Missing required field: status")
    
    if not isinstance(value, str):
        raise ValidationError(
            f"Invalid type for status: expected string, got {type(value).__name__}"
        )
    
    normalized = value.lower().strip()
    
    if normalized not in VALID_STATUSES:
        raise ValidationError(
            f"Invalid status: '{value}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )
    
    return normalized


def validate_phase(value: str) -> str:
    """
    Validate that a string is a valid task phase.
    
    Valid phases: preparation, drafting, verification, execution, confirmation
    
    Args:
        value: The phase string to validate
    
    Returns:
        The validated phase (normalized to lowercase)
    
    Raises:
        ValidationError: If the value is not a valid phase
    """
    VALID_PHASES = {'preparation', 'drafting', 'verification', 'execution', 'confirmation'}
    
    if not value:
        raise ValidationError("Missing required field: phase")
    
    if not isinstance(value, str):
        raise ValidationError(
            f"Invalid type for phase: expected string, got {type(value).__name__}"
        )
    
    normalized = value.lower().strip()
    
    if normalized not in VALID_PHASES:
        raise ValidationError(
            f"Invalid phase: '{value}'. Must be one of: {', '.join(sorted(VALID_PHASES))}"
        )
    
    return normalized


__all__ = [
    'ValidationError',
    'validate_uuid',
    'validate_task_type',
    'validate_status',
    'validate_phase',
]
