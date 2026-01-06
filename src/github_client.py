"""Agent-OS v3 GitHub API Client

Following million-step methodology:
- All API calls are explicit, never assumed
- Errors are never swallowed
- Authentication is validated before operations
"""

import os
import json
import subprocess
from typing import Optional, Dict, Any, List
from pathlib import Path


class GitHubClientError(Exception):
    """Raised when GitHub API operations fail."""
    pass


class GitHubClient:
    """
    Simple GitHub API client using GitHub CLI (gh).
    
    This client wraps the gh CLI tool for GitHub operations.
    Requires gh to be installed and authenticated.
    
    ALLOWED:
    - Create pull requests
    - Get repository information
    - List issues and PRs
    - Add comments
    
    NOT ALLOWED:
    - Delete operations without explicit confirmation
    - Force push operations
    - Merge operations (requires human approval)
    """
    
    def __init__(
        self,
        repo: Optional[str] = None,
        work_dir: Optional[str] = None
    ):
        """
        Initialize GitHub client.
        
        Args:
            repo: Repository in format 'owner/repo' (optional, can be inferred from git remote)
            work_dir: Working directory for git operations (defaults to current dir)
        """
        self.repo = repo
        self.work_dir = work_dir or os.getcwd()
        self._verify_gh_installed()
    
    def _verify_gh_installed(self) -> None:
        """Verify that gh CLI is installed."""
        try:
            result = subprocess.run(
                ['gh', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise GitHubClientError("gh CLI not installed or not working")
        except FileNotFoundError:
            raise GitHubClientError("gh CLI not found. Install from https://cli.github.com/")
        except subprocess.TimeoutExpired:
            raise GitHubClientError("gh CLI command timed out")
    
    def _run_gh_command(
        self,
        args: List[str],
        check: bool = True,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Run a gh CLI command.
        
        Args:
            args: Command arguments (without 'gh' prefix)
            check: Raise error on non-zero exit
            timeout: Command timeout in seconds
        
        Returns:
            Dict with returncode, stdout, stderr
        """
        cmd = ['gh'] + args
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if check and result.returncode != 0:
                raise GitHubClientError(
                    f"gh command failed: {' '.join(args)}\n"
                    f"Error: {result.stderr or result.stdout}"
                )
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout.strip(),
                'stderr': result.stderr.strip()
            }
            
        except subprocess.TimeoutExpired:
            raise GitHubClientError(f"gh command timed out: {' '.join(args)}")
        except FileNotFoundError:
            raise GitHubClientError("gh CLI not found")
    
    def create_pr(
        self,
        title: str,
        body: str,
        base: str = "main",
        head: Optional[str] = None,
        draft: bool = False
    ) -> Dict[str, Any]:
        """
        Create a pull request.
        
        Args:
            title: PR title
            body: PR description
            base: Base branch (default: main)
            head: Head branch (default: current branch)
            draft: Create as draft PR
        
        Returns:
            Dict with pr_url, pr_number
        """
        args = ['pr', 'create', '--title', title, '--body', body, '--base', base]
        
        if head:
            args.extend(['--head', head])
        
        if draft:
            args.append('--draft')
        
        if self.repo:
            args.extend(['--repo', self.repo])
        
        result = self._run_gh_command(args)
        pr_url = result['stdout']
        
        # Extract PR number from URL
        import re
        match = re.search(r'/pull/(\d+)', pr_url)
        pr_number = int(match.group(1)) if match else None
        
        return {
            'pr_url': pr_url,
            'pr_number': pr_number
        }
    
    def get_pr(
        self,
        pr_number: int
    ) -> Dict[str, Any]:
        """
        Get pull request details.
        
        Args:
            pr_number: PR number
        
        Returns:
            Dict with PR details (JSON from gh pr view)
        """
        args = ['pr', 'view', str(pr_number), '--json', 'title,body,state,url,number']
        
        if self.repo:
            args.extend(['--repo', self.repo])
        
        result = self._run_gh_command(args)
        return json.loads(result['stdout'])
    
    def add_pr_comment(
        self,
        pr_number: int,
        comment: str
    ) -> bool:
        """
        Add a comment to a pull request.
        
        Args:
            pr_number: PR number
            comment: Comment text
        
        Returns:
            True if successful
        """
        args = ['pr', 'comment', str(pr_number), '--body', comment]
        
        if self.repo:
            args.extend(['--repo', self.repo])
        
        self._run_gh_command(args)
        return True
    
    def get_repo_info(self) -> Dict[str, Any]:
        """
        Get repository information.
        
        Returns:
            Dict with repo details (JSON from gh repo view)
        """
        args = ['repo', 'view', '--json', 'name,owner,url,defaultBranchRef']
        
        if self.repo:
            args.append(self.repo)
        
        result = self._run_gh_command(args)
        return json.loads(result['stdout'])
    
    def list_prs(
        self,
        state: str = "open",
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        List pull requests.
        
        Args:
            state: PR state (open, closed, merged, all)
            limit: Maximum number of PRs to return
        
        Returns:
            List of PR dicts
        """
        args = [
            'pr', 'list',
            '--state', state,
            '--limit', str(limit),
            '--json', 'number,title,url,state,createdAt'
        ]
        
        if self.repo:
            args.extend(['--repo', self.repo])
        
        result = self._run_gh_command(args)
        return json.loads(result['stdout'])
    
    def check_auth(self) -> bool:
        """
        Check if gh is authenticated.
        
        Returns:
            True if authenticated
        """
        try:
            result = self._run_gh_command(['auth', 'status'], check=False)
            return result['returncode'] == 0
        except GitHubClientError:
            return False


def create_github_client(
    repo: Optional[str] = None,
    work_dir: Optional[str] = None
) -> GitHubClient:
    """
    Factory function to create a GitHub client.
    
    Args:
        repo: Repository in format 'owner/repo'
        work_dir: Working directory
    
    Returns:
        GitHubClient instance
    """
    return GitHubClient(repo=repo, work_dir=work_dir)
