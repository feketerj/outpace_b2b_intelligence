#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  STATIC CONTRACT TEST: Frontend Sync Implementation                          ║
║                                                                              ║
║  THIS IS A STATIC CODE ANALYSIS TEST - NO PLAYWRIGHT/BROWSER REQUIRED        ║
║                                                                              ║
║  These tests verify the frontend code correctly implements the sync          ║
║  contract by inspecting the source files directly.                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

TESTS PERFORMED:
1. IntelligenceFeed.js imports useAuth for role checking
2. IntelligenceFeed.js uses isSuperAdmin() to guard Sync Now button
3. IntelligenceFeed.js toast includes actual count expression
4. TenantsPage.js uses response counts in toast message

DO NOT ADD BROWSER AUTOMATION - USE STATIC CODE INSPECTION ONLY.
DO NOT MODIFY WITHOUT QC APPROVAL.
"""
import pytest
import re
import os
from pathlib import Path


def _get_repo_root() -> Path:
    """
    Resolve repo root dynamically for GitHub Actions compatibility.
    Priority: GITHUB_WORKSPACE > REPO_ROOT > FRONTEND_ROOT parent > path traversal from this file.
    """
    # 1. GitHub Actions sets GITHUB_WORKSPACE
    if os.environ.get("GITHUB_WORKSPACE"):
        return Path(os.environ["GITHUB_WORKSPACE"])
    
    # 2. Explicit REPO_ROOT env var
    if os.environ.get("REPO_ROOT"):
        return Path(os.environ["REPO_ROOT"])
    
    # 3. FRONTEND_ROOT points to frontend/ dir
    if os.environ.get("FRONTEND_ROOT"):
        return Path(os.environ["FRONTEND_ROOT"]).parent
    
    # 4. Path traversal: this file is at <repo>/backend/tests/test_sync_frontend_contract.py
    #    So repo root is 3 levels up
    return Path(__file__).resolve().parent.parent.parent


# Dynamically resolved frontend file paths (no hardcoded /app)
_REPO_ROOT = _get_repo_root()
INTELLIGENCE_FEED_PATH = str(_REPO_ROOT / "frontend" / "src" / "pages" / "IntelligenceFeed.js")
TENANTS_PAGE_PATH = str(_REPO_ROOT / "frontend" / "src" / "pages" / "TenantsPage.js")


class TestSyncButtonVisibilityContract:
    """
    STATIC CONTRACT TESTS: Verify frontend code implements role-based visibility.
    
    These tests inspect the source code to verify the contract is implemented.
    They do NOT require Playwright or browser automation.
    """
    
    def test_intelligence_feed_imports_use_auth(self):
        """
        INVARIANT: IntelligenceFeed.js MUST import useAuth from AuthContext.
        
        This is required to access isSuperAdmin() for role checking.
        """
        with open(INTELLIGENCE_FEED_PATH, "r") as f:
            code = f.read()
        
        # Check for useAuth import
        assert "useAuth" in code, \
            "IntelligenceFeed.js must import useAuth from AuthContext"
        
        # Verify it's actually imported (not just mentioned in a comment)
        import_pattern = r"import\s*{[^}]*useAuth[^}]*}\s*from"
        assert re.search(import_pattern, code), \
            "useAuth must be properly imported (import { useAuth } from ...)"
    
    def test_intelligence_feed_uses_is_super_admin_guard(self):
        """
        INVARIANT: IntelligenceFeed.js MUST use isSuperAdmin() to guard Sync Now button.
        
        The pattern should be: {isSuperAdmin() && (<Button...Sync Now...)}
        This ensures tenant users cannot see the button.
        """
        with open(INTELLIGENCE_FEED_PATH, "r") as f:
            code = f.read()
        
        # Check isSuperAdmin is destructured from useAuth
        assert "isSuperAdmin" in code, \
            "IntelligenceFeed.js must use isSuperAdmin() for role checking"
        
        # Find the Sync Now button location
        sync_now_match = re.search(r"Sync Now", code)
        assert sync_now_match, "Could not find 'Sync Now' button text in code"
        sync_now_pos = sync_now_match.start()
        
        # Find isSuperAdmin() guard location
        is_super_admin_match = re.search(r"isSuperAdmin\(\)", code)
        assert is_super_admin_match, "Could not find isSuperAdmin() call in code"
        guard_pos = is_super_admin_match.start()
        
        # The guard should appear BEFORE the Sync Now button (within 500 chars)
        # This verifies the conditional rendering pattern
        distance = sync_now_pos - guard_pos
        assert 0 < distance < 500, \
            f"isSuperAdmin() guard must be near Sync Now button (distance: {distance} chars). " \
            f"Expected pattern: {{isSuperAdmin() && (<Button>Sync Now</Button>)}}"
    
    def test_intelligence_feed_toast_uses_count_expression(self):
        """
        INVARIANT: Toast message MUST include the actual count from API response.
        
        The toast should show something like:
        - `${result.intelligence_synced} new reports`
        - `Intelligence sync complete: ${result.intelligence_synced || 0} new reports`
        
        NOT a generic "Sync successful" without counts.
        """
        with open(INTELLIGENCE_FEED_PATH, "r") as f:
            code = f.read()
        
        # Find the handleSyncIntelligence function
        handler_match = re.search(r"handleSyncIntelligence\s*=\s*async", code)
        assert handler_match, "Could not find handleSyncIntelligence function"
        
        # Extract the function body (approximate - up to next function or 1000 chars)
        handler_start = handler_match.start()
        handler_section = code[handler_start:handler_start + 1500]
        
        # Look for toast.success with count expression
        toast_pattern = r"toast\.success\([^)]*intelligence_synced[^)]*\)"
        toast_match = re.search(toast_pattern, handler_section)
        
        assert toast_match, \
            "Toast in handleSyncIntelligence must include intelligence_synced count. " \
            "Expected pattern: toast.success(`...${result.intelligence_synced}...`)"
        
        # Verify it's using the count in a string interpolation, not just checking it
        toast_content = toast_match.group(0)
        assert "${" in toast_content or "`" in handler_section[:toast_match.end() - handler_start + 100], \
            "Toast must use template literal with count interpolation"


class TestTenantsPageToastContract:
    """
    STATIC CONTRACT TESTS: Verify TenantsPage.js uses response counts in toast.
    """
    
    def test_tenants_page_sync_toast_uses_summed_counts(self):
        """
        INVARIANT: TenantsPage.js sync toast MUST display summed counts.
        
        The toast should show total synced items:
        - `Synced ${response.data.opportunities_synced + response.data.intelligence_synced} items!`
        """
        with open(TENANTS_PAGE_PATH, "r") as f:
            code = f.read()
        
        # Verify both count fields are referenced
        assert "opportunities_synced" in code, \
            "TenantsPage.js must reference opportunities_synced"
        assert "intelligence_synced" in code, \
            "TenantsPage.js must reference intelligence_synced"
        
        # Find the sync button handler (onClick with sync/manual)
        sync_handler_pattern = r"onClick\s*=\s*\{\s*async\s*\(\)\s*=>\s*\{[^}]*sync/manual"
        # Broader search for the sync-related toast
        toast_pattern = r"toast\.success\([^)]*synced[^)]*\)"
        
        toast_match = re.search(toast_pattern, code, re.IGNORECASE)
        assert toast_match, \
            "TenantsPage.js must have toast.success with 'synced' showing counts"
        
        # Verify the toast includes count arithmetic or interpolation
        toast_area = code[max(0, toast_match.start()-200):toast_match.end()+50]
        assert "+" in toast_area or "opportunities_synced" in toast_area, \
            "Toast should sum or display sync counts"


class TestNoBrowserDependency:
    """
    META-TEST: Verify this test file does not import browser automation libs.
    """
    
    def test_no_browser_automation_import(self):
        """
        This test file must NOT depend on browser automation.
        It should use static code inspection only.
        """
        with open(__file__, "r") as f:
            test_code = f.read()
        
        # Check imports section only (first 50 lines)
        imports_section = "\n".join(test_code.split("\n")[:50])
        
        assert "from playwright" not in imports_section, \
            "This test file must not import browser automation libraries"
        assert "import selenium" not in imports_section.lower(), \
            "This test file must not import selenium"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
