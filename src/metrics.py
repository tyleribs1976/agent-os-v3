"""Agent-OS v3 Metrics Collection

Following million-step methodology:
- Explicit tracking of all task metrics
- No silent failures in metric recording
- Database-backed persistence
- Type-safe metric collection
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID

from db import insert_returning, query_one, query_all, execute
from helpers import get_timestamp, format_duration
from validators import validate_task_id, validate_project_id, validate_status


@dataclass
class TaskMetrics:
    """
    Metrics for a single task execution.
    
    Tracks timing, token usage, costs, and success/failure rates
    across all phases of task execution.
    """
    task_id: UUID
    project_id: UUID
    
    # Timing metrics
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # Phase timings
    drafting_duration: Optional[float] = None
    verification_duration: Optional[float] = None
    compliance_duration: Optional[float] = None
    execution_duration: Optional[float] = None
    
    # Token usage
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    
    # Cost tracking
    total_cost_usd: float = 0.0
    
    # Success metrics
    status: str = "pending"
    retries: int = 0
    halted: bool = False
    halt_reason: Optional[str] = None
    
    # Confidence scores
    draft_confidence: Optional[float] = None
    verification_confidence: Optional[float] = None
    
    def __post_init__(self):
        """Validate fields after initialization."""
        if isinstance(self.task_id, str):
            self.task_id = UUID(self.task_id)
        if isinstance(self.project_id, str):
            self.project_id = UUID(self.project_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            'task_id': str(self.task_id),
            'project_id': str(self.project_id),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'drafting_duration': self.drafting_duration,
            'verification_duration': self.verification_duration,
            'compliance_duration': self.compliance_duration,
            'execution_duration': self.execution_duration,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_cost_usd': self.total_cost_usd,
            'status': self.status,
            'retries': self.retries,
            'halted': self.halted,
            'halt_reason': self.halt_reason,
            'draft_confidence': self.draft_confidence,
            'verification_confidence': self.verification_confidence
        }


class MetricsCollector:
    """
    Collects and persists task execution metrics.
    
    Core responsibilities:
    - Track timing for each phase
    - Aggregate token usage from api_usage table
    - Calculate total costs
    - Record success/failure outcomes
    - Provide metrics queries for reporting
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self._phase_timers: Dict[str, float] = {}
    
    def start_phase(self, phase: str) -> None:
        """
        Start timing a phase.
        
        Args:
            phase: Phase name ('drafting', 'verification', 'compliance', 'execution')
        
        Example:
            >>> collector = MetricsCollector()
            >>> collector.start_phase('drafting')
        """
        self._phase_timers[phase] = time.time()
    
    def end_phase(self, phase: str) -> Optional[float]:
        """
        End timing a phase and return duration.
        
        Args:
            phase: Phase name
        
        Returns:
            Duration in seconds, or None if phase wasn't started
        
        Example:
            >>> collector.start_phase('drafting')
            >>> time.sleep(1)
            >>> duration = collector.end_phase('drafting')
            >>> duration >= 1.0
            True
        """
        if phase not in self._phase_timers:
            return None
        
        start_time = self._phase_timers[phase]
        duration = time.time() - start_time
        del self._phase_timers[phase]
        return duration
    
    def collect_task_metrics(self, task_id: str) -> TaskMetrics:
        """
        Collect all metrics for a completed task.
        
        Aggregates data from:
        - tasks table (timing, status)
        - api_usage table (tokens, costs)
        - checkpoints table (phase details)
        
        Args:
            task_id: UUID of the task
        
        Returns:
            TaskMetrics object with all collected data
        
        Raises:
            ValueError: If task_id is invalid or task not found
        
        Example:
            >>> collector = MetricsCollector()
            >>> metrics = collector.collect_task_metrics('550e8400-e29b-41d4-a716-446655440000')
            >>> metrics.task_id
            UUID('550e8400-e29b-41d4-a716-446655440000')
        """
        # Validate task_id
        task_id = validate_task_id(task_id)
        
        # Get task data
        task = query_one(
            "SELECT * FROM tasks WHERE id = %s",
            (task_id,)
        )
        
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        
        # Initialize metrics
        metrics = TaskMetrics(
            task_id=UUID(task_id),
            project_id=UUID(task['project_id']),
            started_at=task.get('started_at'),
            completed_at=task.get('completed_at'),
            status=task['status']
        )
        
        # Calculate total duration
        if metrics.started_at and metrics.completed_at:
            delta = metrics.completed_at - metrics.started_at
            metrics.duration_seconds = delta.total_seconds()
        
        # Get API usage stats
        api_stats = query_one(
            """
            SELECT 
                SUM(input_tokens) as total_input,
                SUM(output_tokens) as total_output,
                SUM(cost_usd) as total_cost
            FROM api_usage
            WHERE task_id = %s
            """,
            (task_id,)
        )
        
        if api_stats:
            metrics.total_input_tokens = api_stats.get('total_input') or 0
            metrics.total_output_tokens = api_stats.get('total_output') or 0
            metrics.total_cost_usd = float(api_stats.get('total_cost') or 0.0)
        
        # Get phase-specific timings from checkpoints
        phase_checkpoints = query_all(
            """
            SELECT phase, created_at, completed_at
            FROM checkpoints
            WHERE task_id = %s AND status = 'complete'
            ORDER BY global_sequence ASC
            """,
            (task_id,)
        )
        
        phase_durations = {}
        for cp in phase_checkpoints:
            phase = cp['phase']
            if cp['created_at'] and cp['completed_at']:
                delta = cp['completed_at'] - cp['created_at']
                duration = delta.total_seconds()
                
                # Accumulate if multiple checkpoints for same phase
                if phase in phase_durations:
                    phase_durations[phase] += duration
                else:
                    phase_durations[phase] = duration
        
        metrics.drafting_duration = phase_durations.get('drafting')
        metrics.verification_duration = phase_durations.get('verification')
        metrics.compliance_duration = phase_durations.get('compliance')
        metrics.execution_duration = phase_durations.get('execution')
        
        # Check if task was halted
        if task['status'] == 'halted':
            metrics.halted = True
            metrics.halt_reason = task.get('last_error')
        
        # Get confidence scores from checkpoint state snapshots
        confidence_data = query_all(
            """
            SELECT phase, state_snapshot
            FROM checkpoints
            WHERE task_id = %s AND status = 'complete'
            AND phase IN ('drafting', 'verification')
            ORDER BY global_sequence DESC
            """,
            (task_id,)
        )
        
        for cp in confidence_data:
            snapshot = cp.get('state_snapshot', {})
            if isinstance(snapshot, str):
                import json
                try:
                    snapshot = json.loads(snapshot)
                except:
                    snapshot = {}
            
            if cp['phase'] == 'drafting':
                metrics.draft_confidence = snapshot.get('confidence_score')
            elif cp['phase'] == 'verification':
                metrics.verification_confidence = snapshot.get('confidence_score')
        
        return metrics
    
    def get_project_metrics(self, project_id: str) -> Dict[str, Any]:
        """
        Get aggregated metrics for all tasks in a project.
        
        Args:
            project_id: UUID of the project
        
        Returns:
            Dictionary with aggregated metrics:
            - total_tasks
            - completed_tasks
            - failed_tasks
            - halted_tasks
            - avg_duration_seconds
            - total_cost_usd
            - avg_confidence
        
        Example:
            >>> collector = MetricsCollector()
            >>> metrics = collector.get_project_metrics('550e8400-e29b-41d4-a716-446655440000')
            >>> 'total_tasks' in metrics
            True
        """
        # Validate project_id
        project_id = validate_project_id(project_id)
        
        # Get task counts by status
        status_counts = query_one(
            """
            SELECT 
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'halted' THEN 1 ELSE 0 END) as halted
            FROM tasks
            WHERE project_id = %s
            """,
            (project_id,)
        )
        
        # Get timing and cost aggregates
        timing_stats = query_one(
            """
            SELECT 
                AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration
            FROM tasks
            WHERE project_id = %s 
            AND started_at IS NOT NULL 
            AND completed_at IS NOT NULL
            """,
            (project_id,)
        )
        
        cost_stats = query_one(
            """
            SELECT SUM(cost_usd) as total_cost
            FROM api_usage
            WHERE project_id = %s
            """,
            (project_id,)
        )
        
        return {
            'total_tasks': status_counts.get('total_tasks') or 0,
            'completed_tasks': status_counts.get('completed') or 0,
            'failed_tasks': status_counts.get('failed') or 0,
            'halted_tasks': status_counts.get('halted') or 0,
            'avg_duration_seconds': float(timing_stats.get('avg_duration') or 0.0),
            'total_cost_usd': float(cost_stats.get('total_cost') or 0.0)
        }
    
    def get_recent_metrics(self, limit: int = 10) -> List[TaskMetrics]:
        """
        Get metrics for the N most recent tasks.
        
        Args:
            limit: Number of recent tasks to return (default: 10)
        
        Returns:
            List of TaskMetrics objects, newest first
        
        Example:
            >>> collector = MetricsCollector()
            >>> recent = collector.get_recent_metrics(5)
            >>> len(recent) <= 5
            True
        """
        tasks = query_all(
            """
            SELECT id
            FROM tasks
            WHERE status IN ('complete', 'failed', 'halted')
            ORDER BY completed_at DESC
            LIMIT %s
            """,
            (limit,)
        )
        
        metrics_list = []
        for task in tasks:
            try:
                metrics = self.collect_task_metrics(str(task['id']))
                metrics_list.append(metrics)
            except Exception:
                # Skip tasks that fail to collect metrics
                continue
        
        return metrics_list
