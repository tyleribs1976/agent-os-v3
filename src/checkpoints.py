"""
Agent-OS v3 Checkpoint Manager

Following million-step methodology:
- Every state change is checkpointed
- Checkpoints are the primitive for recovery
- State is fully serialized (no implicit state)
- Rollback is always possible for reversible steps
"""

import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import uuid4

from db import (
    get_cursor, transaction, insert_returning, 
    update, query_one, query_all
)


def safe_json_loads(val):
    """Safely load JSON - handles JSONB already parsed by psycopg2."""
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    return json.loads(val)


def compute_hash(data: Dict[str, Any]) -> str:
    """Compute SHA256 hash of data for integrity checking."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


class CheckpointManager:
    """
    Manages checkpoint creation, retrieval, and recovery.
    
    Core principle: All state must pass through checkpoints.
    """
    
    def __init__(self):
        self._global_sequence = None
    
    def get_next_sequence(self) -> int:
        """Get next global sequence number (monotonically increasing)."""
        result = query_one(
            "SELECT COALESCE(MAX(global_sequence), 0) + 1 as next_seq FROM checkpoints"
        )
        return result['next_seq'] if result else 1
    
    def create_checkpoint(
        self,
        project_id: str,
        phase: str,
        step_name: str,
        state_snapshot: Dict[str, Any],
        task_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,  # Additional inputs for context
        inputs_hash: Optional[str] = None,
        outputs_hash: Optional[str] = None,
        outputs: Optional[Dict[str, Any]] = None,
        drafter_agent_id: Optional[str] = None,
        verifier_agent_id: Optional[str] = None,
        previous_checkpoint_id: Optional[int] = None,
        rollback_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new checkpoint.
        
        Returns the created checkpoint record.
        """
        global_sequence = self.get_next_sequence()
        
        if inputs_hash is None:
            inputs_hash = compute_hash(state_snapshot)
        
        checkpoint_data = {
            'global_sequence': global_sequence,
            'project_id': project_id,
            'task_id': task_id,
            'phase': phase,
            'step_name': step_name,
            'state_snapshot': json.dumps(state_snapshot, default=str),
            'inputs_hash': inputs_hash,
            'outputs_hash': outputs_hash,
            'drafter_agent_id': drafter_agent_id,
            'verifier_agent_id': verifier_agent_id,
            'status': 'created',
            'previous_checkpoint_id': previous_checkpoint_id,
            'rollback_data': json.dumps(rollback_data, default=str) if rollback_data else None,
        }
        
        result = insert_returning('checkpoints', checkpoint_data)
        return result
    
    def complete_checkpoint(
        self,
        checkpoint_id: int,
        outputs_hash: Optional[str] = None,
        outputs: Optional[Dict[str, Any]] = None,
        rollback_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark a checkpoint as complete."""
        data = {
            'status': 'complete',
            'completed_at': datetime.utcnow()
        }
        if outputs_hash:
            data['outputs_hash'] = outputs_hash
        elif outputs:
            data['outputs_hash'] = compute_hash(outputs)
        if rollback_data:
            data['rollback_data'] = json.dumps(rollback_data, default=str)
        
        rows = update('checkpoints', data, {'id': checkpoint_id})
        return rows > 0
    
    def fail_checkpoint(
        self,
        checkpoint_id: int,
        error_details: Dict[str, Any]
    ) -> bool:
        """Mark a checkpoint as failed."""
        data = {
            'status': 'failed',
            'completed_at': datetime.utcnow(),
            'error_details': json.dumps(error_details, default=str),
        }
        rows = update('checkpoints', data, {'id': checkpoint_id})
        return rows > 0
    
    def get_checkpoint(self, checkpoint_id: int) -> Optional[Dict[str, Any]]:
        """Get a checkpoint by ID."""
        result = query_one(
            "SELECT * FROM checkpoints WHERE id = %s",
            (checkpoint_id,)
        )
        
        if result:
            # Parse JSON fields - handle both string and pre-parsed JSONB
            if result.get('state_snapshot'):
                result['state_snapshot'] = safe_json_loads(result['state_snapshot'])
            if result.get('error_details'):
                result['error_details'] = safe_json_loads(result['error_details'])
            if result.get('rollback_data'):
                result['rollback_data'] = safe_json_loads(result['rollback_data'])
        
        return result
    
    def get_latest_checkpoint(
        self,
        project_id: str,
        task_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent checkpoint for a project/task."""
        if task_id:
            result = query_one(
                """
                SELECT * FROM checkpoints 
                WHERE project_id = %s AND task_id = %s
                ORDER BY global_sequence DESC
                LIMIT 1
                """,
                (project_id, task_id)
            )
        else:
            result = query_one(
                """
                SELECT * FROM checkpoints 
                WHERE project_id = %s
                ORDER BY global_sequence DESC
                LIMIT 1
                """,
                (project_id,)
            )
        
        if result:
            if result.get('state_snapshot'):
                result['state_snapshot'] = safe_json_loads(result['state_snapshot'])
            if result.get('error_details'):
                result['error_details'] = safe_json_loads(result['error_details'])
            if result.get('rollback_data'):
                result['rollback_data'] = safe_json_loads(result['rollback_data'])
        
        return result
    
    def get_checkpoint_chain(
        self,
        start_checkpoint_id: int,
        end_checkpoint_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get chain of checkpoints from start to end (or latest)."""
        if end_checkpoint_id:
            results = query_all(
                """
                SELECT * FROM checkpoints 
                WHERE global_sequence >= (SELECT global_sequence FROM checkpoints WHERE id = %s)
                AND global_sequence <= (SELECT global_sequence FROM checkpoints WHERE id = %s)
                ORDER BY global_sequence
                """,
                (start_checkpoint_id, end_checkpoint_id)
            )
        else:
            results = query_all(
                """
                SELECT * FROM checkpoints 
                WHERE global_sequence >= (SELECT global_sequence FROM checkpoints WHERE id = %s)
                ORDER BY global_sequence
                """,
                (start_checkpoint_id,)
            )
        
        for result in results:
            if result.get('state_snapshot'):
                result['state_snapshot'] = safe_json_loads(result['state_snapshot'])
            if result.get('error_details'):
                result['error_details'] = safe_json_loads(result['error_details'])
            if result.get('rollback_data'):
                result['rollback_data'] = safe_json_loads(result['rollback_data'])
        
        return results
    
    def get_failed_checkpoints(
        self,
        project_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent failed checkpoints for review."""
        if project_id:
            results = query_all(
                """
                SELECT * FROM checkpoints 
                WHERE status = 'failed' AND project_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (project_id, limit)
            )
        else:
            results = query_all(
                """
                SELECT * FROM checkpoints 
                WHERE status = 'failed'
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,)
            )
        
        for result in results:
            if result.get('error_details'):
                result['error_details'] = safe_json_loads(result['error_details'])
        
        return results


# Convenience functions for common checkpoint operations

def create_task_checkpoint(
    task_id: str,
    project_id: str,
    phase: str,
    step: str,
    state: Dict[str, Any],
    agent_id: Optional[str] = None
) -> Dict[str, Any]:
    """Create a checkpoint for a task execution step."""
    manager = CheckpointManager()
    return manager.create_checkpoint(
        project_id=project_id,
        task_id=task_id,
        phase=phase,
        step_name=step,
        state_snapshot=state,
        drafter_agent_id=agent_id if 'draft' in phase.lower() else None,
        verifier_agent_id=agent_id if 'verif' in phase.lower() else None
    )


def get_task_state(task_id: str, project_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest state for a task."""
    manager = CheckpointManager()
    checkpoint = manager.get_latest_checkpoint(project_id, task_id)
    if checkpoint:
        return checkpoint.get('state_snapshot')
    return None
