"""
Agent-OS v3 Task Progress Tracker

Following million-step methodology:
- Tracks task progress through pipeline phases
- Provides progress percentage calculations
- Integrates with checkpoint system for state recovery
- Emits progress events for notification system
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))

from db import query_one, query_all, update
from checkpoints import CheckpointManager


class TaskPhase(Enum):
    """Task execution phases with progress weights."""
    INITIALIZING = ("initializing", 0)
    DRAFTING = ("drafting", 10)
    DRAFTING_COMPLETE = ("drafting_complete", 30)
    VERIFICATION = ("verification", 35)
    VERIFICATION_COMPLETE = ("verification_complete", 55)
    COMPLIANCE = ("compliance", 60)
    COMPLIANCE_COMPLETE = ("compliance_complete", 70)
    EXECUTION = ("execution", 75)
    COMMITTING = ("committing", 85)
    PUSHING = ("pushing", 90)
    CREATING_PR = ("creating_pr", 95)
    COMPLETE = ("complete", 100)
    
    def __init__(self, phase_name: str, progress_percent: int):
        self.phase_name = phase_name
        self.progress_percent = progress_percent
    
    @classmethod
    def from_string(cls, phase_str: str) -> Optional['TaskPhase']:
        """Get TaskPhase enum from string name."""
        for phase in cls:
            if phase.phase_name == phase_str:
                return phase
        return None


class TaskTracker:
    """
    Tracks task progress through the execution pipeline.
    
    Provides:
    - Current phase and progress percentage
    - Phase transition history from checkpoints
    - Progress updates for notification system
    - Task status queries
    """
    
    def __init__(self, checkpoint_manager: Optional[CheckpointManager] = None):
        """
        Initialize task tracker.
        
        Args:
            checkpoint_manager: Optional CheckpointManager for checkpoint integration
        """
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
    
    def get_task_progress(self, task_id: str) -> Dict[str, Any]:
        """
        Get current progress for a task.
        
        Args:
            task_id: UUID of the task
        
        Returns:
            Dict with:
                - task_id: UUID
                - current_phase: Phase name
                - progress_percent: 0-100
                - status: Task status
                - started_at: Timestamp or None
                - last_checkpoint: Last checkpoint info or None
        """
        task = query_one(
            "SELECT id, status, current_phase, started_at, updated_at FROM tasks WHERE id = %s",
            (task_id,)
        )
        
        if not task:
            return {
                'task_id': task_id,
                'error': 'Task not found',
                'progress_percent': 0
            }
        
        # Get current phase progress
        current_phase_str = task.get('current_phase', 'initializing')
        phase = TaskPhase.from_string(current_phase_str)
        progress_percent = phase.progress_percent if phase else 0
        
        # Get last checkpoint for additional context
        last_checkpoint = query_one(
            """
            SELECT id, phase, step_name, status, created_at, completed_at
            FROM checkpoints
            WHERE task_id = %s
            ORDER BY global_sequence DESC
            LIMIT 1
            """,
            (task_id,)
        )
        
        return {
            'task_id': str(task['id']),
            'current_phase': current_phase_str,
            'progress_percent': progress_percent,
            'status': task['status'],
            'started_at': task.get('started_at'),
            'updated_at': task.get('updated_at'),
            'last_checkpoint': {
                'id': last_checkpoint['id'],
                'phase': last_checkpoint['phase'],
                'step_name': last_checkpoint['step_name'],
                'status': last_checkpoint['status'],
                'created_at': last_checkpoint['created_at']
            } if last_checkpoint else None
        }
    
    def update_task_phase(
        self,
        task_id: str,
        phase: str,
        status: Optional[str] = None
    ) -> bool:
        """
        Update task phase and optionally status.
        
        Args:
            task_id: UUID of the task
            phase: New phase name (must match TaskPhase enum)
            status: Optional new status ('running', 'complete', 'failed', 'halted')
        
        Returns:
            True if update succeeded, False otherwise
        """
        # Validate phase
        if not TaskPhase.from_string(phase):
            return False
        
        update_data = {
            'current_phase': phase,
            'updated_at': datetime.utcnow()
        }
        
        if status:
            update_data['status'] = status
            
            # Set completion timestamp if complete
            if status == 'complete':
                update_data['completed_at'] = datetime.utcnow()
        
        rows = update('tasks', update_data, {'id': task_id})
        return rows > 0
    
    def get_phase_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get phase transition history from checkpoints.
        
        Args:
            task_id: UUID of the task
        
        Returns:
            List of checkpoint records showing phase transitions
        """
        checkpoints = query_all(
            """
            SELECT id, phase, step_name, status, created_at, completed_at
            FROM checkpoints
            WHERE task_id = %s
            ORDER BY global_sequence ASC
            """,
            (task_id,)
        )
        
        return [
            {
                'checkpoint_id': cp['id'],
                'phase': cp['phase'],
                'step_name': cp['step_name'],
                'status': cp['status'],
                'created_at': cp['created_at'],
                'completed_at': cp['completed_at']
            }
            for cp in checkpoints
        ]
    
    def get_all_tasks_progress(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get progress for all tasks, optionally filtered by project.
        
        Args:
            project_id: Optional project UUID filter
        
        Returns:
            List of task progress dicts
        """
        if project_id:
            tasks = query_all(
                "SELECT id FROM tasks WHERE project_id = %s ORDER BY created_at DESC",
                (project_id,)
            )
        else:
            tasks = query_all(
                "SELECT id FROM tasks ORDER BY created_at DESC"
            )
        
        return [self.get_task_progress(str(task['id'])) for task in tasks]
    
    def calculate_estimated_completion(
        self,
        task_id: str,
        current_phase: str
    ) -> Optional[Dict[str, Any]]:
        """
        Estimate remaining time based on checkpoint timing.
        
        Args:
            task_id: UUID of the task
            current_phase: Current phase name
        
        Returns:
            Dict with estimated_seconds_remaining or None if cannot estimate
        """
        task = query_one(
            "SELECT started_at FROM tasks WHERE id = %s",
            (task_id,)
        )
        
        if not task or not task.get('started_at'):
            return None
        
        phase = TaskPhase.from_string(current_phase)
        if not phase:
            return None
        
        # Get elapsed time
        elapsed = (datetime.utcnow() - task['started_at']).total_seconds()
        
        # Calculate estimated total time based on progress
        progress_fraction = phase.progress_percent / 100.0
        if progress_fraction == 0:
            return None
        
        estimated_total = elapsed / progress_fraction
        estimated_remaining = estimated_total - elapsed
        
        return {
            'elapsed_seconds': elapsed,
            'estimated_total_seconds': estimated_total,
            'estimated_seconds_remaining': max(0, estimated_remaining),
            'progress_percent': phase.progress_percent
        }
