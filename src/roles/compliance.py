"""
Agent-OS v3 Compliance Role

The Compliance role enforces organizational policies AFTER verification
and BEFORE execution. It is the final gate before any irreversible action.

Following million-step methodology:
- Never approve security-flagged items without human review
- Never modify proposals or verification results
- Never override human-set holds
- Never proceed without complete audit trail
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from db import query_one, query_all, insert_returning, update, execute
from audit import log_action


class ComplianceDecision:
    """Represents a compliance review decision."""
    
    CLEARED = 'cleared'
    BLOCKED = 'blocked'
    HUMAN_REVIEW_REQUIRED = 'human_review_required'
    
    def __init__(self):
        self.decision = None
        self.policy_checks = []
        self.holds_applied = []
        self.escalation = {'required': False, 'reason': None, 'path': None}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'decision': self.decision,
            'policy_checks': self.policy_checks,
            'holds_applied': self.holds_applied,
            'escalation': self.escalation
        }


class Compliance:
    """
    Compliance role for Agent-OS v3.
    
    Enforces policies:
    - security_review: Security risks require human review
    - breaking_change: Breaking changes require human review
    - external_api: External API changes require human review
    - budget_check: Projects approaching budget need review
    """
    
    def __init__(self):
        self.policies = [
            'security_review',
            'breaking_change',
            'external_api',
            'budget_check'
        ]
    
    def review_proposal(
        self,
        verification_result: Dict[str, Any],
        task: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Review a verified proposal for compliance.
        
        This is called AFTER verification passes and BEFORE execution.
        
        Returns:
            ComplianceDecision dict with decision, policy_checks, holds, escalation
        """
        decision = ComplianceDecision()
        
        # Log compliance review start
        log_action('COMPLIANCE_STARTED', {
            'task_id': task.get('id'),
            'verification_id': verification_result.get('verification_id')
        }, task_id=task.get("id"))
        
        # Run all policy checks
        security_issues = self.check_security_policy(verification_result)
        breaking_issues = self.check_breaking_change_policy(verification_result)
        external_issues = self.check_external_api_policy(verification_result)
        budget_status = self.check_budget_policy(project_context.get('project_id'))
        
        # Record policy check results
        decision.policy_checks = [
            {'policy': 'security_review', 'result': 'pass' if not security_issues else 'fail', 
             'details': security_issues or 'No security issues'},
            {'policy': 'breaking_change', 'result': 'pass' if not breaking_issues else 'fail',
             'details': breaking_issues or 'No breaking changes'},
            {'policy': 'external_api', 'result': 'pass' if not external_issues else 'fail',
             'details': external_issues or 'No external API changes'},
            {'policy': 'budget_check', 'result': budget_status.get('result', 'pass'),
             'details': budget_status.get('details', 'Budget OK')}
        ]
        
        # Determine decision based on policy results
        failed_policies = [p for p in decision.policy_checks if p['result'] == 'fail']
        
        if not failed_policies:
            decision.decision = ComplianceDecision.CLEARED
            log_action('COMPLIANCE_CLEARED', decision.to_dict(), task_id=task.get("id"))
        elif any(p['policy'] in ['security_review'] for p in failed_policies):
            decision.decision = ComplianceDecision.HUMAN_REVIEW_REQUIRED
            decision.escalation = {
                'required': True,
                'reason': 'Security policy requires human review',
                'path': 'security_team'
            }
            self.apply_hold(task.get('id'), 'security', 'Security review required')
            decision.holds_applied.append({'hold_type': 'security', 'reason': 'Security review required'})
            log_action('COMPLIANCE_BLOCKED', decision.to_dict(), task_id=task.get("id"))
        else:
            decision.decision = ComplianceDecision.HUMAN_REVIEW_REQUIRED
            decision.escalation = {
                'required': True,
                'reason': f"Policy failures: {[p['policy'] for p in failed_policies]}",
                'path': 'project_lead'
            }
            log_action('COMPLIANCE_BLOCKED', decision.to_dict(), task_id=task.get("id"))
        
        return decision.to_dict()
    
    def check_security_policy(self, verification_result: Dict[str, Any]) -> Optional[List[str]]:
        """Check for security issues that require human review."""
        issues = []
        
        risk_flags = verification_result.get('risk_flags', [])
        for flag in risk_flags:
            if flag.get('risk_type') == 'security':
                issues.append(flag.get('description', 'Security risk detected'))
        
        # Check for security-related issue categories
        issues_found = verification_result.get('issues_found', [])
        for issue in issues_found:
            if issue.get('category') == 'security':
                issues.append(issue.get('description', 'Security issue'))
        
        return issues if issues else None
    
    def check_breaking_change_policy(self, verification_result: Dict[str, Any]) -> Optional[List[str]]:
        """Check for breaking changes that require human review."""
        issues = []
        
        risk_flags = verification_result.get('risk_flags', [])
        for flag in risk_flags:
            if flag.get('risk_type') == 'breaking_change':
                issues.append(flag.get('description', 'Breaking change detected'))
        
        return issues if issues else None
    
    def check_external_api_policy(self, verification_result: Dict[str, Any]) -> Optional[List[str]]:
        """Check for external API changes that require review."""
        issues = []
        
        risk_flags = verification_result.get('risk_flags', [])
        for flag in risk_flags:
            if flag.get('risk_type') == 'external_dependency':
                issues.append(flag.get('description', 'External API change'))
        
        return issues if issues else None
    
    def check_budget_policy(self, project_id: Optional[str]) -> Dict[str, Any]:
        """Check if project is within budget limits."""
        if not project_id:
            return {'result': 'pass', 'details': 'No project context'}
        
        # Query project budget status
        project = query_one(
            "SELECT config FROM projects WHERE id = %s",
            (project_id,)
        )
        
        if not project or not project.get('config'):
            return {'result': 'pass', 'details': 'No budget configured'}
        
        config = project.get('config', {})
        if isinstance(config, str):
            config = json.loads(config)
        
        budget_limit = config.get('budget_limit')
        budget_used = config.get('budget_used', 0)
        
        if budget_limit and budget_used:
            usage_pct = (budget_used / budget_limit) * 100
            if usage_pct > 80:
                return {
                    'result': 'fail',
                    'details': f'Budget usage at {usage_pct:.1f}% (>{80}% threshold)'
                }
        
        return {'result': 'pass', 'details': 'Budget within limits'}
    
    def apply_hold(
        self,
        task_id: str,
        hold_type: str,
        reason: str
    ) -> bool:
        """
        Apply a hold to block task execution.
        
        Hold types: security, budget, manual, policy
        """
        # Store hold in task metadata or separate holds table
        execute(
            """
            UPDATE tasks 
            SET status = 'held',
                current_phase = 'compliance',
                updated_at = NOW()
            WHERE id = %s
            """,
            (task_id,)
        )
        
        log_action('HALT_TRIGGERED', {
            'hold_type': hold_type,
            'reason': reason
        }, task_id=str(task_id))
        
        return True
    
    def release_hold(
        self,
        task_id: str,
        hold_type: str,
        approver: str
    ) -> bool:
        """
        Release a hold to allow task execution.
        
        Requires approver identification for audit trail.
        """
        execute(
            """
            UPDATE tasks 
            SET status = 'queued',
                current_phase = NULL,
                updated_at = NOW()
            WHERE id = %s AND status = 'held'
            """,
            (task_id,)
        )
        
        log_action('COMPLIANCE_CLEARED', {
            'hold_type': hold_type,
            'released_by': approver,
            'release_time': datetime.utcnow().isoformat()
        }, task_id=str(task_id))
        
        return True
    
    def get_active_holds(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of tasks with active holds."""
        if task_id:
            result = query_one(
                "SELECT id, title, status, current_phase FROM tasks WHERE id = %s AND status = 'held'",
                (task_id,)
            )
            return [result] if result else []
        
        return query_all(
            "SELECT id, title, status, current_phase FROM tasks WHERE status = 'held' ORDER BY updated_at DESC"
        ) or []


# Factory function
def create_compliance() -> Compliance:
    """Create a Compliance instance."""
    return Compliance()
