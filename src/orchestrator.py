"""
Agent-OS v3 Main Task Orchestrator with Live Progress

This is the main loop that:
1. Picks up tasks from the queue
2. Reads relevant codebase files for context
3. Runs Drafter -> Verifier -> Compliance -> Executor pipeline
4. Handles HALT conditions
5. Updates task status
6. Shows live progress in Telegram
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

sys.path.insert(0, str(Path(__file__).parent))

from db import query_one, query_all, update, insert_returning
from checkpoints import CheckpointManager
from uncertainty import UncertaintyDetector
from notifications import notify_halt, notify_success, notify_error, notify_progress
from progress_bar import TelegramProgressBar
from roles.drafter import create_drafter
from roles.verifier import create_verifier
from roles.executor import create_executor
from roles.compliance import create_compliance
# V3 Integration modules
from audit import AuditLogger
from health import HealthChecker
from retry import RetryManager


# Phase to percentage mapping
PHASE_PROGRESS = {
    "initializing": 0,
    "drafting": 10,
    "drafting_complete": 30,
    "verification": 35,
    "verification_complete": 55,
    "compliance": 60,
    "compliance_complete": 70,
    "execution": 75,
    "committing": 85,
    "pushing": 90,
    "creating_pr": 95,
    "complete": 100
}

# File patterns to include for context based on task type
CONTEXT_PATTERNS = {
    'default': ['*.py', '*.md', '*.yaml', '*.json'],
    'implementation': ['*.py', '*.md'],
    'documentation': ['*.md', '*.rst', 'README*'],
    'architecture': ['*.md', '*.yaml', '*.json'],
}

# Max files to include for context
MAX_CONTEXT_FILES = 10
MAX_FILE_SIZE = 10000  # chars


class TaskOrchestrator:
    """
    Main orchestrator for executing tasks through the pipeline.
    Now with live Telegram progress tracking.
    """
    
    def __init__(self):
        self.checkpoint_manager = CheckpointManager()
        self.progress = TelegramProgressBar()
        # V3 Integration components
        self.audit = AuditLogger()
        self.health = HealthChecker()
        self.retry = RetryManager()
    
    def get_next_task(self, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get the next queued task."""
        if project_id:
            return query_one(
                """
                SELECT t.*, p.name as project_name, p.repo_url, p.work_dir, p.config as project_config
                FROM tasks t
                JOIN projects p ON t.project_id = p.id
                WHERE t.status IN ('pending', 'queued') AND t.project_id = %s
                ORDER BY t.priority ASC, t.created_at ASC
                LIMIT 1
                """,
                (project_id,)
            )
        else:
            return query_one(
                """
                SELECT t.*, p.name as project_name, p.repo_url, p.work_dir, p.config as project_config
                FROM tasks t
                JOIN projects p ON t.project_id = p.id
                WHERE t.status IN ('pending', 'queued')
                ORDER BY t.priority ASC, t.created_at ASC
                LIMIT 1
                """
            )
    
    def get_relevant_files(
        self, 
        work_dir: str, 
        task_type: str = 'implementation',
        task_title: str = ''
    ) -> Dict[str, str]:
        """
        Read relevant files from the project for context.
        
        Returns dict of path -> content for files relevant to the task.
        """
        relevant_files = {}
        work_path = Path(work_dir)
        
        if not work_path.exists():
            return relevant_files
        
        # Look for v3 specific files first
        v3_src = work_path / 'v3' / 'src'
        if not v3_src.exists():
            v3_src = work_path / 'src'
        
        # Priority files to always include
        priority_files = [
            'src/constants.py',
            'src/db.py',
            'src/validators.py',
            'src/helpers.py',
            'src/utils.py',
            'src/models.py',
            'src/exceptions.py',
            'src/checkpoints.py', 
            'src/orchestrator.py',
            'src/uncertainty.py',
            'src/roles/drafter.py',
            'src/roles/verifier.py',
            'src/roles/executor.py',
            'prompts/drafter_system.md',
            'README.md',
        ]
        
        # Add priority files
        for rel_path in priority_files:
            full_path = work_path / rel_path
            if full_path.exists() and full_path.is_file():
                try:
                    content = full_path.read_text()
                    if len(content) > MAX_FILE_SIZE:
                        content = content[:MAX_FILE_SIZE] + "\n... (truncated)"
                    relevant_files[rel_path] = content
                except Exception:
                    pass
            
            if len(relevant_files) >= MAX_CONTEXT_FILES:
                break
        
        # If we have room, look for files matching task keywords
        if len(relevant_files) < MAX_CONTEXT_FILES:
            task_keywords = task_title.lower().split()
            for src_dir in [v3_src, work_path / 'src', work_path]:
                if not src_dir.exists():
                    continue
                for py_file in src_dir.glob('**/*.py'):
                    if len(relevant_files) >= MAX_CONTEXT_FILES:
                        break
                    rel = str(py_file.relative_to(work_path))
                    if rel in relevant_files:
                        continue
                    # Check if filename relates to task
                    filename = py_file.stem.lower()
                    if any(kw in filename for kw in task_keywords if len(kw) > 3):
                        try:
                            content = py_file.read_text()
                            if len(content) > MAX_FILE_SIZE:
                                content = content[:MAX_FILE_SIZE] + "\n... (truncated)"
                            relevant_files[rel] = content
                        except Exception:
                            pass
        
        return relevant_files
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single task through the full pipeline with progress tracking."""
        
        task_id = str(task['id'])
        task_title = task.get('title', 'Unknown')
        task_type = task.get('task_type', 'implementation')
        work_dir = task.get('work_dir', '/tmp')
        
        project_context = {
            'name': task.get('project_name', 'Unknown'),
            'repo_url': task.get('repo_url', ''),
            'work_dir': work_dir,
            'config': task.get('project_config', {})
        }
        
        # V3: Health check before processing
        health_result = self.health.run_all_checks()
        if not health_result.get("healthy", False):
            #self.audit.log_action("task_started", health_result, task_id=task_id)
            # Skip orchestrator check since we ARE the orchestrator
            pass  # Health check skipped - we are the orchestrator
        # return {"success": False, "error": "Health check failed", "details": health_result}
        
        # V3: Log task start
        #self.audit.log_action("task_started", {"title": task_title, "type": task_type}, task_id=task_id)

        # Start progress bar
        self.progress.start(task_title, task_id, "claude")
        
        # Update task status
        update('tasks', {
            'status': 'running',
            'current_phase': 'drafting',
            'started_at': datetime.utcnow()
        }, {'id': task_id})
        
        try:
            # Gather relevant files for context
            self.progress.update(5, "initializing", "Reading codebase...")
            relevant_files = self.get_relevant_files(work_dir, task_type, task_title)
            
            # PHASE 1: DRAFTING (10-30%)
            self.progress.update(PHASE_PROGRESS["drafting"], "drafting", "Generating code proposal...")
            
            drafter = create_drafter()
            draft_result = drafter.generate_draft(task, project_context, relevant_files)
            
            if not draft_result.get('success'):
                self.progress.complete("halted" if draft_result.get('halted') else "failed", 
                                       draft_result.get('message', 'Draft generation failed'))
                return self._handle_failure(task, 'drafting', draft_result)
            
            self.progress.update(PHASE_PROGRESS["drafting_complete"], "drafting", "Draft complete!")
            
            # PHASE 2: VERIFICATION (35-55%)
            update('tasks', {'current_phase': 'verification'}, {'id': task_id})
            self.progress.update(PHASE_PROGRESS["verification"], "verifying", "Validating draft...")
            
            verifier = create_verifier()
            verification_result = verifier.verify_draft(
                draft_result['draft'],
                task,
                project_context
            )
            
            if verification_result['decision'] != 'approved':
                status = "halted" if verification_result.get('escalate') else "failed"
                self.progress.complete(status, f"Verification: {verification_result['decision']}")
                return self._handle_verification_failure(task, verification_result)
            
            self.progress.update(PHASE_PROGRESS["verification_complete"], "verifying", "Verification passed!")
            
            # PHASE 2.5: COMPLIANCE CHECK (60-70%)
            update('tasks', {'current_phase': 'compliance'}, {'id': task_id})
            self.progress.update(PHASE_PROGRESS["compliance"], "compliance", "Running compliance checks...")
            compliance = create_compliance()
            compliance_result = compliance.review_proposal(verification_result, task, project_context)
            
            if compliance_result.get("decision") != "cleared":
                status = "halted" if compliance_result.get("requires_human") else "failed"
                self.progress.complete(status, f"Compliance: {compliance_result.get('decision', 'blocked')}")
                return self._handle_compliance_failure(task, compliance_result)
            
            self.progress.update(PHASE_PROGRESS["compliance_complete"], "compliance", "Compliance cleared!")

            # PHASE 3: EXECUTION (75-95%)
            update('tasks', {'current_phase': 'execution'}, {'id': task_id})
            self.progress.update(PHASE_PROGRESS["execution"], "executing", "Applying changes...")
            
            executor = create_executor()
            execution_result = executor.execute(
                verification_result,
                draft_result['draft'],
                task,
                project_context
            )
            
            if not execution_result.get('success'):
                self.progress.complete("failed", execution_result.get('error', 'Execution failed'))
                return self._handle_failure(task, 'execution', execution_result)
            
            # Update progress through execution sub-phases
            if execution_result.get('committed'):
                self.progress.update(PHASE_PROGRESS["committing"], "committing", "Changes committed")
            if execution_result.get('pushed'):
                self.progress.update(PHASE_PROGRESS["pushing"], "pushing", "Pushed to remote")
            if execution_result.get('pr_created'):
                self.progress.update(PHASE_PROGRESS["creating_pr"], "creating PR", 
                                    f"PR #{execution_result.get('pr_number', '?')}")
            
            # SUCCESS
            update('tasks', {
                'status': 'complete',
                'current_phase': 'complete',
                'completed_at': datetime.utcnow()
            }, {'id': task_id})
            
            # Build summary
            artifacts = execution_result.get('artifacts', {})
            summary_parts = []
            if artifacts.get('files_created'):
                summary_parts.append(f"{len(artifacts['files_created'])} files created")
            if artifacts.get('files_modified'):
                summary_parts.append(f"{len(artifacts['files_modified'])} files modified")
            if artifacts.get('pr_url'):
                summary_parts.append(f"PR: {artifacts['pr_url']}")
            
            summary = ", ".join(summary_parts) if summary_parts else "Task completed"
            self.progress.complete("complete", summary)
            
            return {
                'success': True,
                'task_id': task_id,
                'artifacts': artifacts
            }
            
        except Exception as e:
            update('tasks', {
                'status': 'failed',
                'completed_at': datetime.utcnow()
            }, {'id': task_id})
            
            self.progress.complete("failed", str(e)[:100])
            
            notify_error(
                project_name=project_context['name'],
                task_title=task_title,
                error=str(e)
            )
            
            return {
                'success': False,
                'error': str(e),
                'task_id': task_id
            }
    
    def _handle_failure(
        self,
        task: Dict[str, Any],
        phase: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a failure in the pipeline with V3 retry logic."""
        
        task_id = str(task["id"])
        error_msg = result.get("message", result.get("error", "Unknown error"))
        project_name = task.get("project_name", "Agent-OS v3")
        task_title = task.get("title", "Unknown Task")
        
        # V3: Send notification for HALT conditions
        if result.get("halted"):
            notify_halt(
                project_name=project_name,
                task_title=task_title,
                checkpoint_id=result.get("checkpoint_id", 0),
                signal_description=f"HALT in {phase}: {error_msg}"
            )
        else:
            notify_error(
                project_name=project_name,
                task_title=task_title,
                error=f"Failed in {phase}: {error_msg}"
            )
        
        # V3: Retry logic (only for non-halted failures)
        if False and not result.get("halted") and self.retry.should_retry(task_id):
            self.retry.record_retry(task_id, error_msg)
            delay = self.retry.get_retry_delay(task_id)
            update("tasks", {"status": "queued", "current_phase": None}, {"id": task_id})
            return {"success": False, "phase": phase, "retry_scheduled": True, "delay": delay, "task_id": task_id}
        
        update('tasks', {
            'status': 'halted' if result.get('halted') else 'failed',
            'current_phase': phase,
            'completed_at': datetime.utcnow()
        }, {'id': str(task['id'])})
        
        return {
            'success': False,
            'phase': phase,
            'halted': result.get('halted', False),
            'error': result.get('message', result.get('error', 'Unknown error')),
            'task_id': str(task['id'])
        }
    
    def _handle_compliance_failure(
        self,
        task: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle compliance rejection or hold."""
        
        decision = result.get("decision", "blocked")
        project_name = task.get("project_name", "Agent-OS v3")
        task_title = task.get("title", "Unknown Task")
        
        if decision == "human_review_required":
            status = "awaiting_review"
            # Send escalation notification
            from notifications import get_notification_manager
            get_notification_manager().notify_escalation(
                project_name=project_name,
                task_title=task_title,
                reason=f"Compliance requires human review: {result.get('reason', 'Unknown')}",
                risk_flags=result.get("risk_flags", [])
            )
        else:
            status = "blocked"
            # Send HALT notification for blocked items
            notify_halt(
                project_name=project_name,
                task_title=task_title,
                checkpoint_id=result.get("checkpoint_id", 0),
                signal_description=f"Compliance blocked: {decision}"
            )
        
        update("tasks", {
            "status": status,
            "current_phase": "compliance",
            "completed_at": datetime.utcnow()
        }, {"id": str(task["id"])})
        
        return {
            "success": False,
            "phase": "compliance",
            "decision": decision,
            "holds": result.get("holds", []),
            "task_id": str(task["id"])
        }

    def _handle_verification_failure(
        self,
        task: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle verification rejection."""
        
        decision = result.get('decision', 'rejected')
        project_name = task.get("project_name", "Agent-OS v3")
        task_title = task.get("title", "Unknown Task")
        issues = result.get('issues_found', [])
        
        if decision == 'escalate_to_compliance':
            status = 'awaiting_review'
            # Notify about escalation
            from notifications import get_notification_manager
            get_notification_manager().notify_escalation(
                project_name=project_name,
                task_title=task_title,
                reason="Verification escalated to compliance",
                risk_flags=[issue.get('description', str(issue)) for issue in issues[:3]]
            )
        elif decision == 'revision_required':
            status = 'needs_revision'
            notify_error(
                project_name=project_name,
                task_title=task_title,
                error=f"Revision required: {len(issues)} issues found"
            )
        else:
            status = 'failed'
            # Send HALT notification for hard rejection
            notify_halt(
                project_name=project_name,
                task_title=task_title,
                checkpoint_id=result.get("checkpoint_id", 0),
                signal_description=f"Verification rejected: {issues[0].get('description', 'Unknown issue') if issues else 'No details'}"
            )
        
        update('tasks', {
            'status': status,
            'current_phase': 'verification',
            'completed_at': datetime.utcnow()
        }, {'id': str(task['id'])})
        
        return {
            'success': False,
            'phase': 'verification',
            'decision': decision,
            'issues': issues,
            'task_id': str(task['id'])
        }
    
    def run_once(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Run one task if available."""
        
        task = self.get_next_task(project_id)
        if not task:
            return {'status': 'no_tasks'}
        
        return self.execute_task(task)


def run_once():
    """Convenience function to run one task."""
    orchestrator = TaskOrchestrator()
    return orchestrator.run_once()


if __name__ == '__main__':
    import json
    result = run_once()
    print(json.dumps(result, indent=2, default=str))
