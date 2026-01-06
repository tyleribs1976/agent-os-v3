"""
Pytest configuration and fixtures for Agent-OS v3 tests.

Provides:
- Database connection fixtures
- Sample task data fixtures
- Cleanup utilities
"""

import os
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any

# Ensure test environment uses test database
os.environ['DB_NAME'] = os.environ.get('TEST_DB_NAME', 'agent_os_v3_test')


@pytest.fixture(scope='session')
def db_config() -> Dict[str, Any]:
    """Database configuration for tests."""
    return {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': int(os.environ.get('DB_PORT', '5432')),
        'database': os.environ.get('DB_NAME', 'agent_os_v3_test'),
        'user': os.environ.get('DB_USER', 'maestro'),
        'password': os.environ.get('DB_PASSWORD', 'maestro_secret_2024'),
    }


@pytest.fixture(scope='session')
def db_connection(db_config):
    """Session-scoped database connection for tests."""
    conn = psycopg2.connect(**db_config)
    yield conn
    conn.close()


@pytest.fixture
def db_cursor(db_connection):
    """Function-scoped cursor with automatic rollback."""
    conn = db_connection
    conn.rollback()  # Clean slate
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    yield cursor
    conn.rollback()  # Rollback after each test
    cursor.close()


@pytest.fixture
def sample_project(db_cursor) -> Dict[str, Any]:
    """Create a sample project for testing."""
    project_id = str(uuid4())
    db_cursor.execute(
        """
        INSERT INTO projects (id, name, repo_url, work_dir, config, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, name, repo_url, work_dir, config, created_at
        """,
        (
            project_id,
            'test-project',
            'https://github.com/test/repo',
            '/tmp/test-project',
            '{"skip_git_push": true, "skip_pr_creation": true}',
            datetime.utcnow()
        )
    )
    return dict(db_cursor.fetchone())


@pytest.fixture
def sample_task(db_cursor, sample_project) -> Dict[str, Any]:
    """Create a sample task for testing."""
    task_id = str(uuid4())
    db_cursor.execute(
        """
        INSERT INTO tasks (
            id, project_id, title, description, task_type, status,
            priority, current_phase, dependencies, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, project_id, title, description, task_type, status,
                  priority, current_phase, dependencies, created_at, updated_at
        """,
        (
            task_id,
            sample_project['id'],
            'Test Task',
            'A test task for unit testing',
            'implementation',
            'pending',
            1,
            'preparation',
            '[]',
            datetime.utcnow(),
            datetime.utcnow()
        )
    )
    return dict(db_cursor.fetchone())


@pytest.fixture
def sample_checkpoint(db_cursor, sample_project, sample_task) -> Dict[str, Any]:
    """Create a sample checkpoint for testing."""
    db_cursor.execute(
        """
        INSERT INTO checkpoints (
            checkpoint_uuid, global_sequence, project_id, task_id,
            phase, step_name, state_snapshot, inputs_hash, status, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, checkpoint_uuid, global_sequence, project_id, task_id,
                  phase, step_name, state_snapshot, inputs_hash, status, created_at
        """,
        (
            str(uuid4()),
            1,
            sample_project['id'],
            sample_task['id'],
            'drafting',
            'generate_draft',
            '{"test": "data"}',
            'abc123',
            'created',
            datetime.utcnow()
        )
    )
    return dict(db_cursor.fetchone())


@pytest.fixture
def clean_tables(db_cursor):
    """Clean test tables before test runs."""
    # Order matters due to foreign key constraints
    tables = ['api_usage', 'checkpoints', 'tasks', 'projects']
    for table in tables:
        db_cursor.execute(f"DELETE FROM {table} WHERE TRUE")
    yield
    # Cleanup after test
    for table in tables:
        db_cursor.execute(f"DELETE FROM {table} WHERE TRUE")
