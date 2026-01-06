-- Agent-OS v3 Agents Registry Table
-- Migration: 002_create_agents_table.sql
-- Purpose: Store information about all agents in the system

CREATE TABLE agents (
    id VARCHAR(50) PRIMARY KEY,
    role VARCHAR(50) NOT NULL,
    model VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    last_active_at TIMESTAMP,
    total_tasks_processed INTEGER DEFAULT 0,
    config JSONB,
    status VARCHAR(20) DEFAULT 'active'
);

-- Indexes for common queries
CREATE INDEX idx_agents_role ON agents(role);
CREATE INDEX idx_agents_status ON agents(status);

-- Comments for documentation
COMMENT ON TABLE agents IS 'Registry of all agents in the Agent-OS v3 system';
COMMENT ON COLUMN agents.id IS 'Unique identifier for the agent';
COMMENT ON COLUMN agents.role IS 'Role type: drafter, verifier, executor, etc.';
COMMENT ON COLUMN agents.model IS 'LLM model used by this agent (e.g., claude-sonnet-4-20250514)';
COMMENT ON COLUMN agents.created_at IS 'When this agent was first registered';
COMMENT ON COLUMN agents.last_active_at IS 'Last time this agent processed a task';
COMMENT ON COLUMN agents.total_tasks_processed IS 'Counter of tasks handled by this agent';
COMMENT ON COLUMN agents.config IS 'Agent-specific configuration as JSON';
COMMENT ON COLUMN agents.status IS 'Current status: active, inactive, disabled';
