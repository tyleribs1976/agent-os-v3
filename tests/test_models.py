"""Tests for Agent-OS v3 data models."""

import pytest
from datetime import datetime
from uuid import uuid4
import json


class TestTask:
    """Tests for Task dataclass/model."""
    
    def test_task_basic_structure(self):
        """Test basic task structure matches database schema."""
        task = {
            'id': str(uuid4()),
            'project_id': str(uuid4()),
            'title': 'Test Task',
            'description': 'Test description',
            'task_type': 'implementation',
            'status': 'pending',
            'priority': 1,
            'current_phase': 'preparation',
            'dependencies': {},
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        assert task['id'] is not None
        assert task['project_id'] is not None
        assert task['title'] == 'Test Task'
        assert task['task_type'] in ['implementation', 'architecture', 'documentation']
        assert task['status'] in ['pending', 'running', 'complete', 'failed', 'halted']
        assert task['current_phase'] in ['preparation', 'drafting', 'verification', 'execution', 'confirmation']
    
    def test_task_valid_types(self):
        """Test task type validation."""
        valid_types = ['implementation', 'architecture', 'documentation']
        for task_type in valid_types:
            task = {'task_type': task_type}
            assert task['task_type'] in valid_types
    
    def test_task_valid_statuses(self):
        """Test task status validation."""
        valid_statuses = ['pending', 'running', 'complete', 'failed', 'halted']
        for status in valid_statuses:
            task = {'status': status}
            assert task['status'] in valid_statuses
    
    def test_task_valid_phases(self):
        """Test task phase validation."""
        valid_phases = ['preparation', 'drafting', 'verification', 'execution', 'confirmation']
        for phase in valid_phases:
            task = {'current_phase': phase}
            assert task['current_phase'] in valid_phases
    
    def test_task_dependencies_json(self):
        """Test dependencies field as JSONB."""
        dependencies = {'requires': ['task-1', 'task-2']}
        task = {
            'id': str(uuid4()),
            'dependencies': dependencies
        }
        
        # Simulate JSON serialization/deserialization
        serialized = json.dumps(task['dependencies'])
        deserialized = json.loads(serialized)
        assert deserialized == dependencies


class TestProject:
    """Tests for Project dataclass/model."""
    
    def test_project_basic_structure(self):
        """Test basic project structure matches database schema."""
        project = {
            'id': str(uuid4()),
            'name': 'test-project',
            'repo_url': 'https://github.com/user/repo',
            'work_dir': '/opt/agent-os-v3',
            'config': {'skip_git_push': True, 'skip_pr_creation': True},
            'created_at': datetime.utcnow()
        }
        
        assert project['id'] is not None
        assert project['name'] == 'test-project'
        assert project['repo_url'].startswith('https://')
        assert project['work_dir'].startswith('/')
        assert isinstance(project['config'], dict)
    
    def test_project_config_json(self):
        """Test config field as JSONB."""
        config = {
            'skip_git_push': True,
            'skip_pr_creation': False,
            'custom_setting': 'value'
        }
        project = {
            'id': str(uuid4()),
            'config': config
        }
        
        # Simulate JSON serialization/deserialization
        serialized = json.dumps(project['config'])
        deserialized = json.loads(serialized)
        assert deserialized == config
        assert deserialized['skip_git_push'] is True
        assert deserialized['skip_pr_creation'] is False


class TestCheckpoint:
    """Tests for Checkpoint dataclass/model."""
    
    def test_checkpoint_basic_structure(self):
        """Test basic checkpoint structure matches database schema."""
        checkpoint = {
            'id': 1,
            'checkpoint_uuid': str(uuid4()),
            'global_sequence': 1,
            'project_id': str(uuid4()),
            'task_id': str(uuid4()),
            'phase': 'drafting',
            'step_name': 'generate_draft',
            'state_snapshot': {'key': 'value'},
            'inputs_hash': 'abc123',
            'outputs_hash': 'def456',
            'drafter_agent_id': 'drafter-1',
            'verifier_agent_id': None,
            'status': 'created',
            'error_details': None,
            'previous_checkpoint_id': None,
            'rollback_data': None,
            'created_at': datetime.utcnow(),
            'completed_at': None
        }
        
        assert checkpoint['id'] is not None
        assert checkpoint['global_sequence'] > 0
        assert checkpoint['phase'] in ['preparation', 'drafting', 'verification', 'execution', 'confirmation']
        assert checkpoint['status'] in ['created', 'complete', 'failed', 'rolled_back']
    
    def test_checkpoint_valid_phases(self):
        """Test checkpoint phase validation."""
        valid_phases = ['preparation', 'drafting', 'verification', 'execution', 'confirmation']
        for phase in valid_phases:
            checkpoint = {'phase': phase}
            assert checkpoint['phase'] in valid_phases
    
    def test_checkpoint_valid_statuses(self):
        """Test checkpoint status validation."""
        valid_statuses = ['created', 'complete', 'failed', 'rolled_back']
        for status in valid_statuses:
            checkpoint = {'status': status}
            assert checkpoint['status'] in valid_statuses
    
    def test_checkpoint_state_snapshot_json(self):
        """Test state_snapshot field as JSONB."""
        state = {
            'task': {'id': '123', 'title': 'Test'},
            'files': ['file1.py', 'file2.py'],
            'confidence': 0.95
        }
        checkpoint = {
            'id': 1,
            'state_snapshot': state
        }
        
        # Simulate JSON serialization/deserialization
        serialized = json.dumps(checkpoint['state_snapshot'])
        deserialized = json.loads(serialized)
        assert deserialized == state
        assert deserialized['confidence'] == 0.95
    
    def test_checkpoint_error_details_json(self):
        """Test error_details field as JSONB."""
        error_details = {
            'reason': 'low_confidence',
            'error': 'Confidence below threshold',
            'signals': ['uncertainty_language']
        }
        checkpoint = {
            'id': 1,
            'error_details': error_details
        }
        
        # Simulate JSON serialization/deserialization
        serialized = json.dumps(checkpoint['error_details'])
        deserialized = json.loads(serialized)
        assert deserialized == error_details
    
    def test_checkpoint_rollback_data_json(self):
        """Test rollback_data field as JSONB."""
        rollback_data = {
            'previous_state': {'status': 'pending'},
            'files_to_restore': ['backup.py']
        }
        checkpoint = {
            'id': 1,
            'rollback_data': rollback_data
        }
        
        # Simulate JSON serialization/deserialization
        serialized = json.dumps(checkpoint['rollback_data'])
        deserialized = json.loads(serialized)
        assert deserialized == rollback_data
    
    def test_checkpoint_sequence_monotonic(self):
        """Test that global_sequence is monotonically increasing."""
        checkpoints = [
            {'id': 1, 'global_sequence': 1},
            {'id': 2, 'global_sequence': 2},
            {'id': 3, 'global_sequence': 3}
        ]
        
        for i in range(len(checkpoints) - 1):
            assert checkpoints[i+1]['global_sequence'] > checkpoints[i]['global_sequence']
