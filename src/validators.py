"""
Agent-OS v3 Input Validators

Following million-step methodology:
- Explicit validation of all inputs
- No silent coercion or fallbacks
- Clear error messages for invalid inputs
- Type safety and boundary checks
"""

import re
from typing import Optional, List
from uuid import UUID


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


def validate_task_id(task_id: str) -> str:
    """
    Validate task ID format.
    
    Args:
        task_id: Task ID to validate (should be UUID format)
    
    Returns:
        Validated task ID as string
    
    Raises:
        ValidationError: If task_id is invalid
    
    Examples:
        >>> validate_task_id("550e8400-e29b-41d4-a716-446655440000")
        '550e8400-e29b-41d4-a716-446655440000'
        >>> validate_task_id("invalid")
        ValidationError: Invalid task_id format: must be valid UUID
    """
    if not task_id:
        raise ValidationError("task_id is required")
    
    if not isinstance(task_id, str):
        raise ValidationError(f"task_id must be string, got {type(task_id).__name__}")
    
    # Strip whitespace
    task_id = task_id.strip()
    
    # Validate UUID format
    try:
        UUID(task_id)
    except ValueError:
        raise ValidationError(f"Invalid task_id format: must be valid UUID, got '{task_id}'")
    
    return task_id


def validate_project_id(project_id: str) -> str:
    """
    Validate project ID format.
    
    Args:
        project_id: Project ID to validate (should be UUID format)
    
    Returns:
        Validated project ID as string
    
    Raises:
        ValidationError: If project_id is invalid
    
    Examples:
        >>> validate_project_id("550e8400-e29b-41d4-a716-446655440000")
        '550e8400-e29b-41d4-a716-446655440000'
        >>> validate_project_id("")
        ValidationError: project_id is required
    """
    if not project_id:
        raise ValidationError("project_id is required")
    
    if not isinstance(project_id, str):
        raise ValidationError(f"project_id must be string, got {type(project_id).__name__}")
    
    # Strip whitespace
    project_id = project_id.strip()
    
    # Validate UUID format
    try:
        UUID(project_id)
    except ValueError:
        raise ValidationError(f"Invalid project_id format: must be valid UUID, got '{project_id}'")
    
    return project_id


def validate_status(status: str, allowed_statuses: Optional[List[str]] = None) -> str:
    """
    Validate status value.
    
    Args:
        status: Status value to validate
        allowed_statuses: Optional list of allowed status values.
                         Defaults to standard task statuses.
    
    Returns:
        Validated status as string
    
    Raises:
        ValidationError: If status is invalid
    
    Examples:
        >>> validate_status("pending")
        'pending'
        >>> validate_status("invalid")
        ValidationError: Invalid status: must be one of [...]
        >>> validate_status("active", allowed_statuses=["active", "inactive"])
        'active'
    """
    if not status:
        raise ValidationError("status is required")
    
    if not isinstance(status, str):
        raise ValidationError(f"status must be string, got {type(status).__name__}")
    
    # Strip whitespace and lowercase
    status = status.strip().lower()
    
    # Default allowed statuses for tasks
    if allowed_statuses is None:
        allowed_statuses = [
            'pending',
            'queued',
            'running',
            'complete',
            'failed',
            'halted'
        ]
    
    # Normalize allowed statuses
    allowed_statuses = [s.lower() for s in allowed_statuses]
    
    if status not in allowed_statuses:
        raise ValidationError(
            f"Invalid status '{status}': must be one of {allowed_statuses}"
        )
    
    return status
