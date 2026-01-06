"""
Agent-OS v3 Task Retry Mechanism

Following million-step methodology:
- Tracks retry counts per task
- Implements exponential backoff with max cap
- Maximum 3 retries before permanent failure
- Uses existing db infrastructure
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from db import query_one, update


class RetryManager:
    """
    Manages task retry logic with exponential backoff.
    
    Core principle: Failed tasks get limited retries with increasing delays.
    After max retries, tasks are marked as permanently_failed.
    """
    
    def __init__(self, max_retries: int = 3, base_delay: int = 30, max_delay: int = 300):
        """
        Initialize retry manager.
        
        Args:
            max_retries: Maximum retry attempts (default: 3)
            base_delay: Base delay in seconds (default: 30)
            max_delay: Maximum delay cap in seconds (default: 300)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def should_retry(self, task_id: str) -> bool:
        """
        Check if a task should be retried based on current retry count.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if task can be retried, False if max retries exceeded
        """
        task = query_one(
            "SELECT retry_count FROM tasks WHERE id = %s",
            (task_id,)
        )
        
        if not task:
            return False
            
        retry_count = task.get('retry_count', 0)
        return retry_count < self.max_retries
    
    def record_retry(self, task_id: str, error_reason: Optional[str] = None) -> bool:
        """
        Record a retry attempt and update task status.
        
        Args:
            task_id: Task identifier
            error_reason: Optional reason for the retry
            
        Returns:
            True if retry was recorded, False if max retries exceeded
        """
        # Get current task state
        task = query_one(
            "SELECT retry_count, retry_history FROM tasks WHERE id = %s",
            (task_id,)
        )
        
        if not task:
            return False
        
        current_retry_count = task.get('retry_count', 0)
        
        # Check if we can retry
        if current_retry_count >= self.max_retries:
            # Mark as permanently failed
            update(
                'tasks',
                {
                    'status': 'permanently_failed',
                    'updated_at': datetime.utcnow()
                },
                {'id': task_id}
            )
            return False
        
        # Increment retry count
        new_retry_count = current_retry_count + 1
        
        # Update retry history
        retry_history = task.get('retry_history') or []
        if isinstance(retry_history, str):
            try:
                retry_history = json.loads(retry_history)
            except:
                retry_history = []
        
        retry_entry = {
            'attempt': new_retry_count,
            'timestamp': datetime.utcnow().isoformat(),
            'reason': error_reason
        }
        retry_history.append(retry_entry)
        
        # Calculate next retry time
        delay = self.get_retry_delay(new_retry_count)
        next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
        
        # Update task
        if new_retry_count >= self.max_retries:
            # This was the last retry attempt
            status = 'permanently_failed'
        else:
            # Schedule for retry
            status = 'queued'
        
        rows_updated = update(
            'tasks',
            {
                'retry_count': new_retry_count,
                'retry_history': json.dumps(retry_history, default=str),
                'status': status,
                'next_retry_at': next_retry_at,
                'updated_at': datetime.utcnow()
            },
            {'id': task_id}
        )
        
        return rows_updated > 0
    
    def get_retry_delay(self, retry_count: int) -> int:
        """
        Calculate exponential backoff delay for retry attempt.
        
        Formula: min(max_delay, base_delay * 2^retry_count)
        
        Args:
            retry_count: Current retry attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        if retry_count <= 0:
            return 0
        
        # Exponential backoff: 30 * 2^retry_count
        delay = self.base_delay * (2 ** (retry_count - 1))
        
        # Cap at maximum delay
        return min(self.max_delay, delay)
    
    def reset_retries(self, task_id: str) -> bool:
        """
        Reset retry count and history for a task.
        
        Useful when task requirements change or manual intervention occurs.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if reset was successful
        """
        rows_updated = update(
            'tasks',
            {
                'retry_count': 0,
                'retry_history': json.dumps([]),
                'next_retry_at': None,
                'updated_at': datetime.utcnow()
            },
            {'id': task_id}
        )
        
        return rows_updated > 0
    
    def get_retry_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current retry status for a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dict with retry information or None if task not found
        """
        task = query_one(
            "SELECT retry_count, retry_history, next_retry_at, status FROM tasks WHERE id = %s",
            (task_id,)
        )
        
        if not task:
            return None
        
        retry_history = task.get('retry_history', '[]')
        if isinstance(retry_history, str):
            try:
                retry_history = json.loads(retry_history)
            except:
                retry_history = []
        
        return {
            'task_id': task_id,
            'retry_count': task.get('retry_count', 0),
            'max_retries': self.max_retries,
            'can_retry': self.should_retry(task_id),
            'retry_history': retry_history,
            'next_retry_at': task.get('next_retry_at'),
            'status': task.get('status')
        }
    
    def get_tasks_ready_for_retry(self) -> list:
        """
        Get tasks that are ready to be retried (past their retry delay).
        
        Returns:
            List of task records ready for retry
        """
        from db import query_all
        
        tasks = query_all(
            """
            SELECT id, title, retry_count, next_retry_at
            FROM tasks 
            WHERE status = 'queued' 
            AND retry_count > 0 
            AND next_retry_at <= %s
            ORDER BY next_retry_at ASC
            """,
            (datetime.utcnow(),)
        )
        
        return tasks or []
