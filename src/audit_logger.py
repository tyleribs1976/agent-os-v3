"""
Agent-OS v3 Audit Logger Module

Following million-step methodology:
- All significant actions are audited
- Audit logs are structured and searchable
- No silent failures in logging
- Supports compliance and debugging
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, Union
from uuid import uuid4

from db import insert_returning


# Action type constants
EXECUTION_START = "execution_start"
STEP_COMPLETE = "step_complete"
STEP_FAILED = "step_failed"
EXECUTION_COMPLETE = "execution_complete"
EXECUTION_FAILED = "execution_failed"

# Additional common action types
CHECKPOINT_CREATED = "checkpoint_created"
CHECKPOINT_COMPLETED = "checkpoint_completed"
VERIFICATION_APPROVED = "verification_approved"
VERIFICATION_REJECTED = "verification_rejected"
UNCERTAINTY_DETECTED = "uncertainty_detected"
HALT_TRIGGERED = "halt_triggered"


class AuditLogger:
    """
    Audit logger for tracking all significant Agent-OS v3 operations.
    
    Provides structured logging of actions with inputs, outputs, and metadata
    for compliance, debugging, and system transparency.
    """
    
    def __init__(self, default_agent_id: Optional[str] = None, default_role: Optional[str] = None):
        """
        Initialize audit logger.
        
        Args:
            default_agent_id: Default agent ID to use if not specified per log
            default_role: Default role to use if not specified per log
        """
        self.default_agent_id = default_agent_id
        self.default_role = default_role
    
    def log_audit(
        self,
        action: str,
        description: str,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        checkpoint_id: Optional[int] = None,
        agent_id: Optional[str] = None,
        role: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Log an audit entry.
        
        Args:
            action: Action type (use constants like EXECUTION_START)
            description: Human-readable description of the action
            project_id: Project ID if applicable
            task_id: Task ID if applicable
            checkpoint_id: Checkpoint ID if applicable
            agent_id: Agent performing the action (uses default if not provided)
            role: Role of the agent (uses default if not provided)
            inputs: Input data/parameters for the action
            outputs: Output data/results from the action
            metadata: Additional metadata
        
        Returns:
            The ID of the created audit log entry
        
        Raises:
            ValueError: If required action parameter is missing
        """
        if not action:
            raise ValueError("Action is required for audit logging")
        
        # Use defaults if not provided
        final_agent_id = agent_id or self.default_agent_id
        final_role = role or self.default_role
        
        # Prepare data for insertion
        audit_data = {
            'timestamp': datetime.utcnow(),
            'project_id': project_id,
            'task_id': task_id,
            'checkpoint_id': checkpoint_id,
            'agent_id': final_agent_id,
            'role': final_role,
            'action': action,
            'description': description,
            'inputs_summary': self._format_as_json_summary(inputs) if inputs else None,
            'outputs_summary': self._format_as_json_summary(outputs) if outputs else None,
            'metadata': json.dumps(metadata, default=str) if metadata else None
        }
        
        # Remove None values to avoid unnecessary nulls
        audit_data = {k: v for k, v in audit_data.items() if v is not None}
        
        # Insert and return the ID
        return insert_returning('audit_log', audit_data, returning='id')
    
    def _format_as_json_summary(
        self, 
        data: Union[Dict[str, Any], list, str, int, float, bool], 
        max_length: int = 1000
    ) -> str:
        """
        Format data as JSON summary, truncating if necessary.
        
        Args:
            data: Data to format
            max_length: Maximum length of the JSON string
        
        Returns:
            JSON string, possibly truncated with indicator
        """
        if data is None:
            return None
        
        try:
            json_str = json.dumps(data, default=str, separators=(',', ':'))
            
            if len(json_str) <= max_length:
                return json_str
            
            # Truncate and add indicator
            truncated = json_str[:max_length-20]  # Leave room for truncation indicator
            return truncated + '..."[TRUNCATED]"'
            
        except (TypeError, ValueError) as e:
            # If serialization fails, return string representation
            str_repr = str(data)
            if len(str_repr) <= max_length:
                return json.dumps({"_repr": str_repr}, default=str)
            else:
                truncated_repr = str_repr[:max_length-30]
                return json.dumps({"_repr": truncated_repr + "...[TRUNCATED]"}, default=str)
    
    def log_execution_start(
        self,
        project_id: str,
        task_id: str,
        agent_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Convenience method to log execution start.
        
        Args:
            project_id: Project ID
            task_id: Task ID
            agent_id: Agent starting execution
            inputs: Execution inputs
        
        Returns:
            Audit log entry ID
        """
        return self.log_audit(
            action=EXECUTION_START,
            description=f"Started execution of task {task_id}",
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            role="executor",
            inputs=inputs
        )
    
    def log_step_complete(
        self,
        project_id: str,
        task_id: str,
        checkpoint_id: int,
        step_name: str,
        agent_id: Optional[str] = None,
        outputs: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Convenience method to log step completion.
        
        Args:
            project_id: Project ID
            task_id: Task ID
            checkpoint_id: Checkpoint ID
            step_name: Name of completed step
            agent_id: Agent that completed the step
            outputs: Step outputs
        
        Returns:
            Audit log entry ID
        """
        return self.log_audit(
            action=STEP_COMPLETE,
            description=f"Completed step: {step_name}",
            project_id=project_id,
            task_id=task_id,
            checkpoint_id=checkpoint_id,
            agent_id=agent_id,
            outputs=outputs
        )
    
    def log_halt(
        self,
        project_id: str,
        task_id: str,
        reason: str,
        checkpoint_id: Optional[int] = None,
        agent_id: Optional[str] = None,
        role: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Convenience method to log HALT conditions.
        
        Args:
            project_id: Project ID
            task_id: Task ID
            reason: Reason for halt
            checkpoint_id: Checkpoint ID if applicable
            agent_id: Agent triggering halt
            role: Role of agent triggering halt
            metadata: Additional halt metadata
        
        Returns:
            Audit log entry ID
        """
        return self.log_audit(
            action=HALT_TRIGGERED,
            description=f"HALT triggered: {reason}",
            project_id=project_id,
            task_id=task_id,
            checkpoint_id=checkpoint_id,
            agent_id=agent_id,
            role=role,
            metadata=metadata
        )
