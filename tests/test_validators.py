#!/usr/bin/env python3
"""
Agent-OS v3 Validator Tests

Tests for src/validators.py functions.
Following million-step methodology: explicit test cases, no magic.
"""

import pytest
from uuid import uuid4

from src.validators import (
    validate_task_id,
    validate_project_id,
    validate_status,
    ValidationError
)


class TestValidateTaskId:
    """Tests for validate_task_id function."""
    
    def test_valid_uuid(self):
        """Test that valid UUID strings are accepted."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_task_id(valid_uuid)
        assert result == valid_uuid
    
    def test_valid_uuid_with_whitespace(self):
        """Test that UUIDs with surrounding whitespace are stripped."""
        uuid_with_space = "  550e8400-e29b-41d4-a716-446655440000  "
        result = validate_task_id(uuid_with_space)
        assert result == "550e8400-e29b-41d4-a716-446655440000"
    
    def test_generated_uuid(self):
        """Test that dynamically generated UUIDs are accepted."""
        generated_uuid = str(uuid4())
        result = validate_task_id(generated_uuid)
        assert result == generated_uuid
    
    def test_empty_string(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_task_id("")
        assert "task_id is required" in str(exc_info.value)
    
    def test_none_value(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_task_id(None)
        assert "task_id is required" in str(exc_info.value)
    
    def test_invalid_uuid_format(self):
        """Test that invalid UUID format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_task_id("invalid-uuid")
        assert "must be valid UUID" in str(exc_info.value)
        assert "invalid-uuid" in str(exc_info.value)
    
    def test_non_string_type(self):
        """Test that non-string types raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_task_id(12345)
        assert "must be string" in str(exc_info.value)
        assert "int" in str(exc_info.value)
    
    def test_partial_uuid(self):
        """Test that partial UUIDs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            validate_task_id("550e8400-e29b")
        assert "must be valid UUID" in str(exc_info.value)


class TestValidateProjectId:
    """Tests for validate_project_id function."""
    
    def test_valid_uuid(self):
        """Test that valid UUID strings are accepted."""
        valid_uuid = "650e8400-e29b-41d4-a716-446655440001"
        result = validate_project_id(valid_uuid)
        assert result == valid_uuid
    
    def test_valid_uuid_with_whitespace(self):
        """Test that UUIDs with surrounding whitespace are stripped."""
        uuid_with_space = "\n650e8400-e29b-41d4-a716-446655440001\t"
        result = validate_project_id(uuid_with_space)
        assert result == "650e8400-e29b-41d4-a716-446655440001"
    
    def test_generated_uuid(self):
        """Test that dynamically generated UUIDs are accepted."""
        generated_uuid = str(uuid4())
        result = validate_project_id(generated_uuid)
        assert result == generated_uuid
    
    def test_empty_string(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_project_id("")
        assert "project_id is required" in str(exc_info.value)
    
    def test_none_value(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_project_id(None)
        assert "project_id is required" in str(exc_info.value)
    
    def test_invalid_uuid_format(self):
        """Test that invalid UUID format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_project_id("not-a-uuid")
        assert "must be valid UUID" in str(exc_info.value)
        assert "not-a-uuid" in str(exc_info.value)
    
    def test_non_string_type(self):
        """Test that non-string types raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_project_id(["list", "of", "strings"])
        assert "must be string" in str(exc_info.value)
        assert "list" in str(exc_info.value)


class TestValidateStatus:
    """Tests for validate_status function."""
    
    def test_valid_pending_status(self):
        """Test that 'pending' is accepted."""
        result = validate_status("pending")
        assert result == "pending"
    
    def test_valid_queued_status(self):
        """Test that 'queued' is accepted."""
        result = validate_status("queued")
        assert result == "queued"
    
    def test_valid_running_status(self):
        """Test that 'running' is accepted."""
        result = validate_status("running")
        assert result == "running"
    
    def test_valid_complete_status(self):
        """Test that 'complete' is accepted."""
        result = validate_status("complete")
        assert result == "complete"
    
    def test_valid_failed_status(self):
        """Test that 'failed' is accepted."""
        result = validate_status("failed")
        assert result == "failed"
    
    def test_valid_halted_status(self):
        """Test that 'halted' is accepted."""
        result = validate_status("halted")
        assert result == "halted"
    
    def test_case_insensitive(self):
        """Test that status validation is case-insensitive."""
        assert validate_status("PENDING") == "pending"
        assert validate_status("Running") == "running"
        assert validate_status("COMPLETE") == "complete"
    
    def test_whitespace_stripped(self):
        """Test that whitespace is stripped."""
        result = validate_status("  pending  ")
        assert result == "pending"
    
    def test_invalid_status(self):
        """Test that invalid status raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_status("invalid_status")
        assert "Invalid status" in str(exc_info.value)
        assert "invalid_status" in str(exc_info.value)
    
    def test_empty_string(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_status("")
        assert "status is required" in str(exc_info.value)
    
    def test_none_value(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_status(None)
        assert "status is required" in str(exc_info.value)
    
    def test_non_string_type(self):
        """Test that non-string types raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_status(123)
        assert "must be string" in str(exc_info.value)
        assert "int" in str(exc_info.value)
    
    def test_custom_allowed_statuses(self):
        """Test that custom allowed_statuses parameter works."""
        custom_statuses = ["active", "inactive", "archived"]
        
        # Valid custom status
        result = validate_status("active", allowed_statuses=custom_statuses)
        assert result == "active"
        
        # Invalid custom status
        with pytest.raises(ValidationError) as exc_info:
            validate_status("pending", allowed_statuses=custom_statuses)
        assert "Invalid status" in str(exc_info.value)
        assert "pending" in str(exc_info.value)
    
    def test_custom_statuses_case_insensitive(self):
        """Test that custom statuses are also case-insensitive."""
        custom_statuses = ["Active", "INACTIVE"]
        result = validate_status("active", allowed_statuses=custom_statuses)
        assert result == "active"
