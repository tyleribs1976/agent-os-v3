-- Agent-OS v3 Schema
-- Following million-step methodology: checkpoints are the core primitive

-- Global sequence for checkpoint ordering
CREATE SEQUENCE IF NOT EXISTS global_checkpoint_seq;

-- Projects (enhanced from v2)
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    repo_url VARCHAR(500),
    work_dir VARCHAR(500),
    config JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Tasks (enhanced with v3 fields)
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    title TEXT NOT NULL,
    description TEXT,
    task_type VARCHAR(50) DEFAULT 'implementation',
    status VARCHAR(50) DEFAULT 'queued',
    priority INTEGER DEFAULT 50,
    dependencies TEXT[],
    slug TEXT,
    
    -- v3 additions
    current_phase VARCHAR(50),
    current_step VARCHAR(100),
    assigned_drafter VARCHAR(50),
    assigned_verifier VARCHAR(50),
    draft_id UUID,
    verification_id UUID,
    uncertainty_flags JSONB DEFAULT '[]',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Checkpoints (core of v3 - every state change is checkpointed)
CREATE TABLE IF NOT EXISTS checkpoints (
    id SERIAL PRIMARY KEY,
    checkpoint_uuid UUID DEFAULT gen_random_uuid(),
    global_sequence BIGINT DEFAULT nextval('global_checkpoint_seq'),
    
    project_id UUID REFERENCES projects(id),
    task_id UUID REFERENCES tasks(id),
    
    phase VARCHAR(50) NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    
    state_snapshot JSONB NOT NULL,
    inputs_hash VARCHAR(64) NOT NULL,
    outputs_hash VARCHAR(64),
    
    drafter_agent_id VARCHAR(50),
    verifier_agent_id VARCHAR(50),
    
    status VARCHAR(20) DEFAULT 'created',
    error_details JSONB,
    
    previous_checkpoint_id INTEGER REFERENCES checkpoints(id),
    rollback_data JSONB,
    
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    
    UNIQUE(global_sequence)
);

-- Drafts (proposals from drafter role)
CREATE TABLE IF NOT EXISTS drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id),
    checkpoint_id INTEGER REFERENCES checkpoints(id),
    
    drafter_agent_id VARCHAR(50) NOT NULL,
    
    files_to_create JSONB DEFAULT '[]',
    files_to_modify JSONB DEFAULT '[]',
    reasoning_trace TEXT,
    
    confidence_score FLOAT,
    uncertainty_flags JSONB DEFAULT '[]',
    estimated_complexity VARCHAR(20),
    
    status VARCHAR(20) DEFAULT 'draft',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Verifications (results from verifier role)
CREATE TABLE IF NOT EXISTS verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    draft_id UUID NOT NULL REFERENCES drafts(id),
    checkpoint_id INTEGER REFERENCES checkpoints(id),
    
    verifier_agent_id VARCHAR(50) NOT NULL,
    
    decision VARCHAR(20) NOT NULL,
    checks_performed JSONB DEFAULT '[]',
    issues_found JSONB DEFAULT '[]',
    risk_flags JSONB DEFAULT '[]',
    revision_requests JSONB DEFAULT '[]',
    
    verifier_confidence FLOAT,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Executions (records from execution controller)
CREATE TABLE IF NOT EXISTS executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id),
    verification_id UUID REFERENCES verifications(id),
    checkpoint_id INTEGER REFERENCES checkpoints(id),
    
    execution_manifest JSONB NOT NULL,
    steps_executed JSONB DEFAULT '[]',
    final_status VARCHAR(20),
    
    commit_sha VARCHAR(64),
    branch_name VARCHAR(255),
    pr_number INTEGER,
    pr_url VARCHAR(500),
    
    rollback_required BOOLEAN DEFAULT FALSE,
    rollback_instructions TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Uncertainty signals (for tracking HALTs)
CREATE TABLE IF NOT EXISTS uncertainty_signals (
    id SERIAL PRIMARY KEY,
    task_id UUID REFERENCES tasks(id),
    checkpoint_id INTEGER REFERENCES checkpoints(id),
    
    signal_type VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    
    resolved BOOLEAN DEFAULT FALSE,
    resolution TEXT,
    resolved_by VARCHAR(100),
    resolved_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit log (enhanced)
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT NOW(),
    
    project_id UUID REFERENCES projects(id),
    task_id UUID REFERENCES tasks(id),
    checkpoint_id INTEGER REFERENCES checkpoints(id),
    
    agent_id VARCHAR(50),
    role VARCHAR(50),
    
    action VARCHAR(50) NOT NULL,
    description TEXT,
    
    inputs_summary JSONB,
    outputs_summary JSONB,
    
    metadata JSONB
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_checkpoints_task ON checkpoints(task_id, global_sequence DESC);
CREATE INDEX IF NOT EXISTS idx_checkpoints_project ON checkpoints(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON checkpoints(status) WHERE status != 'complete';
CREATE INDEX IF NOT EXISTS idx_drafts_task ON drafts(task_id);
CREATE INDEX IF NOT EXISTS idx_verifications_draft ON verifications(draft_id);
CREATE INDEX IF NOT EXISTS idx_uncertainty_unresolved ON uncertainty_signals(resolved) WHERE resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_log(task_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
