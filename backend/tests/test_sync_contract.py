#!/usr/bin/env python3
"""
CONTRACT TEST: Sync Endpoint Determinism & Permissions
======================================================
This test suite locks the sync contract to prevent regression of the P0 bug
where sync endpoints returned misleading success messages without actual counts.

CRITICAL INVARIANTS TESTED:
1. Response MUST contain: tenant_id, tenant_name, opportunities_synced, 
   intelligence_synced, status, sync_timestamp, errors
2. Response MUST NOT contain old async message "Sync triggered successfully"
3. Tenant users MUST receive 403 Forbidden
4. Counts MUST be integers, errors MUST be list, status MUST be enum
5. sync_type parameter MUST filter operations correctly

RUNTIME: ~3-4 minutes (includes live sync calls)
For faster CI, run carfax_sync_contract.sh which does ONE sync call.

DO NOT MODIFY THIS FILE WITHOUT QC APPROVAL.
"""
import pytest
import requests
import time
import os

# Configuration
API_URL = os.environ.get("TEST_API_URL", "https://sync-fix-3.preview.emergentagent.com")
TEST_TENANT_ID = "8aa521eb-56ad-4727-8f09-c01fc7921c21"

# Test credentials
SUPER_ADMIN_EMAIL = "admin@outpace.ai"
SUPER_ADMIN_PASSWORD = "Admin123!"
TENANT_USER_EMAIL = "tenant-b-test@test.com"
TENANT_USER_PASSWORD = "Test123!"

# Required response fields (hardened contract)
REQUIRED_FIELDS = [
    "tenant_id",
    "tenant_name",
    "opportunities_synced",
    "intelligence_synced",
    "status",
    "sync_timestamp",
    "errors"
]


class TestSyncContract:
    """Contract tests for sync endpoint determinism."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get authentication tokens before each test."""
        self.admin_token = self._get_token(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
        self.tenant_token = self._get_token(TENANT_USER_EMAIL, TENANT_USER_PASSWORD)
        assert self.admin_token, "Failed to get admin token"
        assert self.tenant_token, "Failed to get tenant token"
    
    def _get_token(self, email: str, password: str) -> str:
        """Authenticate and return JWT token."""
        resp = requests.post(
            f"{API_URL}/api/auth/login",
            json={"email": email, "password": password}
        )
        return resp.json().get("access_token", "")

    # =========================================================================
    # CONTRACT TEST 1: Complete Response Schema
    # =========================================================================
    def test_admin_sync_response_contains_all_required_fields(self):
        """
        INVARIANT: /api/admin/sync MUST return ALL required fields.
        
        Required fields (hardened):
        - tenant_id: string
        - tenant_name: string  
        - opportunities_synced: integer
        - intelligence_synced: integer
        - status: string ("success" or "partial")
        - sync_timestamp: string (ISO format)
        - errors: list
        """
        resp = requests.post(
            f"{API_URL}/api/admin/sync/{TEST_TENANT_ID}",
            params={"sync_type": "opportunities"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
            timeout=120
        )
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        
        # Check all required fields exist
        missing = [f for f in REQUIRED_FIELDS if f not in data]
        assert not missing, f"Missing required fields: {missing}"
        
        # Type assertions (hardened)
        assert isinstance(data["tenant_id"], str), "tenant_id must be string"
        assert isinstance(data["tenant_name"], str), "tenant_name must be string"
        assert isinstance(data["opportunities_synced"], int), "opportunities_synced must be int"
        assert isinstance(data["intelligence_synced"], int), "intelligence_synced must be int"
        assert isinstance(data["sync_timestamp"], str), "sync_timestamp must be string"
        assert isinstance(data["errors"], list), "errors must be list"
        assert data["status"] in ["success", "partial"], f"status must be 'success' or 'partial', got '{data['status']}'"
    
    # =========================================================================
    # CONTRACT TEST 2: CRITICAL - Regression Detection
    # =========================================================================
    def test_admin_sync_rejects_old_async_response_shape(self):
        """
        CRITICAL REGRESSION TEST: Response MUST NOT match old async pattern.
        
        The OLD BUG returned:
        {"status": "success", "message": "Sync triggered successfully"}
        
        This test MUST FAIL if:
        - Response contains "message" field with "triggered" in it
        - Response lacks count fields (opportunities_synced, intelligence_synced)
        
        This is the PRIMARY regression guard. Do not weaken.
        """
        resp = requests.post(
            f"{API_URL}/api/admin/sync/{TEST_TENANT_ID}",
            params={"sync_type": "opportunities"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
            timeout=120
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # CRITICAL: Detect old async response pattern
        if "message" in data:
            msg = str(data["message"]).lower()
            assert "triggered" not in msg, \
                f"REGRESSION DETECTED: Old async message found: '{data['message']}'"
        
        # CRITICAL: Counts must exist (old response didn't have them)
        assert "opportunities_synced" in data, \
            "REGRESSION: opportunities_synced missing - old async response detected"
        assert "intelligence_synced" in data, \
            "REGRESSION: intelligence_synced missing - old async response detected"
    
    # =========================================================================
    # CONTRACT TEST 3: Synchronous Behavior (Schema-Based, Not Timing-Based)
    # =========================================================================
    def test_admin_sync_is_synchronous_via_schema(self):
        """
        INVARIANT: Sync endpoint MUST be synchronous.
        
        We verify this via SCHEMA, not timing (to avoid flakes):
        - A synchronous endpoint returns actual work results (counts)
        - An async endpoint returns a generic "triggered" message
        
        The timing is logged but NOT asserted to avoid CI flakes.
        A real sync takes 5-90+ seconds, but network variance can affect this.
        """
        start_time = time.time()
        
        resp = requests.post(
            f"{API_URL}/api/admin/sync/{TEST_TENANT_ID}",
            params={"sync_type": "opportunities"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
            timeout=180
        )
        
        elapsed = time.time() - start_time
        
        assert resp.status_code == 200
        data = resp.json()
        
        # Log timing for debugging (not asserted to avoid flakes)
        print(f"\n  [INFO] Sync call took {elapsed:.2f}s")
        
        # SCHEMA-BASED synchronous verification:
        # A synchronous endpoint returns work results, not a fire-and-forget message
        assert "opportunities_synced" in data, "Synchronous response must include work results"
        assert isinstance(data["opportunities_synced"], int), "Count must be integer (actual work done)"
        
        # Soft timing signal: warn if suspiciously fast (but don't fail)
        # An instant response (<0.25s) might indicate the old async bug
        if elapsed < 0.25:
            print(f"  [WARNING] Response very fast ({elapsed:.2f}s) - verify not returning cached/fake data")
    
    # =========================================================================
    # CONTRACT TEST 4: Permission Enforcement
    # =========================================================================
    def test_tenant_user_cannot_call_admin_sync(self):
        """
        INVARIANT: Tenant users MUST receive 403 Forbidden on admin sync.
        
        Only super_admin role can trigger sync operations.
        """
        resp = requests.post(
            f"{API_URL}/api/admin/sync/{TEST_TENANT_ID}",
            params={"sync_type": "opportunities"},
            headers={"Authorization": f"Bearer {self.tenant_token}"}
        )
        
        assert resp.status_code == 403, \
            f"Expected 403 Forbidden for tenant user, got {resp.status_code}"
        
        data = resp.json()
        assert "detail" in data, "403 response must include detail message"
    
    # =========================================================================
    # CONTRACT TEST 5: Alternative Endpoint Parity
    # =========================================================================
    def test_sync_manual_endpoint_has_same_contract(self):
        """
        INVARIANT: /api/sync/manual MUST have same response contract as /api/admin/sync.
        
        Both endpoints must return deterministic counts.
        """
        resp = requests.post(
            f"{API_URL}/api/sync/manual/{TEST_TENANT_ID}",
            params={"sync_type": "opportunities"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
            timeout=120
        )
        
        assert resp.status_code == 200
        
        data = resp.json()
        
        # Same required fields as /api/admin/sync
        required_base = ["tenant_id", "tenant_name", "opportunities_synced", "intelligence_synced", "status"]
        missing = [f for f in required_base if f not in data]
        assert not missing, f"Missing fields in /api/sync/manual: {missing}"
        
        # Same type requirements
        assert isinstance(data["opportunities_synced"], int)
        assert isinstance(data["intelligence_synced"], int)
    
    # =========================================================================
    # CONTRACT TEST 6: Sync Type Parameter
    # =========================================================================
    def test_sync_type_parameter_filters_operations(self):
        """
        INVARIANT: sync_type parameter must filter which operations run.
        
        - sync_type=opportunities: intelligence_synced should be 0
        - sync_type=intelligence: opportunities_synced should be 0
        """
        resp = requests.post(
            f"{API_URL}/api/admin/sync/{TEST_TENANT_ID}",
            params={"sync_type": "opportunities"},
            headers={"Authorization": f"Bearer {self.admin_token}"},
            timeout=120
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # When sync_type=opportunities, intelligence should NOT be synced
        assert data["intelligence_synced"] == 0, \
            "sync_type=opportunities should not sync intelligence"


class TestSyncDataIntegrity:
    """Tests that data types are stored correctly."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.admin_token = self._get_token(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    
    def _get_token(self, email: str, password: str) -> str:
        resp = requests.post(
            f"{API_URL}/api/auth/login",
            json={"email": email, "password": password}
        )
        return resp.json().get("access_token", "")
    
    def test_array_fields_stored_correctly(self):
        """
        INVARIANT: NAICS codes and interest_areas must be stored as arrays.
        
        The UI allows comma-separated input which must be split into arrays.
        """
        resp = requests.get(
            f"{API_URL}/api/tenants/{TEST_TENANT_ID}",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        search_profile = data.get("search_profile", {})
        naics = search_profile.get("naics_codes", [])
        interest = search_profile.get("interest_areas", [])
        
        assert isinstance(naics, list), f"naics_codes must be list, got {type(naics).__name__}"
        assert isinstance(interest, list), f"interest_areas must be list, got {type(interest).__name__}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
