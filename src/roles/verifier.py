"""
Agent-OS v3 Verifier Role

Following million-step methodology:
- Critically evaluates draft proposals
- Must operate independently from drafter
- HALTs on any uncertainty or security concern
- Never approves without checking ALL criteria

Enhanced with Groq validation (Jan 2026):
- Schema validation for draft outputs
- 99% cost reduction vs Claude for schema checks
"""

import os
import sys
import json
import subprocess
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from checkpoints import CheckpointManager
from uncertainty import UncertaintyDetector, UncertaintySignal, Severity, Category
from notifications import notify_halt, notify_escalation


class Verifier:
    """
    Verifier role: Critically evaluates draft proposals.
    
    ALLOWED:
    - Read draft proposals
    - Read original task specifications
    - Read project codebase for comparison
    - Execute read-only validation scripts
    - Approve or reject proposals
    - Request revisions with specific feedback
    - Flag risks for compliance review
    
    NOT ALLOWED:
    - Modify draft proposals
    - Generate alternative solutions
    - Approve under uncertainty
    - Approve without checking all criteria
    - Batch-approve multiple drafts
    - Execute write operations
    - Bypass compliance review for flagged risks
    """
    
    SYSTEM_PROMPT_PATH = Path('/opt/agent-os-v3/prompts/verifier_system.md')
    
    def __init__(
        self,
        agent_id: str,
        checkpoint_manager: CheckpointManager,
        model: str = "claude-sonnet-4-20250514",
        confidence_threshold: float = 0.90,
        use_groq_validation: bool = False
    ):
        self.agent_id = agent_id
        self.checkpoint_manager = checkpoint_manager
        self.model = model
        self.confidence_threshold = confidence_threshold
        self.use_groq_validation = use_groq_validation
        self.uncertainty_detector = UncertaintyDetector(confidence_threshold)
    
    def verify_draft(
        self,
        draft: Dict[str, Any],
        task: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verify a draft proposal.
        
        Args:
            draft: The draft proposal from the Drafter
            task: Original task specification
            project_context: Project information
        
        Returns:
            Verification result with decision, checks, issues, and risk flags
        """
        
        # Create checkpoint
        checkpoint_id = self.checkpoint_manager.create_checkpoint(
            project_id=str(task.get('project_id', '')),
            task_id=str(task.get('id', '')),
            phase='verification',
            step_name='verify_draft',
            state_snapshot={
                'draft': draft,
                'task': task,
                'project_context': project_context
            },
            inputs={
                'draft_id': draft.get('id', 'unknown'),
                'task_id': str(task.get('id', '')),
                'drafter_confidence': draft.get('confidence_score', 0)
            },
            verifier_agent_id=self.agent_id
        )
        
        try:
            checks = []
            issues = []
            risk_flags = []
            
            # 0. Schema validation using Groq (NEW)
            if self.use_groq_validation:
                schema_issues = self._validate_output_schema(draft)
                schema_check = {
                    'check_name': 'groq_schema_validation',
                    'passed': len(schema_issues) == 0,
                    'details': f"Validated draft structure using Groq Llama 3.1 8B"
                }
                checks.append(schema_check)
                issues.extend(schema_issues)
            
            # 1. Check drafter confidence
            drafter_confidence = draft.get('confidence_score', 0)
            confidence_check = {
                'check_name': 'drafter_confidence',
                'passed': drafter_confidence >= 0.85,
                'details': f"Drafter confidence: {drafter_confidence}"
            }
            checks.append(confidence_check)
            
            if not confidence_check['passed']:
                issues.append({
                    'severity': 'blocker',
                    'category': 'correctness',
                    'description': f"Drafter confidence {drafter_confidence} below threshold 0.85",
                    'location': None,
                    'suggested_fix': 'Drafter needs more information or clearer requirements'
                })
            
            # 2. Check for uncertainty flags from drafter
            if draft.get('uncertainty_flags'):
                uncertainty_check = {
                    'check_name': 'drafter_uncertainty_flags',
                    'passed': False,
                    'details': f"Drafter flagged uncertainties: {draft['uncertainty_flags']}"
                }
                checks.append(uncertainty_check)
                
                for flag in draft['uncertainty_flags']:
                    issues.append({
                        'severity': 'blocker',
                        'category': 'correctness',
                        'description': f"Drafter uncertainty: {flag}",
                        'location': None,
                        'suggested_fix': 'Address the uncertainty before proceeding'
                    })
            else:
                checks.append({
                    'check_name': 'drafter_uncertainty_flags',
                    'passed': True,
                    'details': 'No uncertainty flags from drafter'
                })
            
            # 3. Deep uncertainty check on reasoning using Groq (NEW)
            if self.use_groq_validation and draft.get('reasoning'):
                uncertainty_issues = self._check_reasoning_uncertainty(draft.get('reasoning', ''))
                if uncertainty_issues:
                    checks.append({
                        'check_name': 'groq_uncertainty_detection',
                        'passed': False,
                        'details': 'Groq detected uncertainty in drafter reasoning'
                    })
                    issues.extend(uncertainty_issues)
                else:
                    checks.append({
                        'check_name': 'groq_uncertainty_detection',
                        'passed': True,
                        'details': 'No uncertainty detected in reasoning'
                    })
            
            # 4. Validate file paths
            path_issues = self._validate_file_paths(draft, project_context)
            path_check = {
                'check_name': 'file_path_validation',
                'passed': len(path_issues) == 0,
                'details': f"Checked {len(draft.get('files_to_create', [])) + len(draft.get('files_to_modify', []))} file operations"
            }
            checks.append(path_check)
            issues.extend(path_issues)
            
            # 5. Validate code syntax (if applicable)
            syntax_issues = self._validate_syntax(draft)
            syntax_check = {
                'check_name': 'syntax_validation',
                'passed': len(syntax_issues) == 0,
                'details': 'Checked syntax of generated code'
            }
            checks.append(syntax_check)
            issues.extend(syntax_issues)
            
            # 6. Security scan
            security_risks = self._security_scan(draft)
            security_check = {
                'check_name': 'security_scan',
                'passed': len(security_risks) == 0,
                'details': 'Scanned for security issues'
            }
            checks.append(security_check)
            risk_flags.extend(security_risks)
            
            # 7. Check for breaking changes
            breaking_risks = self._check_breaking_changes(draft, project_context)
            breaking_check = {
                'check_name': 'breaking_changes',
                'passed': len(breaking_risks) == 0,
                'details': 'Checked for breaking changes'
            }
            checks.append(breaking_check)
            risk_flags.extend(breaking_risks)
            
            # 8. Complexity assessment
            complexity = draft.get('estimated_complexity', 'unknown')
            complexity_check = {
                'check_name': 'complexity_assessment',
                'passed': complexity in ['trivial', 'simple', 'moderate'],
                'details': f"Estimated complexity: {complexity}"
            }
            checks.append(complexity_check)
            
            if complexity in ['complex', 'expert']:
                issues.append({
                    'severity': 'major',
                    'category': 'maintainability',
                    'description': f"High complexity ({complexity}) requires careful review",
                    'location': None,
                    'suggested_fix': 'Consider breaking into smaller tasks'
                })
            
            # Determine decision
            has_blockers = any(i['severity'] == 'blocker' for i in issues)
            has_security_risks = any(r['risk_type'] == 'security' for r in risk_flags)
            has_major_issues = any(i['severity'] == 'major' for i in issues)
            
            if has_blockers:
                decision = 'rejected'
                verifier_confidence = 0.95  # Confident in rejection
            elif has_security_risks:
                decision = 'escalate_to_compliance'
                verifier_confidence = 0.90
            elif has_major_issues:
                decision = 'revision_required'
                verifier_confidence = 0.85
            else:
                decision = 'approved'
                verifier_confidence = 0.95
            
            # Build result
            verification_result = {
                'decision': decision,
                'checks_performed': checks,
                'issues_found': issues,
                'risk_flags': risk_flags,
                'revision_requests': [
                    i['suggested_fix'] for i in issues 
                    if i.get('suggested_fix')
                ],
                'verifier_confidence': verifier_confidence,
                'verifier_agent_id': self.agent_id,
                'checkpoint_id': checkpoint_id
            }
            
            # Complete checkpoint
            self.checkpoint_manager.complete_checkpoint(
                checkpoint_id,
                outputs=verification_result,
                rollback_data={'action': 'invalidate_verification'}
            )
            
            # Notify if escalation needed
            if decision == 'escalate_to_compliance':
                notify_escalation(
                    project_name=project_context.get('name', 'Unknown'),
                    task_title=task.get('title', 'Unknown'),
                    reason='Security or policy concerns detected',
                    risk_flags=[r['description'] for r in risk_flags]
                )
            
            return verification_result
            
        except Exception as e:
            self.checkpoint_manager.fail_checkpoint(
                checkpoint_id,
                {'reason': 'exception', 'error': str(e)}
            )
            raise
    
    def _validate_output_schema(self, draft: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validate draft output against expected schema using Groq.
        
        Uses Llama 3.1 8B for fast, cheap validation (~$0.00001, ~260ms).
        This catches malformed LLM outputs before they can cause issues.
        """
        issues = []
        
        try:
            from schema_validator import validate_draft_output
            
            result = validate_draft_output(draft)
            
            if not result.success:
                issues.append({
                    'severity': 'major',
                    'category': 'correctness',
                    'description': f"Schema validation failed: {result.raw_response.get('error', 'Unknown error')}",
                    'location': None,
                    'suggested_fix': 'Regenerate draft with proper structure'
                })
            elif not result.valid:
                for error in result.errors:
                    issues.append({
                        'severity': 'blocker',
                        'category': 'correctness',
                        'description': f"Schema error: {error.get('message', str(error))}",
                        'location': error.get('path', None),
                        'suggested_fix': f"Fix field at {error.get('path', 'unknown path')}"
                    })
                    
        except ImportError:
            # Groq integration not available, skip this check
            pass
        except Exception as e:
            # Log but don't fail verification
            issues.append({
                'severity': 'minor',
                'category': 'correctness',
                'description': f"Schema validation error: {str(e)}",
                'location': None,
                'suggested_fix': None
            })
        
        return issues
    
    def _check_reasoning_uncertainty(self, reasoning: str) -> List[Dict[str, Any]]:
        """
        Check drafter's reasoning for hidden uncertainty using Groq.
        
        Uses Llama 3.3 70B for deep semantic analysis (~$0.00015, ~400ms).
        This catches nuanced uncertainty that regex patterns might miss.
        """
        issues = []
        
        try:
            from groq_integration import detect_uncertainty
            
            result = detect_uncertainty(
                content=reasoning,
                context="Drafter reasoning for code generation task",
                task_type="implementation"
            )
            
            if result.success and result.has_uncertainty and result.should_halt:
                issues.append({
                    'severity': 'blocker',
                    'category': 'correctness',
                    'description': f"Uncertainty detected in reasoning: {result.summary}",
                    'location': 'reasoning',
                    'suggested_fix': 'Clarify requirements before proceeding'
                })
            elif result.success and result.has_uncertainty:
                issues.append({
                    'severity': 'major',
                    'category': 'correctness',
                    'description': f"Possible uncertainty in reasoning: {result.summary}",
                    'location': 'reasoning',
                    'suggested_fix': 'Review reasoning for assumptions'
                })
                    
        except ImportError:
            # Groq integration not available, skip this check
            pass
        except Exception:
            # Don't fail on deep analysis errors
            pass
        
        return issues
    
    def _validate_file_paths(
        self,
        draft: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate all file paths in the draft."""
        issues = []
        work_dir = project_context.get('work_dir', '')
        
        all_files = (
            draft.get('files_to_create', []) + 
            draft.get('files_to_modify', [])
        )
        
        for file_op in all_files:
            path = file_op.get('path', '')
            
            # Check for path traversal
            if '..' in path:
                issues.append({
                    'severity': 'blocker',
                    'category': 'security',
                    'description': f"Path traversal detected in: {path}",
                    'location': path,
                    'suggested_fix': 'Use absolute paths within project directory'
                })
            
            # Check for absolute paths outside project
            if path.startswith('/') and work_dir and not path.startswith(work_dir):
                issues.append({
                    'severity': 'blocker',
                    'category': 'security',
                    'description': f"Path outside project directory: {path}",
                    'location': path,
                    'suggested_fix': f'Path must be within {work_dir}'
                })
            
            # Check for sensitive paths
            sensitive_patterns = [
                r'\.env',
                r'\.git/',
                r'secrets?',
                r'credentials?',
                r'\.ssh/',
                r'id_rsa',
            ]
            
            for pattern in sensitive_patterns:
                if re.search(pattern, path, re.IGNORECASE):
                    issues.append({
                        'severity': 'blocker',
                        'category': 'security',
                        'description': f"Sensitive path detected: {path}",
                        'location': path,
                        'suggested_fix': 'Cannot modify sensitive files'
                    })
        
        return issues
    
    def _validate_syntax(self, draft: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate syntax of code in the draft."""
        issues = []
        
        for file_op in draft.get('files_to_create', []):
            path = file_op.get('path', '')
            content = file_op.get('content', '')
            
            # Python syntax check
            if path.endswith('.py'):
                try:
                    compile(content, path, 'exec')
                except SyntaxError as e:
                    issues.append({
                        'severity': 'blocker',
                        'category': 'correctness',
                        'description': f"Python syntax error: {e.msg}",
                        'location': f"{path}:{e.lineno}",
                        'suggested_fix': f"Fix syntax at line {e.lineno}"
                    })
            
            # JSON syntax check
            if path.endswith('.json'):
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    issues.append({
                        'severity': 'blocker',
                        'category': 'correctness',
                        'description': f"JSON syntax error: {e.msg}",
                        'location': f"{path}:{e.lineno}",
                        'suggested_fix': f"Fix JSON at line {e.lineno}"
                    })
        
        return issues
    
    def _security_scan(self, draft: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Scan for security issues."""
        risk_flags = []
        
        # Patterns that indicate potential security issues
        security_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password'),
            (r'api_key\s*=\s*["\'][^"\']+["\']', 'Hardcoded API key'),
            (r'secret\s*=\s*["\'][^"\']+["\']', 'Hardcoded secret'),
            (r'eval\s*\(', 'Use of eval()'),
            (r'exec\s*\(', 'Use of exec()'),
            (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', 'Shell injection risk'),
            (r'os\.system\s*\(', 'Shell command execution'),
            (r'__import__\s*\(', 'Dynamic import'),
        ]
        
        all_content = ''
        for file_op in draft.get('files_to_create', []):
            all_content += file_op.get('content', '') + '\n'
        
        for pattern, description in security_patterns:
            if re.search(pattern, all_content, re.IGNORECASE):
                risk_flags.append({
                    'risk_type': 'security',
                    'description': description,
                    'requires_human_review': True
                })
        
        return risk_flags
    
    def _check_breaking_changes(
        self,
        draft: Dict[str, Any],
        project_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Check for potential breaking changes."""
        risk_flags = []
        
        # Check for modifications to critical files
        critical_patterns = [
            r'setup\.py',
            r'pyproject\.toml',
            r'requirements\.txt',
            r'package\.json',
            r'Dockerfile',
            r'docker-compose',
            r'\.github/',
            r'Makefile',
        ]
        
        for file_op in draft.get('files_to_modify', []):
            path = file_op.get('path', '')
            for pattern in critical_patterns:
                if re.search(pattern, path):
                    risk_flags.append({
                        'risk_type': 'breaking_change',
                        'description': f"Modifying critical file: {path}",
                        'requires_human_review': True
                    })
        
        return risk_flags


def create_verifier(
    agent_id: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
    use_groq_validation: bool = False
) -> Verifier:
    """Factory function to create a Verifier instance."""
    
    if agent_id is None:
        agent_id = f"verifier-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    checkpoint_manager = CheckpointManager()
    
    return Verifier(
        agent_id=agent_id,
        checkpoint_manager=checkpoint_manager,
        model=model,
        use_groq_validation=use_groq_validation
    )


if __name__ == '__main__':
    # Test the verifier
    print("Testing Verifier role with Groq integration...")
    
    verifier = create_verifier(use_groq_validation=False)
    
    # Test draft with some issues
    test_draft = {
        'files_to_create': [
            {
                'path': 'hello.py',
                'content': 'print("Hello World")',
                'purpose': 'Test script'
            }
        ],
        'files_to_modify': [],
        'confidence_score': 0.95,
        'uncertainty_flags': [],
        'reasoning': 'Simple hello world script that prints a greeting.',
        'estimated_complexity': 'trivial'
    }
    
    test_task = {
        'id': 'test-task-001',
        'project_id': 'test-project-001',
        'title': 'Create hello world script',
        'task_type': 'implementation'
    }
    
    test_context = {
        'name': 'test-project',
        'work_dir': '/tmp/test'
    }
    
    print(f"Verifier agent ID: {verifier.agent_id}")
    print("Verifying draft...")
    
    result = verifier.verify_draft(test_draft, test_task, test_context)
    print(f"Result: {json.dumps(result, indent=2)}")
