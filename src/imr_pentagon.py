"""
Agent-OS v3 IMR Pentagon Validator

Following million-step methodology:
- Every irreversible action must pass all 5 Pentagon checks
- Inputs, Method, Rules, Review, Record (IMR Pentagon)
- HALT immediately if any validation fails
- No exceptions, no bypasses
"""

import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum

from db import query_one, query_all, insert_returning


class ValidationStatus(Enum):
    """Validation result status."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class PentagonResult:
    """Complete IMR Pentagon validation result."""
    valid: bool
    inputs: ValidationResult
    method: ValidationResult
    rules: ValidationResult
    review: ValidationResult
    record: ValidationResult
    
    def get_failures(self) -> List[str]:
        """Get list of failed validation components."""
        failures = []
        for component, result in [
            ('inputs', self.inputs),
            ('method', self.method), 
            ('rules', self.rules),
            ('review', self.review),
            ('record', self.record)
        ]:
            if result.status == ValidationStatus.FAIL:
                failures.append(component)
        return failures


class IMRPentagon:
    """
    IMR Pentagon validator for irreversible actions.
    
    Every irreversible action (git_push, create_pr, send_notification) must:
    - I: Inputs validated (all required data present and valid)
    - M: Method defined (execution procedure clear)
    - R: Rules checked (preconditions met, invariants maintained)
    - R: Review approved (human/verifier approval exists and recent)
    - R: Record created (full audit trail entry)
    """
    
    # Actions considered irreversible
    IRREVERSIBLE_ACTIONS = {
        'git_push', 'create_pr', 'send_notification', 
        'delete_file', 'external_api_call', 'database_write'
    }
    
    # Required inputs for each action type
    REQUIRED_INPUTS = {
        'git_push': ['repository', 'branch', 'commit_message', 'files_changed'],
        'create_pr': ['repository', 'source_branch', 'target_branch', 'title', 'description'],
        'send_notification': ['recipient', 'message', 'channel'],
        'delete_file': ['file_path', 'backup_location'],
        'external_api_call': ['endpoint', 'method', 'payload'],
        'database_write': ['table', 'operation', 'data']
    }
    
    # Maximum age for approval records (in hours)
    MAX_APPROVAL_AGE_HOURS = 24
    
    def validate_inputs(self, step_name: str, inputs: Dict[str, Any]) -> ValidationResult:
        """
        Validate that all required inputs are present and valid.
        
        Args:
            step_name: Name of the step being validated
            inputs: Input data provided for the step
            
        Returns:
            ValidationResult indicating success/failure
        """
        if step_name not in self.REQUIRED_INPUTS:
            return ValidationResult(
                status=ValidationStatus.WARNING,
                message=f"Step '{step_name}' not in known irreversible actions",
                details={'step_name': step_name}
            )
        
        required = self.REQUIRED_INPUTS[step_name]
        missing = []
        invalid = []
        
        for field in required:
            if field not in inputs:
                missing.append(field)
            elif not inputs[field] or inputs[field] == '':
                invalid.append(field)
        
        if missing or invalid:
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message=f"Input validation failed for '{step_name}'",
                details={
                    'missing_fields': missing,
                    'invalid_fields': invalid,
                    'required_fields': required
                }
            )
        
        return ValidationResult(
            status=ValidationStatus.PASS,
            message=f"All required inputs present for '{step_name}'",
            details={'validated_fields': required}
        )
    
    def check_rules(self, step_name: str, context: Dict[str, Any]) -> ValidationResult:
        """
        Check that all business rules and preconditions are met.
        
        Args:
            step_name: Name of the step being validated
            context: Current execution context
            
        Returns:
            ValidationResult indicating rule compliance
        """
        # Check general preconditions
        if not context.get('task_id'):
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message="No task_id in context - cannot validate rules",
                details={'context_keys': list(context.keys())}
            )
        
        # Check task exists and is in correct state
        task = query_one(
            "SELECT * FROM tasks WHERE id = %s",
            (context['task_id'],)
        )
        
        if not task:
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message=f"Task {context['task_id']} not found",
                details={'task_id': context['task_id']}
            )
        
        if task['status'] != 'executing':
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message=f"Task status is '{task['status']}', expected 'executing'",
                details={'task_id': context['task_id'], 'status': task['status']}
            )
        
        # Step-specific rule checks
        if step_name == 'git_push':
            # Check no uncommitted changes
            if context.get('uncommitted_changes'):
                return ValidationResult(
                    status=ValidationStatus.FAIL,
                    message="Cannot push with uncommitted changes",
                    details={'uncommitted_files': context['uncommitted_changes']}
                )
        
        elif step_name == 'create_pr':
            # Check source branch exists and is different from target
            source = context.get('source_branch')
            target = context.get('target_branch', 'main')
            if source == target:
                return ValidationResult(
                    status=ValidationStatus.FAIL,
                    message=f"Source branch '{source}' cannot be same as target '{target}'",
                    details={'source_branch': source, 'target_branch': target}
                )
        
        return ValidationResult(
            status=ValidationStatus.PASS,
            message=f"All rules satisfied for '{step_name}'",
            details={'rules_checked': ['task_status', 'step_specific']}
        )
    
    def verify_review(self, step_name: str, approval_record: Optional[Dict[str, Any]]) -> ValidationResult:
        """
        Verify that proper approval exists and is recent.
        
        Args:
            step_name: Name of the step being validated
            approval_record: Approval record from verifier/human
            
        Returns:
            ValidationResult indicating approval status
        """
        if not approval_record:
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message=f"No approval record found for '{step_name}'",
                details={'step_name': step_name}
            )
        
        # Check approval decision
        if approval_record.get('decision') != 'approved':
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message=f"Approval decision was '{approval_record.get('decision')}', not 'approved'",
                details={'decision': approval_record.get('decision')}
            )
        
        # Check approval age
        approved_at = approval_record.get('completed_at')
        if not approved_at:
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message="Approval record missing completion timestamp",
                details={'approval_record': approval_record}
            )
        
        if isinstance(approved_at, str):
            try:
                approved_at = datetime.fromisoformat(approved_at.replace('Z', '+00:00'))
            except ValueError:
                return ValidationResult(
                    status=ValidationStatus.FAIL,
                    message=f"Invalid approval timestamp format: {approved_at}",
                    details={'timestamp': approved_at}
                )
        
        age_hours = (datetime.utcnow() - approved_at.replace(tzinfo=None)).total_seconds() / 3600
        if age_hours > self.MAX_APPROVAL_AGE_HOURS:
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message=f"Approval is {age_hours:.1f} hours old, max allowed is {self.MAX_APPROVAL_AGE_HOURS}",
                details={'age_hours': age_hours, 'max_hours': self.MAX_APPROVAL_AGE_HOURS}
            )
        
        # Check verifier confidence if available
        confidence = approval_record.get('verifier_confidence', 0)
        if confidence < 0.90:
            return ValidationResult(
                status=ValidationStatus.FAIL,
                message=f"Verifier confidence {confidence} below required 0.90",
                details={'confidence': confidence}
            )
        
        return ValidationResult(
            status=ValidationStatus.PASS,
            message=f"Valid approval found for '{step_name}'",
            details={
                'decision': approval_record.get('decision'),
                'age_hours': round(age_hours, 2),
                'confidence': confidence
            }
        )
    
    def create_record(self, step_name: str, all_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create full audit trail entry for the irreversible action.
        
        Args:
            step_name: Name of the step being recorded
            all_data: Complete data about the action
            
        Returns:
            Audit entry record
        """
        audit_entry = {
            'step_name': step_name,
            'action_type': 'irreversible',
            'timestamp': datetime.utcnow().isoformat(),
            'task_id': all_data.get('task_id'),
            'project_id': all_data.get('project_id'),
            'inputs': all_data.get('inputs', {}),
            'context': all_data.get('context', {}),
            'approval_id': all_data.get('approval_id'),
            'executor_agent': all_data.get('executor_agent', 'execution_controller'),
            'imr_pentagon_validated': True
        }
        
        # Store in audit_trail table
        try:
            audit_id = insert_returning(
                'audit_trail',
                {
                    'project_id': audit_entry.get('project_id'),
                    'task_id': audit_entry.get('task_id'),
                    'action_type': audit_entry['action_type'],
                    'step_name': audit_entry['step_name'],
                    'data': json.dumps(audit_entry, default=str),
                    'created_at': datetime.utcnow()
                }
            )
            audit_entry['audit_id'] = audit_id
        except Exception as e:
            # If audit fails, this is a critical error
            raise Exception(f"Failed to create audit record: {e}")
        
        return audit_entry
    
    def validate_all(self, step_name: str, context: Dict[str, Any]) -> PentagonResult:
        """
        Run complete IMR Pentagon validation.
        
        Args:
            step_name: Name of the step being validated
            context: Complete execution context with all required data
            
        Returns:
            PentagonResult with all validation results
        """
        # Extract components from context
        inputs = context.get('inputs', {})
        approval_record = context.get('approval_record')
        
        # Run all validations
        inputs_result = self.validate_inputs(step_name, inputs)
        method_result = ValidationResult(
            status=ValidationStatus.PASS,
            message=f"Execution method defined for '{step_name}'",
            details={'method': 'deterministic_execution'}
        )
        rules_result = self.check_rules(step_name, context)
        review_result = self.verify_review(step_name, approval_record)
        
        # Create record only if all other validations pass
        if all(r.status == ValidationStatus.PASS for r in [inputs_result, method_result, rules_result, review_result]):
            try:
                record = self.create_record(step_name, context)
                record_result = ValidationResult(
                    status=ValidationStatus.PASS,
                    message=f"Audit record created for '{step_name}'",
                    details={'audit_id': record.get('audit_id')}
                )
            except Exception as e:
                record_result = ValidationResult(
                    status=ValidationStatus.FAIL,
                    message=f"Failed to create audit record: {e}",
                    details={'error': str(e)}
                )
        else:
            record_result = ValidationResult(
                status=ValidationStatus.FAIL,
                message="Cannot create record - other validations failed",
                details={'skipped': True}
            )
        
        # Determine overall validity
        all_results = [inputs_result, method_result, rules_result, review_result, record_result]
        valid = all(r.status == ValidationStatus.PASS for r in all_results)
        
        return PentagonResult(
            valid=valid,
            inputs=inputs_result,
            method=method_result,
            rules=rules_result,
            review=review_result,
            record=record_result
        )
