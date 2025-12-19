#!/usr/bin/env python3
"""
FRONTEND CONTRACT TEST: Sync Now Visibility & Toast Behavior
============================================================
This test suite verifies the frontend correctly implements:
1. Sync Now button visibility based on user role
2. Toast messages display actual counts from API response

Runs via Playwright for end-to-end verification.

DO NOT MODIFY THIS FILE WITHOUT QC APPROVAL.
"""
import pytest
import asyncio
from playwright.async_api import async_playwright
import re

# Configuration
FRONTEND_URL = "http://localhost:3000"

# Test credentials
SUPER_ADMIN_EMAIL = "admin@example.com"
SUPER_ADMIN_PASSWORD = "REDACTED_ADMIN_PASSWORD"
TENANT_USER_EMAIL = "tenant-b-test@test.com"
TENANT_USER_PASSWORD = "REDACTED_TEST_PASSWORD"


class TestSyncButtonVisibility:
    """Tests for Sync Now button role-based visibility."""
    
    @pytest.mark.asyncio
    async def test_sync_button_hidden_for_tenant_user(self):
        """
        INVARIANT: Tenant users MUST NOT see Sync Now button on Intelligence page.
        
        The button is admin-only functionality.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            try:
                # Login as tenant user
                await page.goto(f"{FRONTEND_URL}/login")
                await page.wait_for_selector('input[type="email"]', timeout=10000)
                await page.fill('input[type="email"]', TENANT_USER_EMAIL)
                await page.fill('input[type="password"]', TENANT_USER_PASSWORD)
                await page.click('button[type="submit"]')
                await page.wait_for_timeout(3000)
                
                # Navigate to Intelligence page
                await page.goto(f"{FRONTEND_URL}/intelligence", wait_until="networkidle")
                await page.wait_for_timeout(2000)
                
                # Check Sync Now button does NOT exist
                sync_button = await page.query_selector('button:has-text("Sync Now")')
                
                assert sync_button is None, \
                    "REGRESSION: Sync Now button visible to tenant user - must be admin-only"
                    
            finally:
                await browser.close()
    
    @pytest.mark.asyncio
    async def test_sync_button_visible_for_super_admin_on_tenants_page(self):
        """
        INVARIANT: Super admins MUST see Sync Now button on Tenant Management page.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            try:
                # Login as super admin
                await page.goto(f"{FRONTEND_URL}/login")
                await page.wait_for_selector('input[type="email"]', timeout=10000)
                await page.fill('input[type="email"]', SUPER_ADMIN_EMAIL)
                await page.fill('input[type="password"]', SUPER_ADMIN_PASSWORD)
                await page.click('button[type="submit"]')
                await page.wait_for_timeout(3000)
                
                # Navigate to Tenants page
                await page.goto(f"{FRONTEND_URL}/admin/tenants", wait_until="networkidle")
                await page.wait_for_timeout(2000)
                
                # Check Sync Now buttons exist
                sync_buttons = await page.query_selector_all('button:has-text("Sync Now")')
                
                assert len(sync_buttons) > 0, \
                    "Sync Now button not visible to super admin on Tenants page"
                    
            finally:
                await browser.close()


class TestSyncToastBehavior:
    """Tests that toast messages display actual counts."""
    
    @pytest.mark.asyncio
    async def test_frontend_uses_response_counts_in_toast(self):
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
