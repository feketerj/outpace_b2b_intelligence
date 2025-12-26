# Test Execution Environment

## Overview

This document defines canonical environments for test execution.
Following these guidelines prevents network namespace isolation issues.

## The Namespace Invariant

**Rule:** The test runner and the system under test (API) MUST share a routable network namespace.

If this invariant is violated, tests will fail with connection errors even when the API is healthy.

## Canonical Configurations

### Configuration A: Git Bash + Windows API (RECOMMENDED)

| Component | Location | Network |
|-----------|----------|---------|
| API (FastAPI) | Windows host | 127.0.0.1:8000 |
| Test Runner | Git Bash (MINGW64) | Windows network stack |
| Database | Docker on Windows | localhost:27017 |

**Why it works:** Git Bash runs in the Windows network namespace, same as the API.

**Invocation:**
```bash
# From PowerShell
& "C:\Program Files\Git\bin\bash.exe" -lc "API_URL='http://127.0.0.1:8000' bash carfax.sh all"
```

### Configuration B: All-Docker

| Component | Location | Network |
|-----------|----------|---------|
| API | Docker container | docker network |
| Test Runner | Docker container | docker network |
| Database | Docker container | docker network |

**Why it works:** All components share the Docker bridge network.

### Configuration C: All-WSL (Alternative)

| Component | Location | Network |
|-----------|----------|---------|
| API | WSL2 | WSL network namespace |
| Test Runner | WSL2 | WSL network namespace |
| Database | WSL2 or Docker | Accessible from WSL |

**Why it works:** All components run inside WSL's network namespace.

## Anti-Patterns (DO NOT USE)

### ❌ WSL Tests + Windows API

| Component | Location | Problem |
|-----------|----------|---------|
| API | Windows host (127.0.0.1:8000) | Windows loopback |
| Test Runner | WSL2 | WSL loopback (different!) |

**Why it fails:** WSL2 has its own network namespace. `127.0.0.1` in WSL points to the WSL VM, not Windows.

### ❌ Using 'localhost' instead of '127.0.0.1'

On Windows with Python, `localhost` may resolve to IPv6 (`::1`) first, causing 2000ms+ timeouts before falling back to IPv4.

**Always use:** `127.0.0.1` (explicit IPv4)

## Preflight Check

Before running tests, execute the preflight namespace check:
```bash
API_URL="http://127.0.0.1:8000" ./scripts/preflight_namespace.sh
```

This will:
1. Detect your platform (Git Bash, WSL, Linux)
2. Warn if namespace isolation is likely
3. Verify API connectivity
4. Exit non-zero if environment is invalid

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| API_URL | Yes | http://127.0.0.1:8000 | Base URL for API |
| MONGO_URL | Yes | mongodb://localhost:27017 | MongoDB connection string |
| DB_NAME | Yes | outpace_intelligence | Database name |
| JWT_SECRET | Yes | (any non-empty) | JWT signing secret |

## Troubleshooting

### "Connection refused" from tests

1. Check API is running: `curl http://127.0.0.1:8000/health`
2. Check namespace: Are you in WSL but API is on Windows? Use Git Bash.
3. Run preflight: `./scripts/preflight_namespace.sh`

### "2000ms+ latency on first request"

1. You're using `localhost` instead of `127.0.0.1`
2. Python is trying IPv6 first, timing out, then falling back to IPv4
3. Fix: Use `API_URL=http://127.0.0.1:8000` explicitly

### "Tests pass locally but fail in CI"

1. CI environment is different from local
2. Check CI logs for namespace/connectivity issues
3. Ensure CI uses the same configuration as local (e.g., All-Docker)
