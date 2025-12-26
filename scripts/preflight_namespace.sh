#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Preflight Namespace Check
# Ensures test runner can reach the API (same network namespace)
# ============================================================

API_URL="${API_URL:-http://127.0.0.1:8000}"
STRICT_MODE="${PREFLIGHT_STRICT:-1}"

echo "=== PREFLIGHT NAMESPACE CHECK ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Detect platform
echo "Platform Detection:"
UNAME_OUTPUT="$(uname -a)"
echo "  uname: $UNAME_OUTPUT"

IS_WSL=0
IS_MINGW=0
IS_LINUX=0

if [[ "$UNAME_OUTPUT" == *"Microsoft"* ]] || [[ "$UNAME_OUTPUT" == *"WSL"* ]]; then
    IS_WSL=1
    echo "  Detected: WSL/WSL2"
elif [[ "$UNAME_OUTPUT" == *"MINGW"* ]] || [[ "$UNAME_OUTPUT" == *"MSYS"* ]]; then
    IS_MINGW=1
    echo "  Detected: Git Bash / MINGW"
elif [[ "$UNAME_OUTPUT" == *"Linux"* ]]; then
    IS_LINUX=1
    echo "  Detected: Native Linux"
else
    echo "  Detected: Unknown (assuming compatible)"
fi
echo ""

# Check if API_URL uses localhost/127.0.0.1
USES_LOOPBACK=0
if [[ "$API_URL" == *"localhost"* ]] || [[ "$API_URL" == *"127.0.0.1"* ]]; then
    USES_LOOPBACK=1
fi

# WSL + loopback = likely namespace isolation issue
if [[ $IS_WSL -eq 1 ]] && [[ $USES_LOOPBACK -eq 1 ]]; then
    echo "WARNING: WSL detected with loopback API_URL"
    echo "  API_URL: $API_URL"
    echo "  This configuration may fail due to network namespace isolation."
    echo "  WSL2's 127.0.0.1 is NOT the same as Windows host's 127.0.0.1."
    echo ""
    echo "Recommendations:"
    echo "  1. Run tests via Git Bash (Windows-native) instead of WSL"
    echo "  2. OR bind API to 0.0.0.0 and use host IP from WSL"
    echo "  3. OR run API inside WSL/Docker"
    echo ""

    if [[ $STRICT_MODE -eq 1 ]]; then
        echo "PREFLIGHT FAIL: Namespace isolation detected (strict mode)"
        exit 1
    else
        echo "PREFLIGHT WARN: Proceeding despite namespace warning (non-strict mode)"
    fi
fi

# Test API connectivity
echo "API Connectivity Check:"
echo "  URL: $API_URL/health"

HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 5 "$API_URL/health" 2>&1) || HTTP_CODE="000"

echo "  Response: HTTP $HTTP_CODE"
echo ""

if [[ "$HTTP_CODE" == "200" ]]; then
    echo "=== PREFLIGHT PASS ==="
    echo "  Platform: $(if [[ $IS_MINGW -eq 1 ]]; then echo 'Git Bash (OK)'; elif [[ $IS_WSL -eq 1 ]]; then echo 'WSL (risky)'; else echo 'Linux/Other'; fi)"
    echo "  API: Reachable"
    echo "  Namespace: Unified (inferred from connectivity)"
    exit 0
else
    echo "=== PREFLIGHT FAIL ==="
    echo "  API not reachable at $API_URL/health"
    echo "  HTTP code: $HTTP_CODE"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Is the API running? Check: curl $API_URL/health"
    echo "  2. Is API_URL correct? Current: $API_URL"
    echo "  3. Network namespace issue? Try Git Bash instead of WSL"
    exit 1
fi
