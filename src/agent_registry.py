"""
Agent-OS v3 Agent Registry Module

Following million-step methodology:
- All agent registrations are tracked
- Heartbeats monitor agent health
- Task counts track agent workload
- State changes are atomic
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from db import (
    get_cursor, transaction, insert_returning,
    update, query_one, query_all
)


class AgentRegistry:
    """
    Registry for managing agent lifecycle and tracking.
    
    Core principle: All agents must be registered and tracked.
    """
    
    def __init__(self):
        pass
    
    def register_agent(
        self, 
        role: str, 
        model: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a new agent.
        
        Args:
            role: Agent role (e.g., 'drafter', 'verifier', 'executor')
            model: Model identifier (e.g., 'claude-sonnet-4-20250514')
            config: Optional configuration dict
        
        Returns:
            agent_id: Generated agent ID in format 'role-uuid4short'
        """
        # Generate short UUID (first 8 chars)
        short_uuid = str(uuid.uuid4())[:8]
        agent_id = f"{role}-{short_uuid}"
        
        agent_data = {
            'agent_id': agent_id,
            'role': role,
            'model': model,
            'status': 'active',
            'config': config,
            'created_at': datetime.utcnow(),
            'last_heartbeat': datetime.utcnow(),
            'task_count': 0
        }
        
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agents (agent_id, role, model, status, config, 
                                      created_at, last_heartbeat, task_count)
                    VALUES (%(agent_id)s, %(role)s, %(model)s, %(status)s, 
                           %(config)s, %(created_at)s, %(last_heartbeat)s, %(task_count)s)
                    """,
                    agent_data
                )
        
        return agent_id
    
    def update_heartbeat(self, agent_id: str) -> bool:
        """
        Update agent heartbeat timestamp.
        
        Args:
            agent_id: The agent ID to update
        
        Returns:
            True if updated successfully, False if agent not found
        """
        data = {
            'last_heartbeat': datetime.utcnow()
        }
        where = {'agent_id': agent_id}
        
        rows_updated = update('agents', data, where)
        return rows_updated > 0
    
    def increment_tasks(self, agent_id: str) -> bool:
        """
        Increment the task count for an agent.
        
        Args:
            agent_id: The agent ID to update
        
        Returns:
            True if updated successfully, False if agent not found
        """
        with get_cursor(dict_cursor=False) as cur:
            cur.execute(
                "UPDATE agents SET task_count = task_count + 1 WHERE agent_id = %s",
                (agent_id,)
            )
            return cur.rowcount > 0
    
    def deactivate_agent(self, agent_id: str) -> bool:
        """
        Deactivate an agent.
        
        Args:
            agent_id: The agent ID to deactivate
        
        Returns:
            True if deactivated successfully, False if agent not found
        """
        data = {
            'status': 'inactive',
            'deactivated_at': datetime.utcnow()
        }
        where = {'agent_id': agent_id}
        
        rows_updated = update('agents', data, where)
        return rows_updated > 0
    
    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent information by ID.
        
        Args:
            agent_id: The agent ID to retrieve
        
        Returns:
            Agent dict or None if not found
        """
        return query_one(
            "SELECT * FROM agents WHERE agent_id = %s",
            (agent_id,)
        )
    
    def get_active_agents(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all active agents, optionally filtered by role.
        
        Args:
            role: Optional role filter
        
        Returns:
            List of agent dicts
        """
        if role:
            return query_all(
                "SELECT * FROM agents WHERE status = 'active' AND role = %s ORDER BY created_at",
                (role,)
            )
        else:
            return query_all(
                "SELECT * FROM agents WHERE status = 'active' ORDER BY created_at"
            )
    
    def get_stale_agents(self, stale_threshold_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Get agents that haven't sent a heartbeat recently.
        
        Args:
            stale_threshold_minutes: Minutes without heartbeat to consider stale
        
        Returns:
            List of stale agent dicts
        """
        threshold_time = datetime.utcnow() - timedelta(minutes=stale_threshold_minutes)
        
        return query_all(
            "SELECT * FROM agents WHERE status = 'active' AND last_heartbeat < %s",
            (threshold_time,)
        )
