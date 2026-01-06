"""Tests for src/validators.py"""
import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from validators import (
    ValidationError,
    validate_task_id,
    validate_project_id,
    validate_status
)


class TestValidateTaskId:
    """Tests for validate_task_id function."""
    
    def test_valid_uuid(self):
        """Test that valid UUID is accepted and returned."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_task_id(valid_uuid)
        assert result == valid_uuid
    
    def test_valid_uuid_with_whitespace(self):
        """Test that UUID with surrounding whitespace is stripped."""
        uuid_with_spaces = "  550e8400-e29b-41d4-a716-446655440000  "
        result = validate_task_id(uuid_with_spaces)
        assert result == "550e8400-e29b-41d4-a716-446655440000"
    
    def test_empty_string_raises_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="task_id is required"):
            validate_task_id("")
    
    def test_none_raises_error(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError, match="task_id is required"):
            validate_task_id(None)
    
    def test_non_string_raises_error(self):
        """Test that non-string input raises ValidationError."""
        with pytest.raises(ValidationError, match="task_id must be string, got int"):
            validate_task_id(123)
    
    def test_invalid_uuid_format_raises_error(self):
        """Test that invalid UUID format raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid task_id format: must be valid UUID"):
            validate_task_id("invalid-uuid")
    
    def test_partial_uuid_raises_error(self):
        """Test that partial UUID raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid task_id format: must be valid UUID"):
            validate_task_id("550e8400-e29b")
    
    def test_uppercase_uuid(self):
        """Test that uppercase UUID is accepted."""
        uppercase_uuid = "550E8400-E29B-41D4-A716-446655440000"
        result = validate_task_id(uppercase_uuid)
        assert result == uppercase_uuid


class TestValidateProjectId:
    """Tests for validate_project_id function."""
    
    def test_valid_uuid(self):
        """Test that valid UUID is accepted and returned."""
        valid_uuid = "660e8400-e29b-41d4-a716-446655440000"
        result = validate_project_id(valid_uuid)
        assert result == valid_uuid
    
    def test_valid_uuid_with_whitespace(self):
        """Test that UUID with surrounding whitespace is stripped."""
        uuid_with_spaces = "  660e8400-e29b-41d4-a716-446655440000  "
        result = validate_project_id(uuid_with_spaces)
        assert result == "660e8400-e29b-41d4-a716-446655440000"
    
    def test_empty_string_raises_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="project_id is required"):
            validate_project_id("")
    
    def test_none_raises_error(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError, match="project_id is required"):
            validate_project_id(None)
    
    def test_non_string_raises_error(self):
        """Test that non-string input raises ValidationError."""
        with pytest.raises(ValidationError, match="project_id must be string, got int"):
            validate_project_id(456)
    
    def test_invalid_uuid_format_raises_error(self):
        """Test that invalid UUID format raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid project_id format: must be valid UUID"):
            validate_project_id("not-a-uuid")
    
    def test_uuid_like_but_invalid_raises_error(self):
        """Test that UUID-like but invalid string raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid project_id format: must be valid UUID"):
            validate_project_id("550e8400-e29b-41d4-a716-44665544000g")  # 'g' at end is invalid


class TestValidateStatus:
    """Tests for validate_status function."""
    
    def test_valid_status_pending(self):
        """Test that 'pending' status is accepted."""
        result = validate_status("pending")
        assert result == "pending"
    
    def test_valid_status_queued(self):
        """Test that 'queued' status is accepted."""
        result = validate_status("queued")
        assert result == "queued"
    
    def test_valid_status_running(self):
        """Test that 'running' status is accepted."""
        result = validate_status("running")
        assert result == "running"
    
    def test_valid_status_complete(self):
        """Test that 'complete' status is accepted."""
        result = validate_status("complete")
        assert result == "complete"
    
    def test_valid_status_failed(self):
        """Test that 'failed' status is accepted."""
        result = validate_status("failed")
        assert result == "failed"
    
    def test_valid_status_halted(self):
        """Test that 'halted' status is accepted."""
        result = validate_status("halted")
        assert result == "halted"
    
    def test_status_case_insensitive(self):
        """Test that status is case-insensitive and normalized to lowercase."""
        result = validate_status("PENDING")
        assert result == "pending"
        
        result = validate_status("RuNnInG")
        assert result == "running"
    
    def test_status_with_whitespace(self):
        """Test that status with surrounding whitespace is stripped."""
        result = validate_status("  pending  ")
        assert result == "pending"
    
    def test_empty_string_raises_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="status is required"):
            validate_status("")
    
    def test_none_raises_error(self):
        """Test that None raises ValidationError."""
        with pytest.raises(ValidationError, match="status is required"):
            validate_status(None)
    
    def test_non_string_raises_error(self):
        """Test that non-string input raises ValidationError."""
        with pytest.raises(ValidationError, match="status must be string, got int"):
            validate_status(789)
    
    def test_invalid_status_raises_error(self):
        """Test that invalid status value raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid status 'invalid'"):
            validate_status("invalid")
    
    def test_custom_allowed_statuses(self):
        """Test that custom allowed_statuses parameter works."""
        result = validate_status("active", allowed_statuses=["active", "inactive"])
        assert result == "active"
        
        result = validate_status("inactive", allowed_statuses=["active", "inactive"])
        assert result == "inactive"
    
    def test_custom_allowed_statuses_rejects_invalid(self):
        """Test that custom allowed_statuses rejects values not in list."""
        with pytest.raises(ValidationError, match="Invalid status 'pending'"):
            validate_status("pending", allowed_statuses=["active", "inactive"])
    
    def test_custom_allowed_statuses_case_insensitive(self):
        """Test that custom allowed_statuses are case-insensitive."""
        result = validate_status("ACTIVE", allowed_statuses=["active", "inactive"])
        assert result == "active"
        
        # Test mixed case in allowed_statuses
        result = validate_status("active", allowed_statuses=["ACTIVE", "InAcTiVe"])
        assert result == "active"


class TestValidationError:
    """Tests for ValidationError exception."""
    
    def test_validation_error_is_exception(self):
        """Test that ValidationError is an Exception subclass."""
        assert issubclass(ValidationError, Exception)
    
    def test_validation_error_can_be_raised(self):
        """Test that ValidationError can be raised with a message."""
        with pytest.raises(ValidationError, match="Test error message"):
            raise ValidationError("Test error message")
    
    def test_validation_error_can_be_caught(self):
        """Test that ValidationError can be caught and message retrieved."""
        try:
            raise ValidationError("Specific error")
        except ValidationError as e:
            assert str(e) == "Specific error"
