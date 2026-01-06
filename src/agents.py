"""
Agent-OS v3 Agent Registry

Manages lifecycle of agents (drafter, verifier, executor, compliance).
Each agent is tracked with its role, model, status, and task statistics.
"""

from typing import Dict, Any, Optional, List
import json
import uuid
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from db import query_one, query_all, insert_returning, update, execute


class AgentRegistry:
    """
    Registry for managing agent lifecycle.
    
    Agents have roles: drafter, verifier, executor, compliance
    Status values: idle, active, terminated
    """
    
    VALID_ROLES = ['drafter', 'verifier', 'executor', 'compliance']
    VALID_STATUSES = ['idle', 'active', 'terminated']
    
    def register_agent(
        self, 
        role: str, 
        model: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Register a new agent.
        
        Args:
            role: One of drafter, verifier, executor, compliance
            model: Model identifier (e.g., claude-sonnet-4-20250514)
            config: Optional configuration dict
            
        Returns:
            Complete agent record with id
        """
        if role not in self.VALID_ROLES:
            raise ValueError(f"Invalid role: {role}. Must be one of {self.VALID_ROLES}")
        
        agent_data = {
            'id': str(uuid.uuid4()),
            'role': role,
            'model': model,
            'status': 'idle',
            'created_at': datetime.utcnow(),
            'last_active_at': datetime.utcnow(),
            'total_tasks_processed': 0,
            'config': json.dumps(config or {})
        }
        
        agent_id = agent_data["id"]
        insert_returning("agents", agent_data)
        return query_one("SELECT * FROM agents WHERE id = %s", (agent_id,))
    
    def get_agent(self, agent_id: int) -> Optional[Dict[str, Any]]:
        """Get agent by ID."""
        return query_one("SELECT * FROM agents WHERE id = %s", (agent_id,))
    
    def get_available_agent(self, role: str) -> Optional[Dict[str, Any]]:
        """
        Get an available (idle) agent for the given role.
        
        Returns None if no idle agent exists for the role.
        """
        return query_one(
            "SELECT * FROM agents WHERE role = %s AND status = 'idle' ORDER BY last_active_at ASC LIMIT 1",
            (role,)
        )
    
    def get_or_create_agent(self, role: str, model: str) -> Dict[str, Any]:
        """
        Get an available agent or create a new one.
        
        This is the primary method for obtaining an agent for a task.
        """
        agent = self.get_available_agent(role)
        if agent:
            return agent
        return self.register_agent(role, model)
    
    def update_agent_status(self, agent_id: int, status: str) -> bool:
        """
        Update agent status.
        
        Status transitions:
        - idle -> active (when starting task)
        - active -> idle (when task complete)
        - any -> terminated (when shutting down)
        - terminated cannot transition to other states
        """
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {self.VALID_STATUSES}")
        
        # Check current status
        current = self.get_agent(agent_id)
        if not current:
            return False
        
        if current['status'] == 'terminated' and status != 'terminated':
            raise ValueError("Cannot change status of terminated agent")
        
        rows = update('agents', {'status': status, 'last_active_at': datetime.utcnow()}, {'id': agent_id})
        return rows > 0
    
    def record_task_completion(self, agent_id: int) -> bool:
        """
        Record that an agent completed a task.
        Increments total_tasks_processed and updates last_active_at.
        """
        execute(
            "UPDATE agents SET total_tasks_processed = total_tasks_processed + 1, last_active_at = NOW() WHERE id = %s",
            (agent_id,)
        )
        return True
    
    def get_agents_by_role(self, role: str) -> List[Dict[str, Any]]:
        """List all agents with given role."""
        return query_all("SELECT * FROM agents WHERE role = %s ORDER BY created_at", (role,))
    
    def get_all_agents(self) -> List[Dict[str, Any]]:
        """List all agents."""
        return query_all("SELECT * FROM agents ORDER BY role, created_at")
    
    def terminate_agent(self, agent_id: int) -> bool:
        """Mark agent as terminated."""
        return self.update_agent_status(agent_id, 'terminated')
    
    def get_agent_stats(self) -> Dict[str, Any]:
        """Get summary statistics about agents."""
        stats = query_one("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'active') as active,
                COUNT(*) FILTER (WHERE status = 'idle') as idle,
                COUNT(*) FILTER (WHERE status = 'terminated') as terminated,
                SUM(total_tasks_processed) as total_tasks
            FROM agents
        """)
        return dict(stats) if stats else {}


# Singleton instance
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Get the singleton AgentRegistry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
