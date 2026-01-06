"""
Agent-OS v3 Data Models

Centralized model exports for tasks, projects, and checkpoints.
Provides type hints and dataclass representations of database entities.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
import json


@dataclass
class Task:
    """
    Represents a task in Agent-OS v3.
    
    Maps to tasks table in PostgreSQL.
    """
    id: UUID
    project_id: UUID
    title: str
    description: str
    task_type: str  # 'implementation', 'architecture', 'documentation'
    status: str  # 'pending', 'running', 'complete', 'failed', 'halted'
    priority: int
    current_phase: Optional[str] = None  # 'preparation', 'drafting', 'verification', 'execution', 'confirmation'
    dependencies: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Task':
        """Create Task instance from database row dict."""
        # Handle JSONB field
        dependencies = row.get('dependencies')
        if isinstance(dependencies, str):
            dependencies = json.loads(dependencies)
        
        return cls(
            id=row['id'],
            project_id=row['project_id'],
            title=row['title'],
            description=row['description'],
            task_type=row['task_type'],
            status=row['status'],
            priority=row['priority'],
            current_phase=row.get('current_phase'),
            dependencies=dependencies,
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at'),
            started_at=row.get('started_at'),
            completed_at=row.get('completed_at'),
            last_error=row.get('last_error')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'title': self.title,
            'description': self.description,
            'task_type': self.task_type,
            'status': self.status,
            'priority': self.priority,
            'current_phase': self.current_phase,
            'dependencies': json.dumps(self.dependencies) if self.dependencies else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_error': self.last_error
        }


@dataclass
class Project:
    """
    Represents a project in Agent-OS v3.
    
    Maps to projects table in PostgreSQL.
    """
    id: UUID
    name: str
    repo_url: str
    work_dir: str
    config: Optional[Dict[str, Any]] = None  # {"skip_git_push": bool, "skip_pr_creation": bool}
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Project':
        """Create Project instance from database row dict."""
        # Handle JSONB field
        config = row.get('config')
        if isinstance(config, str):
            config = json.loads(config)
        
        return cls(
            id=row['id'],
            name=row['name'],
            repo_url=row['repo_url'],
            work_dir=row['work_dir'],
            config=config,
            created_at=row.get('created_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': str(self.id),
            'name': self.name,
            'repo_url': self.repo_url,
            'work_dir': self.work_dir,
            'config': json.dumps(self.config) if self.config else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class Checkpoint:
    """
    Represents a checkpoint in Agent-OS v3.
    
    Maps to checkpoints table in PostgreSQL.
    """
    id: int
    checkpoint_uuid: Optional[UUID] = None
    global_sequence: Optional[int] = None
    project_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    phase: Optional[str] = None
    step_name: Optional[str] = None
    state_snapshot: Optional[Dict[str, Any]] = None
    inputs_hash: Optional[str] = None
    outputs_hash: Optional[str] = None
    drafter_agent_id: Optional[str] = None
    verifier_agent_id: Optional[str] = None
    status: Optional[str] = None  # 'created', 'complete', 'failed', 'rolled_back'
    error_details: Optional[Dict[str, Any]] = None
    previous_checkpoint_id: Optional[int] = None
    rollback_data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Checkpoint':
        """Create Checkpoint instance from database row dict."""
        # Handle JSONB fields
        state_snapshot = row.get('state_snapshot')
        if isinstance(state_snapshot, str):
            state_snapshot = json.loads(state_snapshot)
        
        error_details = row.get('error_details')
        if isinstance(error_details, str):
            error_details = json.loads(error_details)
        
        rollback_data = row.get('rollback_data')
        if isinstance(rollback_data, str):
            rollback_data = json.loads(rollback_data)
        
        return cls(
            id=row['id'],
            checkpoint_uuid=row.get('checkpoint_uuid'),
            global_sequence=row.get('global_sequence'),
            project_id=row.get('project_id'),
            task_id=row.get('task_id'),
            phase=row.get('phase'),
            step_name=row.get('step_name'),
            state_snapshot=state_snapshot,
            inputs_hash=row.get('inputs_hash'),
            outputs_hash=row.get('outputs_hash'),
            drafter_agent_id=row.get('drafter_agent_id'),
            verifier_agent_id=row.get('verifier_agent_id'),
            status=row.get('status'),
            error_details=error_details,
            previous_checkpoint_id=row.get('previous_checkpoint_id'),
            rollback_data=rollback_data,
            created_at=row.get('created_at'),
            completed_at=row.get('completed_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'checkpoint_uuid': str(self.checkpoint_uuid) if self.checkpoint_uuid else None,
            'global_sequence': self.global_sequence,
            'project_id': str(self.project_id) if self.project_id else None,
            'task_id': str(self.task_id) if self.task_id else None,
            'phase': self.phase,
            'step_name': self.step_name,
            'state_snapshot': json.dumps(self.state_snapshot) if self.state_snapshot else None,
            'inputs_hash': self.inputs_hash,
            'outputs_hash': self.outputs_hash,
            'drafter_agent_id': self.drafter_agent_id,
            'verifier_agent_id': self.verifier_agent_id,
            'status': self.status,
            'error_details': json.dumps(self.error_details) if self.error_details else None,
            'previous_checkpoint_id': self.previous_checkpoint_id,
            'rollback_data': json.dumps(self.rollback_data) if self.rollback_data else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


__all__ = ['Task', 'Project', 'Checkpoint']
