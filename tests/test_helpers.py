"""Tests for src/helpers.py"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone
import json

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from helpers import (
    get_timestamp,
    format_duration,
    parse_json
)


class TestGetTimestamp:
    """Tests for get_timestamp function."""
    
    def test_utc_timestamp_has_timezone(self):
        """Test that UTC timestamp has timezone info."""
        ts = get_timestamp(utc=True)
        assert isinstance(ts, datetime)
        assert ts.tzinfo is not None
        assert ts.tzinfo == timezone.utc
    
    def test_utc_timestamp_default(self):
        """Test that utc=True is the default behavior."""
        ts = get_timestamp()
        assert isinstance(ts, datetime)
        assert ts.tzinfo == timezone.utc
    
    def test_local_timestamp_returns_datetime(self):
        """Test that local timestamp returns datetime object."""
        ts = get_timestamp(utc=False)
        assert isinstance(ts, datetime)
    
    def test_timestamps_are_recent(self):
        """Test that timestamps are within reasonable range of now."""
        before = datetime.now(timezone.utc)
        ts = get_timestamp()
        after = datetime.now(timezone.utc)
        
        # Should be between before and after (within a few milliseconds)
        assert before <= ts <= after
    
    def test_multiple_calls_increase(self):
        """Test that successive calls return increasing timestamps."""
        ts1 = get_timestamp()
        ts2 = get_timestamp()
        # Second timestamp should be >= first (could be equal if very fast)
        assert ts2 >= ts1


class TestFormatDuration:
    """Tests for format_duration function."""
    
    def test_zero_seconds(self):
        """Test formatting of zero duration."""
        assert format_duration(0) == "0s"
    
    def test_negative_seconds_returns_zero(self):
        """Test that negative duration returns 0s."""
        assert format_duration(-5) == "0s"
        assert format_duration(-100) == "0s"
    
    def test_subsecond_float(self):
        """Test formatting of subsecond durations with decimal places."""
        assert format_duration(0.234) == "0.23s"
        assert format_duration(0.5) == "0.50s"
        assert format_duration(0.999) == "1.00s"  # Rounds to 2 decimal places
    
    def test_seconds_only(self):
        """Test formatting of durations under 1 minute."""
        assert format_duration(1) == "1s"
        assert format_duration(45) == "45s"
        assert format_duration(59) == "59s"
    
    def test_minutes_and_seconds(self):
        """Test formatting of durations with minutes."""
        assert format_duration(60) == "1m"
        assert format_duration(61) == "1m 1s"
        assert format_duration(125) == "2m 5s"
        assert format_duration(3599) == "59m 59s"
    
    def test_hours_minutes_seconds(self):
        """Test formatting of durations with hours."""
        assert format_duration(3600) == "1h"
        assert format_duration(3601) == "1h 1s"
        assert format_duration(3660) == "1h 1m"
        assert format_duration(3665) == "1h 1m 5s"
        assert format_duration(7384) == "2h 3m 4s"
    
    def test_exact_minutes_no_seconds(self):
        """Test that exact minutes don't show 0 seconds."""
        assert format_duration(120) == "2m"
        assert format_duration(300) == "5m"
    
    def test_exact_hours_no_minutes_or_seconds(self):
        """Test that exact hours don't show 0 minutes or seconds."""
        assert format_duration(7200) == "2h"
        assert format_duration(10800) == "3h"
    
    def test_float_input_truncates_to_int(self):
        """Test that float >= 1 second is truncated to int."""
        assert format_duration(45.9) == "45s"
        assert format_duration(125.7) == "2m 5s"
    
    def test_large_duration(self):
        """Test formatting of large durations."""
        # 25 hours, 30 minutes, 45 seconds
        assert format_duration(91845) == "25h 30m 45s"


class TestParseJson:
    """Tests for parse_json function."""
    
    def test_parse_valid_json_string(self):
        """Test parsing valid JSON string."""
        result = parse_json('{"key": "value"}')
        assert result == {"key": "value"}
    
    def test_parse_json_array_string(self):
        """Test parsing JSON array string."""
        result = parse_json('[1, 2, 3]')
        assert result == [1, 2, 3]
    
    def test_already_parsed_dict(self):
        """Test that already-parsed dict is returned as-is."""
        input_dict = {"key": "value"}
        result = parse_json(input_dict)
        assert result == input_dict
        assert result is input_dict  # Same object
    
    def test_already_parsed_list(self):
        """Test that already-parsed list is returned as-is."""
        input_list = [1, 2, 3]
        result = parse_json(input_list)
        assert result == input_list
        assert result is input_list  # Same object
    
    def test_none_returns_default(self):
        """Test that None returns default value."""
        result = parse_json(None, default={})
        assert result == {}
        
        result = parse_json(None, default=[])
        assert result == []
        
        result = parse_json(None, default="fallback")
        assert result == "fallback"
    
    def test_none_with_no_default(self):
        """Test that None with no default returns None."""
        result = parse_json(None)
        assert result is None
    
    def test_invalid_json_returns_default(self):
        """Test that invalid JSON string returns default."""
        result = parse_json('invalid json', default={})
        assert result == {}
        
        result = parse_json('{incomplete', default=[])
        assert result == []
    
    def test_invalid_json_with_no_default(self):
        """Test that invalid JSON with no default returns None."""
        result = parse_json('not valid json')
        assert result is None
    
    def test_empty_string_returns_default(self):
        """Test that empty string returns default."""
        result = parse_json('', default={'empty': True})
        assert result == {'empty': True}
    
    def test_nested_json_object(self):
        """Test parsing nested JSON structures."""
        json_str = '{"outer": {"inner": [1, 2, 3]}, "flag": true}'
        result = parse_json(json_str)
        assert result == {"outer": {"inner": [1, 2, 3]}, "flag": True}
    
    def test_unknown_type_returns_default(self):
        """Test that unknown types return default value."""
        result = parse_json(12345, default={})
        assert result == {}
        
        result = parse_json(True, default=[])
        assert result == []
    
    def test_psycopg2_jsonb_behavior(self):
        """Test simulating psycopg2 JSONB already-parsed behavior."""
        # Simulate psycopg2 returning JSONB as dict
        db_result = {"field": "value", "count": 42}
        result = parse_json(db_result)
        assert result == db_result
        
        # Simulate JSONB array
        db_array = ["item1", "item2", "item3"]
        result = parse_json(db_array)
        assert result == db_array
    
    def test_json_with_special_characters(self):
        """Test parsing JSON with special characters."""
        json_str = '{"message": "Line 1\\nLine 2", "quote": "He said \\"hello\\""}'
        result = parse_json(json_str)
        assert "message" in result
        assert "quote" in result
