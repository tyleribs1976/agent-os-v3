"""Tests for src/utils.py

Following pytest conventions:
- Test functions named test_*
- Clear test names describing behavior
- Arrange-Act-Assert pattern
- Edge cases and error conditions
"""

import pytest
from datetime import datetime
from src.utils import format_timestamp, truncate_string, safe_json_loads


class TestFormatTimestamp:
    """Tests for format_timestamp function."""
    
    def test_format_timestamp_basic(self):
        """Test basic datetime formatting to ISO 8601."""
        dt = datetime(2026, 1, 6, 12, 34, 56)
        result = format_timestamp(dt)
        assert result == '2026-01-06T12:34:56'
    
    def test_format_timestamp_with_microseconds(self):
        """Test datetime with microseconds."""
        dt = datetime(2026, 1, 6, 12, 34, 56, 789012)
        result = format_timestamp(dt)
        assert result == '2026-01-06T12:34:56.789012'
    
    def test_format_timestamp_midnight(self):
        """Test datetime at midnight."""
        dt = datetime(2026, 1, 1, 0, 0, 0)
        result = format_timestamp(dt)
        assert result == '2026-01-01T00:00:00'
    
    def test_format_timestamp_end_of_day(self):
        """Test datetime at end of day."""
        dt = datetime(2026, 12, 31, 23, 59, 59)
        result = format_timestamp(dt)
        assert result == '2026-12-31T23:59:59'


class TestTruncateString:
    """Tests for truncate_string function."""
    
    def test_truncate_string_no_truncation_needed(self):
        """Test string shorter than max length."""
        result = truncate_string('Short', 10)
        assert result == 'Short'
    
    def test_truncate_string_exact_length(self):
        """Test string exactly at max length."""
        result = truncate_string('Exactly10!', 10)
        assert result == 'Exactly10!'
    
    def test_truncate_string_with_truncation(self):
        """Test string exceeding max length gets truncated with ellipsis."""
        result = truncate_string('Hello World', 8)
        assert result == 'Hello Wo...'
        assert len(result) == 11  # 8 chars + '...'
    
    def test_truncate_string_default_max_len(self):
        """Test default max_len of 100."""
        long_string = 'x' * 150
        result = truncate_string(long_string)
        assert result == ('x' * 100) + '...'
        assert len(result) == 103
    
    def test_truncate_string_empty(self):
        """Test empty string."""
        result = truncate_string('', 10)
        assert result == ''
    
    def test_truncate_string_single_char(self):
        """Test single character string."""
        result = truncate_string('X', 1)
        assert result == 'X'
    
    def test_truncate_string_max_len_zero(self):
        """Test max_len of 0 truncates to ellipsis only."""
        result = truncate_string('Hello', 0)
        assert result == '...'


class TestSafeJsonLoads:
    """Tests for safe_json_loads function."""
    
    def test_safe_json_loads_valid_json_string(self):
        """Test parsing valid JSON string."""
        result = safe_json_loads('{"key": "value"}')
        assert result == {'key': 'value'}
    
    def test_safe_json_loads_invalid_json_returns_empty_dict(self):
        """Test invalid JSON returns empty dict instead of raising."""
        result = safe_json_loads('invalid json')
        assert result == {}
    
    def test_safe_json_loads_none_returns_empty_dict(self):
        """Test None input returns empty dict."""
        result = safe_json_loads(None)
        assert result == {}
    
    def test_safe_json_loads_already_dict(self):
        """Test already-parsed dict passes through (psycopg2 JSONB case)."""
        input_dict = {'already': 'parsed'}
        result = safe_json_loads(input_dict)
        assert result == input_dict
        assert result is input_dict  # Same object
    
    def test_safe_json_loads_already_list(self):
        """Test already-parsed list passes through (psycopg2 JSONB case)."""
        input_list = [1, 2, 3]
        result = safe_json_loads(input_list)
        assert result == input_list
        assert result is input_list  # Same object
    
    def test_safe_json_loads_empty_string(self):
        """Test empty string returns empty dict."""
        result = safe_json_loads('')
        assert result == {}
    
    def test_safe_json_loads_json_array(self):
        """Test parsing JSON array string."""
        result = safe_json_loads('[1, 2, 3]')
        assert result == [1, 2, 3]
    
    def test_safe_json_loads_nested_json(self):
        """Test parsing nested JSON structure."""
        json_str = '{"outer": {"inner": "value"}, "array": [1, 2]}'
        result = safe_json_loads(json_str)
        assert result == {'outer': {'inner': 'value'}, 'array': [1, 2]}
    
    def test_safe_json_loads_malformed_brackets(self):
        """Test malformed JSON with unmatched brackets."""
        result = safe_json_loads('{"key": "value"')
        assert result == {}
    
    def test_safe_json_loads_type_error(self):
        """Test non-string, non-dict, non-list type returns empty dict."""
        result = safe_json_loads(12345)
        assert result == {}
