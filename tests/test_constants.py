"""Tests for src/constants.py"""
import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from constants import VERSION, AUTHOR, PROJECT_NAME


def test_version_exists():
    """Test that VERSION constant exists and is a string."""
    assert VERSION is not None
    assert isinstance(VERSION, str)
    assert len(VERSION) > 0


def test_author_exists():
    """Test that AUTHOR constant exists and is a string."""
    assert AUTHOR is not None
    assert isinstance(AUTHOR, str)
    assert len(AUTHOR) > 0


def test_project_name_exists():
    """Test that PROJECT_NAME constant exists and is a string."""
    assert PROJECT_NAME is not None
    assert isinstance(PROJECT_NAME, str)
    assert len(PROJECT_NAME) > 0


def test_version_format():
    """Test that VERSION follows semantic versioning pattern."""
    import re
    # Allow patterns like "3.0.0", "1.2.3-alpha", "2.0.0-beta.1"
    semver_pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9\.]+)?$'
    assert re.match(semver_pattern, VERSION), f"VERSION '{VERSION}' does not match semantic versioning pattern"
