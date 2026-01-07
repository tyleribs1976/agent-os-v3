#!/usr/bin/env python3
"""Tests for src/utils.py utility functions."""

import json
import pytest
from datetime import datetime
from src.utils import format_timestamp, truncate_string, safe_json_loads


class TestFormatTimestamp:
    """Test cases for format_timestamp function."""
    
    def test_format_timestamp_basic(self):
        """Test basic ISO 8601 formatting."""
        dt = datetime(2026, 1, 6, 12, 34, 56)
        result = format_timestamp(dt)
        assert result == '2026-01-06T12:34:56'
    
    def test_format_timestamp_with_microseconds(self):
        """Test formatting with microseconds."""
        dt = datetime(2026, 1, 6, 12, 34, 56, 789012)
        result = format_timestamp(dt)
        assert result == '2026-01-06T12:34:56.789012'
    
    def test_format_timestamp_midnight(self):
        """Test formatting at midnight."""
        dt = datetime(2026, 1, 1, 0, 0, 0)
        result = format_timestamp(dt)
        assert result == '2026-01-01T00:00:00'
    
    def test_format_timestamp_end_of_day(self):
        """Test formatting at end of day."""
        dt = datetime(2026, 12, 31, 23, 59, 59)
        result = format_timestamp(dt)
        assert result == '2026-12-31T23:59:59'


class TestTruncateString:
    """Test cases for truncate_string function."""
    
    def test_truncate_string_exceeds_max_len(self):
        """Test truncation when string exceeds max length."""
        result = truncate_string('Hello World', 8)
        assert result == 'Hello...'
    
    def test_truncate_string_under_max_len(self):
        """Test no truncation when string is under max length."""
        result = truncate_string('Short', 10)
        assert result == 'Short'
    
    def test_truncate_string_exact_max_len(self):
        """Test no truncation when string equals max length."""
        result = truncate_string('Exactly10!', 10)
        assert result == 'Exactly10!'
    
    def test_truncate_string_empty(self):
        """Test truncation of empty string."""
        result = truncate_string('', 10)
        assert result == ''
    
    def test_truncate_string_default_max_len(self):
        """Test truncation with default max_len of 100."""
        long_string = 'a' * 150
        result = truncate_string(long_string)
        assert result == ('a' * 100) + '...'
        assert len(result) == 103  # 100 chars + '...'
    
    def test_truncate_string_single_char(self):
        """Test truncation to single character."""
        result = truncate_string('Hello', 1)
        assert result == 'H...'


class TestSafeJsonLoads:
    """Test cases for safe_json_loads function."""
    
    def test_safe_json_loads_valid_json_string(self):
        """Test parsing valid JSON string."""
        result = safe_json_loads('{"key": "value"}')
        assert result == {'key': 'value'}
    
    def test_safe_json_loads_invalid_json(self):
        """Test handling of invalid JSON string."""
        result = safe_json_loads('invalid json')
        assert result == {}
    
    def test_safe_json_loads_none(self):
        """Test handling of None input."""
        result = safe_json_loads(None)
        assert result == {}
    
    def test_safe_json_loads_already_dict(self):
        """Test handling of already-parsed dict (psycopg2 JSONB case)."""
        input_dict = {'already': 'parsed'}
        result = safe_json_loads(input_dict)
        assert result == {'already': 'parsed'}
        assert result is input_dict  # Should return same object
    
    def test_safe_json_loads_already_list(self):
        """Test handling of already-parsed list (psycopg2 JSONB case)."""
        input_list = ['item1', 'item2']
        result = safe_json_loads(input_list)
        assert result == ['item1', 'item2']
        assert result is input_list  # Should return same object
    
    def test_safe_json_loads_empty_string(self):
        """Test handling of empty string."""
        result = safe_json_loads('')
        assert result == {}
    
    def test_safe_json_loads_complex_json(self):
        """Test parsing complex nested JSON."""
        json_str = '{"outer": {"inner": [1, 2, 3]}, "flag": true}'
        result = safe_json_loads(json_str)
        assert result == {'outer': {'inner': [1, 2, 3]}, 'flag': True}
    
    def test_safe_json_loads_json_array(self):
        """Test parsing JSON array string."""
        result = safe_json_loads('[1, 2, 3]')
        assert result == [1, 2, 3]
    
    def test_safe_json_loads_malformed_json(self):
        """Test handling of malformed JSON with missing quotes."""
        result = safe_json_loads('{key: value}')
        assert result == {}
    
    def test_safe_json_loads_integer(self):
        """Test handling of non-string, non-dict, non-list types."""
        result = safe_json_loads(123)
        assert result == {}
