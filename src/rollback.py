"""
Agent-OS v3 Rollback Manager

Following million-step methodology:
- Rollback is ONLY for reversible steps
- HALT on any rollback failure (never proceed with corrupted state)
- Verify state at each rollback step
- Full audit trail of all rollback operations
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from db import query_one, query_all, update
from checkpoints import CheckpointManager, safe_json_loads


class RollbackStatus(Enum):
    """Status of rollback operations."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    BLOCKED = "blocked"


@dataclass
class RollbackResult:
    """Result of a rollback operation."""
    status: RollbackStatus
    rolled_back_to: Optional[int]  # checkpoint_id we rolled back to
    steps_executed: int
    steps_failed: int
    error_details: Optional[Dict[str, Any]] = None
    verification_results: Optional[List[Dict[str, Any]]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status.value,
            'rolled_back_to': self.rolled_back_to,
            'steps_executed': self.steps_executed,
            'steps_failed': self.steps_failed,
            'error_details': self.error_details,
            'verification_results': self.verification_results
        }


class RollbackManager:
    """
    Manages rollback operations for checkpoint recovery.
    
    Core principles:
    - Only rollback reversible steps
    - HALT immediately on any rollback failure
    - Verify state matches expected after each rollback
    - Never proceed with corrupted state
    """
    
    def __init__(self):
        self.checkpoint_manager = CheckpointManager()
    
    def rollback_to_checkpoint(self, target_checkpoint_id: int) -> RollbackResult:
        """
        Rollback to a specific checkpoint.
        
        Args:
            target_checkpoint_id: Checkpoint to rollback to
        
        Returns:
            RollbackResult with status and details
        """
        
        # Validate target checkpoint exists
        target_checkpoint = self.checkpoint_manager.get_checkpoint(target_checkpoint_id)
        if not target_checkpoint:
            return RollbackResult(
                status=RollbackStatus.FAILED,
                rolled_back_to=None,
                steps_executed=0,
                steps_failed=1,
                error_details={
                    'reason': 'target_not_found',
                    'message': f'Target checkpoint {target_checkpoint_id} not found'
                }
            )
        
        # Get the checkpoint chain to rollback
        try:
            checkpoint_chain = self.get_checkpoint_chain(target_checkpoint_id)
        except Exception as e:
            return RollbackResult(
                status=RollbackStatus.FAILED,
                rolled_back_to=None,
                steps_executed=0,
                steps_failed=1,
                error_details={
                    'reason': 'chain_retrieval_failed',
                    'message': str(e)
                }
            )
        
        if not checkpoint_chain:
            # Already at target or no rollback needed
            return RollbackResult(
                status=RollbackStatus.SUCCESS,
                rolled_back_to=target_checkpoint_id,
                steps_executed=0,
                steps_failed=0
            )
        
        # Execute rollbacks in reverse order
        steps_executed = 0
        verification_results = []
        
        for checkpoint in reversed(checkpoint_chain):
            # Check if this checkpoint has rollback data
            rollback_data = checkpoint.get('rollback_data')
            if not rollback_data:
                return RollbackResult(
                    status=RollbackStatus.BLOCKED,
                    rolled_back_to=None,
                    steps_executed=steps_executed,
                    steps_failed=1,
                    error_details={
                        'reason': 'no_rollback_data',
                        'message': f'Checkpoint {checkpoint["id"]} has no rollback data - step may be irreversible',
                        'checkpoint_id': checkpoint['id']
                    }
                )
            
            # Execute the rollback for this checkpoint
            try:
                rollback_result = self.execute_rollback(checkpoint)
                if not rollback_result['success']:
                    return RollbackResult(
                        status=RollbackStatus.FAILED,
                        rolled_back_to=None,
                        steps_executed=steps_executed,
                        steps_failed=1,
                        error_details={
                            'reason': 'rollback_execution_failed',
                            'message': rollback_result.get('error', 'Unknown rollback error'),
                            'checkpoint_id': checkpoint['id']
                        }
                    )
                
                steps_executed += 1
                
                # Verify state matches expected after rollback
                verification = self.verify_state_matches(checkpoint['id'])
                verification_results.append({
                    'checkpoint_id': checkpoint['id'],
                    'verified': verification,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                if not verification:
                    # CRITICAL: State verification failed - HALT
                    return RollbackResult(
                        status=RollbackStatus.FAILED,
                        rolled_back_to=None,
                        steps_executed=steps_executed,
                        steps_failed=1,
                        error_details={
                            'reason': 'state_verification_failed',
                            'message': f'State verification failed after rolling back checkpoint {checkpoint["id"]}',
                            'checkpoint_id': checkpoint['id']
                        },
                        verification_results=verification_results
                    )
                    
            except Exception as e:
                # CRITICAL: Rollback threw exception - HALT
                return RollbackResult(
                    status=RollbackStatus.FAILED,
                    rolled_back_to=None,
                    steps_executed=steps_executed,
                    steps_failed=1,
                    error_details={
                        'reason': 'rollback_exception',
                        'message': str(e),
                        'checkpoint_id': checkpoint['id']
                    },
                    verification_results=verification_results
                )
        
        # All rollbacks succeeded
        return RollbackResult(
            status=RollbackStatus.SUCCESS,
            rolled_back_to=target_checkpoint_id,
            steps_executed=steps_executed,
            steps_failed=0,
            verification_results=verification_results
        )
    
    def get_checkpoint_chain(self, target_id: int) -> List[Dict[str, Any]]:
        """
        Get the chain of checkpoints between current state and target checkpoint.
        
        Args:
            target_id: Target checkpoint ID to rollback to
        
        Returns:
            List of checkpoints that need to be rolled back (in creation order)
        """
        
        # Get target checkpoint to find its sequence
        target_checkpoint = query_one(
            "SELECT global_sequence, project_id, task_id FROM checkpoints WHERE id = %s",
            (target_id,)
        )
        
        if not target_checkpoint:
            raise ValueError(f"Target checkpoint {target_id} not found")
        
        # Get all checkpoints after the target in the same task/project
        # that need to be rolled back
        checkpoints = query_all(
            """
            SELECT id, global_sequence, phase, step_name, status, 
                   state_snapshot, rollback_data, created_at
            FROM checkpoints 
            WHERE global_sequence > %s 
              AND project_id = %s 
              AND (task_id = %s OR task_id IS NULL)
              AND status = 'complete'
            ORDER BY global_sequence ASC
            """,
            (
                target_checkpoint['global_sequence'],
                target_checkpoint['project_id'], 
                target_checkpoint['task_id']
            )
        )
        
        # Parse JSON fields
        for cp in checkpoints:
            if cp.get('state_snapshot'):
                cp['state_snapshot'] = safe_json_loads(cp['state_snapshot'])
            if cp.get('rollback_data'):
                cp['rollback_data'] = safe_json_loads(cp['rollback_data'])
        
        return checkpoints
    
    def execute_rollback(self, checkpoint: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute rollback for a single checkpoint.
        
        Args:
            checkpoint: Checkpoint dict with rollback_data
        
        Returns:
            Dict with success status and details
        """
        
        rollback_data = checkpoint.get('rollback_data')
        if not rollback_data:
            return {
                'success': False,
                'error': 'No rollback data available'
            }
        
        checkpoint_id = checkpoint['id']
        
        try:
            # Mark checkpoint as being rolled back
            update(
                'checkpoints',
                {
                    'status': 'rolling_back',
                    'rollback_started_at': datetime.utcnow()
                },
                {'id': checkpoint_id}
            )
            
            # Execute rollback operations based on rollback_data structure
            rollback_type = rollback_data.get('type', 'unknown')
            
            if rollback_type == 'file_operations':
                result = self._rollback_file_operations(rollback_data)
            elif rollback_type == 'database_operations':
                result = self._rollback_database_operations(rollback_data)
            elif rollback_type == 'git_operations':
                result = self._rollback_git_operations(rollback_data)
            else:
                return {
                    'success': False,
                    'error': f'Unknown rollback type: {rollback_type}'
                }
            
            if result['success']:
                # Mark checkpoint as rolled back
                update(
                    'checkpoints',
                    {
                        'status': 'rolled_back',
                        'rollback_completed_at': datetime.utcnow()
                    },
                    {'id': checkpoint_id}
                )
            else:
                # Mark rollback as failed
                update(
                    'checkpoints',
                    {
                        'status': 'rollback_failed',
                        'rollback_error': json.dumps(result.get('error_details', {}), default=str)
                    },
                    {'id': checkpoint_id}
                )
            
            return result
            
        except Exception as e:
            # Mark rollback as failed
            update(
                'checkpoints',
                {
                    'status': 'rollback_failed',
                    'rollback_error': str(e)
                },
                {'id': checkpoint_id}
            )
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def verify_state_matches(self, checkpoint_id: int) -> bool:
        """
        Verify that the current state matches what's expected for this checkpoint.
        
        Args:
            checkpoint_id: Checkpoint to verify against
        
        Returns:
            True if state matches, False otherwise
        """
        
        checkpoint = self.checkpoint_manager.get_checkpoint(checkpoint_id)
        if not checkpoint:
            return False
        
        state_snapshot = checkpoint.get('state_snapshot', {})
        
        # Basic verification - check if key state elements match
        # This is a simplified implementation - real verification would be more thorough
        
        try:
            # Verify project state if available
            if 'project_context' in state_snapshot:
                project_context = state_snapshot['project_context']
                work_dir = project_context.get('work_dir')
                
                if work_dir:
                    import os
                    if not os.path.exists(work_dir):
                        return False
            
            # Verify file states if tracked
            if 'file_states' in state_snapshot:
                for file_path, expected_hash in state_snapshot['file_states'].items():
                    import os
                    import hashlib
                    
                    if not os.path.exists(file_path):
                        return False
                    
                    # Check file hash matches
                    with open(file_path, 'rb') as f:
                        actual_hash = hashlib.sha256(f.read()).hexdigest()
                    
                    if actual_hash != expected_hash:
                        return False
            
            return True
            
        except Exception:
            # If verification throws exception, assume state doesn't match
            return False
    
    def _rollback_file_operations(self, rollback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback file system operations.
        
        Args:
            rollback_data: Contains file operations to reverse
        
        Returns:
            Dict with success status
        """
        
        import os
        import shutil
        
        operations = rollback_data.get('operations', [])
        
        try:
            for op in reversed(operations):  # Reverse order
                op_type = op.get('type')
                
                if op_type == 'create_file':
                    # Remove the created file
                    file_path = op.get('path')
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                        
                elif op_type == 'modify_file':
                    # Restore original content
                    file_path = op.get('path')
                    original_content = op.get('original_content')
                    
                    if file_path and original_content is not None:
                        with open(file_path, 'w') as f:
                            f.write(original_content)
                            
                elif op_type == 'delete_file':
                    # Restore the deleted file
                    file_path = op.get('path')
                    original_content = op.get('original_content')
                    
                    if file_path and original_content is not None:
                        # Ensure directory exists
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        with open(file_path, 'w') as f:
                            f.write(original_content)
            
            return {'success': True}
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_details': {'operation_type': 'file_operations'}
            }
    
    def _rollback_database_operations(self, rollback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback database operations.
        
        Args:
            rollback_data: Contains database operations to reverse
        
        Returns:
            Dict with success status
        """
        
        from db import execute
        
        operations = rollback_data.get('operations', [])
        
        try:
            for op in reversed(operations):  # Reverse order
                sql = op.get('rollback_sql')
                params = op.get('rollback_params', [])
                
                if sql:
                    execute(sql, tuple(params) if params else None)
            
            return {'success': True}
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_details': {'operation_type': 'database_operations'}
            }
    
    def _rollback_git_operations(self, rollback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rollback git operations.
        
        Args:
            rollback_data: Contains git operations to reverse
        
        Returns:
            Dict with success status
        """
        
        import subprocess
        
        operations = rollback_data.get('operations', [])
        work_dir = rollback_data.get('work_dir')
        
        try:
            for op in reversed(operations):  # Reverse order
                op_type = op.get('type')
                
                if op_type == 'git_commit':
                    # Reset to previous commit
                    commit_hash = op.get('previous_commit')
                    if commit_hash:
                        subprocess.run(
                            ['git', 'reset', '--hard', commit_hash],
                            cwd=work_dir,
                            check=True,
                            capture_output=True
                        )
                        
                elif op_type == 'git_branch':
                    # Delete created branch and switch back
                    branch_name = op.get('branch_name')
                    previous_branch = op.get('previous_branch', 'main')
                    
                    if branch_name:
                        # Switch back to previous branch
                        subprocess.run(
                            ['git', 'checkout', previous_branch],
                            cwd=work_dir,
                            check=True,
                            capture_output=True
                        )
                        
                        # Delete the created branch
                        subprocess.run(
                            ['git', 'branch', '-D', branch_name],
                            cwd=work_dir,
                            check=True,
                            capture_output=True
                        )
            
            return {'success': True}
            
        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'error': f'Git operation failed: {e.stderr.decode() if e.stderr else str(e)}',
                'error_details': {'operation_type': 'git_operations'}
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_details': {'operation_type': 'git_operations'}
            }
