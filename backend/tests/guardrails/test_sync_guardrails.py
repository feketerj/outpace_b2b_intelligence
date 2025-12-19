#!/usr/bin/env python3
"""
Tests for SYNC-02 Guardrails
"""
import pytest
import os
import tempfile
from datetime import datetime, timezone

from .sync_guardrails import (
    SyncGuard,
    SyncGuardViolation,
    sync_guard,
    assert_no_sync_calls,
    assert_single_sync_call,
)


class TestSyncGuardrails:
    """Test the sync call guardrails."""
    
    @pytest.fixture(autouse=True)
    def reset_guard(self):
        """Reset guard before each test."""
        sync_guard.reset()
        yield
        sync_guard.reset()
    
    def test_sync_not_allowed_by_default(self):
        """Sync calls should fail outside allowed context."""
        with pytest.raises(SyncGuardViolation) as exc:
            sync_guard.register_sync_call()
        assert "outside allowed context" in str(exc.value)
    
    def test_sync_allowed_in_context(self):
        """Sync calls should succeed in allowed context."""
        with sync_guard.allow_sync():
            sync_guard.register_sync_call()
        
        assert sync_guard.sync_count == 1
    
    def test_only_one_sync_allowed(self):
        """Second sync call should fail."""
        with sync_guard.allow_sync():
            sync_guard.register_sync_call()
        
        with pytest.raises(SyncGuardViolation) as exc:
            with sync_guard.allow_sync():
                sync_guard.register_sync_call()
        
        assert "already executed" in str(exc.value)
    
    def test_protected_decorator(self):
        """Protected functions cannot make sync calls."""
        @sync_guard.protected
        def protected_test():
            sync_guard.register_sync_call()
        
        with pytest.raises(SyncGuardViolation):
            protected_test()
    
    def test_sync_remaining_count(self):
        """Remaining count should decrement."""
        assert sync_guard.sync_remaining == 1
        
        with sync_guard.allow_sync():
            sync_guard.register_sync_call()
        
        assert sync_guard.sync_remaining == 0
    
    def test_assert_no_sync_calls_passes(self):
        """assert_no_sync_calls should pass when no calls made."""
        assert_no_sync_calls()  # Should not raise
    
    def test_assert_no_sync_calls_fails(self):
        """assert_no_sync_calls should fail after sync call."""
        with sync_guard.allow_sync():
            sync_guard.register_sync_call()
        
        with pytest.raises(SyncGuardViolation):
            assert_no_sync_calls()
    
    def test_assert_single_sync_call_passes(self):
        """assert_single_sync_call should pass after one call."""
        with sync_guard.allow_sync():
            sync_guard.register_sync_call()
        
        assert_single_sync_call()  # Should not raise
    
    def test_assert_single_sync_call_fails_zero(self):
        """assert_single_sync_call should fail with zero calls."""
        with pytest.raises(SyncGuardViolation):
            assert_single_sync_call()


class TestMarkerAtomicWrite:
    """Test atomic marker file writing."""
    
    @pytest.fixture
    def temp_marker_path(self):
        """Create temporary marker path."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as f:
            path = f.name
        os.unlink(path)  # Delete so we start fresh
        yield path
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    
    @pytest.fixture
    def valid_sync_response(self):
        return {
            "tenant_id": "8aa521eb-56ad-4727-8f09-c01fc7921c21",
            "tenant_name": "Test Tenant",
            "opportunities_synced": 10,
            "intelligence_synced": 0,
            "status": "success",
            "sync_timestamp": datetime.now(timezone.utc).isoformat(),
            "errors": []
        }
    
    @pytest.fixture(autouse=True)
    def reset_guard(self):
        sync_guard.reset()
        yield
        sync_guard.reset()
    
    def test_marker_written_on_valid_contract(self, temp_marker_path, valid_sync_response):
        """Marker should be written for valid contract."""
        result = sync_guard.write_marker_atomic(valid_sync_response, temp_marker_path)
        
        assert result is True
        assert os.path.exists(temp_marker_path)
    
    def test_marker_not_written_on_invalid_contract(self, temp_marker_path):
        """Marker should NOT be written for invalid contract."""
        invalid_response = {
            "status": "success",
            "message": "Sync triggered successfully"  # Old regression pattern
        }
        
        result = sync_guard.write_marker_atomic(invalid_response, temp_marker_path)
        
        assert result is False
        assert not os.path.exists(temp_marker_path)
    
    def test_marker_not_written_on_missing_fields(self, temp_marker_path):
        """Marker should NOT be written when fields missing."""
        incomplete_response = {
            "status": "success",
            "tenant_id": "8aa521eb-56ad-4727-8f09-c01fc7921c21"
            # Missing most required fields
        }
        
        result = sync_guard.write_marker_atomic(incomplete_response, temp_marker_path)
        
        assert result is False
        assert not os.path.exists(temp_marker_path)
    
    def test_delete_marker(self, temp_marker_path, valid_sync_response):
        """delete_marker should remove file."""
        sync_guard.write_marker_atomic(valid_sync_response, temp_marker_path)
        assert os.path.exists(temp_marker_path)
        
        sync_guard.delete_marker(temp_marker_path)
        assert not os.path.exists(temp_marker_path)
    
    def test_delete_nonexistent_marker(self, temp_marker_path):
        """delete_marker should not raise on missing file."""
        sync_guard.delete_marker(temp_marker_path)  # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
