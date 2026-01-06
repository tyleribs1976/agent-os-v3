"""
Agent-OS v3 Checkpoint Verifier Module

Following million-step methodology:
- Verify checkpoint integrity
- Detect gaps in checkpoint sequences
- Validate phase transitions
- Report on checkpoint health
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from db import query_one, query_all


# Valid phase transitions
VALID_PHASE_TRANSITIONS = {
    None: ['preparation', 'drafting'],
    'preparation': ['drafting'],
    'drafting': ['verification', 'drafting'],  # Can retry drafting
    'verification': ['execution', 'drafting'],  # Can go back to drafting if rejected
    'execution': ['confirmation', 'verification'],  # Can go back if execution fails
    'confirmation': []  # Terminal state
}


class CheckpointVerifier:
    """
    Verifier for checkpoint integrity and consistency.
    
    Ensures checkpoints are valid, sequential, and follow
    proper phase transitions per the million-step methodology.
    """
    
    def __init__(self):
        pass
    
    def verify_checkpoint(self, checkpoint_id: int) -> Dict[str, Any]:
        """
        Verify a single checkpoint has valid data.
        
        Returns:
            {
                "checkpoint_id": int,
                "is_valid": bool,
                "issues": [{"field": str, "issue": str}]
            }
        """
        checkpoint = query_one(
            "SELECT * FROM checkpoints WHERE id = %s",
            (checkpoint_id,)
        )
        
        if not checkpoint:
            return {
                "checkpoint_id": checkpoint_id,
                "is_valid": False,
                "issues": [{"field": "id", "issue": "Checkpoint not found"}]
            }
        
        issues = []
        
        # Check required fields
        if not checkpoint.get('state_snapshot'):
            issues.append({
                "field": "state_snapshot",
                "issue": "Missing or null state_snapshot"
            })
        
        if not checkpoint.get('inputs_hash'):
            issues.append({
                "field": "inputs_hash", 
                "issue": "Missing inputs_hash"
            })
        
        # For completed checkpoints, outputs_hash should exist
        if checkpoint.get('status') == 'complete' and not checkpoint.get('outputs_hash'):
            issues.append({
                "field": "outputs_hash",
                "issue": "Completed checkpoint missing outputs_hash"
            })
        
        # Validate phase is known
        valid_phases = ['preparation', 'drafting', 'verification', 'execution', 'confirmation']
        if checkpoint.get('phase') and checkpoint['phase'] not in valid_phases:
            issues.append({
                "field": "phase",
                "issue": f"Invalid phase: {checkpoint['phase']}"
            })
        
        return {
            "checkpoint_id": checkpoint_id,
            "is_valid": len(issues) == 0,
            "issues": issues,
            "checkpoint_status": checkpoint.get('status'),
            "phase": checkpoint.get('phase')
        }
    
    def verify_task_chain(self, task_id: str) -> Dict[str, Any]:
        """
        Verify all checkpoints for a task are valid and sequential.
        
        Returns:
            {
                "task_id": str,
                "total_checkpoints": int,
                "valid_checkpoints": int,
                "issues": [{"checkpoint_id": int, "issue": str}],
                "is_valid": bool
            }
        """
        checkpoints = query_all(
            """SELECT id, global_sequence, phase, step_name, status, 
                      state_snapshot IS NOT NULL as has_state,
                      inputs_hash IS NOT NULL as has_inputs,
                      outputs_hash IS NOT NULL as has_outputs
               FROM checkpoints 
               WHERE task_id = %s 
               ORDER BY global_sequence""",
            (task_id,)
        )
        
        if not checkpoints:
            return {
                "task_id": task_id,
                "total_checkpoints": 0,
                "valid_checkpoints": 0,
                "issues": [{"checkpoint_id": None, "issue": "No checkpoints found for task"}],
                "is_valid": False
            }
        
        issues = []
        valid_count = 0
        prev_sequence = None
        prev_phase = None
        
        for cp in checkpoints:
            cp_issues = []
            
            # Check for sequence gaps
            if prev_sequence is not None:
                if cp['global_sequence'] != prev_sequence + 1:
                    # Allow gaps since global_sequence is across all tasks
                    pass
            
            # Check phase transitions
            current_phase = cp['phase']
            if prev_phase is not None and current_phase:
                valid_next = VALID_PHASE_TRANSITIONS.get(prev_phase, [])
                if current_phase != prev_phase and current_phase not in valid_next:
                    cp_issues.append(f"Invalid phase transition: {prev_phase} -> {current_phase}")
            
            # Check required fields
            if not cp['has_state']:
                cp_issues.append("Missing state_snapshot")
            
            if not cp['has_inputs']:
                cp_issues.append("Missing inputs_hash")
            
            if cp['status'] == 'complete' and not cp['has_outputs']:
                cp_issues.append("Completed checkpoint missing outputs_hash")
            
            if cp_issues:
                issues.append({
                    "checkpoint_id": cp['id'],
                    "issue": "; ".join(cp_issues)
                })
            else:
                valid_count += 1
            
            prev_sequence = cp['global_sequence']
            if current_phase:
                prev_phase = current_phase
        
        return {
            "task_id": task_id,
            "total_checkpoints": len(checkpoints),
            "valid_checkpoints": valid_count,
            "issues": issues,
            "is_valid": len(issues) == 0
        }
    
    def get_checkpoint_summary(self, task_id: str) -> Dict[str, Any]:
        """
        Get summary of checkpoints for a task.
        
        Returns:
            {
                "task_id": str,
                "total_checkpoints": int,
                "by_status": {"status": count},
                "by_phase": {"phase": count},
                "latest_checkpoint": {...},
                "first_checkpoint": {...}
            }
        """
        # Get counts by status
        status_counts = query_all(
            """SELECT status, COUNT(*) as count 
               FROM checkpoints 
               WHERE task_id = %s 
               GROUP BY status""",
            (task_id,)
        )
        
        # Get counts by phase
        phase_counts = query_all(
            """SELECT phase, COUNT(*) as count 
               FROM checkpoints 
               WHERE task_id = %s 
               GROUP BY phase""",
            (task_id,)
        )
        
        # Get latest checkpoint
        latest = query_one(
            """SELECT id, phase, step_name, status, created_at 
               FROM checkpoints 
               WHERE task_id = %s 
               ORDER BY created_at DESC 
               LIMIT 1""",
            (task_id,)
        )
        
        # Get first checkpoint
        first = query_one(
            """SELECT id, phase, step_name, status, created_at 
               FROM checkpoints 
               WHERE task_id = %s 
               ORDER BY created_at ASC 
               LIMIT 1""",
            (task_id,)
        )
        
        total = sum(s['count'] for s in status_counts) if status_counts else 0
        
        return {
            "task_id": task_id,
            "total_checkpoints": total,
            "by_status": {s['status']: s['count'] for s in status_counts} if status_counts else {},
            "by_phase": {p['phase']: p['count'] for p in phase_counts} if phase_counts else {},
            "latest_checkpoint": dict(latest) if latest else None,
            "first_checkpoint": dict(first) if first else None
        }


def verify_all_tasks() -> Dict[str, Any]:
    """
    Verify checkpoints for all tasks in the system.
    
    Returns summary of verification results.
    """
    verifier = CheckpointVerifier()
    
    tasks = query_all("SELECT DISTINCT task_id FROM checkpoints")
    
    results = {
        "total_tasks": len(tasks) if tasks else 0,
        "valid_tasks": 0,
        "invalid_tasks": 0,
        "task_results": []
    }
    
    for task in (tasks or []):
        task_id = task['task_id']
        result = verifier.verify_task_chain(task_id)
        
        if result['is_valid']:
            results['valid_tasks'] += 1
        else:
            results['invalid_tasks'] += 1
        
        results['task_results'].append({
            "task_id": task_id,
            "is_valid": result['is_valid'],
            "total_checkpoints": result['total_checkpoints'],
            "issues_count": len(result['issues'])
        })
    
    return results
