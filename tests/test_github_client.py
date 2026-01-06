"""Tests for src/github_client.py"""
import pytest
import sys
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from github_client import GitHubClient, GitHubClientError, create_github_client


class TestGitHubClientInit:
    """Test GitHubClient initialization."""
    
    @patch('github_client.subprocess.run')
    def test_init_with_repo_and_work_dir(self, mock_run):
        """Test initialization with repo and work_dir parameters."""
        mock_run.return_value = Mock(returncode=0, stdout='gh version 2.0.0', stderr='')
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        
        assert client.repo == 'owner/repo'
        assert client.work_dir == '/tmp/test'
        mock_run.assert_called_once()
    
    @patch('github_client.subprocess.run')
    @patch('github_client.os.getcwd')
    def test_init_without_work_dir(self, mock_getcwd, mock_run):
        """Test initialization defaults to current directory."""
        mock_run.return_value = Mock(returncode=0, stdout='gh version 2.0.0', stderr='')
        mock_getcwd.return_value = '/current/dir'
        
        client = GitHubClient()
        
        assert client.work_dir == '/current/dir'
    
    @patch('github_client.subprocess.run')
    def test_init_raises_on_gh_not_installed(self, mock_run):
        """Test initialization fails when gh CLI is not installed."""
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(GitHubClientError, match="gh CLI not found"):
            GitHubClient()
    
    @patch('github_client.subprocess.run')
    def test_init_raises_on_gh_not_working(self, mock_run):
        """Test initialization fails when gh CLI returns non-zero."""
        mock_run.return_value = Mock(returncode=1, stdout='', stderr='error')
        
        with pytest.raises(GitHubClientError, match="gh CLI not installed or not working"):
            GitHubClient()
    
    @patch('github_client.subprocess.run')
    def test_init_raises_on_timeout(self, mock_run):
        """Test initialization fails when gh CLI command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired('gh', 5)
        
        with pytest.raises(GitHubClientError, match="gh CLI command timed out"):
            GitHubClient()


class TestRunGhCommand:
    """Test _run_gh_command internal method."""
    
    @patch('github_client.subprocess.run')
    def test_run_gh_command_success(self, mock_run):
        """Test successful gh command execution."""
        mock_run.return_value = Mock(returncode=0, stdout='success output', stderr='')
        
        client = GitHubClient(work_dir='/tmp/test')
        result = client._run_gh_command(['pr', 'list'])
        
        assert result['returncode'] == 0
        assert result['stdout'] == 'success output'
        assert result['stderr'] == ''
    
    @patch('github_client.subprocess.run')
    def test_run_gh_command_with_check_raises(self, mock_run):
        """Test gh command with check=True raises on failure."""
        # First call for __init__ verification
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=1, stdout='', stderr='error message')
        ]
        
        client = GitHubClient(work_dir='/tmp/test')
        
        with pytest.raises(GitHubClientError, match="gh command failed"):
            client._run_gh_command(['pr', 'list'], check=True)
    
    @patch('github_client.subprocess.run')
    def test_run_gh_command_without_check_no_raise(self, mock_run):
        """Test gh command with check=False does not raise on failure."""
        # First call for __init__ verification
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=1, stdout='', stderr='error message')
        ]
        
        client = GitHubClient(work_dir='/tmp/test')
        result = client._run_gh_command(['pr', 'list'], check=False)
        
        assert result['returncode'] == 1
    
    @patch('github_client.subprocess.run')
    def test_run_gh_command_timeout(self, mock_run):
        """Test gh command times out."""
        # First call for __init__ verification
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            subprocess.TimeoutExpired('gh', 30)
        ]
        
        client = GitHubClient(work_dir='/tmp/test')
        
        with pytest.raises(GitHubClientError, match="gh command timed out"):
            client._run_gh_command(['pr', 'list'], timeout=30)


class TestCreatePr:
    """Test create_pr method."""
    
    @patch('github_client.subprocess.run')
    def test_create_pr_basic(self, mock_run):
        """Test basic PR creation."""
        # First call for __init__, second for create_pr
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout='https://github.com/owner/repo/pull/42', stderr='')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        result = client.create_pr(title='Test PR', body='Test body')
        
        assert result['pr_url'] == 'https://github.com/owner/repo/pull/42'
        assert result['pr_number'] == 42
    
    @patch('github_client.subprocess.run')
    def test_create_pr_with_draft(self, mock_run):
        """Test draft PR creation."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout='https://github.com/owner/repo/pull/43', stderr='')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        result = client.create_pr(title='Draft PR', body='Draft body', draft=True)
        
        assert result['pr_number'] == 43
        # Verify --draft was passed
        call_args = mock_run.call_args_list[1][0][0]
        assert '--draft' in call_args
    
    @patch('github_client.subprocess.run')
    def test_create_pr_with_custom_base(self, mock_run):
        """Test PR creation with custom base branch."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout='https://github.com/owner/repo/pull/44', stderr='')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        result = client.create_pr(title='Test PR', body='Test body', base='develop')
        
        assert result['pr_number'] == 44
        # Verify --base develop was passed
        call_args = mock_run.call_args_list[1][0][0]
        base_idx = call_args.index('--base')
        assert call_args[base_idx + 1] == 'develop'
    
    @patch('github_client.subprocess.run')
    def test_create_pr_failure(self, mock_run):
        """Test PR creation failure."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=1, stdout='', stderr='PR creation failed')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        
        with pytest.raises(GitHubClientError, match="gh command failed"):
            client.create_pr(title='Test PR', body='Test body')


class TestGetPr:
    """Test get_pr method."""
    
    @patch('github_client.subprocess.run')
    def test_get_pr_success(self, mock_run):
        """Test getting PR details."""
        pr_data = {
            'number': 42,
            'title': 'Test PR',
            'body': 'Test body',
            'state': 'OPEN',
            'url': 'https://github.com/owner/repo/pull/42'
        }
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout=json.dumps(pr_data), stderr='')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        result = client.get_pr(42)
        
        assert result['number'] == 42
        assert result['title'] == 'Test PR'
        assert result['state'] == 'OPEN'


class TestAddPrComment:
    """Test add_pr_comment method."""
    
    @patch('github_client.subprocess.run')
    def test_add_pr_comment_success(self, mock_run):
        """Test adding a comment to a PR."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout='Comment added', stderr='')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        result = client.add_pr_comment(42, 'Test comment')
        
        assert result is True
    
    @patch('github_client.subprocess.run')
    def test_add_pr_comment_failure(self, mock_run):
        """Test add_pr_comment raises on failure."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=1, stdout='', stderr='Comment failed')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        
        with pytest.raises(GitHubClientError):
            client.add_pr_comment(42, 'Test comment')


class TestGetRepoInfo:
    """Test get_repo_info method."""
    
    @patch('github_client.subprocess.run')
    def test_get_repo_info_success(self, mock_run):
        """Test getting repository information."""
        repo_data = {
            'name': 'repo',
            'owner': {'login': 'owner'},
            'url': 'https://github.com/owner/repo',
            'defaultBranchRef': {'name': 'main'}
        }
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout=json.dumps(repo_data), stderr='')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        result = client.get_repo_info()
        
        assert result['name'] == 'repo'
        assert result['owner']['login'] == 'owner'


class TestListPrs:
    """Test list_prs method."""
    
    @patch('github_client.subprocess.run')
    def test_list_prs_default(self, mock_run):
        """Test listing PRs with default parameters."""
        prs_data = [
            {'number': 1, 'title': 'PR 1', 'state': 'OPEN', 'url': 'url1', 'createdAt': '2024-01-01'},
            {'number': 2, 'title': 'PR 2', 'state': 'OPEN', 'url': 'url2', 'createdAt': '2024-01-02'}
        ]
        
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout=json.dumps(prs_data), stderr='')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        result = client.list_prs()
        
        assert len(result) == 2
        assert result[0]['number'] == 1
        assert result[1]['number'] == 2
    
    @patch('github_client.subprocess.run')
    def test_list_prs_with_state(self, mock_run):
        """Test listing PRs with specific state."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout='[]', stderr='')
        ]
        
        client = GitHubClient(repo='owner/repo', work_dir='/tmp/test')
        result = client.list_prs(state='closed', limit=10)
        
        # Verify correct arguments were passed
        call_args = mock_run.call_args_list[1][0][0]
        assert '--state' in call_args
        state_idx = call_args.index('--state')
        assert call_args[state_idx + 1] == 'closed'
        assert '--limit' in call_args
        limit_idx = call_args.index('--limit')
        assert call_args[limit_idx + 1] == '10'


class TestCheckAuth:
    """Test check_auth method."""
    
    @patch('github_client.subprocess.run')
    def test_check_auth_authenticated(self, mock_run):
        """Test check_auth returns True when authenticated."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=0, stdout='Logged in', stderr='')
        ]
        
        client = GitHubClient(work_dir='/tmp/test')
        result = client.check_auth()
        
        assert result is True
    
    @patch('github_client.subprocess.run')
    def test_check_auth_not_authenticated(self, mock_run):
        """Test check_auth returns False when not authenticated."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            Mock(returncode=1, stdout='', stderr='Not logged in')
        ]
        
        client = GitHubClient(work_dir='/tmp/test')
        result = client.check_auth()
        
        assert result is False
    
    @patch('github_client.subprocess.run')
    def test_check_auth_handles_error(self, mock_run):
        """Test check_auth returns False on errors."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout='gh version 2.0.0', stderr=''),
            FileNotFoundError()
        ]
        
        client = GitHubClient(work_dir='/tmp/test')
        result = client.check_auth()
        
        assert result is False


class TestFactoryFunction:
    """Test create_github_client factory function."""
    
    @patch('github_client.subprocess.run')
    def test_factory_creates_client(self, mock_run):
        """Test factory function creates GitHubClient instance."""
        mock_run.return_value = Mock(returncode=0, stdout='gh version 2.0.0', stderr='')
        
        client = create_github_client(repo='owner/repo', work_dir='/tmp/test')
        
        assert isinstance(client, GitHubClient)
        assert client.repo == 'owner/repo'
        assert client.work_dir == '/tmp/test'
