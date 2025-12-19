#!/usr/bin/env python3
"""
DELIVERABLE B (Part 2): Marker Tamper Tests
===========================================
Adversarial tests for marker file validation.

Tests tamper scenarios:
- Missing marker
- Malformed JSON
- Stale marker (>10 minutes old)
- Missing fields
- Wrong types
- Non-UUID tenant_id
- contract_validated=false
- Invalid status
- partial with empty errors (via sync contract)
- success with errors (via sync contract)
"""
import pytest
import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .marker_validator import MarkerValidator, validate_marker, MarkerValidationResult


class TestMarkerTamperScenarios:
    """Adversarial tests for marker validation."""
    
    @pytest.fixture
    def temp_marker_dir(self):
        """Create a temporary directory for marker files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def valid_marker_data(self):
        """Valid marker data for modification in tests."""
        return {
            "tenant_id": "8aa521eb-56ad-4727-8f09-c01fc7921c21",
            "status": "success",
            "sync_timestamp": datetime.now(timezone.utc).isoformat(),
            "opportunities_synced": 10,
            "intelligence_synced": 5,
            "contract_validated": True,
            "marker_created_utc": datetime.now(timezone.utc).isoformat()
        }
    
    def _write_marker(self, tmpdir: str, data: dict) -> str:
        """Write marker file and return path."""
        path = os.path.join(tmpdir, "test_marker.json")
        with open(path, 'w') as f:
            json.dump(data, f)
        return path
    
    # =========================================================================
    # Missing marker test
    # =========================================================================
    
    def test_missing_marker_fails(self, temp_marker_dir):
        """Missing marker file MUST fail."""
        missing_path = os.path.join(temp_marker_dir, "nonexistent.json")
        validator = MarkerValidator(missing_path)
        result = validator.validate()
        
        assert not result.valid
        assert any("MARKER_NOT_FOUND" in e for e in result.errors)
    
    # =========================================================================
    # Malformed JSON test
    # =========================================================================
    
    def test_malformed_json_fails(self, temp_marker_dir):
        """Malformed JSON MUST fail."""
        path = os.path.join(temp_marker_dir, "malformed.json")
        with open(path, 'w') as f:
            f.write("{invalid json: syntax")
        
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
        assert any("JSON_PARSE_ERROR" in e for e in result.errors)
    
    def test_empty_file_fails(self, temp_marker_dir):
        """Empty file MUST fail."""
        path = os.path.join(temp_marker_dir, "empty.json")
        with open(path, 'w') as f:
            f.write("")
        
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
    
    # =========================================================================
    # Stale marker test (CRITICAL)
    # =========================================================================
    
    def test_stale_marker_fails(self, temp_marker_dir, valid_marker_data):
        """Marker older than 10 minutes MUST fail."""
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        valid_marker_data['marker_created_utc'] = stale_time.isoformat()
        
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path, max_age_minutes=10)
        result = validator.validate()
        
        assert not result.valid
        assert any("STALE_MARKER" in e for e in result.errors)
    
    def test_marker_exactly_at_limit_passes(self, temp_marker_dir, valid_marker_data):
        """Marker at exactly 10 minutes should still pass."""
        at_limit = datetime.now(timezone.utc) - timedelta(minutes=9, seconds=59)
        valid_marker_data['marker_created_utc'] = at_limit.isoformat()
        
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path, max_age_minutes=10)
        result = validator.validate()
        
        assert result.valid, f"Should pass at limit: {result.errors}"
    
    def test_future_timestamp_fails(self, temp_marker_dir, valid_marker_data):
        """Marker with future timestamp (>1 min) MUST fail."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        valid_marker_data['marker_created_utc'] = future_time.isoformat()
        
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
        assert any("FUTURE_TIMESTAMP" in e for e in result.errors)
    
    # =========================================================================
    # Missing fields tests
    # =========================================================================
    
    def test_missing_tenant_id_fails(self, temp_marker_dir, valid_marker_data):
        del valid_marker_data['tenant_id']
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
        assert any("MISSING_FIELDS" in e for e in result.errors)
    
    def test_missing_contract_validated_fails(self, temp_marker_dir, valid_marker_data):
        del valid_marker_data['contract_validated']
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
    
    def test_missing_marker_created_utc_fails(self, temp_marker_dir, valid_marker_data):
        del valid_marker_data['marker_created_utc']
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
    
    # =========================================================================
    # Wrong type tests
    # =========================================================================
    
    def test_opportunities_synced_wrong_type_fails(self, temp_marker_dir, valid_marker_data):
        valid_marker_data['opportunities_synced'] = "10"  # string not int
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
        assert any("INVALID_TYPE" in e for e in result.errors)
    
    def test_intelligence_synced_wrong_type_fails(self, temp_marker_dir, valid_marker_data):
        valid_marker_data['intelligence_synced'] = 5.5  # float not int
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
    
    # =========================================================================
    # Non-UUID tenant_id test
    # =========================================================================
    
    def test_non_uuid_tenant_id_fails(self, temp_marker_dir, valid_marker_data):
        valid_marker_data['tenant_id'] = "not-a-valid-uuid"
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
        assert any("INVALID_TENANT_ID" in e for e in result.errors)
    
    def test_empty_tenant_id_fails(self, temp_marker_dir, valid_marker_data):
        valid_marker_data['tenant_id'] = ""
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
    
    # =========================================================================
    # contract_validated tests
    # =========================================================================
    
    def test_contract_validated_false_fails(self, temp_marker_dir, valid_marker_data):
        """contract_validated=false MUST fail."""
        valid_marker_data['contract_validated'] = False
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
        assert any("CONTRACT_NOT_VALIDATED" in e for e in result.errors)
    
    def test_contract_validated_string_true_fails(self, temp_marker_dir, valid_marker_data):
        """contract_validated='true' (string) MUST fail - must be boolean."""
        valid_marker_data['contract_validated'] = "true"
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
    
    def test_contract_validated_1_fails(self, temp_marker_dir, valid_marker_data):
        """contract_validated=1 MUST fail - must be boolean True."""
        valid_marker_data['contract_validated'] = 1
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
    
    # =========================================================================
    # Invalid status tests
    # =========================================================================
    
    def test_invalid_status_fails(self, temp_marker_dir, valid_marker_data):
        valid_marker_data['status'] = "completed"
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
        assert any("INVALID_STATUS" in e for e in result.errors)
    
    def test_status_uppercase_fails(self, temp_marker_dir, valid_marker_data):
        valid_marker_data['status'] = "SUCCESS"  # must be lowercase
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert not result.valid
    
    # =========================================================================
    # Valid marker passes test
    # =========================================================================
    
    def test_valid_marker_passes(self, temp_marker_dir, valid_marker_data):
        """A completely valid marker should pass."""
        path = self._write_marker(temp_marker_dir, valid_marker_data)
        validator = MarkerValidator(path)
        result = validator.validate()
        
        assert result.valid, f"Should pass: {result.errors}"
        assert result.marker_data is not None
        assert result.age_seconds is not None
        assert result.age_seconds < 60  # Should be fresh


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
