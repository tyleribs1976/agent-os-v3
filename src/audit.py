"""
Agent-OS v3 Immutable Audit Logger

All actions are logged immutably. Records cannot be updated or deleted.
This provides complete audit trail for compliance and debugging.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import json

from db import query_one, query_all, execute


# Valid action types
ACTION_TYPES = [
    'TASK_CREATED',
    'TASK_QUEUED',
    'TASK_STARTED',
    'DRAFT_STARTED',
    'DRAFT_COMPLETED',
    'DRAFT_FAILED',
    'VERIFICATION_STARTED',
    'VERIFICATION_PASSED',
    'VERIFICATION_FAILED',
    'COMPLIANCE_STARTED',
    'COMPLIANCE_CLEARED',
    'COMPLIANCE_BLOCKED',
    'EXECUTION_STARTED',
    'EXECUTION_COMPLETED',
    'EXECUTION_FAILED',
    'HALT_TRIGGERED',
    'ERROR_OCCURRED',
    'CHECKPOINT_CREATED',
    'ROLLBACK_STARTED',
    'ROLLBACK_COMPLETED',
    'AGENT_REGISTERED',
    'AGENT_TERMINATED',
]


class AuditLogger:
    """
    Immutable audit logger for Agent-OS v3.
    
    All inserts are append-only. Records are never updated or deleted.
    Uses project_id to link related actions across task lifecycle.
    """
    
    def __init__(self):
        self._current_project_id: Optional[str] = None
    
    def start_correlation(self) -> str:
        """Start a new correlation context. Returns project_id."""
        self._current_project_id = str(uuid.uuid4())
        return self._current_project_id
    
    def set_correlation(self, project_id: str):
        """Set project_id for subsequent log entries."""
        self._current_project_id = project_id
    
    def log_action(
        self,
        action: str,
        details: Dict[str, Any],
        agent_id: Optional[int] = None,
        task_id: Optional[str] = None,
        checkpoint_id: Optional[int] = None,
        project_id: Optional[str] = None
    ) -> int:
        """
        Log an action to the audit trail.
        
        Args:
            action: One of the valid ACTION_TYPES
            details: Dict with action-specific details
            agent_id: Optional agent that performed action
            task_id: Optional task this action relates to
            checkpoint_id: Optional checkpoint this action relates to
            project_id: Optional correlation ID (uses current if not provided)
            
        Returns:
            The log entry ID
        """
        if action not in ACTION_TYPES:
            # Log unknown types anyway but flag them
            details['_unknown_action'] = True
        
        corr_id = project_id or self._current_project_id
        
        # Build the INSERT SQL manually to ensure immutability
        sql = """
            INSERT INTO audit_log (
                timestamp, action, agent_id, task_id, 
                checkpoint_id, metadata, project_id
            ) VALUES (
                NOW(), %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """
        
        params = (
            action,
            agent_id,
            task_id,
            checkpoint_id,
            json.dumps(details, default=str),
            corr_id
        )
        
        result = query_one(sql, params)
        return result['id'] if result else 0
    
    def get_task_audit_trail(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all audit log entries for a task, ordered by time."""
        return query_all(
            "SELECT * FROM audit_log WHERE task_id = %s ORDER BY timestamp ASC",
            (task_id,)
        ) or []
    
    def get_agent_audit_trail(self, agent_id: int) -> List[Dict[str, Any]]:
        """Get all audit log entries for an agent, ordered by time."""
        return query_all(
            "SELECT * FROM audit_log WHERE agent_id = %s ORDER BY timestamp ASC",
            (agent_id,)
        ) or []
    
    def get_correlation_trail(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all audit log entries with given project_id."""
        return query_all(
            "SELECT * FROM audit_log WHERE project_id = %s ORDER BY timestamp ASC",
            (project_id,)
        ) or []
    
    def get_recent_actions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get most recent audit log entries."""
        return query_all(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT %s",
            (limit,)
        ) or []
    
    def search_logs(
        self,
        action: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Search audit logs with filters.
        
        Args:
            action: Filter by action type
            start_time: Filter entries after this time
            end_time: Filter entries before this time
            limit: Maximum entries to return
        """
        conditions = []
        params = []
        
        if action:
            conditions.append("action = %s")
            params.append(action)
        
        if start_time:
            conditions.append("timestamp >= %s")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= %s")
            params.append(end_time)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        
        sql = f"SELECT * FROM audit_log WHERE {where_clause} ORDER BY timestamp DESC LIMIT %s"
        
        return query_all(sql, tuple(params)) or []
    
    def get_action_counts(self) -> Dict[str, int]:
        """Get count of each action type."""
        results = query_all(
            "SELECT action, COUNT(*) as count FROM audit_log GROUP BY action ORDER BY count DESC"
        )
        return {r['action']: r['count'] for r in (results or [])}
    
    def get_error_summary(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent errors and halts."""
        return query_all(
            """
            SELECT * FROM audit_log 
            WHERE action IN ('ERROR_OCCURRED', 'HALT_TRIGGERED', 'DRAFT_FAILED', 'EXECUTION_FAILED')
            AND timestamp > NOW() - INTERVAL '%s hours'
            ORDER BY timestamp DESC
            """,
            (hours,)
        ) or []


# Singleton instance
_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the singleton AuditLogger instance."""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger


# Convenience functions
def log_action(action: str, details: Dict[str, Any], **kwargs) -> int:
    """Convenience function to log an action."""
    return get_audit_logger().log_action(action, details, **kwargs)
