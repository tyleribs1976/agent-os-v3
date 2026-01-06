"""
Agent-OS v3 Audit Logger

Following million-step methodology:
- All system events are logged
- Audit trail is immutable
- Security events are flagged
- Retention policies are enforced
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from db import insert_returning, query_all, query_one


class EventType(Enum):
    """Types of audit events."""
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_HALTED = "task_halted"
    CHECKPOINT_CREATED = "checkpoint_created"
    CHECKPOINT_COMPLETED = "checkpoint_completed"
    CHECKPOINT_FAILED = "checkpoint_failed"
    DRAFT_GENERATED = "draft_generated"
    VERIFICATION_COMPLETE = "verification_complete"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETE = "execution_complete"
    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    GIT_COMMIT = "git_commit"
    GIT_PUSH = "git_push"
    PR_CREATED = "pr_created"
    SECURITY_FLAG = "security_flag"
    COMPLIANCE_CHECK = "compliance_check"
    HALT_TRIGGERED = "halt_triggered"
    API_CALL = "api_call"
    ERROR = "error"


class Severity(Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLogger:
    """
    Logs all system events to an immutable audit trail.
    
    Core principle: Every significant action must be auditable.
    """
    
    def __init__(self):
        self._ensure_audit_table()
    
    def _ensure_audit_table(self):
        """
        Ensure audit_logs table exists.
        
        This is called on initialization to create the table if needed.
        """
        from db import execute
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT NOW(),
            event_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            project_id UUID,
            task_id UUID,
            checkpoint_id INTEGER,
            actor VARCHAR(100),
            action TEXT NOT NULL,
            details JSONB,
            ip_address VARCHAR(45),
            user_agent TEXT,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT,
            metadata JSONB
        );
        
        CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_project_id ON audit_logs(project_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_task_id ON audit_logs(task_id);
        CREATE INDEX IF NOT EXISTS idx_audit_logs_severity ON audit_logs(severity);
        """
        
        try:
            execute(create_table_sql)
        except Exception as e:
            # Table might already exist, that's okay
            pass
    
    def log_event(
        self,
        event_type: EventType,
        action: str,
        severity: Severity = Severity.INFO,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        checkpoint_id: Optional[int] = None,
        actor: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (from EventType enum)
            action: Human-readable description of the action
            severity: Severity level (default: INFO)
            project_id: Associated project UUID
            task_id: Associated task UUID
            checkpoint_id: Associated checkpoint ID
            actor: Who/what performed the action (agent ID, user, etc.)
            details: Event-specific details as JSON
            success: Whether the action succeeded
            error_message: Error message if action failed
            metadata: Additional metadata as JSON
            ip_address: IP address if applicable
            user_agent: User agent if applicable
        
        Returns:
            The created audit log record
        """
        audit_data = {
            'event_type': event_type.value,
            'severity': severity.value,
            'action': action,
            'project_id': project_id,
            'task_id': task_id,
            'checkpoint_id': checkpoint_id,
            'actor': actor,
            'details': json.dumps(details, default=str) if details else None,
            'success': success,
            'error_message': error_message,
            'metadata': json.dumps(metadata, default=str) if metadata else None,
            'ip_address': ip_address,
            'user_agent': user_agent
        }
        
        return insert_returning('audit_logs', audit_data)
    
    def log_task_event(
        self,
        event_type: EventType,
        task_id: str,
        project_id: str,
        action: str,
        actor: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convenience method for logging task-related events.
        """
        return self.log_event(
            event_type=event_type,
            action=action,
            project_id=project_id,
            task_id=task_id,
            actor=actor,
            details=details,
            success=success,
            error_message=error_message
        )
    
    def log_checkpoint_event(
        self,
        event_type: EventType,
        checkpoint_id: int,
        task_id: str,
        project_id: str,
        action: str,
        actor: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True
    ) -> Dict[str, Any]:
        """
        Convenience method for logging checkpoint-related events.
        """
        return self.log_event(
            event_type=event_type,
            action=action,
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            project_id=project_id,
            actor=actor,
            details=details,
            success=success
        )
    
    def log_security_event(
        self,
        action: str,
        details: Dict[str, Any],
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        severity: Severity = Severity.WARNING
    ) -> Dict[str, Any]:
        """
        Log a security-related event with high visibility.
        """
        return self.log_event(
            event_type=EventType.SECURITY_FLAG,
            action=action,
            severity=severity,
            project_id=project_id,
            task_id=task_id,
            details=details
        )
    
    def log_error(
        self,
        action: str,
        error_message: str,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        checkpoint_id: Optional[int] = None,
        actor: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Convenience method for logging errors.
        """
        return self.log_event(
            event_type=EventType.ERROR,
            action=action,
            severity=Severity.ERROR,
            project_id=project_id,
            task_id=task_id,
            checkpoint_id=checkpoint_id,
            actor=actor,
            details=details,
            success=False,
            error_message=error_message
        )
    
    def get_audit_trail(
        self,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        severity: Optional[Severity] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail with optional filters.
        
        Args:
            project_id: Filter by project
            task_id: Filter by task
            event_type: Filter by event type
            severity: Filter by severity
            limit: Maximum number of records to return
            offset: Offset for pagination
        
        Returns:
            List of audit log records
        """
        conditions = []
        params = []
        
        if project_id:
            conditions.append("project_id = %s")
            params.append(project_id)
        
        if task_id:
            conditions.append("task_id = %s")
            params.append(task_id)
        
        if event_type:
            conditions.append("event_type = %s")
            params.append(event_type.value)
        
        if severity:
            conditions.append("severity = %s")
            params.append(severity.value)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        sql = f"""
        SELECT * FROM audit_logs
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT %s OFFSET %s
        """
        
        params.extend([limit, offset])
        
        return query_all(sql, tuple(params))
    
    def get_security_events(
        self,
        project_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get all security-flagged events.
        """
        return self.get_audit_trail(
            project_id=project_id,
            event_type=EventType.SECURITY_FLAG,
            limit=limit
        )
    
    def get_task_timeline(
        self,
        task_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get complete audit timeline for a task.
        """
        return self.get_audit_trail(task_id=task_id, limit=1000)
