#!/usr/bin/env python3
"""
Agent-OS v3 Data Models

Dataclasses representing core entities in the system.
These models mirror the database schema and provide type-safe
interfaces for working with tasks, projects, and checkpoints.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID


@dataclass
class Task:
    """
    Represents a task in the Agent-OS v3 system.
    
    Mirrors the tasks table schema.
    """
    id: UUID
    project_id: UUID
    title: str
    description: str
    task_type: str  # 'implementation', 'architecture', 'documentation'
    status: str  # 'pending', 'running', 'complete', 'failed', 'halted'
    priority: int
    current_phase: str  # 'preparation', 'drafting', 'verification', 'execution', 'confirmation'
    dependencies: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    
    def __post_init__(self):
        """Validate task fields after initialization."""
        valid_types = ['implementation', 'architecture', 'documentation']
        if self.task_type not in valid_types:
            raise ValueError(f"Invalid task_type: {self.task_type}. Must be one of {valid_types}")
        
        valid_statuses = ['pending', 'running', 'complete', 'failed', 'halted']
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status: {self.status}. Must be one of {valid_statuses}")
        
        valid_phases = ['preparation', 'drafting', 'verification', 'execution', 'confirmation']
        if self.current_phase not in valid_phases:
            raise ValueError(f"Invalid current_phase: {self.current_phase}. Must be one of {valid_phases}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for serialization."""
        return {
            'id': str(self.id),
            'project_id': str(self.project_id),
            'title': self.title,
            'description': self.description,
            'task_type': self.task_type,
            'status': self.status,
            'priority': self.priority,
            'current_phase': self.current_phase,
            'dependencies': self.dependencies,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_error': self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create Task from dictionary (e.g., from database query)."""
        # Convert string UUIDs to UUID objects
        if isinstance(data.get('id'), str):
            data['id'] = UUID(data['id'])
        if isinstance(data.get('project_id'), str):
            data['project_id'] = UUID(data['project_id'])
        
        # Convert ISO format strings to datetime objects
        for field in ['created_at', 'updated_at', 'started_at', 'completed_at']:
            if isinstance(data.get(field), str):
                data[field] = datetime.fromisoformat(data[field])
        
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class Project:
    """
    Represents a project in the Agent-OS v3 system.
    
    Mirrors the projects table schema.
    """
    id: UUID
    name: str
    repo_url: str
    work_dir: str
    config: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for serialization."""
        return {
            'id': str(self.id),
            'name': self.name,
            'repo_url': self.repo_url,
            'work_dir': self.work_dir,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create Project from dictionary (e.g., from database query)."""
        if isinstance(data.get('id'), str):
            data['id'] = UUID(data['id'])
        
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


@dataclass
class Checkpoint:
    """
    Represents a checkpoint in the Agent-OS v3 system.
    
    Mirrors the checkpoints table schema.
    """
    id: int
    checkpoint_uuid: UUID
    global_sequence: int
    project_id: UUID
    task_id: Optional[UUID]
    phase: str
    step_name: str
    state_snapshot: Dict[str, Any]
    inputs_hash: str
    outputs_hash: Optional[str] = None
    drafter_agent_id: Optional[str] = None
    verifier_agent_id: Optional[str] = None
    status: str = 'created'  # 'created', 'complete', 'failed', 'rolled_back'
    error_details: Optional[Dict[str, Any]] = None
    previous_checkpoint_id: Optional[int] = None
    rollback_data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate checkpoint fields after initialization."""
        valid_statuses = ['created', 'complete', 'failed', 'rolled_back']
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status: {self.status}. Must be one of {valid_statuses}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary for serialization."""
        return {
            'id': self.id,
            'checkpoint_uuid': str(self.checkpoint_uuid),
            'global_sequence': self.global_sequence,
            'project_id': str(self.project_id),
            'task_id': str(self.task_id) if self.task_id else None,
            'phase': self.phase,
            'step_name': self.step_name,
            'state_snapshot': self.state_snapshot,
            'inputs_hash': self.inputs_hash,
            'outputs_hash': self.outputs_hash,
            'drafter_agent_id': self.drafter_agent_id,
            'verifier_agent_id': self.verifier_agent_id,
            'status': self.status,
            'error_details': self.error_details,
            'previous_checkpoint_id': self.previous_checkpoint_id,
            'rollback_data': self.rollback_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create Checkpoint from dictionary (e.g., from database query)."""
        # Convert string UUIDs to UUID objects
        for field in ['checkpoint_uuid', 'project_id', 'task_id']:
            if isinstance(data.get(field), str):
                data[field] = UUID(data[field])
        
        # Convert ISO format strings to datetime objects
        for field in ['created_at', 'completed_at']:
            if isinstance(data.get(field), str):
                data[field] = datetime.fromisoformat(data[field])
        
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})
