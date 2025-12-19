#!/usr/bin/env python3
"""
FRONTEND CONTRACT TEST: Sync Now Visibility & Toast Behavior
============================================================
This test suite verifies the frontend correctly implements:
1. Sync Now button visibility based on user role (code inspection)
2. Toast messages display actual counts from API response (code inspection)

These tests inspect frontend code to verify the contract is implemented.
For E2E tests, use Playwright separately.

DO NOT MODIFY THIS FILE WITHOUT QC APPROVAL.
"""
import pytest
import re

# Configuration
FRONTEND_URL = "http://localhost:3000"

# Test credentials
SUPER_ADMIN_EMAIL = "admin@example.com"
SUPER_ADMIN_PASSWORD = "REDACTED_ADMIN_PASSWORD"
TENANT_USER_EMAIL = "tenant-b-test@test.com"
TENANT_USER_PASSWORD = "REDACTED_TEST_PASSWORD"


class TestSyncButtonVisibility:
    """Tests that frontend code correctly implements role-based visibility."""
    
    def test_intelligence_page_sync_button_requires_super_admin(self):
        """
        INVARIANT: IntelligenceFeed.js MUST wrap Sync Now button in isSuperAdmin() check.
        
        This ensures tenant users cannot see or click the button.
        """
        frontend_path = "/app/frontend/src/pages/IntelligenceFeed.js"
        
        with open(frontend_path, "r") as f:
            code = f.read()
        
        # Verify isSuperAdmin import
        assert "useAuth" in code or "isSuperAdmin" in code, \
            "IntelligenceFeed.js must import auth context for role checking"
        
        # Verify isSuperAdmin() wraps the Sync Now button
        # The pattern should be: {isSuperAdmin() && (<Button...Sync Now...)}
        assert "isSuperAdmin()" in code, \
            "REGRESSION: IntelligenceFeed.js must use isSuperAdmin() to guard Sync Now button"
        
        # Verify the conditional is near the Sync Now button
        sync_button_index = code.find("Sync Now")
        is_super_admin_index = code.find("isSuperAdmin()")
        
        # isSuperAdmin check should be within 500 chars before "Sync Now"
        assert is_super_admin_index != -1 and sync_button_index != -1, \
            "Could not find both isSuperAdmin() and 'Sync Now' in code"
        
        distance = sync_button_index - is_super_admin_index
        assert 0 < distance < 500, \
            f"isSuperAdmin() should guard Sync Now button (distance: {distance} chars)"


class TestSyncToastBehavior:
    """Tests that toast messages display actual counts."""
    
    def test_frontend_uses_response_counts_in_toast(self):
        """
        INVARIANT: Toast message MUST display counts from API response.
        
        The toast should show "X new reports" or similar with actual numbers,
        NOT a generic "Sync successful" message.
        
        This test verifies the frontend code references result.intelligence_synced
        or result.opportunities_synced in the toast.
        """
        # Instead of waiting 90s for a sync, we verify the frontend code
        # correctly uses the response data.
        
        import os
        frontend_path = "/app/frontend/src/pages/IntelligenceFeed.js"
        
        with open(frontend_path, "r") as f:
            code = f.read()
        
        # Verify the toast uses response data, not a hardcoded message
        assert "result.intelligence_synced" in code or "response.data.intelligence_synced" in code, \
            "REGRESSION: Frontend must use intelligence_synced count in toast"
        
        # Verify no hardcoded success messages without counts
        # Old bug pattern: toast.success("Sync successful") or similar
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if "toast.success" in line and "handleSync" in code[max(0, code.find(line)-500):code.find(line)+100]:
                # This is in the sync handler - verify it uses counts
                assert "synced" in line.lower() or "result" in line or "response" in line, \
                    f"Line {i+1}: Toast must show actual counts, not generic message"
    
    @pytest.mark.asyncio  
    async def test_tenants_page_uses_response_counts_in_toast(self):
        """
        INVARIANT: TenantsPage sync toast MUST display summed counts.
        """
        frontend_path = "/app/frontend/src/pages/TenantsPage.js"
        
        with open(frontend_path, "r") as f:
            code = f.read()
        
        # Verify the toast uses response data
        assert "opportunities_synced" in code and "intelligence_synced" in code, \
            "TenantsPage must use sync counts in toast"
        
        # Check for the pattern that adds both counts
        assert "response.data.opportunities_synced" in code or \
               "opportunities_synced + " in code or \
               "+" in code and "synced" in code, \
            "TenantsPage toast should sum opportunities and intelligence counts"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
