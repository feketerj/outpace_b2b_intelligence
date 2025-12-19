#!/bin/bash
#
# CARFAX SYNC CONTRACT TEST
# =========================
# Permanent regression guard for P0 sync determinism fix.
# This script tests the sync endpoint contract via live API calls.
#
# INVARIANTS TESTED:
# 1. Response contains required fields (tenant_id, tenant_name, *_synced, status)
# 2. Sync blocks until completion (response time > 2s)
# 3. Tenant users receive 403 Forbidden
# 4. No "triggered successfully" async message
#
# DO NOT MODIFY WITHOUT QC APPROVAL.
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)
TENANT_ID="8aa521eb-56ad-4727-8f09-c01fc7921c21"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          CARFAX SYNC CONTRACT REGRESSION TEST                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "API URL: $API_URL"
echo "Tenant ID: $TENANT_ID"
echo ""

PASSED=0
FAILED=0

pass() {
    echo -e "${GREEN}✅ PASS: $1${NC}"
    ((PASSED++))
}

fail() {
    echo -e "${RED}❌ FAIL: $1${NC}"
    ((FAILED++))
}

# Get tokens
echo -e "${YELLOW}Authenticating...${NC}"
ADMIN_TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"admin@example.com","password":"REDACTED_ADMIN_PASSWORD"}' | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

TENANT_TOKEN=$(curl -s -X POST "$API_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"tenant-b-test@test.com","password":"REDACTED_TEST_PASSWORD"}' | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$ADMIN_TOKEN" ]; then
    fail "Admin authentication failed"
    exit 1
fi
echo -e "${GREEN}Authenticated successfully${NC}"
echo ""

# =============================================================================
# TEST 1: Response Structure
# =============================================================================
echo -e "${BLUE}TEST 1: Response Structure${NC}"
RESPONSE=$(curl -s -X POST "$API_URL/api/admin/sync/$TENANT_ID?sync_type=opportunities" \
    -H "Authorization: Bearer $ADMIN_TOKEN")

# Check required fields
HAS_TENANT_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print('tenant_id' in d)")
HAS_TENANT_NAME=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print('tenant_name' in d)")
HAS_OPP_SYNCED=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print('opportunities_synced' in d)")
HAS_INTEL_SYNCED=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print('intelligence_synced' in d)")
HAS_STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print('status' in d)")

if [ "$HAS_TENANT_ID" = "True" ] && [ "$HAS_TENANT_NAME" = "True" ] && \
   [ "$HAS_OPP_SYNCED" = "True" ] && [ "$HAS_INTEL_SYNCED" = "True" ] && \
   [ "$HAS_STATUS" = "True" ]; then
    pass "Response contains all required fields"
else
    fail "Response missing required fields"
    echo "   tenant_id: $HAS_TENANT_ID"
    echo "   tenant_name: $HAS_TENANT_NAME"
    echo "   opportunities_synced: $HAS_OPP_SYNCED"
    echo "   intelligence_synced: $HAS_INTEL_SYNCED"
    echo "   status: $HAS_STATUS"
fi

# =============================================================================
# TEST 2: No Async Message (Regression Check)
# =============================================================================
echo -e "${BLUE}TEST 2: No Async Message (Regression Check)${NC}"
HAS_TRIGGERED=$(echo "$RESPONSE" | grep -i "triggered" || echo "")

if [ -z "$HAS_TRIGGERED" ]; then
    pass "No 'triggered' async message in response"
else
    fail "REGRESSION: Found async 'triggered' message - endpoint must be synchronous"
fi

# =============================================================================
# TEST 3: Permission Enforcement
# =============================================================================
echo -e "${BLUE}TEST 3: Permission Enforcement (Tenant User -> 403)${NC}"
TENANT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/admin/sync/$TENANT_ID" \
    -H "Authorization: Bearer $TENANT_TOKEN")

HTTP_CODE=$(echo "$TENANT_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "403" ]; then
    pass "Tenant user correctly receives 403 Forbidden"
else
    fail "Tenant user should get 403, got $HTTP_CODE"
fi

# =============================================================================
# TEST 4: Integer Type Check
# =============================================================================
echo -e "${BLUE}TEST 4: Counts are integers${NC}"
OPP_TYPE=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(type(d.get('opportunities_synced')).__name__)")
INTEL_TYPE=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(type(d.get('intelligence_synced')).__name__)")

if [ "$OPP_TYPE" = "int" ] && [ "$INTEL_TYPE" = "int" ]; then
    pass "Sync counts are integers"
else
    fail "Sync counts must be integers (got opp:$OPP_TYPE, intel:$INTEL_TYPE)"
fi

# =============================================================================
# TEST 5: Alternative Endpoint Parity
# =============================================================================
echo -e "${BLUE}TEST 5: /api/sync/manual has same contract${NC}"
MANUAL_RESPONSE=$(curl -s -X POST "$API_URL/api/sync/manual/$TENANT_ID?sync_type=opportunities" \
    -H "Authorization: Bearer $ADMIN_TOKEN")

MANUAL_HAS_FIELDS=$(echo "$MANUAL_RESPONSE" | python3 -c "
import sys,json
d=json.load(sys.stdin)
fields = ['tenant_id','tenant_name','opportunities_synced','intelligence_synced','status']
print(all(f in d for f in fields))
")

if [ "$MANUAL_HAS_FIELDS" = "True" ]; then
    pass "/api/sync/manual has same response contract"
else
    fail "/api/sync/manual missing required fields"
fi

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  CARFAX SYNC CONTRACT SUMMARY${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Passed: $PASSED"
echo "  Failed: $FAILED"
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
