#!/usr/bin/env python3
"""
Comprehensive API Endpoint Test Suite.

Tests EVERY endpoint in the system for:
- Authentication requirements
- Input validation
- Expected responses
- Error handling

Run: python scripts/test_all_endpoints.py
"""

import urllib.request
import urllib.error
import json
import sys

API = "http://localhost:8000"
results = []


def test(name, passed, detail=""):
    """Record and display test result."""
    status = "PASS" if passed else "FAIL"
    results.append((name, passed, detail))
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))


def api_call(method, path, data=None, headers=None):
    """Make API call and return (status_code, body)."""
    headers = headers or {}
    headers["Content-Type"] = "application/json"
    try:
        req = urllib.request.Request(f"{API}{path}", method=method, headers=headers)
        if data:
            req.data = json.dumps(data).encode()
        with urllib.request.urlopen(req, timeout=15) as resp:
            try:
                body = json.loads(resp.read().decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = {}
            return resp.status, body
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode()) if e.fp else {}
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            body = {}
        return e.code, body
    except Exception as e:
        return 0, {"error": str(e)}


def run_auth_tests():
    """Test authentication endpoints."""
    print("\n[1] AUTHENTICATION TESTS")
    print("-" * 40)

    # Valid login
    status, body = api_call("POST", "/api/auth/login", {
        "email": "admin@outpace.ai",
        "password": "Admin123!"
    })
    test("Valid login returns token", status == 200 and "access_token" in body)
    token = body.get("access_token")

    # Wrong password
    status, body = api_call("POST", "/api/auth/login", {
        "email": "admin@outpace.ai",
        "password": "wrongpassword"
    })
    test("Wrong password returns 401", status == 401)

    # Unknown user
    status, body = api_call("POST", "/api/auth/login", {
        "email": "unknown@test.com",
        "password": "password"
    })
    test("Unknown user returns 401", status == 401)

    # Empty email
    status, body = api_call("POST", "/api/auth/login", {
        "email": "",
        "password": "test"
    })
    test("Empty email returns 422", status == 422)

    # Malformed email
    status, body = api_call("POST", "/api/auth/login", {
        "email": "not-an-email",
        "password": "test"
    })
    test("Malformed email returns 422", status == 422)

    # Empty password
    status, body = api_call("POST", "/api/auth/login", {
        "email": "test@test.com",
        "password": ""
    })
    test("Empty password returns 401/422", status in [401, 422])

    # SQL injection attempts
    status, body = api_call("POST", "/api/auth/login", {
        "email": "admin@outpace.ai' OR '1'='1",
        "password": "x"
    })
    test("SQL injection in email blocked", status in [401, 422])

    status, body = api_call("POST", "/api/auth/login", {
        "email": "admin@outpace.ai",
        "password": "' OR '1'='1"
    })
    test("SQL injection in password blocked", status == 401)

    return token


def run_protection_tests():
    """Test that routes are protected without auth."""
    print("\n[2] ROUTE PROTECTION (NO AUTH)")
    print("-" * 40)

    protected_routes = [
        ("GET", "/api/opportunities"),
        ("GET", "/api/tenants"),
        ("GET", "/api/users"),
        ("GET", "/api/intelligence"),
        ("GET", "/api/auth/me"),
        ("GET", "/api/admin/dashboard"),
    ]

    for method, path in protected_routes:
        status, body = api_call(method, path)
        test(f"{method} {path} blocked", status in [401, 403])

    # Chat endpoint needs body
    status, body = api_call("POST", "/api/chat/message", {"message": "test"})
    test("POST /api/chat/message blocked", status in [401, 403, 422])


def run_token_validation_tests():
    """Test token validation."""
    print("\n[3] TOKEN VALIDATION")
    print("-" * 40)

    # Invalid token
    status, body = api_call("GET", "/api/auth/me", headers={
        "Authorization": "Bearer invalidtoken123"
    })
    test("Invalid token rejected", status == 401)

    # Empty token
    status, body = api_call("GET", "/api/auth/me", headers={
        "Authorization": "Bearer "
    })
    test("Empty token rejected", status in [401, 403])

    # Wrong auth scheme
    status, body = api_call("GET", "/api/auth/me", headers={
        "Authorization": "Basic dGVzdDp0ZXN0"
    })
    test("Basic auth rejected", status in [401, 403])

    # Missing Authorization header entirely
    status, body = api_call("GET", "/api/auth/me")
    test("Missing auth header rejected", status in [401, 403])


def run_authenticated_tests(token):
    """Test endpoints that require authentication."""
    print("\n[4] AUTHENTICATED ENDPOINTS")
    print("-" * 40)

    auth = {"Authorization": f"Bearer {token}"}

    # Current user
    status, body = api_call("GET", "/api/auth/me", headers=auth)
    test("/api/auth/me works", status == 200 and "email" in body)
    test("User has role field", "role" in body)
    test("User is super_admin", body.get("role") == "super_admin")

    # Tenants list
    status, body = api_call("GET", "/api/tenants", headers=auth)
    test("/api/tenants returns 200", status == 200)
    test("Response has data field", "data" in body)
    tenants = body.get("data", [])
    tenant_count = len(tenants)
    test("Tenants exist", tenant_count > 0, f"{tenant_count} found")

    tenant_id = tenants[0].get("id") if tenant_count > 0 else None
    tenant_name = tenants[0].get("name") if tenant_count > 0 else None

    # Users list
    status, body = api_call("GET", "/api/users", headers=auth)
    test("/api/users returns 200", status == 200)

    # Opportunities
    status, body = api_call("GET", "/api/opportunities", headers=auth)
    test("/api/opportunities returns 200", status == 200)

    # Intelligence
    status, body = api_call("GET", "/api/intelligence", headers=auth)
    test("/api/intelligence returns 200", status == 200)

    # Admin dashboard
    status, body = api_call("GET", "/api/admin/dashboard", headers=auth)
    test("/api/admin/dashboard returns 200", status == 200)

    # Deep health
    status, body = api_call("GET", "/api/health/deep", headers=auth)
    test("/api/health/deep returns 200", status == 200)

    return tenant_id, tenant_name


def run_tenant_specific_tests(token, tenant_id, tenant_name):
    """Test tenant-specific endpoints."""
    if not tenant_id:
        print("\n[5] TENANT-SPECIFIC TESTS - SKIPPED (no tenant)")
        return

    print(f"\n[5] TENANT-SPECIFIC ENDPOINTS ({tenant_name})")
    print("-" * 40)

    auth = {"Authorization": f"Bearer {token}"}

    # Get specific tenant
    status, body = api_call("GET", f"/api/tenants/{tenant_id}", headers=auth)
    test("Get tenant by ID", status == 200)
    test("Tenant ID matches", body.get("id") == tenant_id)

    # Opportunity stats
    status, body = api_call("GET", f"/api/opportunities/stats/{tenant_id}", headers=auth)
    test("Get opportunity stats", status == 200)

    # RAG status
    status, body = api_call("GET", f"/api/rag/{tenant_id}/rag/status", headers=auth)
    test("Get RAG status", status in [200, 404])

    # Intelligence config
    status, body = api_call("GET", f"/api/config/tenants/{tenant_id}/intelligence-config", headers=auth)
    test("Get intelligence config", status in [200, 404])

    # Knowledge snippets
    status, body = api_call("GET", f"/api/tenants/{tenant_id}/knowledge-snippets", headers=auth)
    test("Get knowledge snippets", status == 200)


def run_health_tests():
    """Test health endpoints."""
    print("\n[6] HEALTH ENDPOINTS")
    print("-" * 40)

    status, body = api_call("GET", "/health")
    test("/health returns 200", status == 200)
    test("Status is healthy", body.get("status") == "healthy")
    test("Has timestamp", "timestamp" in body)


def run_input_validation_tests(token):
    """Test input validation across endpoints."""
    print("\n[7] INPUT VALIDATION")
    print("-" * 40)

    auth = {"Authorization": f"Bearer {token}"}

    # Create tenant with missing required field
    status, body = api_call("POST", "/api/tenants", {
        # Missing "name" field
        "slug": "test-tenant"
    }, headers=auth)
    test("Create tenant without name -> 422", status == 422)

    # Create user with invalid email
    status, body = api_call("POST", "/api/users", {
        "email": "invalid",
        "password": "test123",
        "full_name": "Test User",  # Required field
        "role": "tenant_user"
    }, headers=auth)
    test("Create user with invalid email -> 422", status == 422)

    # Create opportunity with missing fields
    status, body = api_call("POST", "/api/opportunities", {
        # Missing required fields (external_id, title, description, tenant_id)
    }, headers=auth)
    test("Create opportunity without data -> 422", status == 422)


def run_export_tests(token, tenant_id):
    """Test export endpoints return proper status codes."""
    print("\n[8] EXPORT ENDPOINTS")
    print("-" * 40)

    auth = {"Authorization": f"Bearer {token}"}

    # Export with no IDs should return 400 (bad request), not 404 (not found)
    # Bug fix in exports.py changes 404 -> 400. Server restart required.
    status, body = api_call("POST", "/api/exports/pdf", {
        "opportunity_ids": [],
        "intelligence_ids": [],
        "tenant_id": tenant_id
    }, headers=auth)
    # Accept both 400 (fixed) and 404 (pre-fix) but flag 404 as needing restart
    if status == 404:
        test("PDF export with no IDs -> 400 (RESTART NEEDED)", False, "Server returning 404, restart to get 400")
    else:
        test("PDF export with no IDs -> 400", status == 400, body.get("detail", ""))

    status, body = api_call("POST", "/api/exports/excel", {
        "opportunity_ids": [],
        "intelligence_ids": [],
        "tenant_id": tenant_id
    }, headers=auth)
    if status == 404:
        test("Excel export with no IDs -> 400 (RESTART NEEDED)", False, "Server returning 404, restart to get 400")
    else:
        test("Excel export with no IDs -> 400", status == 400, body.get("detail", ""))


def print_summary():
    """Print test summary."""
    print("\n" + "=" * 60)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total = len(results)
    pct = (passed / total) * 100 if total > 0 else 0

    print(f"TOTAL: {passed}/{total} tests passed ({pct:.0f}%)")

    if failed > 0:
        print(f"\n{failed} FAILURES:")
        for name, p, detail in results:
            if not p:
                print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))
    else:
        print("\nALL TESTS PASSED!")

    print("=" * 60)
    return failed


def main():
    """Run all tests."""
    print("=" * 60)
    print("COMPREHENSIVE API TEST SUITE")
    print("=" * 60)

    # Check backend is running
    try:
        status, _ = api_call("GET", "/health")
        if status != 200:
            print("\nERROR: Backend not running at", API)
            return 1
    except Exception:
        print("\nERROR: Cannot connect to backend at", API)
        return 1

    # Run all test categories
    token = run_auth_tests()
    run_protection_tests()
    run_token_validation_tests()

    tenant_id = None
    if token:
        tenant_id, tenant_name = run_authenticated_tests(token)
        run_tenant_specific_tests(token, tenant_id, tenant_name)
        run_input_validation_tests(token)
        if tenant_id:
            run_export_tests(token, tenant_id)

    run_health_tests()

    # Summary
    failed = print_summary()
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
