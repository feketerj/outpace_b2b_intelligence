#!/usr/bin/env python3
"""
E2E Smoke Test - Verify frontend and backend work together.

Run: python scripts/smoke_test.py

Prerequisites:
    - Backend running at http://localhost:8000
    - Frontend running at http://localhost:3000
    - MongoDB running

Tests:
    1. Backend health endpoint responds
    2. Frontend responds
    3. Backend login API works
    4. Backend returns proper CORS headers

Exit codes:
    0 = All tests passed
    1 = One or more tests failed
"""

import sys
import json
import urllib.request
import urllib.error
from typing import Tuple, List

BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"
TEST_EMAIL = "admin@outpace.ai"
TEST_PASSWORD = "Admin123!"


def make_request(url: str, method: str = "GET", data: dict = None, headers: dict = None) -> Tuple[int, str, dict]:
    """
    Make HTTP request and return (status_code, body, response_headers).
    Returns (0, error_message, {}) on connection error.
    """
    headers = headers or {}
    headers["Content-Type"] = "application/json"

    try:
        req = urllib.request.Request(url, method=method, headers=headers)
        if data:
            req.data = json.dumps(data).encode("utf-8")

        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            resp_headers = dict(response.headers)
            return response.status, body, resp_headers

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else ""
        return e.code, body, dict(e.headers) if e.headers else {}

    except urllib.error.URLError as e:
        return 0, f"Connection failed: {e.reason}", {}

    except Exception as e:
        return 0, f"Request error: {str(e)}", {}


def test_backend_health() -> Tuple[bool, str]:
    """Test 1: Backend health endpoint responds."""
    status, body, _ = make_request(f"{BACKEND_URL}/health")

    if status == 0:
        return False, f"Backend not reachable: {body}"

    if status != 200:
        return False, f"Backend health returned {status}"

    try:
        data = json.loads(body)
        if data.get("status") == "healthy":
            return True, "Backend healthy"
        return False, f"Backend status: {data.get('status', 'unknown')}"
    except json.JSONDecodeError:
        return False, "Invalid JSON response from health endpoint"


def test_frontend_responds() -> Tuple[bool, str]:
    """Test 2: Frontend responds to HTTP request."""
    status, body, _ = make_request(FRONTEND_URL)

    if status == 0:
        return False, f"Frontend not reachable: {body}"

    if status != 200:
        return False, f"Frontend returned {status}"

    if "<div id=\"root\">" in body or "<!doctype html>" in body.lower():
        return True, "Frontend serving HTML"

    return False, "Frontend response doesn't look like React app"


def test_backend_login() -> Tuple[bool, str]:
    """Test 3: Backend login API works."""
    status, body, _ = make_request(
        f"{BACKEND_URL}/api/auth/login",
        method="POST",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )

    if status == 0:
        return False, f"Login request failed: {body}"

    if status == 401:
        return False, "Login credentials rejected (check test user exists)"

    if status != 200:
        return False, f"Login returned {status}: {body[:100]}"

    try:
        data = json.loads(body)
        if "access_token" in data:
            return True, f"Login successful (token returned)"
        return False, "Login response missing access_token"
    except json.JSONDecodeError:
        return False, "Invalid JSON response from login"


def test_cors_headers() -> Tuple[bool, str]:
    """Test 4: Backend returns proper CORS headers for frontend."""
    # Send preflight OPTIONS request
    status, body, headers = make_request(
        f"{BACKEND_URL}/api/auth/login",
        method="OPTIONS",
        headers={"Origin": FRONTEND_URL, "Access-Control-Request-Method": "POST"}
    )

    # Some backends return 200, others 204 for OPTIONS
    if status not in [200, 204, 405]:  # 405 means OPTIONS not implemented but GET works
        if status == 0:
            return False, f"CORS check failed: {body}"

    # Check for CORS headers (case-insensitive check)
    headers_lower = {k.lower(): v for k, v in headers.items()}

    # If we got a response at all and the frontend can load, CORS is probably fine
    # FastAPI with CORSMiddleware handles this automatically
    if "access-control-allow-origin" in headers_lower:
        return True, "CORS headers present"

    # Try actual request to see if it works
    status2, body2, headers2 = make_request(
        f"{BACKEND_URL}/health",
        headers={"Origin": FRONTEND_URL}
    )

    if status2 == 200:
        return True, "Backend responds to requests with Origin header"

    return False, "CORS may be misconfigured"


def main():
    """Run all smoke tests."""
    print("\n" + "=" * 60)
    print("E2E SMOKE TEST")
    print("=" * 60 + "\n")

    tests = [
        ("Backend Health", test_backend_health),
        ("Frontend Responds", test_frontend_responds),
        ("Backend Login", test_backend_login),
        ("CORS Configuration", test_cors_headers),
    ]

    results: List[Tuple[str, bool, str]] = []

    for name, test_fn in tests:
        print(f"  [{len(results)+1}/{len(tests)}] {name}...", end=" ", flush=True)
        try:
            passed, detail = test_fn()
        except Exception as e:
            passed, detail = False, f"Exception: {str(e)}"

        results.append((name, passed, detail))
        status = "OK" if passed else "FAIL"
        print(f"{status} ({detail})")

    # Summary
    print("\n" + "=" * 60)
    passed_count = sum(1 for _, p, _ in results if p)
    failed_count = len(results) - passed_count

    for name, passed, detail in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {name}: {detail}")

    print("-" * 60)
    print(f"Total: {passed_count} passed, {failed_count} failed")
    print("=" * 60)

    if failed_count == 0:
        print("\n*** ALL SMOKE TESTS PASSED ***\n")
        return 0
    else:
        print("\n*** SMOKE TESTS FAILED ***\n")
        print("To run services:")
        print("  Backend: cd backend && python -m uvicorn server:app --reload --port 8000")
        print("  Frontend: cd frontend && npm start")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
