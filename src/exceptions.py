"""
Agent-OS v3 Custom Exception Classes

Following million-step methodology:
- Explicit error types for different failure modes
- All exceptions carry context for logging and recovery
- Exception hierarchy supports granular error handling
"""

from typing import Optional, Dict, Any


class AgentOSError(Exception):
    """
    Base exception for all Agent-OS v3 errors.
    
    All custom exceptions inherit from this to allow:
    - Unified exception handling (catch AgentOSError)
    - Context preservation through error chain
    - Structured error logging
    
    Attributes:
        message: Human-readable error description
        context: Additional context for debugging (task_id, phase, etc.)
        original_error: Wrapped exception if this is a re-raise
    """
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.context = context or {}
        self.original_error = original_error
        
        # Build full message with context
        full_message = message
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            full_message = f"{message} (context: {context_str})"
        
        super().__init__(full_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dict for logging/serialization."""
        return {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'context': self.context,
            'original_error': str(self.original_error) if self.original_error else None
        }


class TaskError(AgentOSError):
    """
    Raised when task execution fails.
    
    Used for errors during task processing:
    - Task not found
    - Invalid task state transitions
    - Task execution failures
    - Missing required task fields
    
    Example:
        raise TaskError(
            "Task not found",
            context={'task_id': task_id, 'project_id': project_id}
        )
    """
    pass


class ValidationError(AgentOSError):
    """
    Raised when validation fails.
    
    Used for:
    - Schema validation failures (draft output, verification result)
    - Input validation failures (missing required fields)
    - Constraint violations (confidence below threshold)
    - Data integrity checks
    
    Example:
        raise ValidationError(
            "Draft missing required field 'confidence_score'",
            context={'draft_keys': list(draft.keys()), 'phase': 'drafting'}
        )
    """
    pass


class ExecutionError(AgentOSError):
    """
    Raised when execution of approved proposals fails.
    
    Used for:
    - File operation failures (write, modify)
    - Git operation failures (commit, push, PR creation)
    - IMR Pentagon validation failures
    - Postcondition check failures
    - Irreversible operation failures
    
    This is distinct from TaskError - ExecutionError specifically means
    the ExecutionController encountered a failure during approved action execution.
    
    Example:
        raise ExecutionError(
            "Failed to write file",
            context={
                'file_path': path,
                'step': 'write_files',
                'checkpoint_id': checkpoint_id
            },
            original_error=e
        )
    """
    pass
