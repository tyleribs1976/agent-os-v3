#!/usr/bin/env python3
"""Test Agent-OS V3 system components"""

import sys
sys.path.insert(0, '/opt/agent-os-v3/src')

from agents import AgentRegistry
from audit import AuditLogger, log_action
from roles.compliance import Compliance
import json

# Initialize
registry = AgentRegistry()
logger = AuditLogger()
compliance_checker = Compliance()

# Register agents for each role
print("=== Registering Agents ===")
drafter = registry.register_agent("drafter", "claude-sonnet-4-20250514", {"max_tokens": 16000})
print(f"Drafter: ID={drafter['id']}, role={drafter['role']}")

verifier = registry.register_agent("verifier", "claude-sonnet-4-20250514")
print(f"Verifier: ID={verifier['id']}, role={verifier['role']}")

executor = registry.register_agent("executor", "deterministic-v1")
print(f"Executor: ID={executor['id']}, role={executor['role']}")

compliance_agent = registry.register_agent("compliance", "claude-sonnet-4-20250514")
print(f"Compliance: ID={compliance_agent['id']}, role={compliance_agent['role']}")

# Log some actions
print("\n=== Testing Audit Logger ===")
correlation_id = logger.start_correlation()
print(f"Correlation ID: {correlation_id}")

log_id = log_action("AGENT_REGISTERED", {"agent_id": drafter['id'], "role": "drafter"})
print(f"Logged action, ID={log_id}")

log_id = log_action("TASK_CREATED", {"title": "Test task", "priority": 1})
print(f"Logged action, ID={log_id}")

# Test compliance check
print("\n=== Testing Compliance ===")
mock_verification = {
    "decision": "approved",
    "risk_flags": [],
    "issues_found": []
}
mock_task = {"title": "Test task"}
mock_project = {"project_id": None}

result = compliance_checker.review_proposal(mock_verification, mock_task, mock_project)
print(f"Compliance decision: {result['decision']}")
print(f"Policy checks: {len(result['policy_checks'])}")

# Get stats
print("\n=== Agent Stats ===")
stats = registry.get_agent_stats()
print(json.dumps(stats, default=str, indent=2))

print("\n=== All Agents ===")
for agent in registry.get_all_agents():
    print(f"  {agent['role']}: ID={agent['id']}, status={agent['status']}")

print("\n=== Recent Audit Logs ===")
recent = logger.get_recent_actions(limit=5)
for log in recent:
    print(f"  {log['action_type']}: {log.get('details', {})}")

print("\n=== V3 System Test Complete ===")
