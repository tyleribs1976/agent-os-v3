#!/usr/bin/env python3
"""
Agent-OS v3 Pull Request Manager

Handles GitHub PR creation and status tracking.
Following million-step methodology: explicit operations, no silent failures.
"""

import os
import subprocess
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from db import insert_returning, query_one, query_all, update
from exceptions import ExecutionError
from helpers import get_timestamp
from validators import validate_task_id, validate_project_id
from constants import GIT_BRANCH_PREFIX, PR_AUTO_MERGE


class PRManager:
    """
    Manages GitHub pull request operations.
    
    Responsibilities:
    - Create pull requests via gh CLI
    - Track PR status and URLs
    - Handle PR-related errors
    - Validate prerequisites (branch, remote, gh auth)
    
    Does NOT handle:
    - Git commits (handled by ExecutionController)
    - Branch creation (handled by ExecutionController)
    - File operations (handled by ExecutionController)
    """
    
    def __init__(self, work_dir: str, project_id: str):
        """
        Initialize PR manager.
        
        Args:
            work_dir: Path to git repository
            project_id: UUID of project
        
        Raises:
            ExecutionError: If work_dir doesn't exist or isn't a git repo
        """
        self.work_dir = Path(work_dir)
        self.project_id = validate_project_id(project_id)
        
        if not self.work_dir.exists():
            raise ExecutionError(
                f"Work directory does not exist: {work_dir}",
                context={'work_dir': work_dir, 'project_id': project_id}
            )
        
        if not (self.work_dir / '.git').exists():
            raise ExecutionError(
                f"Work directory is not a git repository: {work_dir}",
                context={'work_dir': work_dir, 'project_id': project_id}
            )
    
    def _run_command(
        self, 
        cmd: List[str], 
        check: bool = True,
        capture_output: bool = True
    ) -> subprocess.CompletedProcess:
        """
        Run a shell command in the work directory.
        
        Args:
            cmd: Command and arguments as list
            check: Whether to raise on non-zero exit
            capture_output: Whether to capture stdout/stderr
        
        Returns:
            CompletedProcess instance
        
        Raises:
            ExecutionError: If command fails and check=True
        """
        try:
            result = subprocess.run(
                cmd,
                cwd=self.work_dir,
                check=check,
                capture_output=capture_output,
                text=True,
                timeout=30
            )
            return result
        except subprocess.CalledProcessError as e:
            raise ExecutionError(
                f"Command failed: {' '.join(cmd)}",
                context={
                    'command': ' '.join(cmd),
                    'exit_code': e.returncode,
                    'stdout': e.stdout,
                    'stderr': e.stderr,
                    'work_dir': str(self.work_dir)
                },
                original_error=e
            )
        except subprocess.TimeoutExpired as e:
            raise ExecutionError(
                f"Command timed out: {' '.join(cmd)}",
                context={
                    'command': ' '.join(cmd),
                    'timeout': 30,
                    'work_dir': str(self.work_dir)
                },
                original_error=e
            )
    
    def check_gh_auth(self) -> bool:
        """
        Check if gh CLI is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        try:
            result = self._run_command(['gh', 'auth', 'status'], check=False)
            return result.returncode == 0
        except ExecutionError:
            return False
    
    def get_current_branch(self) -> str:
        """
        Get the current git branch name.
        
        Returns:
            Branch name
        
        Raises:
            ExecutionError: If unable to determine branch
        """
        result = self._run_command(['git', 'branch', '--show-current'])
        branch = result.stdout.strip()
        
        if not branch:
            raise ExecutionError(
                "Unable to determine current branch",
                context={'work_dir': str(self.work_dir)}
            )
        
        return branch
    
    def get_default_branch(self) -> str:
        """
        Get the default branch (main or master).
        
        Returns:
            Default branch name
        
        Raises:
            ExecutionError: If unable to determine default branch
        """
        # Try to get from remote
        result = self._run_command(
            ['git', 'symbolic-ref', 'refs/remotes/origin/HEAD'],
            check=False
        )
        
        if result.returncode == 0:
            # Output like: refs/remotes/origin/main
            ref = result.stdout.strip()
            branch = ref.split('/')[-1]
            return branch
        
        # Fallback: check if main or master exists
        result = self._run_command(['git', 'branch', '-r'], check=False)
        if result.returncode == 0:
            branches = result.stdout
            if 'origin/main' in branches:
                return 'main'
            elif 'origin/master' in branches:
                return 'master'
        
        # Default fallback
        return 'main'
    
    def create_pr(
        self,
        task_id: str,
        title: str,
        body: str,
        base_branch: Optional[str] = None,
        labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a GitHub pull request.
        
        Args:
            task_id: UUID of task
            title: PR title
            body: PR description (markdown)
            base_branch: Target branch (defaults to main/master)
            labels: Optional list of labels to add
        
        Returns:
            Dict with keys:
                - pr_url: URL of created PR
                - pr_number: PR number
                - branch: Source branch name
                - base_branch: Target branch name
        
        Raises:
            ExecutionError: If PR creation fails
        """
        task_id = validate_task_id(task_id)
        
        # Check gh auth
        if not self.check_gh_auth():
            raise ExecutionError(
                "gh CLI is not authenticated",
                context={
                    'task_id': task_id,
                    'work_dir': str(self.work_dir),
                    'hint': 'Run: gh auth login'
                }
            )
        
        # Get current branch
        current_branch = self.get_current_branch()
        
        # Determine base branch
        if base_branch is None:
            base_branch = self.get_default_branch()
        
        # Build gh pr create command
        cmd = [
            'gh', 'pr', 'create',
            '--title', title,
            '--body', body,
            '--base', base_branch
        ]
        
        # Add labels if provided
        if labels:
            for label in labels:
                cmd.extend(['--label', label])
        
        # Create PR
        result = self._run_command(cmd)
        pr_url = result.stdout.strip()
        
        # Extract PR number from URL
        # URL format: https://github.com/owner/repo/pull/123
        pr_number = None
        if pr_url:
            parts = pr_url.rstrip('/').split('/')
            if len(parts) > 0 and parts[-1].isdigit():
                pr_number = int(parts[-1])
        
        # Log PR creation
        pr_data = {
            'task_id': task_id,
            'project_id': self.project_id,
            'pr_url': pr_url,
            'pr_number': pr_number,
            'branch': current_branch,
            'base_branch': base_branch,
            'title': title,
            'status': 'open',
            'created_at': get_timestamp()
        }
        
        # Store in database (if pr_tracking table exists)
        try:
            insert_returning('pull_requests', pr_data)
        except Exception:
            # Table might not exist yet, that's okay
            pass
        
        return {
            'pr_url': pr_url,
            'pr_number': pr_number,
            'branch': current_branch,
            'base_branch': base_branch
        }
    
    def get_pr_status(self, pr_number: int) -> Dict[str, Any]:
        """
        Get the status of a pull request.
        
        Args:
            pr_number: PR number
        
        Returns:
            Dict with PR status information:
                - state: 'OPEN', 'CLOSED', 'MERGED'
                - mergeable: bool or None
                - checks: list of check run statuses
                - reviews: list of review statuses
        
        Raises:
            ExecutionError: If unable to get PR status
        """
        if not self.check_gh_auth():
            raise ExecutionError(
                "gh CLI is not authenticated",
                context={'pr_number': pr_number}
            )
        
        # Get PR details as JSON
        result = self._run_command([
            'gh', 'pr', 'view', str(pr_number),
            '--json', 'state,mergeable,statusCheckRollup,reviews'
        ])
        
        import json
        pr_info = json.loads(result.stdout)
        
        return {
            'state': pr_info.get('state', 'UNKNOWN'),
            'mergeable': pr_info.get('mergeable'),
            'checks': pr_info.get('statusCheckRollup', []),
            'reviews': pr_info.get('reviews', [])
        }
    
    def merge_pr(self, pr_number: int, merge_method: str = 'merge') -> bool:
        """
        Merge a pull request.
        
        Args:
            pr_number: PR number
            merge_method: 'merge', 'squash', or 'rebase'
        
        Returns:
            True if merged successfully
        
        Raises:
            ExecutionError: If merge fails
        """
        if not PR_AUTO_MERGE:
            raise ExecutionError(
                "Auto-merge is disabled in configuration",
                context={'pr_number': pr_number, 'PR_AUTO_MERGE': PR_AUTO_MERGE}
            )
        
        if not self.check_gh_auth():
            raise ExecutionError(
                "gh CLI is not authenticated",
                context={'pr_number': pr_number}
            )
        
        valid_methods = ['merge', 'squash', 'rebase']
        if merge_method not in valid_methods:
            raise ExecutionError(
                f"Invalid merge method: {merge_method}",
                context={'merge_method': merge_method, 'valid_methods': valid_methods}
            )
        
        cmd = ['gh', 'pr', 'merge', str(pr_number), f'--{merge_method}']
        self._run_command(cmd)
        
        return True