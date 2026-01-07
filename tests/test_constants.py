#!/usr/bin/env python3
"""Tests for src/constants.py

Verifies that VERSION, AUTHOR, and ERROR_CODES exist and have expected types.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from constants import VERSION, AUTHOR, ERROR_CODES


class TestConstants:
    """Test suite for constants module."""
    
    def test_version_exists(self):
        """Test that VERSION constant exists."""
        assert VERSION is not None
    
    def test_version_is_string(self):
        """Test that VERSION is a string."""
        assert isinstance(VERSION, str)
    
    def test_version_format(self):
        """Test that VERSION follows semantic versioning pattern."""
        # Should match pattern like "3.0.0"
        parts = VERSION.split('.')
        assert len(parts) == 3, f"VERSION should have 3 parts, got {len(parts)}"
        for part in parts:
            assert part.isdigit(), f"VERSION part '{part}' should be numeric"
    
    def test_author_exists(self):
        """Test that AUTHOR constant exists."""
        assert AUTHOR is not None
    
    def test_author_is_string(self):
        """Test that AUTHOR is a string."""
        assert isinstance(AUTHOR, str)
    
    def test_author_not_empty(self):
        """Test that AUTHOR is not an empty string."""
        assert len(AUTHOR) > 0
    
    def test_error_codes_exists(self):
        """Test that ERROR_CODES constant exists."""
        assert ERROR_CODES is not None
    
    def test_error_codes_is_dict(self):
        """Test that ERROR_CODES is a dictionary."""
        assert isinstance(ERROR_CODES, dict)
    
    def test_error_codes_not_empty(self):
        """Test that ERROR_CODES contains at least one entry."""
        assert len(ERROR_CODES) > 0
    
    def test_error_codes_keys_format(self):
        """Test that ERROR_CODES keys follow E### pattern."""
        for key in ERROR_CODES.keys():
            assert isinstance(key, str), f"Error code key '{key}' should be string"
            assert key.startswith('E'), f"Error code '{key}' should start with 'E'"
            assert key[1:].isdigit(), f"Error code '{key}' should be E followed by digits"
    
    def test_error_codes_values_are_strings(self):
        """Test that ERROR_CODES values are strings."""
        for code, message in ERROR_CODES.items():
            assert isinstance(message, str), f"Error message for '{code}' should be string"
            assert len(message) > 0, f"Error message for '{code}' should not be empty"
    
    def test_specific_error_codes(self):
        """Test that expected error codes are present."""
        expected_codes = ['E001', 'E002', 'E003', 'E004']
        for code in expected_codes:
            assert code in ERROR_CODES, f"Expected error code '{code}' not found"
