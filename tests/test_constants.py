#!/usr/bin/env python3
"""
Tests for src/constants.py

Verifies that core constants are properly defined and have correct values.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from constants import (
    VERSION,
    AUTHOR,
    APP_NAME,
    BUILD_NUMBER,
    RELEASE_DATE,
    PROJECT_NAME,
    DESCRIPTION,
    GITHUB_REPO,
    HOMEPAGE,
    GIT_BRANCH_PREFIX,
    GITHUB_INTEGRATION,
    LOG_LEVEL,
    TESTED,
    PR_AUTO_MERGE,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_COMPLETE,
    STATUS_FAILED,
    STATUS_HALTED,
    PHASE_DRAFTING,
    PHASE_VERIFICATION,
    PHASE_EXECUTION,
    DRAFTER_MODEL,
    MIN_DRAFTER_CONFIDENCE,
    CONFIDENCE_THRESHOLD,
    MIN_VERIFIER_CONFIDENCE,
    VERIFIER_MODEL,
    DRAFT_TIMEOUT,
    DEFAULT_TIMEOUT,
    VERIFY_TIMEOUT,
    EXECUTE_TIMEOUT,
    MAX_RETRIES,
    ERROR_CODES
)


class TestVersionConstants:
    """Test version-related constants."""
    
    def test_version_exists(self):
        """VERSION constant should exist and be a string."""
        assert VERSION is not None
        assert isinstance(VERSION, str)
    
    def test_version_format(self):
        """VERSION should follow semantic versioning (X.Y.Z)."""
        parts = VERSION.split('.')
        assert len(parts) == 3, f"Expected X.Y.Z format, got {VERSION}"
        for part in parts:
            assert part.isdigit(), f"Expected numeric version parts, got {VERSION}"
    
    def test_version_value(self):
        """VERSION should be 3.0.0 for Agent-OS v3."""
        assert VERSION == "3.0.0"
    
    def test_build_number_exists(self):
        """BUILD_NUMBER should exist and be an integer."""
        assert BUILD_NUMBER is not None
        assert isinstance(BUILD_NUMBER, int)
        assert BUILD_NUMBER > 0
    
    def test_release_date_exists(self):
        """RELEASE_DATE should exist and be a string."""
        assert RELEASE_DATE is not None
        assert isinstance(RELEASE_DATE, str)
        # Should be YYYY-MM-DD format
        assert len(RELEASE_DATE) == 10
        assert RELEASE_DATE.count('-') == 2


class TestIdentityConstants:
    """Test identity-related constants."""
    
    def test_app_name_exists(self):
        """APP_NAME constant should exist and be a string."""
        assert APP_NAME is not None
        assert isinstance(APP_NAME, str)
    
    def test_app_name_value(self):
        """APP_NAME should be 'AgentOS'."""
        assert APP_NAME == "AgentOS"
    
    def test_app_name_not_empty(self):
        """APP_NAME should not be empty."""
        assert len(APP_NAME) > 0
    
    def test_author_exists(self):
        """AUTHOR constant should exist and be a string."""
        assert AUTHOR is not None
        assert isinstance(AUTHOR, str)
    
    def test_author_value(self):
        """AUTHOR should be 'Ty Fisher'."""
        assert AUTHOR == "Ty Fisher"
    
    def test_author_not_empty(self):
        """AUTHOR should not be empty."""
        assert len(AUTHOR) > 0
    
    def test_project_name_exists(self):
        """PROJECT_NAME should exist and be a string."""
        assert PROJECT_NAME is not None
        assert isinstance(PROJECT_NAME, str)
        assert PROJECT_NAME == "Agent-OS v3"
    
    def test_description_exists(self):
        """DESCRIPTION should exist and be a string."""
        assert DESCRIPTION is not None
        assert isinstance(DESCRIPTION, str)
        assert len(DESCRIPTION) > 0


class TestGitHubConstants:
    """Test GitHub-related constants."""
    
    def test_github_repo_exists(self):
        """GITHUB_REPO should exist and be a string."""
        assert GITHUB_REPO is not None
        assert isinstance(GITHUB_REPO, str)
        assert len(GITHUB_REPO) > 0
    
    def test_homepage_exists(self):
        """HOMEPAGE should exist and be a valid URL string."""
        assert HOMEPAGE is not None
        assert isinstance(HOMEPAGE, str)
        assert HOMEPAGE.startswith('https://')
        assert 'github.com' in HOMEPAGE
    
    def test_git_branch_prefix_exists(self):
        """GIT_BRANCH_PREFIX should exist and be 'aos'."""
        assert GIT_BRANCH_PREFIX is not None
        assert isinstance(GIT_BRANCH_PREFIX, str)
        assert GIT_BRANCH_PREFIX == "aos"
    
    def test_github_integration_exists(self):
        """GITHUB_INTEGRATION should exist and be a string."""
        assert GITHUB_INTEGRATION is not None
        assert isinstance(GITHUB_INTEGRATION, str)
        assert GITHUB_INTEGRATION in ['enabled', 'disabled']


class TestConfigConstants:
    """Test configuration constants."""
    
    def test_log_level_exists(self):
        """LOG_LEVEL should exist and be a valid level."""
        assert LOG_LEVEL is not None
        assert isinstance(LOG_LEVEL, str)
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        assert LOG_LEVEL in valid_levels
    
    def test_tested_flag_exists(self):
        """TESTED flag should exist and be boolean."""
        assert TESTED is not None
        assert isinstance(TESTED, bool)
    
    def test_pr_auto_merge_exists(self):
        """PR_AUTO_MERGE should exist and be boolean."""
        assert PR_AUTO_MERGE is not None
        assert isinstance(PR_AUTO_MERGE, bool)


class TestStatusConstants:
    """Test task status constants."""
    
    def test_status_constants_exist(self):
        """All status constants should exist and be strings."""
        statuses = [
            STATUS_QUEUED,
            STATUS_RUNNING,
            STATUS_COMPLETE,
            STATUS_FAILED,
            STATUS_HALTED
        ]
        for status in statuses:
            assert status is not None
            assert isinstance(status, str)
            assert len(status) > 0
    
    def test_status_values(self):
        """Status constants should have expected values."""
        assert STATUS_QUEUED == "queued"
        assert STATUS_RUNNING == "running"
        assert STATUS_COMPLETE == "complete"
        assert STATUS_FAILED == "failed"
        assert STATUS_HALTED == "halted"


class TestPhaseConstants:
    """Test phase constants."""
    
    def test_phase_constants_exist(self):
        """All phase constants should exist and be strings."""
        phases = [
            PHASE_DRAFTING,
            PHASE_VERIFICATION,
            PHASE_EXECUTION
        ]
        for phase in phases:
            assert phase is not None
            assert isinstance(phase, str)
            assert len(phase) > 0
    
    def test_phase_values(self):
        """Phase constants should have expected values."""
        assert PHASE_DRAFTING == "drafting"
        assert PHASE_VERIFICATION == "verification"
        assert PHASE_EXECUTION == "execution"


class TestModelConstants:
    """Test model configuration constants."""
    
    def test_drafter_model_exists(self):
        """DRAFTER_MODEL should exist and be a string."""
        assert DRAFTER_MODEL is not None
        assert isinstance(DRAFTER_MODEL, str)
        assert len(DRAFTER_MODEL) > 0
    
    def test_verifier_model_exists(self):
        """VERIFIER_MODEL should exist and be a string."""
        assert VERIFIER_MODEL is not None
        assert isinstance(VERIFIER_MODEL, str)
        assert len(VERIFIER_MODEL) > 0


class TestConfidenceConstants:
    """Test confidence threshold constants."""
    
    def test_confidence_thresholds_exist(self):
        """All confidence thresholds should exist and be floats."""
        thresholds = [
            MIN_DRAFTER_CONFIDENCE,
            CONFIDENCE_THRESHOLD,
            MIN_VERIFIER_CONFIDENCE
        ]
        for threshold in thresholds:
            assert threshold is not None
            assert isinstance(threshold, (int, float))
    
    def test_confidence_thresholds_range(self):
        """Confidence thresholds should be between 0 and 1."""
        thresholds = [
            MIN_DRAFTER_CONFIDENCE,
            CONFIDENCE_THRESHOLD,
            MIN_VERIFIER_CONFIDENCE
        ]
        for threshold in thresholds:
            assert 0.0 <= threshold <= 1.0
    
    def test_confidence_threshold_values(self):
        """Confidence thresholds should have expected values."""
        assert MIN_DRAFTER_CONFIDENCE == 0.85
        assert CONFIDENCE_THRESHOLD == 0.85
        assert MIN_VERIFIER_CONFIDENCE == 0.90


class TestTimeoutConstants:
    """Test timeout configuration constants."""
    
    def test_timeout_constants_exist(self):
        """All timeout constants should exist and be integers."""
        timeouts = [
            DRAFT_TIMEOUT,
            DEFAULT_TIMEOUT,
            VERIFY_TIMEOUT,
            EXECUTE_TIMEOUT
        ]
        for timeout in timeouts:
            assert timeout is not None
            assert isinstance(timeout, int)
    
    def test_timeout_values_positive(self):
        """Timeout values should be positive."""
        timeouts = [
            DRAFT_TIMEOUT,
            DEFAULT_TIMEOUT,
            VERIFY_TIMEOUT,
            EXECUTE_TIMEOUT
        ]
        for timeout in timeouts:
            assert timeout > 0
    
    def test_timeout_values(self):
        """Timeout constants should have expected values."""
        assert DRAFT_TIMEOUT == 600
        assert DEFAULT_TIMEOUT == 300
        assert VERIFY_TIMEOUT == 300
        assert EXECUTE_TIMEOUT == 300


class TestRetryConstants:
    """Test retry configuration constants."""
    
    def test_max_retries_exists(self):
        """MAX_RETRIES should exist and be an integer."""
        assert MAX_RETRIES is not None
        assert isinstance(MAX_RETRIES, int)
    
    def test_max_retries_positive(self):
        """MAX_RETRIES should be positive."""
        assert MAX_RETRIES > 0
    
    def test_max_retries_value(self):
        """MAX_RETRIES should be 3."""
        assert MAX_RETRIES == 3


class TestErrorCodeConstants:
    """Test error code constants."""
    
    def test_error_codes_exist(self):
        """ERROR_CODES should exist and be a dictionary."""
        assert ERROR_CODES is not None
        assert isinstance(ERROR_CODES, dict)
    
    def test_error_codes_not_empty(self):
        """ERROR_CODES should not be empty."""
        assert len(ERROR_CODES) > 0
    
    def test_error_codes_format(self):
        """ERROR_CODES should have string keys and values."""
        for key, value in ERROR_CODES.items():
            assert isinstance(key, str)
            assert isinstance(value, str)
            assert key.startswith('E')
    
    def test_error_codes_values(self):
        """ERROR_CODES should contain expected error codes."""
        assert 'E001' in ERROR_CODES
        assert ERROR_CODES['E001'] == "TASK_NOT_FOUND"
        assert 'E002' in ERROR_CODES
        assert ERROR_CODES['E002'] == "VALIDATION_FAILED"
        assert 'E003' in ERROR_CODES
        assert ERROR_CODES['E003'] == "EXECUTION_FAILED"
        assert 'E004' in ERROR_CODES
        assert ERROR_CODES['E004'] == "CHECKPOINT_ERROR"
