#!/usr/bin/env python3
"""
Unit tests for Sync Contract Validator
"""
import pytest
from .sync_contract_validator import (
    SyncContractValidator,
    validate_sync_contract,
    validate_sync_contract_strict,
    ValidationResult,
)


class TestSyncContractValidator:
    """Test suite for sync contract validation."""
    
    @pytest.fixture
    def valid_success_response(self):
        return {
            "tenant_id": "8aa521eb-56ad-4727-8f09-c01fc7921c21",
            "tenant_name": "Test Tenant",
            "opportunities_synced": 10,
            "intelligence_synced": 5,
            "status": "success",
            "sync_timestamp": "2025-01-01T12:00:00+00:00",
            "errors": []
        }
    
    @pytest.fixture
    def valid_partial_response(self):
        return {
            "tenant_id": "8aa521eb-56ad-4727-8f09-c01fc7921c21",
            "tenant_name": "Test Tenant",
            "opportunities_synced": 10,
            "intelligence_synced": 0,
            "status": "partial",
            "sync_timestamp": "2025-01-01T12:00:00+00:00",
            "errors": ["HigherGov API rate limited"]
        }
    
    # =========================================================================
    # Valid contract tests
    # =========================================================================
    
    def test_valid_success_response(self, valid_success_response):
        """Valid success response should pass."""
        result = validate_sync_contract(valid_success_response)
        assert result.valid, f"Should be valid: {result.errors}"
        assert len(result.errors) == 0
    
    def test_valid_partial_response(self, valid_partial_response):
        """Valid partial response with errors should pass."""
        result = validate_sync_contract(valid_partial_response)
        assert result.valid, f"Should be valid: {result.errors}"
    
    # =========================================================================
    # Regression detection tests
    # =========================================================================
    
    def test_detects_old_async_message(self):
        """MUST detect old 'triggered successfully' regression pattern."""
        old_response = {
            "status": "success",
            "message": "Sync triggered successfully"
        }
        result = validate_sync_contract(old_response)
        assert not result.valid
        assert any("REGRESSION" in e for e in result.errors)
    
    def test_detects_triggered_in_message_case_insensitive(self):
        """Regression detection must be case-insensitive."""
        old_response = {
            "status": "success",
            "message": "SYNC TRIGGERED Successfully"
        }
        result = validate_sync_contract(old_response)
        assert not result.valid
        assert any("REGRESSION" in e for e in result.errors)
    
    # =========================================================================
    # Missing field tests
    # =========================================================================
    
    def test_missing_tenant_id(self, valid_success_response):
        del valid_success_response['tenant_id']
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
        assert any("MISSING_FIELDS" in e for e in result.errors)
    
    def test_missing_status(self, valid_success_response):
        del valid_success_response['status']
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
    
    def test_missing_sync_timestamp(self, valid_success_response):
        del valid_success_response['sync_timestamp']
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
    
    def test_missing_errors_list(self, valid_success_response):
        del valid_success_response['errors']
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
    
    def test_missing_multiple_fields(self):
        """Empty response should fail with missing fields."""
        result = validate_sync_contract({})
        assert not result.valid
        assert any("MISSING_FIELDS" in e for e in result.errors)
    
    # =========================================================================
    # Type validation tests
    # =========================================================================
    
    def test_invalid_type_opportunities_synced(self, valid_success_response):
        valid_success_response['opportunities_synced'] = "10"  # string not int
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
        assert any("TYPE_ERROR" in e for e in result.errors)
    
    def test_invalid_type_errors_not_list(self, valid_success_response):
        valid_success_response['errors'] = "some error"  # string not list
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
        assert any("TYPE_ERROR" in e for e in result.errors)
    
    def test_invalid_type_tenant_id_not_string(self, valid_success_response):
        valid_success_response['tenant_id'] = 12345
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
    
    # =========================================================================
    # UUID validation tests
    # =========================================================================
    
    def test_invalid_uuid_format(self, valid_success_response):
        valid_success_response['tenant_id'] = "not-a-uuid"
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
        assert any("INVALID_UUID" in e for e in result.errors)
    
    def test_invalid_uuid_short(self, valid_success_response):
        valid_success_response['tenant_id'] = "8aa521eb-56ad"
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
    
    def test_empty_uuid(self, valid_success_response):
        valid_success_response['tenant_id'] = ""
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
    
    # =========================================================================
    # Status enum validation tests
    # =========================================================================
    
    def test_invalid_status_value(self, valid_success_response):
        valid_success_response['status'] = "completed"
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
        assert any("INVALID_STATUS" in e for e in result.errors)
    
    def test_status_case_sensitive(self, valid_success_response):
        valid_success_response['status'] = "SUCCESS"  # must be lowercase
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
    
    # =========================================================================
    # Conditional validation tests (CRITICAL)
    # =========================================================================
    
    def test_success_with_errors_fails(self, valid_success_response):
        """status=success with non-empty errors MUST fail."""
        valid_success_response['errors'] = ["Some error"]
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
        assert any("CONTRACT_VIOLATION" in e for e in result.errors)
    
    def test_partial_with_empty_errors_fails(self, valid_partial_response):
        """status=partial with empty errors MUST fail."""
        valid_partial_response['errors'] = []
        result = validate_sync_contract(valid_partial_response)
        assert not result.valid
        assert any("CONTRACT_VIOLATION" in e for e in result.errors)
    
    # =========================================================================
    # Timestamp validation tests
    # =========================================================================
    
    def test_invalid_timestamp_format(self, valid_success_response):
        valid_success_response['sync_timestamp'] = "not-a-timestamp"
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
        assert any("UNPARSEABLE_TIMESTAMP" in e for e in result.errors)
    
    def test_valid_timestamp_with_z_suffix(self, valid_success_response):
        valid_success_response['sync_timestamp'] = "2025-01-01T12:00:00Z"
        result = validate_sync_contract(valid_success_response)
        assert result.valid
    
    def test_valid_timestamp_with_offset(self, valid_success_response):
        valid_success_response['sync_timestamp'] = "2025-01-01T12:00:00-05:00"
        result = validate_sync_contract(valid_success_response)
        assert result.valid
    
    # =========================================================================
    # Negative count tests
    # =========================================================================
    
    def test_negative_opportunities_synced(self, valid_success_response):
        valid_success_response['opportunities_synced'] = -1
        result = validate_sync_contract(valid_success_response)
        assert not result.valid
        assert any("NEGATIVE_COUNT" in e for e in result.errors)
    
    def test_negative_intelligence_synced(self, valid_success_response):
        valid_success_response['intelligence_synced'] = -5
        result = validate_sync_contract(valid_success_response)
        assert not result.valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
