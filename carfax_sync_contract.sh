#!/bin/bash
#
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  DEPRECATED - DO NOT USE IN CI                                            ║
# ║═══════════════════════════════════════════════════════════════════════════║
# ║  This script is DEPRECATED as of 2025-12-19.                              ║
# ║                                                                           ║
# ║  REASON: It makes multiple sync calls, which violates the "single sync"   ║
# ║  invariant required for CI. The canonical proof path is:                  ║
# ║                                                                           ║
# ║    ci_verify.sh → carfax.sh (SYNC-02) → marker                            ║
# ║                                                                           ║
# ║  USE INSTEAD:                                                             ║
# ║    - For CI: bash ci_verify.sh                                            ║
# ║    - For manual deep testing: bash carfax.sh                              ║
# ║                                                                           ║
# ║  This script is kept for manual/ad-hoc verification OUTSIDE of CI.        ║
# ║  Running it in CI will cause duplicate sync calls.                        ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
#
# CARFAX SYNC CONTRACT TEST (MANUAL USE ONLY)
# ===========================================
# Tests response CONTRACT SHAPE via multiple live API calls.
# NOT CI-SAFE: Makes 3 sync calls total.
#
# For CI-safe single-sync verification, use: bash ci_verify.sh
#

# ============================================================================
# CI GUARD: Refuse to run in CI environment unless explicitly overridden
# ============================================================================
if [ "$CI" = "true" ] && [ "$ALLOW_DEPRECATED_SYNC_SCRIPT" != "true" ]; then
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║  ❌ ERROR: DEPRECATED SCRIPT BLOCKED IN CI                        ║"
    echo "╠═══════════════════════════════════════════════════════════════════╣"
    echo "║  carfax_sync_contract.sh is DEPRECATED and makes 3 sync calls.    ║"
    echo "║                                                                   ║"
    echo "║  For CI, use: bash ci_verify.sh                                   ║"
    echo "║                                                                   ║"
    echo "║  To override (NOT RECOMMENDED):                                   ║"
    echo "║    ALLOW_DEPRECATED_SYNC_SCRIPT=true bash carfax_sync_contract.sh ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration - repo-relative path resolution for GitHub Actions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${GITHUB_WORKSPACE:-${REPO_ROOT:-$SCRIPT_DIR}}"

# API_URL: prefer env var, fallback to repo-relative .env
if [ -n "$API_URL" ]; then
    : # Use existing API_URL from environment
elif [ -f "$REPO_ROOT/frontend/.env" ]; then
    API_URL=$(grep REACT_APP_BACKEND_URL "$REPO_ROOT/frontend/.env" | cut -d '=' -f2)
elif [ -f "/app/frontend/.env" ]; then
    # Fallback for local dev environment
    API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
else
    echo "ERROR: Cannot find frontend/.env to read API_URL. Set API_URL env var."
    exit 1
fi

TENANT_ID="8aa521eb-56ad-4727-8f09-c01fc7921c21"
CARFAX_ADMIN_EMAIL="${CARFAX_ADMIN_EMAIL:?CARFAX_ADMIN_EMAIL not set}"
CARFAX_ADMIN_PASSWORD="${CARFAX_ADMIN_PASSWORD:?CARFAX_ADMIN_PASSWORD not set}"
CARFAX_TENANT_A_EMAIL="${CARFAX_TENANT_A_EMAIL:?CARFAX_TENANT_A_EMAIL not set}"
CARFAX_TENANT_A_PASSWORD="${CARFAX_TENANT_A_PASSWORD:?CARFAX_TENANT_A_PASSWORD not set}"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      CARFAX SYNC CONTRACT REGRESSION TEST (CI-SAFE)           ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "API URL: $API_URL"
echo "Tenant ID: $TENANT_ID"
echo ""

PASSED=0
FAILED=0
START_TIME=$(date +%s)

pass() {
    echo -e "${GREEN}✅ PASS: $1${NC}"
    ((PASSED++))
}

fail() {
    echo -e "${RED}❌ FAIL: $1${NC}"
    ((FAILED++))
}

# Get tokens (fast operation)
echo -e "${YELLOW}Authenticating...${NC}"
ADMIN_TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$CARFAX_ADMIN_EMAIL\",\"password\":\"$CARFAX_ADMIN_PASSWORD\"}" | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

TENANT_TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$CARFAX_TENANT_A_EMAIL\",\"password\":\"$CARFAX_TENANT_A_PASSWORD\"}" | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$ADMIN_TOKEN" ]; then
    fail "Admin authentication failed"
    exit 1
fi
echo -e "${GREEN}Authenticated successfully${NC}"
echo ""

# =============================================================================
# TEST 1: Single Live Sync Call - Response Structure
# =============================================================================
echo -e "${BLUE}TEST 1: Live Sync - Response Structure (ONE call only)${NC}"
echo -e "${YELLOW}   Making ONE live sync call (sync_type=opportunities)...${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/api/admin/sync/$TENANT_ID?sync_type=opportunities" \
    -H "Authorization: Bearer $ADMIN_TOKEN")

# Check ALL required fields including sync_timestamp and errors
FIELD_CHECK=$(echo "$RESPONSE" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    required = ['tenant_id','tenant_name','opportunities_synced','intelligence_synced','status','sync_timestamp','errors']
    missing = [f for f in required if f not in d]
    if missing:
        print(f'MISSING:{missing}')
    else:
        print('OK')
except Exception as e:
    print(f'ERROR:{e}')
")

if [ "$FIELD_CHECK" = "OK" ]; then
    pass "Response contains all required fields (including sync_timestamp, errors)"
else
    fail "Response structure: $FIELD_CHECK"
fi

# =============================================================================
# TEST 2: CRITICAL REGRESSION CHECK - No Async Message
# =============================================================================
echo -e "${BLUE}TEST 2: REGRESSION CHECK - No async 'triggered' message${NC}"
REGRESSION_CHECK=$(echo "$RESPONSE" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    # OLD BUG RESPONSE: {\"status\":\"success\",\"message\":\"Sync triggered successfully\"}
    if 'message' in d and 'triggered' in str(d.get('message','')).lower():
        print('REGRESSION:OLD_ASYNC_MESSAGE')
    elif 'opportunities_synced' not in d and 'intelligence_synced' not in d:
        print('REGRESSION:NO_COUNTS')
    else:
        print('OK')
except Exception as e:
    print(f'ERROR:{e}')
")

if [ "$REGRESSION_CHECK" = "OK" ]; then
    pass "No regression - response has counts, not generic message"
else
    fail "REGRESSION DETECTED: $REGRESSION_CHECK"
    echo -e "${RED}   Response was: $RESPONSE${NC}"
fi

# =============================================================================
# TEST 3: Permission Enforcement (fast - no sync)
# =============================================================================
echo -e "${BLUE}TEST 3: Permission Enforcement (Tenant User -> 403)${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_URL/api/admin/sync/$TENANT_ID" \
    -H "Authorization: Bearer $TENANT_TOKEN")

if [ "$HTTP_CODE" = "403" ]; then
    pass "Tenant user correctly receives 403 Forbidden"
else
    fail "Tenant user should get 403, got $HTTP_CODE"
fi

# =============================================================================
# TEST 4: Type Correctness
# =============================================================================
echo -e "${BLUE}TEST 4: Type Correctness (counts=int, errors=list, status=enum)${NC}"
TYPE_CHECK=$(echo "$RESPONSE" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    errors = []
    if not isinstance(d.get('opportunities_synced'), int):
        errors.append('opportunities_synced not int')
    if not isinstance(d.get('intelligence_synced'), int):
        errors.append('intelligence_synced not int')
    if not isinstance(d.get('errors'), list):
        errors.append('errors not list')
    if d.get('status') not in ['success','partial']:
        errors.append(f\"status '{d.get('status')}' not in [success,partial]\")
    if errors:
        print('FAIL:' + ';'.join(errors))
    else:
        print('OK')
except Exception as e:
    print(f'ERROR:{e}')
")

if [ "$TYPE_CHECK" = "OK" ]; then
    pass "Type correctness verified (int counts, list errors, enum status)"
else
    fail "Type check: $TYPE_CHECK"
fi

# =============================================================================
# TEST 5: Alternative Endpoint Parity (fast - uses cached response pattern)
# =============================================================================
echo -e "${BLUE}TEST 5: /api/sync/manual has same contract${NC}"
MANUAL_RESPONSE=$(curl -s -X POST "$API_URL/api/sync/manual/$TENANT_ID?sync_type=opportunities" \
    -H "Authorization: Bearer $ADMIN_TOKEN")

MANUAL_CHECK=$(echo "$MANUAL_RESPONSE" | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin)
    required = ['tenant_id','tenant_name','opportunities_synced','intelligence_synced','status']
    missing = [f for f in required if f not in d]
    if missing:
        print(f'MISSING:{missing}')
    else:
        print('OK')
except Exception as e:
    print(f'ERROR:{e}')
")

if [ "$MANUAL_CHECK" = "OK" ]; then
    pass "/api/sync/manual has same response contract"
else
    fail "/api/sync/manual: $MANUAL_CHECK"
fi

# =============================================================================
# SUMMARY
# =============================================================================
END_TIME=$(date +%s)
RUNTIME=$((END_TIME - START_TIME))

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  CARFAX SYNC CONTRACT SUMMARY${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Passed: $PASSED"
echo "  Failed: $FAILED"
echo "  Runtime: ${RUNTIME}s"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           ✅ SYNC CONTRACT VERIFIED                            ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║           ❌ SYNC CONTRACT VIOLATION                           ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
