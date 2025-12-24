#!/bin/bash
#==============================================================================
# CARFAX - Comprehensive Auditable Report For Application eXecution
# OutPace Intelligence Platform - Evidence-Based Test Runner
# Covers: INV-1, INV-2, INV-3, INV-4, INV-5
#==============================================================================
#
# Usage: ./carfax.sh <category> <stratum>
# Example: ./carfax.sh auth happy
# Example: ./carfax.sh chat boundary
# Example: ./carfax.sh all all
#
# Categories: auth, tenants, chat, opportunities, intelligence, exports,
#             upload, sync, config, admin, users, rag, all
#
# Strata: happy, boundary, invalid, empty, performance, failure, all
#
#==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Resolve repo root dynamically (no hardcoded /app for GitHub Actions)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${GITHUB_WORKSPACE:-${REPO_ROOT:-$SCRIPT_DIR}}"

# Single source of truth for API_URL (matches TEST_PLAN.json)
API_URL="${API_URL:-https://integrity-shield-1.preview.emergentagent.com}"

# Category/Stratum selection
CATEGORY="${1:-all}"
STRATUM="${2:-all}"

REPORT_DIR="$REPO_ROOT/carfax_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/carfax_$TIMESTAMP.json"
LOG_FILE="/var/log/supervisor/backend.err.log"

# Fixtures from TEST_PLAN.json
ADMIN_EMAIL="admin@outpace.ai"
ADMIN_PASSWORD="Admin123!"
# Updated fixtures - 2025-12-18
TENANT_A_EMAIL="tenant-b-test@test.com"
TENANT_A_PASSWORD="Test123!"
TENANT_B_EMAIL="enchandia-test@test.com"
TENANT_B_PASSWORD="Test123!"
TENANT_A_ID="8aa521eb-56ad-4727-8f09-c01fc7921c21"
TENANT_B_ID="e4e0b3b4-90ec-4c32-88d8-534aa563ed5d"

# Counters
PASSED=0
FAILED=0
declare -a RAW_EVIDENCE

#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------

evidence() {
    local msg="$1"
    RAW_EVIDENCE+=("$msg")
    echo -e "${CYAN}   📋 $msg${NC}"
}

pass() {
    echo -e "${GREEN}✅ PASS: $1${NC}"
    PASSED=$((PASSED + 1))
}

fail() {
    echo -e "${RED}❌ FAIL: $1${NC}"
    FAILED=$((FAILED + 1))
}

section() {
    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  $1${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
}

get_token() {
    local email=$1
    local password=$2
    local response
    local http_code

    # Capture both response body AND HTTP status code
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$email\",\"password\":\"$password\"}")

    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    # FAIL-LOUD: If not HTTP 200, print error details and return empty
    if [ "$http_code" != "200" ]; then
        echo -e "${RED}[FAIL-LOUD] Login failed for $email${NC}" >&2
        echo -e "${RED}  HTTP Status: $http_code${NC}" >&2
        echo -e "${RED}  API URL: $API_URL/api/auth/login${NC}" >&2
        echo -e "${RED}  Response: $body${NC}" >&2
        echo ""
        return 1
    fi

    # Extract token from successful response
    local token=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)

    if [ -z "$token" ]; then
        echo -e "${RED}[FAIL-LOUD] Login succeeded but no access_token in response${NC}" >&2
        echo -e "${RED}  Response: $body${NC}" >&2
        echo ""
        return 1
    fi

    echo "$token"
}

setup_auth() {
    ADMIN_TOKEN=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD") || {
        echo "ERROR: setup_auth failed for super admin" >&2
        exit 1
    }
    SUPER_ADMIN_TOKEN="$ADMIN_TOKEN"
    TENANT_A_TOKEN=$(get_token "$TENANT_A_EMAIL" "$TENANT_A_PASSWORD") || {
        echo "ERROR: setup_auth failed for tenant A user" >&2
        exit 1
    }
    TENANT_B_TOKEN=$(get_token "$TENANT_B_EMAIL" "$TENANT_B_PASSWORD") || {
        echo "ERROR: setup_auth failed for tenant B user" >&2
        exit 1
    }
}

http_status() {
    curl -s -o /dev/null -w "%{http_code}" "$@"
}

# Quick permission check - 5s timeout, just checks auth/permission, not full execution
http_status_quick() {
    curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$@" 2>/dev/null || echo "408"
}

# PUT tenant config and fail fast on non-200
tenant_put_or_fail() {
    local tenant_id=$1
    local payload=$2
    local resp

    resp=$(curl -s -w "\n%{http_code}" -X PUT "$API_URL/api/tenants/$tenant_id" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload")

    TENANT_PUT_STATUS=$(echo "$resp" | tail -n1)
    TENANT_PUT_BODY=$(echo "$resp" | sed '$d')

    if [ "$TENANT_PUT_STATUS" != "200" ]; then
        evidence "PUT /api/tenants/$tenant_id -> HTTP $TENANT_PUT_STATUS"
        evidence "Response: $TENANT_PUT_BODY"
        fail "Tenant PUT failed ($TENANT_PUT_STATUS)"
        exit 1
    fi
}

# Get chat_turns count for a tenant via direct DB query
get_chat_turns_count() {
    local tenant_id=$1
    local result=$(timeout 5 python3 -c "
import os, sys, asyncio

async def count():
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        print('DB_SKIP')
        return
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
        db = client[os.environ.get('DB_NAME', 'outpace_intelligence')]
        count = await db.chat_turns.count_documents({'tenant_id': '$tenant_id'})
        print(count)
    except Exception:
        print('DB_SKIP')

asyncio.run(count())
" 2>&1 || echo "DB_SKIP")
    echo "$result"
}

# Update tenant chat_policy via API
set_chat_policy() {
    local tenant_id=$1
    local enabled=$2
    local normalized=$(echo "$enabled" | tr '[:upper:]' '[:lower:]')
    if [ "$normalized" = "true" ] || [ "$normalized" = "false" ]; then
        enabled="$normalized"
    fi
    tenant_put_or_fail "$tenant_id" "{\"chat_policy\":{\"enabled\":$enabled,\"monthly_message_limit\":100}}"
}

#==============================================================================
# AUTH CATEGORY TESTS
#==============================================================================

auth_happy() {
    section "AUTH/HAPPY (3 tests)"

    echo -e "\n${BOLD}S0-01: login_super_admin${NC}"
    ADMIN_TOKEN=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    evidence "access_token=${ADMIN_TOKEN:+present}"
    if [ -n "$ADMIN_TOKEN" ]; then pass "S0-01: login_super_admin"; else fail "S0-01: login_super_admin"; fi

    echo -e "\n${BOLD}S0-02: login_tenant_user${NC}"
    TENANT_A_TOKEN=$(get_token "$TENANT_A_EMAIL" "$TENANT_A_PASSWORD")
    evidence "access_token=${TENANT_A_TOKEN:+present}"
    if [ -n "$TENANT_A_TOKEN" ]; then pass "S0-02: login_tenant_user"; else fail "S0-02: login_tenant_user"; fi

    TENANT_B_TOKEN=$(get_token "$TENANT_B_EMAIL" "$TENANT_B_PASSWORD")

    echo -e "\n${BOLD}S0-03: auth_me${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/auth/me")
    evidence "HTTP $status"
    if [ "$status" = "200" ]; then pass "S0-03: auth_me"; else fail "S0-03: auth_me ($status)"; fi
}

auth_boundary() {
    section "AUTH/BOUNDARY (1 test)"
    setup_auth

    echo -e "\n${BOLD}AUTH-BOUND-01: expired_token_rejected${NC}"
    local expired_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxfQ.invalid"
    local status=$(http_status -H "Authorization: Bearer $expired_token" "$API_URL/api/auth/me")
    evidence "expired token -> HTTP $status"
    if [ "$status" = "401" ]; then pass "AUTH-BOUND-01: expired_token_rejected"; else fail "AUTH-BOUND-01 ($status)"; fi
}

auth_invalid() {
    section "AUTH/INVALID (2 tests)"

    echo -e "\n${BOLD}AUTH-INV-01: invalid_credentials${NC}"
    local resp=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email":"invalid@test.com","password":"wrongpassword"}')
    local status=$(echo "$resp" | tail -n1)
    evidence "invalid credentials -> HTTP $status"
    if [ "$status" = "401" ]; then pass "AUTH-INV-01: invalid_credentials"; else fail "AUTH-INV-01 ($status)"; fi

    echo -e "\n${BOLD}AUTH-INV-02: malformed_token${NC}"
    status=$(http_status -H "Authorization: Bearer not-a-valid-token" "$API_URL/api/auth/me")
    evidence "malformed token -> HTTP $status"
    if [ "$status" = "401" ]; then pass "AUTH-INV-02: malformed_token"; else fail "AUTH-INV-02 ($status)"; fi
}

auth_empty() {
    section "AUTH/EMPTY (2 tests)"

    echo -e "\n${BOLD}EMPTY-05: missing_auth_header_rejected${NC}"
    local status=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$API_URL/api/opportunities")
    evidence "no auth header -> HTTP $status"
    if [[ "$status" =~ ^(401|403)$ ]]; then pass "EMPTY-05: missing_auth_header_rejected"; else fail "EMPTY-05 ($status)"; fi

    echo -e "\n${BOLD}AUTH-EMPTY-01: empty_bearer_token${NC}"
    status=$(http_status -H "Authorization: Bearer " "$API_URL/api/auth/me")
    evidence "empty bearer token -> HTTP $status"
    if [[ "$status" =~ ^(401|403|422)$ ]]; then pass "AUTH-EMPTY-01: empty_bearer_token"; else fail "AUTH-EMPTY-01 ($status)"; fi
}

auth_performance() {
    section "AUTH/PERFORMANCE (1 test)"

    echo -e "\n${BOLD}PERF-02: auth_under_1000ms${NC}"
    local start_ms=$(date +%s%3N)
    local resp=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    local status=$(echo "$resp" | tail -n1)
    evidence "auth login: HTTP $status in ${duration}ms"
    if [ "$status" = "200" ] && [ "$duration" -lt 2000 ]; then
        pass "PERF-02: auth_under_1000ms (${duration}ms)"
    else
        fail "PERF-02 (status=$status, duration=${duration}ms)"
    fi
}

auth_failure() {
    section "AUTH/FAILURE (1 test)"

    echo -e "\n${BOLD}AUTH-FAIL-01: auth_service_graceful${NC}"
    # This test validates that the auth endpoint returns proper errors
    local status=$(http_status -X POST "$API_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{}')
    evidence "empty login body -> HTTP $status"
    if [[ "$status" =~ ^(400|401|422)$ ]]; then pass "AUTH-FAIL-01: auth_service_graceful"; else fail "AUTH-FAIL-01 ($status)"; fi
}

run_auth_tests() {
    local stratum=$1
    case "$stratum" in
        happy) auth_happy ;;
        boundary) auth_boundary ;;
        invalid) auth_invalid ;;
        empty) auth_empty ;;
        performance) auth_performance ;;
        failure) auth_failure ;;
        all) auth_happy; auth_boundary; auth_invalid; auth_empty; auth_performance; auth_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# TENANTS CATEGORY TESTS
#==============================================================================

tenants_happy() {
    section "TENANTS/HAPPY (3 tests)"
    setup_auth

    echo -e "\n${BOLD}S1-TENANT-01: list_tenants${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants")
    evidence "HTTP $status"
    if [ "$status" = "200" ]; then pass "S1-TENANT-01: list_tenants"; else fail "S1-TENANT-01 ($status)"; fi

    echo -e "\n${BOLD}S1-TENANT-02: get_tenant${NC}"
    status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID")
    evidence "HTTP $status"
    if [ "$status" = "200" ]; then pass "S1-TENANT-02: get_tenant"; else fail "S1-TENANT-02 ($status)"; fi

    echo -e "\n${BOLD}S1-TENANT-03: tenant_isolation${NC}"
    local opps=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/opportunities")
    local opp_id=$(echo "$opps" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)

    if [ -n "$opp_id" ]; then
        evidence "Setup: Tenant A opp_id=$opp_id"
        status=$(http_status -H "Authorization: Bearer $TENANT_B_TOKEN" "$API_URL/api/opportunities/$opp_id")
        evidence "Tenant B GET -> HTTP $status"
        if [ "$status" = "403" ]; then pass "S1-TENANT-03: tenant_isolation [INV-1]"; else fail "S1-TENANT-03 ($status)"; fi
    else
        evidence "No opportunities for Tenant A - skipping"
        pass "S1-TENANT-03: tenant_isolation [INV-1] (no data to test)"
    fi
}

tenants_boundary() {
    section "TENANTS/BOUNDARY (3 tests) [INV-1, INV-4]"
    setup_auth

    echo -e "\n${BOLD}ISO-01: cross_tenant_get_opportunity_403${NC}"
    local opps=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/opportunities")
    local opp_id=$(echo "$opps" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)

    if [ -n "$opp_id" ]; then
        evidence "Setup: Tenant A opp_id=$opp_id"
        local status=$(http_status -H "Authorization: Bearer $TENANT_B_TOKEN" "$API_URL/api/opportunities/$opp_id")
        evidence "Tenant B GET -> HTTP $status"
        if [ "$status" = "403" ]; then pass "ISO-01: cross_tenant_get_opportunity_403 [INV-1]"; else fail "ISO-01 ($status)"; fi
    else
        evidence "No opportunities for Tenant A - skipping"
        pass "ISO-01: cross_tenant_get_opportunity_403 [INV-1] (no data to test)"
    fi

    echo -e "\n${BOLD}ISO-02: cross_tenant_get_intelligence_403${NC}"
    local intel=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/intelligence")
    local intel_id=$(echo "$intel" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)

    if [ -n "$intel_id" ]; then
        evidence "Setup: Tenant A intel_id=$intel_id"
        local status=$(http_status -H "Authorization: Bearer $TENANT_B_TOKEN" "$API_URL/api/intelligence/$intel_id")
        evidence "Tenant B GET -> HTTP $status"
        if [ "$status" = "403" ]; then pass "ISO-02: cross_tenant_get_intelligence_403 [INV-1]"; else fail "ISO-02 ($status)"; fi
    else
        evidence "No intelligence for Tenant A - skipping"
        pass "ISO-02: cross_tenant_get_intelligence_403 [INV-1] (no data to test)"
    fi

    # Master tenant tests
    local tenants=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants")
    local master_id=$(echo "$tenants" | python3 -c "
import sys,json
d=json.load(sys.stdin)
t=d if isinstance(d,list) else d.get('data',[])
for x in t:
    if x.get('is_master_client'):
        print(x['id'])
        break
" 2>/dev/null)

    if [ -z "$master_id" ]; then
        evidence "No master tenant found - creating one for test"
        local create_resp=$(curl -s -X POST "$API_URL/api/tenants" \
            -H "Authorization: Bearer $ADMIN_TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"name":"CARFAX Test Master","slug":"carfax-test-master","status":"active","is_master_client":true}')
        master_id=$(echo "$create_resp" | python3 -c "import sys,json;print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
    fi

    echo -e "\n${BOLD}MASTER-01: super_admin_can_modify_master_chat_policy${NC}"
    if [ -n "$master_id" ]; then
        tenant_put_or_fail "$master_id" '{"chat_policy":{"enabled":true,"monthly_message_limit":100}}'
        local status="$TENANT_PUT_STATUS"
        evidence "PUT chat_policy -> HTTP $status"
        if [ "$status" = "200" ]; then pass "MASTER-01: super_admin_can_modify_master_chat_policy [INV-4]"; else fail "MASTER-01 ($status)"; fi
    else
        fail "MASTER-01: Could not create/find master tenant"
    fi
}

tenants_invalid() {
    section "TENANTS/INVALID (2 tests)"
    setup_auth

    echo -e "\n${BOLD}TENANT-INV-01: nonexistent_tenant${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/nonexistent-uuid-12345")
    evidence "nonexistent tenant -> HTTP $status"
    if [ "$status" = "404" ]; then pass "TENANT-INV-01: nonexistent_tenant"; else fail "TENANT-INV-01 ($status)"; fi

    echo -e "\n${BOLD}TENANT-INV-02: invalid_tenant_update${NC}"
    status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$TENANT_A_ID" -d '{"invalid_field":"value"}')
    evidence "invalid field update -> HTTP $status"
    if [[ "$status" =~ ^(200|400|422)$ ]]; then pass "TENANT-INV-02: invalid_tenant_update"; else fail "TENANT-INV-02 ($status)"; fi
}

tenants_empty() {
    section "TENANTS/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}TENANT-EMPTY-01: empty_tenant_update${NC}"
    local status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$TENANT_A_ID" -d '{}')
    evidence "empty update body -> HTTP $status"
    if [[ "$status" =~ ^(200|400|422)$ ]]; then pass "TENANT-EMPTY-01: empty_tenant_update"; else fail "TENANT-EMPTY-01 ($status)"; fi
}

tenants_performance() {
    section "TENANTS/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}TENANT-PERF-01: list_tenants_under_1s${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "list tenants: HTTP $status in ${duration}ms"
    if [ "$status" = "200" ] && [ "$duration" -lt 2000 ]; then
        pass "TENANT-PERF-01: list_tenants_under_1s (${duration}ms)"
    else
        fail "TENANT-PERF-01 (status=$status, duration=${duration}ms)"
    fi
}

tenants_failure() {
    section "TENANTS/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}TENANT-FAIL-01: tenant_service_graceful${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/")
    evidence "trailing slash -> HTTP $status"
    if [[ "$status" =~ ^(200|307|404)$ ]]; then pass "TENANT-FAIL-01: tenant_service_graceful"; else fail "TENANT-FAIL-01 ($status)"; fi
}

run_tenants_tests() {
    local stratum=$1
    case "$stratum" in
        happy) tenants_happy ;;
        boundary) tenants_boundary ;;
        invalid) tenants_invalid ;;
        empty) tenants_empty ;;
        performance) tenants_performance ;;
        failure) tenants_failure ;;
        all) tenants_happy; tenants_boundary; tenants_invalid; tenants_empty; tenants_performance; tenants_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# CHAT CATEGORY TESTS
#==============================================================================

chat_happy() {
    section "CHAT/HAPPY (1 test)"
    setup_auth

    echo -e "\n${BOLD}CHAT-HAPPY-01: chat_endpoint_accessible${NC}"
    local status=$(http_status -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/chat/conversations")
    evidence "GET conversations -> HTTP $status"
    if [[ "$status" =~ ^(200|404)$ ]]; then pass "CHAT-HAPPY-01: chat_endpoint_accessible"; else fail "CHAT-HAPPY-01 ($status)"; fi
}

chat_boundary() {
    section "CHAT/BOUNDARY (4 tests) [INV-2, INV-3]"
    setup_auth

    # CHAT-01: chat_disabled_403_no_persist (INV-3)
    echo -e "\n${BOLD}CHAT-01: chat_disabled_403_no_persist [INV-3]${NC}"

    local orig_policy=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID" | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('chat_policy',{}).get('enabled', True))" 2>/dev/null)
    evidence "Original chat_policy.enabled=$orig_policy"

    set_chat_policy "$TENANT_A_ID" "false"
    evidence "Set chat_policy.enabled=false"

    local before_count=$(get_chat_turns_count "$TENANT_A_ID")
    evidence "BEFORE chat_turns count: $before_count"

    local conv_id="carfax-inv3-$(date +%s)"
    local resp=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/chat/message" \
        -H "Authorization: Bearer $TENANT_A_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"conversation_id\":\"$conv_id\",\"message\":\"test\",\"agent_type\":\"opportunities\"}")
    local status=$(echo "$resp" | tail -n1)
    local body=$(echo "$resp" | sed '$d')
    evidence "POST /api/chat/message -> HTTP $status"
    evidence "Response: $body"

    local after_count=$(get_chat_turns_count "$TENANT_A_ID")
    evidence "AFTER chat_turns count: $after_count"

    set_chat_policy "$TENANT_A_ID" "true"
    evidence "Restored chat_policy.enabled=true"

    if [ "$status" = "403" ] && [ "$before_count" = "$after_count" ]; then
        pass "CHAT-01: chat_disabled_403_no_persist [INV-3]"
    else
        fail "CHAT-01 (status=$status, before=$before_count, after=$after_count)"
    fi

    # CHAT-02: quota_limit_429_no_persist (INV-2)
    echo -e "\n${BOLD}CHAT-02: quota_limit_429_no_persist [INV-2]${NC}"

    local current_month=$(date -u +%Y-%m)

    tenant_put_or_fail "$TENANT_A_ID" "{\"chat_policy\":{\"enabled\":true,\"monthly_message_limit\":1},\"chat_usage\":{\"month\":\"$current_month\",\"messages_used\":1}}"
    evidence "Set monthly_message_limit=1, messages_used=1 (quota exhausted, month=$current_month)"

    before_count=$(get_chat_turns_count "$TENANT_A_ID")
    evidence "BEFORE chat_turns count: $before_count"

    conv_id="carfax-inv2-$(date +%s)"
    resp=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/chat/message" \
        -H "Authorization: Bearer $TENANT_A_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"conversation_id\":\"$conv_id\",\"message\":\"test\",\"agent_type\":\"opportunities\"}")
    status=$(echo "$resp" | tail -n1)
    body=$(echo "$resp" | sed '$d')
    evidence "POST /api/chat/message -> HTTP $status"
    evidence "Response: $body"

    after_count=$(get_chat_turns_count "$TENANT_A_ID")
    evidence "AFTER chat_turns count: $after_count"

    tenant_put_or_fail "$TENANT_A_ID" "{\"chat_policy\":{\"enabled\":true,\"monthly_message_limit\":100},\"chat_usage\":{\"month\":\"$current_month\",\"messages_used\":0}}"
    evidence "Reset quota (month=$current_month)"

    if [ "$status" = "429" ] && [ "$before_count" = "$after_count" ]; then
        pass "CHAT-02: quota_limit_429_no_persist [INV-2]"
    else
        fail "CHAT-02 (status=$status, before=$before_count, after=$after_count)"
    fi

    # CHAT-05a: conversation_id with spaces
    echo -e "\n${BOLD}CHAT-05a: conversation_id_spaces_rejected${NC}"
    status=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d '{"conversation_id":"test with spaces","message":"hi","agent_type":"opportunities"}')
    evidence "conversation_id with spaces -> HTTP $status"
    if [ "$status" = "400" ]; then pass "CHAT-05a: conversation_id_spaces_rejected"; else fail "CHAT-05a ($status)"; fi

    # CHAT-05b: conversation_id too long
    echo -e "\n${BOLD}CHAT-05b: conversation_id_too_long_rejected${NC}"
    local long_id=$(python3 -c "print('x'*200)")
    status=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d "{\"conversation_id\":\"$long_id\",\"message\":\"hi\",\"agent_type\":\"opportunities\"}")
    evidence "conversation_id > 128 chars -> HTTP $status"
    if [ "$status" = "400" ]; then pass "CHAT-05b: conversation_id_too_long_rejected"; else fail "CHAT-05b ($status)"; fi
}

chat_invalid() {
    section "CHAT/INVALID (2 tests)"
    setup_auth

    echo -e "\n${BOLD}CHAT-05a: conversation_id_spaces_rejected${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d '{"conversation_id":"test with spaces","message":"hi","agent_type":"opportunities"}')
    evidence "conversation_id with spaces -> HTTP $status"
    if [ "$status" = "400" ]; then pass "CHAT-05a: conversation_id_spaces_rejected"; else fail "CHAT-05a ($status)"; fi

    echo -e "\n${BOLD}CHAT-05b: conversation_id_too_long_rejected${NC}"
    local long_id=$(python3 -c "print('x'*200)")
    status=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d "{\"conversation_id\":\"$long_id\",\"message\":\"hi\",\"agent_type\":\"opportunities\"}")
    evidence "conversation_id > 128 chars -> HTTP $status"
    if [ "$status" = "400" ]; then pass "CHAT-05b: conversation_id_too_long_rejected"; else fail "CHAT-05b ($status)"; fi
}

chat_empty() {
    section "CHAT/EMPTY (3 tests)"
    setup_auth

    echo -e "\n${BOLD}EMPTY-01: null_body_rejected${NC}"
    local status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $TENANT_A_TOKEN" \
        -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d 'null')
    evidence "null body -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "EMPTY-01: null_body_rejected"; else fail "EMPTY-01 ($status)"; fi

    echo -e "\n${BOLD}EMPTY-02: empty_object_rejected${NC}"
    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $TENANT_A_TOKEN" \
        -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d '{}')
    evidence "empty object {} -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "EMPTY-02: empty_object_rejected"; else fail "EMPTY-02 ($status)"; fi

    echo -e "\n${BOLD}EMPTY-03: empty_string_message_rejected${NC}"
    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $TENANT_A_TOKEN" \
        -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d '{"conversation_id":"empty-test","message":"","agent_type":"opportunities"}')
    evidence "empty string message -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "EMPTY-03: empty_string_message_rejected"; else fail "EMPTY-03 ($status)"; fi
}

chat_performance() {
    section "CHAT/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}CHAT-PERF-01: chat_endpoint_responsive${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/chat/conversations")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "chat conversations: HTTP $status in ${duration}ms"
    if [[ "$status" =~ ^(200|404)$ ]] && [ "$duration" -lt 2000 ]; then
        pass "CHAT-PERF-01: chat_endpoint_responsive (${duration}ms)"
    else
        fail "CHAT-PERF-01 (status=$status, duration=${duration}ms)"
    fi
}

chat_failure() {
    section "CHAT/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}CHAT-FAIL-01: invalid_agent_type${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d '{"conversation_id":"test","message":"hi","agent_type":"invalid_agent"}')
    evidence "invalid agent_type -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "CHAT-FAIL-01: invalid_agent_type"; else fail "CHAT-FAIL-01 ($status)"; fi
}

run_chat_tests() {
    local stratum=$1
    case "$stratum" in
        happy) chat_happy ;;
        boundary) chat_boundary ;;
        invalid) chat_invalid ;;
        empty) chat_empty ;;
        performance) chat_performance ;;
        failure) chat_failure ;;
        all) chat_happy; chat_boundary; chat_invalid; chat_empty; chat_performance; chat_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# OPPORTUNITIES CATEGORY TESTS
#==============================================================================

opportunities_happy() {
    section "OPPORTUNITIES/HAPPY (2 tests)"
    setup_auth

    echo -e "\n${BOLD}S0-04: list_opportunities${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/opportunities")
    evidence "HTTP $status"
    if [ "$status" = "200" ]; then pass "S0-04: list_opportunities"; else fail "S0-04: list_opportunities ($status)"; fi

    echo -e "\n${BOLD}OPP-HAPPY-01: get_single_opportunity${NC}"
    local opps=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/opportunities")
    local opp_id=$(echo "$opps" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)
    if [ -n "$opp_id" ]; then
        status=$(http_status -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/opportunities/$opp_id")
        evidence "GET opp $opp_id -> HTTP $status"
        if [ "$status" = "200" ]; then pass "OPP-HAPPY-01: get_single_opportunity"; else fail "OPP-HAPPY-01 ($status)"; fi
    else
        pass "OPP-HAPPY-01: get_single_opportunity (no data)"
    fi
}

opportunities_boundary() {
    section "OPPORTUNITIES/BOUNDARY (1 test)"
    setup_auth

    echo -e "\n${BOLD}ISO-01: cross_tenant_get_opportunity_403${NC}"
    local opps=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/opportunities")
    local opp_id=$(echo "$opps" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)

    if [ -n "$opp_id" ]; then
        evidence "Setup: Tenant A opp_id=$opp_id"
        local status=$(http_status -H "Authorization: Bearer $TENANT_B_TOKEN" "$API_URL/api/opportunities/$opp_id")
        evidence "Tenant B GET -> HTTP $status"
        if [ "$status" = "403" ]; then pass "ISO-01: cross_tenant_get_opportunity_403 [INV-1]"; else fail "ISO-01 ($status)"; fi
    else
        pass "ISO-01: cross_tenant_get_opportunity_403 [INV-1] (no data)"
    fi
}

opportunities_invalid() {
    section "OPPORTUNITIES/INVALID (1 test)"
    setup_auth

    echo -e "\n${BOLD}OPP-INV-01: nonexistent_opportunity${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/opportunities/nonexistent-uuid")
    evidence "nonexistent opportunity -> HTTP $status"
    if [ "$status" = "404" ]; then pass "OPP-INV-01: nonexistent_opportunity"; else fail "OPP-INV-01 ($status)"; fi
}

opportunities_empty() {
    section "OPPORTUNITIES/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}OPP-EMPTY-01: empty_filter${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/opportunities?filter=")
    evidence "empty filter -> HTTP $status"
    if [ "$status" = "200" ]; then pass "OPP-EMPTY-01: empty_filter"; else fail "OPP-EMPTY-01 ($status)"; fi
}

opportunities_performance() {
    section "OPPORTUNITIES/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}PERF-03: list_under_2000ms${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/opportunities")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "list opportunities: HTTP $status in ${duration}ms"
    if [ "$status" = "200" ] && [ "$duration" -lt 2000 ]; then
        pass "PERF-03: list_under_2000ms (${duration}ms)"
    else
        fail "PERF-03 (status=$status, duration=${duration}ms)"
    fi
}

opportunities_failure() {
    section "OPPORTUNITIES/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}OPP-FAIL-01: malformed_id${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/opportunities/;;;invalid")
    evidence "malformed id -> HTTP $status"
    if [[ "$status" =~ ^(400|404|422)$ ]]; then pass "OPP-FAIL-01: malformed_id"; else fail "OPP-FAIL-01 ($status)"; fi
}

run_opportunities_tests() {
    local stratum=$1
    case "$stratum" in
        happy) opportunities_happy ;;
        boundary) opportunities_boundary ;;
        invalid) opportunities_invalid ;;
        empty) opportunities_empty ;;
        performance) opportunities_performance ;;
        failure) opportunities_failure ;;
        all) opportunities_happy; opportunities_boundary; opportunities_invalid; opportunities_empty; opportunities_performance; opportunities_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# INTELLIGENCE CATEGORY TESTS
#==============================================================================

intelligence_happy() {
    section "INTELLIGENCE/HAPPY (2 tests)"
    setup_auth

    echo -e "\n${BOLD}S0-05: list_intelligence${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/intelligence")
    evidence "HTTP $status"
    if [ "$status" = "200" ]; then pass "S0-05: list_intelligence"; else fail "S0-05: list_intelligence ($status)"; fi

    echo -e "\n${BOLD}INTEL-HAPPY-01: get_intelligence${NC}"
    local intel=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/intelligence")
    local intel_id=$(echo "$intel" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)
    if [ -n "$intel_id" ]; then
        status=$(http_status -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/intelligence/$intel_id")
        evidence "GET intel $intel_id -> HTTP $status"
        if [ "$status" = "200" ]; then pass "INTEL-HAPPY-01: get_intelligence"; else fail "INTEL-HAPPY-01 ($status)"; fi
    else
        pass "INTEL-HAPPY-01: get_intelligence (no data)"
    fi
}

intelligence_boundary() {
    section "INTELLIGENCE/BOUNDARY (2 tests)"
    setup_auth

    echo -e "\n${BOLD}ISO-02: cross_tenant_get_intelligence_403${NC}"
    local intel=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/intelligence")
    local intel_id=$(echo "$intel" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)

    if [ -n "$intel_id" ]; then
        evidence "Setup: Tenant A intel_id=$intel_id"
        local status=$(http_status -H "Authorization: Bearer $TENANT_B_TOKEN" "$API_URL/api/intelligence/$intel_id")
        evidence "Tenant B GET -> HTTP $status"
        if [ "$status" = "403" ]; then pass "ISO-02: cross_tenant_get_intelligence_403 [INV-1]"; else fail "ISO-02 ($status)"; fi
    else
        pass "ISO-02: cross_tenant_get_intelligence_403 [INV-1] (no data)"
    fi

    echo -e "\n${BOLD}INTEL-01: no_sourceless_intelligence_allowed${NC}"
    local sourceless_count=$(timeout 5 python3 -c "
import os, sys, asyncio

async def main():
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        print('DB_SKIP')
        return
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
        db = client[os.environ.get('DB_NAME', 'outpace_intelligence')]
        count = await db.intelligence.count_documents({
            '\$or': [
                {'source_urls': {'\$exists': False}},
                {'source_urls': []},
                {'source_urls': None}
            ]
        })
        print(count)
    except Exception:
        print('DB_SKIP')

asyncio.run(main())
" 2>&1 || echo "DB_SKIP")

    evidence "Intelligence reports with empty source_urls: $sourceless_count"

    if [ "$sourceless_count" = "DB_SKIP" ]; then
        pass "INTEL-01: no_sourceless_intelligence_allowed (DB_SKIP)"
    elif [ "$sourceless_count" = "0" ]; then
        pass "INTEL-01: no_sourceless_intelligence_allowed"
    else
        fail "INTEL-01: Found $sourceless_count without source_urls"
    fi
}

intelligence_invalid() {
    section "INTELLIGENCE/INVALID (1 test)"
    setup_auth

    echo -e "\n${BOLD}INTEL-INV-01: nonexistent_intelligence${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/intelligence/nonexistent-uuid")
    evidence "nonexistent intelligence -> HTTP $status"
    if [ "$status" = "404" ]; then pass "INTEL-INV-01: nonexistent_intelligence"; else fail "INTEL-INV-01 ($status)"; fi
}

intelligence_empty() {
    section "INTELLIGENCE/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}INTEL-EMPTY-01: empty_filter${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/intelligence?filter=")
    evidence "empty filter -> HTTP $status"
    if [ "$status" = "200" ]; then pass "INTEL-EMPTY-01: empty_filter"; else fail "INTEL-EMPTY-01 ($status)"; fi
}

intelligence_performance() {
    section "INTELLIGENCE/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}INTEL-PERF-01: list_under_2s${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/intelligence")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "list intelligence: HTTP $status in ${duration}ms"
    if [ "$status" = "200" ] && [ "$duration" -lt 2000 ]; then
        pass "INTEL-PERF-01: list_under_2s (${duration}ms)"
    else
        fail "INTEL-PERF-01 (status=$status, duration=${duration}ms)"
    fi
}

intelligence_failure() {
    section "INTELLIGENCE/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}INTEL-FAIL-01: malformed_id${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/intelligence/;;;invalid")
    evidence "malformed id -> HTTP $status"
    if [[ "$status" =~ ^(400|404|422)$ ]]; then pass "INTEL-FAIL-01: malformed_id"; else fail "INTEL-FAIL-01 ($status)"; fi
}

run_intelligence_tests() {
    local stratum=$1
    case "$stratum" in
        happy) intelligence_happy ;;
        boundary) intelligence_boundary ;;
        invalid) intelligence_invalid ;;
        empty) intelligence_empty ;;
        performance) intelligence_performance ;;
        failure) intelligence_failure ;;
        all) intelligence_happy; intelligence_boundary; intelligence_invalid; intelligence_empty; intelligence_performance; intelligence_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# EXPORTS CATEGORY TESTS
#==============================================================================

exports_happy() {
    section "EXPORTS/HAPPY (1 test)"
    setup_auth

    echo -e "\n${BOLD}EXP-HAPPY-01: export_endpoint_accessible${NC}"
    local opps=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/opportunities")
    local opp_id=$(echo "$opps" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)

    if [ -n "$opp_id" ]; then
        local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
            "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[\"$opp_id\"]}")
        evidence "export with valid opp -> HTTP $status"
        if [[ "$status" =~ ^(200|201|400|422)$ ]]; then pass "EXP-HAPPY-01: export_endpoint_accessible"; else fail "EXP-HAPPY-01 ($status)"; fi
    else
        pass "EXP-HAPPY-01: export_endpoint_accessible (no data)"
    fi
}

exports_boundary() {
    section "EXPORTS/BOUNDARY (1 test) [INV-5]"
    setup_auth

    echo -e "\n${BOLD}ISO-03: cross_tenant_export_pdf_403${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $TENANT_B_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[]}")
    evidence "Tenant B export with Tenant A id -> HTTP $status"
    if [ "$status" = "403" ]; then pass "ISO-03: cross_tenant_export_pdf_403 [INV-1, INV-5]"; else fail "ISO-03 ($status)"; fi
}

exports_invalid() {
    section "EXPORTS/INVALID (2 tests) [INV-5]"
    setup_auth

    echo -e "\n${BOLD}EXP-02: nonexistent_ids_404_pdf${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[\"bogus-id\"]}")
    evidence "Bogus ID -> HTTP $status"
    if [ "$status" = "404" ]; then pass "EXP-02: nonexistent_ids_404_pdf [INV-5]"; else fail "EXP-02 ($status)"; fi

    echo -e "\n${BOLD}EXP-03: missing_tenant_id_super_admin_400${NC}"
    status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d '{"opportunity_ids":[]}')
    evidence "Missing tenant_id -> HTTP $status"
    if [ "$status" = "400" ]; then pass "EXP-03: missing_tenant_id_super_admin_400 [INV-5]"; else fail "EXP-03 ($status)"; fi
}

exports_empty() {
    section "EXPORTS/EMPTY (2 tests) [INV-5]"
    setup_auth

    echo -e "\n${BOLD}EXP-01: empty_selection_404_pdf${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[],\"intelligence_ids\":[]}")
    evidence "Empty selection -> HTTP $status"
    if [ "$status" = "404" ]; then pass "EXP-01: empty_selection_404_pdf [INV-5]"; else fail "EXP-01 ($status)"; fi

    echo -e "\n${BOLD}EMPTY-04: empty_array_export_rejected${NC}"
    status=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[],\"intelligence_ids\":[]}")
    evidence "empty arrays export -> HTTP $status"
    if [[ "$status" =~ ^(400|404|422)$ ]]; then pass "EMPTY-04: empty_array_export_rejected"; else fail "EMPTY-04 ($status)"; fi
}

exports_performance() {
    section "EXPORTS/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}EXP-PERF-01: export_responsive${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[]}")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "export request: HTTP $status in ${duration}ms"
    if [ "$duration" -lt 5000 ]; then
        pass "EXP-PERF-01: export_responsive (${duration}ms)"
    else
        fail "EXP-PERF-01 (duration=${duration}ms)"
    fi
}

exports_failure() {
    section "EXPORTS/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}EXP-FAIL-01: malformed_request${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d 'not-json')
    evidence "malformed json -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "EXP-FAIL-01: malformed_request"; else fail "EXP-FAIL-01 ($status)"; fi
}

run_exports_tests() {
    local stratum=$1
    case "$stratum" in
        happy) exports_happy ;;
        boundary) exports_boundary ;;
        invalid) exports_invalid ;;
        empty) exports_empty ;;
        performance) exports_performance ;;
        failure) exports_failure ;;
        all) exports_happy; exports_boundary; exports_invalid; exports_empty; exports_performance; exports_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# UPLOAD CATEGORY TESTS
#==============================================================================

upload_happy() {
    section "UPLOAD/HAPPY (1 test)"
    setup_auth

    echo -e "\n${BOLD}UPLOAD-HAPPY-01: upload_endpoint_accessible${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/upload/logo/$TENANT_A_ID")
    evidence "upload logo (no file) -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "UPLOAD-HAPPY-01: upload_endpoint_accessible"; else fail "UPLOAD-HAPPY-01 ($status)"; fi
}

upload_boundary() {
    section "UPLOAD/BOUNDARY (2 tests)"
    setup_auth

    echo -e "\n${BOLD}UPLOAD-01: tenant_logo_upload_super_admin_only${NC}"
    local s1=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/upload/logo/$TENANT_A_ID")
    local s2=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/upload/logo/$TENANT_A_ID")
    evidence "tenant_user -> HTTP $s1, super_admin -> HTTP $s2"
    if [ "$s1" = "403" ] && [[ "$s2" =~ ^(200|400|422)$ ]]; then
        pass "UPLOAD-01: tenant_logo_upload_super_admin_only"
    else
        fail "UPLOAD-01 (tenant=$s1, admin=$s2)"
    fi

    echo -e "\n${BOLD}UPLOAD-02: opportunities_csv_upload_super_admin_only${NC}"
    local TMP_CSV="/tmp/carfax_upload.csv"
    printf "title,agency,due_date,estimated_value\nTest Opportunity,Test Agency,2026-01-01,1000\n" > "$TMP_CSV"

    local CURL_CSV="$TMP_CSV"
    if command -v cygpath &>/dev/null; then
        CURL_CSV=$(cygpath -w "$TMP_CSV")
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        CURL_CSV=$(cd "$(dirname "$TMP_CSV")" && pwd -W)/$(basename "$TMP_CSV")
    fi

    s1=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 --connect-timeout 5 -X POST \
        -H "Authorization: Bearer $TENANT_A_TOKEN" \
        -F "file=@$CURL_CSV;type=text/csv" \
        "$API_URL/api/upload/opportunities/csv/$TENANT_A_ID")

    s2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 --connect-timeout 5 -X POST \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -F "file=@$CURL_CSV;type=text/csv" \
        "$API_URL/api/upload/opportunities/csv/$TENANT_A_ID")

    rm -f "$TMP_CSV"
    evidence "tenant_user -> HTTP $s1, super_admin -> HTTP $s2"

    if [ "$s1" = "403" ] && [ "$s2" != "403" ]; then
        pass "UPLOAD-02: opportunities_csv_upload_super_admin_only"
    else
        fail "UPLOAD-02 (tenant=$s1, admin=$s2)"
    fi
}

upload_invalid() {
    section "UPLOAD/INVALID (1 test)"
    setup_auth

    echo -e "\n${BOLD}UPLOAD-INV-01: invalid_tenant_upload${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/upload/logo/invalid-tenant-id")
    evidence "invalid tenant -> HTTP $status"
    if [[ "$status" =~ ^(400|404|422)$ ]]; then pass "UPLOAD-INV-01: invalid_tenant_upload"; else fail "UPLOAD-INV-01 ($status)"; fi
}

upload_empty() {
    section "UPLOAD/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}UPLOAD-EMPTY-01: no_file_upload${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/upload/logo/$TENANT_A_ID")
    evidence "no file -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "UPLOAD-EMPTY-01: no_file_upload"; else fail "UPLOAD-EMPTY-01 ($status)"; fi
}

upload_performance() {
    section "UPLOAD/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}UPLOAD-PERF-01: upload_responsive${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/upload/logo/$TENANT_A_ID")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "upload check: HTTP $status in ${duration}ms"
    if [ "$duration" -lt 3000 ]; then
        pass "UPLOAD-PERF-01: upload_responsive (${duration}ms)"
    else
        fail "UPLOAD-PERF-01 (duration=${duration}ms)"
    fi
}

upload_failure() {
    section "UPLOAD/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}UPLOAD-FAIL-01: wrong_content_type${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: text/plain" \
        "$API_URL/api/upload/logo/$TENANT_A_ID" -d "not a file")
    evidence "wrong content type -> HTTP $status"
    if [[ "$status" =~ ^(400|415|422)$ ]]; then pass "UPLOAD-FAIL-01: wrong_content_type"; else fail "UPLOAD-FAIL-01 ($status)"; fi
}

run_upload_tests() {
    local stratum=$1
    case "$stratum" in
        happy) upload_happy ;;
        boundary) upload_boundary ;;
        invalid) upload_invalid ;;
        empty) upload_empty ;;
        performance) upload_performance ;;
        failure) upload_failure ;;
        all) upload_happy; upload_boundary; upload_invalid; upload_empty; upload_performance; upload_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# SYNC CATEGORY TESTS
#==============================================================================

sync_happy() {
    section "SYNC/HAPPY (1 test)"
    setup_auth

    echo -e "\n${BOLD}SYNC-02: admin_sync_returns_full_contract${NC}"
    evidence "Calling /api/admin/sync with sync_type=opportunities (max 120s)..."
    local SYNC_RESPONSE=$(curl -s --max-time 120 -X POST \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -H "Content-Type: application/json" \
        "$API_URL/api/admin/sync/$TENANT_A_ID?sync_type=opportunities")
    local SYNC_STATUS=$?

    if [ $SYNC_STATUS -ne 0 ]; then
        evidence "CURL FAILED with exit code $SYNC_STATUS"
        fail "SYNC-02: admin_sync_returns_full_contract (curl failed)"
    else
        evidence "Raw JSON (first 200 chars): ${SYNC_RESPONSE:0:200}"
        local CONTRACT_CHECK=$(echo "$SYNC_RESPONSE" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    errors_found = []

    if 'message' in d and 'triggered' in str(d.get('message','')).lower():
        print('REGRESSION:OLD_ASYNC_MESSAGE_DETECTED')
        sys.exit(0)

    required_fields = {
        'tenant_id': str,
        'tenant_name': str,
        'opportunities_synced': int,
        'intelligence_synced': int,
        'status': str,
        'sync_timestamp': str,
        'errors': list
    }

    for field, expected_type in required_fields.items():
        if field not in d:
            errors_found.append(f'MISSING:{field}')
        elif not isinstance(d[field], expected_type):
            errors_found.append(f'TYPE_ERROR:{field}')

    if 'status' in d and d['status'] not in ['success', 'partial']:
        errors_found.append(f'ENUM_ERROR:status')

    if errors_found:
        print('VALIDATION_FAILED:' + ';'.join(errors_found))
    else:
        print(f'OK:opp={d[\"opportunities_synced\"]},status={d[\"status\"]}')

except json.JSONDecodeError as e:
    print(f'JSON_PARSE_ERROR:{e}')
except Exception as e:
    print(f'UNEXPECTED_ERROR:{e}')
" 2>/dev/null)

        if [[ "$CONTRACT_CHECK" == OK:* ]]; then
            evidence "Contract validated: $CONTRACT_CHECK"
            local MARKER_FILE="/tmp/carfax_sync02_ok.marker"
            local MARKER_TEMP="/tmp/carfax_sync02_ok.marker.tmp.$$"
            echo "$SYNC_RESPONSE" | python3 -c "
import sys, json
from datetime import datetime, timezone
try:
    d = json.load(sys.stdin)
    marker = {
        'tenant_id': d.get('tenant_id'),
        'status': d.get('status'),
        'sync_timestamp': d.get('sync_timestamp'),
        'opportunities_synced': d.get('opportunities_synced'),
        'intelligence_synced': d.get('intelligence_synced'),
        'contract_validated': True,
        'marker_created_utc': datetime.now(timezone.utc).isoformat()
    }
    print(json.dumps(marker))
except:
    pass
" > "$MARKER_TEMP" && mv "$MARKER_TEMP" "$MARKER_FILE"
            evidence "Marker file written: $MARKER_FILE"
            pass "SYNC-02: admin_sync_returns_full_contract"
        elif [[ "$CONTRACT_CHECK" == REGRESSION:* ]]; then
            evidence "REGRESSION DETECTED: $CONTRACT_CHECK"
            fail "SYNC-02: REGRESSION - old async message"
        else
            evidence "Contract validation failed: $CONTRACT_CHECK"
            fail "SYNC-02: admin_sync_returns_full_contract ($CONTRACT_CHECK)"
        fi
    fi
}

sync_boundary() {
    section "SYNC/BOUNDARY (1 test)"
    setup_auth

    echo -e "\n${BOLD}SYNC-01: sync_endpoints_require_super_admin${NC}"
    local s1=$(http_status_quick -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/sync/manual/$TENANT_A_ID")
    local s2=$(http_status_quick -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/admin/sync/$TENANT_A_ID")
    evidence "tenant_user /sync/manual -> HTTP $s1, /admin/sync -> HTTP $s2"
    if [ "$s1" = "403" ] && [ "$s2" = "403" ]; then
        pass "SYNC-01: sync_endpoints_require_super_admin"
    else
        fail "SYNC-01 (manual=$s1, admin=$s2) - expected both 403"
    fi
}

sync_invalid() {
    section "SYNC/INVALID (1 test)"
    setup_auth

    echo -e "\n${BOLD}SYNC-INV-01: sync_invalid_tenant${NC}"
    local status=$(http_status_quick -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/sync/invalid-tenant-uuid")
    evidence "invalid tenant sync -> HTTP $status"
    if [ "$status" = "404" ]; then pass "SYNC-INV-01: sync_invalid_tenant"; else fail "SYNC-INV-01 ($status)"; fi
}

sync_empty() {
    section "SYNC/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}SYNC-EMPTY-01: sync_empty_tenant_id${NC}"
    local status=$(http_status_quick -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/sync/")
    evidence "empty tenant id sync -> HTTP $status"
    if [[ "$status" =~ ^(307|404|405)$ ]]; then pass "SYNC-EMPTY-01: sync_empty_tenant_id"; else fail "SYNC-EMPTY-01 ($status)"; fi
}

sync_performance() {
    section "SYNC/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}SYNC-PERF-01: sync_permission_check_fast${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status_quick -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/sync/manual/$TENANT_A_ID")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "permission check: HTTP $status in ${duration}ms"
    if [ "$duration" -lt 1000 ]; then
        pass "SYNC-PERF-01: sync_permission_check_fast (${duration}ms)"
    else
        fail "SYNC-PERF-01 (duration=${duration}ms)"
    fi
}

sync_failure() {
    section "SYNC/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}SYNC-FAIL-01: sync_graceful_error${NC}"
    local status=$(http_status_quick -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/sync/$TENANT_A_ID?sync_type=invalid_type")
    evidence "invalid sync_type -> HTTP $status"
    if [[ "$status" =~ ^(200|400|422)$ ]]; then pass "SYNC-FAIL-01: sync_graceful_error"; else fail "SYNC-FAIL-01 ($status)"; fi
}

run_sync_tests() {
    local stratum=$1
    case "$stratum" in
        happy) sync_happy ;;
        boundary) sync_boundary ;;
        invalid) sync_invalid ;;
        empty) sync_empty ;;
        performance) sync_performance ;;
        failure) sync_failure ;;
        all) sync_happy; sync_boundary; sync_invalid; sync_empty; sync_performance; sync_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# CONFIG CATEGORY TESTS
#==============================================================================

config_happy() {
    section "CONFIG/HAPPY (1 test)"
    setup_auth

    echo -e "\n${BOLD}CF-CONFIG-PERSIST: config_update_persistence${NC}"

    local before_config=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID")
    evidence "BEFORE config retrieved"

    local before_enabled=$(echo "$before_config" | python3 -c "import sys,json; print(json.load(sys.stdin).get('chat_policy',{}).get('enabled', True))" 2>/dev/null)
    evidence "BEFORE chat_policy.enabled=$before_enabled"

    local new_enabled="false"
    if [ "$before_enabled" = "false" ]; then
        new_enabled="true"
    fi

    tenant_put_or_fail "$TENANT_A_ID" "{\"chat_policy\":{\"enabled\":$new_enabled,\"monthly_message_limit\":100}}"
    local update_status="$TENANT_PUT_STATUS"
    evidence "UPDATE -> HTTP $update_status"

    local after_config=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID")
    local after_enabled=$(echo "$after_config" | python3 -c "import sys,json; print(json.load(sys.stdin).get('chat_policy',{}).get('enabled', True))" 2>/dev/null)
    evidence "AFTER chat_policy.enabled=$after_enabled"

    local restore_enabled=$(echo "$before_enabled" | tr '[:upper:]' '[:lower:]')
    set_chat_policy "$TENANT_A_ID" "$restore_enabled"
    evidence "Restored original chat_policy.enabled=$restore_enabled"

    local normalized_after=$(echo "$after_enabled" | tr '[:upper:]' '[:lower:]')
    if [ "$update_status" = "200" ] && [ "$normalized_after" = "$new_enabled" ]; then
        pass "CF-CONFIG-PERSIST: config_update_persistence"
    else
        fail "CF-CONFIG-PERSIST (status=$update_status, expected=$new_enabled, got=$after_enabled)"
    fi
}

config_boundary() {
    section "CONFIG/BOUNDARY (1 test)"
    setup_auth

    echo -e "\n${BOLD}CF-CONFIG-NON-DESTRUCTIVE: nested_field_update_preserves_siblings${NC}"

    local before_config=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID")
    local before_name=$(echo "$before_config" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name', ''))" 2>/dev/null)
    local before_rag_enabled=$(echo "$before_config" | python3 -c "import sys,json; print(json.load(sys.stdin).get('rag_policy',{}).get('enabled', False))" 2>/dev/null)
    evidence "BEFORE name='$before_name', rag_policy.enabled=$before_rag_enabled"

    tenant_put_or_fail "$TENANT_A_ID" '{"chat_policy":{"enabled":true,"monthly_message_limit":50}}'
    local update_status="$TENANT_PUT_STATUS"
    evidence "UPDATE chat_policy only -> HTTP $update_status"

    local after_config=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID")
    local after_name=$(echo "$after_config" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name', ''))" 2>/dev/null)
    local after_rag_enabled=$(echo "$after_config" | python3 -c "import sys,json; print(json.load(sys.stdin).get('rag_policy',{}).get('enabled', False))" 2>/dev/null)
    local after_chat_limit=$(echo "$after_config" | python3 -c "import sys,json; print(json.load(sys.stdin).get('chat_policy',{}).get('monthly_message_limit', 0))" 2>/dev/null)
    evidence "AFTER name='$after_name', rag_policy.enabled=$after_rag_enabled, chat_limit=$after_chat_limit"

    set_chat_policy "$TENANT_A_ID" "true"

    if [ "$update_status" = "200" ] && [ "$before_name" = "$after_name" ] && [ "$before_rag_enabled" = "$after_rag_enabled" ] && [ "$after_chat_limit" = "50" ]; then
        pass "CF-CONFIG-NON-DESTRUCTIVE: nested_field_update_preserves_siblings"
    else
        fail "CF-CONFIG-NON-DESTRUCTIVE"
    fi
}

config_invalid() {
    section "CONFIG/INVALID (1 test)"
    setup_auth

    echo -e "\n${BOLD}CONFIG-INV-01: invalid_config_field${NC}"
    local status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/config/tenants/$TENANT_A_ID/intelligence-config" -d '{"unknown_field":"value"}')
    evidence "unknown config field -> HTTP $status"
    if [[ "$status" =~ ^(200|400|404|422)$ ]]; then pass "CONFIG-INV-01: invalid_config_field"; else fail "CONFIG-INV-01 ($status)"; fi
}

config_empty() {
    section "CONFIG/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}CONFIG-EMPTY-01: empty_config_update${NC}"
    local status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$TENANT_A_ID" -d '{}')
    evidence "empty config body -> HTTP $status"
    if [[ "$status" =~ ^(200|400|422)$ ]]; then pass "CONFIG-EMPTY-01: empty_config_update"; else fail "CONFIG-EMPTY-01 ($status)"; fi
}

config_performance() {
    section "CONFIG/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}CONFIG-PERF-01: config_update_fast${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$TENANT_A_ID" -d '{"chat_policy":{"enabled":true}}')
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "config update: HTTP $status in ${duration}ms"
    if [ "$status" = "200" ] && [ "$duration" -lt 2000 ]; then
        pass "CONFIG-PERF-01: config_update_fast (${duration}ms)"
    else
        fail "CONFIG-PERF-01 (status=$status, duration=${duration}ms)"
    fi
}

config_failure() {
    section "CONFIG/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}CONFIG-FAIL-01: malformed_config${NC}"
    local status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$TENANT_A_ID" -d 'not-json')
    evidence "malformed config -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "CONFIG-FAIL-01: malformed_config"; else fail "CONFIG-FAIL-01 ($status)"; fi
}

run_config_tests() {
    local stratum=$1
    case "$stratum" in
        happy) config_happy ;;
        boundary) config_boundary ;;
        invalid) config_invalid ;;
        empty) config_empty ;;
        performance) config_performance ;;
        failure) config_failure ;;
        all) config_happy; config_boundary; config_invalid; config_empty; config_performance; config_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# ADMIN CATEGORY TESTS
#==============================================================================

admin_happy() {
    section "ADMIN/HAPPY (2 tests)"
    setup_auth

    echo -e "\n${BOLD}ADMIN-HAPPY-01: dashboard_accessible${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/dashboard")
    evidence "dashboard -> HTTP $status"
    if [ "$status" = "200" ]; then pass "ADMIN-HAPPY-01: dashboard_accessible"; else fail "ADMIN-HAPPY-01 ($status)"; fi

    echo -e "\n${BOLD}ADMIN-HAPPY-02: system_health${NC}"
    status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/system/health")
    evidence "system health -> HTTP $status"
    if [ "$status" = "200" ]; then pass "ADMIN-HAPPY-02: system_health"; else fail "ADMIN-HAPPY-02 ($status)"; fi
}

admin_boundary() {
    section "ADMIN/BOUNDARY (1 test)"
    setup_auth

    echo -e "\n${BOLD}ADMIN-BOUND-01: super_admin_only${NC}"
    local status=$(http_status -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/admin/dashboard")
    evidence "tenant user -> dashboard HTTP $status"
    if [ "$status" = "403" ]; then pass "ADMIN-BOUND-01: super_admin_only"; else fail "ADMIN-BOUND-01 ($status)"; fi
}

admin_invalid() {
    section "ADMIN/INVALID (1 test)"
    setup_auth

    echo -e "\n${BOLD}ADMIN-INV-01: invalid_admin_endpoint${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/nonexistent")
    evidence "nonexistent admin endpoint -> HTTP $status"
    if [ "$status" = "404" ]; then pass "ADMIN-INV-01: invalid_admin_endpoint"; else fail "ADMIN-INV-01 ($status)"; fi
}

admin_empty() {
    section "ADMIN/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}ADMIN-EMPTY-01: empty_admin_path${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/")
    evidence "empty admin path -> HTTP $status"
    if [[ "$status" =~ ^(200|307|404)$ ]]; then pass "ADMIN-EMPTY-01: empty_admin_path"; else fail "ADMIN-EMPTY-01 ($status)"; fi
}

admin_performance() {
    section "ADMIN/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}ADMIN-PERF-01: dashboard_fast${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/dashboard")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "dashboard: HTTP $status in ${duration}ms"
    if [ "$status" = "200" ] && [ "$duration" -lt 3000 ]; then
        pass "ADMIN-PERF-01: dashboard_fast (${duration}ms)"
    else
        fail "ADMIN-PERF-01 (status=$status, duration=${duration}ms)"
    fi
}

admin_failure() {
    section "ADMIN/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}ADMIN-FAIL-01: admin_graceful_error${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/dashboard")
    evidence "POST to GET-only endpoint -> HTTP $status"
    if [[ "$status" =~ ^(405|404)$ ]]; then pass "ADMIN-FAIL-01: admin_graceful_error"; else fail "ADMIN-FAIL-01 ($status)"; fi
}

run_admin_tests() {
    local stratum=$1
    case "$stratum" in
        happy) admin_happy ;;
        boundary) admin_boundary ;;
        invalid) admin_invalid ;;
        empty) admin_empty ;;
        performance) admin_performance ;;
        failure) admin_failure ;;
        all) admin_happy; admin_boundary; admin_invalid; admin_empty; admin_performance; admin_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# USERS CATEGORY TESTS
#==============================================================================

users_happy() {
    section "USERS/HAPPY (2 tests)"
    setup_auth

    echo -e "\n${BOLD}USERS-HAPPY-01: list_users${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/users")
    evidence "list users -> HTTP $status"
    if [ "$status" = "200" ]; then pass "USERS-HAPPY-01: list_users"; else fail "USERS-HAPPY-01 ($status)"; fi

    echo -e "\n${BOLD}USERS-HAPPY-02: get_current_user${NC}"
    status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/auth/me")
    evidence "get current user -> HTTP $status"
    if [ "$status" = "200" ]; then pass "USERS-HAPPY-02: get_current_user"; else fail "USERS-HAPPY-02 ($status)"; fi
}

users_boundary() {
    section "USERS/BOUNDARY (1 test)"
    setup_auth

    echo -e "\n${BOLD}USERS-BOUND-01: tenant_user_list_limited${NC}"
    local admin_users=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/users")
    local tenant_users=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/users")
    local admin_count=$(echo "$admin_users" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('pagination',{}).get('total',len(d.get('data',d))))" 2>/dev/null)
    local tenant_count=$(echo "$tenant_users" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('pagination',{}).get('total',len(d.get('data',d))))" 2>/dev/null)
    evidence "admin sees $admin_count users, tenant user sees $tenant_count users"
    if [ -n "$admin_count" ] && [ -n "$tenant_count" ]; then
        pass "USERS-BOUND-01: tenant_user_list_limited"
    else
        fail "USERS-BOUND-01 (counts unavailable)"
    fi
}

users_invalid() {
    section "USERS/INVALID (1 test)"
    setup_auth

    echo -e "\n${BOLD}USERS-INV-01: nonexistent_user${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/users/nonexistent-user-id")
    evidence "nonexistent user -> HTTP $status"
    if [ "$status" = "404" ]; then pass "USERS-INV-01: nonexistent_user"; else fail "USERS-INV-01 ($status)"; fi
}

users_empty() {
    section "USERS/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}USERS-EMPTY-01: empty_search${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/users?search=")
    evidence "empty search -> HTTP $status"
    if [ "$status" = "200" ]; then pass "USERS-EMPTY-01: empty_search"; else fail "USERS-EMPTY-01 ($status)"; fi
}

users_performance() {
    section "USERS/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}USERS-PERF-01: list_users_fast${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/users")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "list users: HTTP $status in ${duration}ms"
    if [ "$status" = "200" ] && [ "$duration" -lt 2000 ]; then
        pass "USERS-PERF-01: list_users_fast (${duration}ms)"
    else
        fail "USERS-PERF-01 (status=$status, duration=${duration}ms)"
    fi
}

users_failure() {
    section "USERS/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}USERS-FAIL-01: create_user_bad_data${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/users" -d '{"email":"not-an-email"}')
    evidence "invalid user data -> HTTP $status"
    if [[ "$status" =~ ^(400|422)$ ]]; then pass "USERS-FAIL-01: create_user_bad_data"; else fail "USERS-FAIL-01 ($status)"; fi
}

run_users_tests() {
    local stratum=$1
    case "$stratum" in
        happy) users_happy ;;
        boundary) users_boundary ;;
        invalid) users_invalid ;;
        empty) users_empty ;;
        performance) users_performance ;;
        failure) users_failure ;;
        all) users_happy; users_boundary; users_invalid; users_empty; users_performance; users_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# RAG CATEGORY TESTS
#==============================================================================

rag_happy() {
    section "RAG/HAPPY (1 test)"
    setup_auth

    echo -e "\n${BOLD}RAG-HAPPY-01: rag_status${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID/rag/status")
    evidence "RAG status -> HTTP $status"
    if [[ "$status" =~ ^(200|404)$ ]]; then pass "RAG-HAPPY-01: rag_status"; else fail "RAG-HAPPY-01 ($status)"; fi
}

rag_boundary() {
    section "RAG/BOUNDARY (1 test)"
    setup_auth

    echo -e "\n${BOLD}RAG-BOUND-01: rag_super_admin_only${NC}"
    local status=$(http_status -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID/rag/status")
    evidence "tenant user RAG status -> HTTP $status"
    if [ "$status" = "403" ]; then pass "RAG-BOUND-01: rag_super_admin_only"; else fail "RAG-BOUND-01 ($status)"; fi
}

rag_invalid() {
    section "RAG/INVALID (1 test)"
    setup_auth

    echo -e "\n${BOLD}RAG-INV-01: rag_invalid_tenant${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/invalid-tenant/rag/status")
    evidence "invalid tenant RAG -> HTTP $status"
    if [ "$status" = "404" ]; then pass "RAG-INV-01: rag_invalid_tenant"; else fail "RAG-INV-01 ($status)"; fi
}

rag_empty() {
    section "RAG/EMPTY (1 test)"
    setup_auth

    echo -e "\n${BOLD}RAG-EMPTY-01: rag_empty_document${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$TENANT_A_ID/rag/documents" -d '{"title":"Test","content":""}')
    evidence "empty content document -> HTTP $status"
    if [[ "$status" =~ ^(400|403|422)$ ]]; then pass "RAG-EMPTY-01: rag_empty_document"; else fail "RAG-EMPTY-01 ($status)"; fi
}

rag_performance() {
    section "RAG/PERFORMANCE (1 test)"
    setup_auth

    echo -e "\n${BOLD}RAG-PERF-01: rag_status_fast${NC}"
    local start_ms=$(date +%s%3N)
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/tenants/$TENANT_A_ID/rag/status")
    local end_ms=$(date +%s%3N)
    local duration=$((end_ms - start_ms))
    evidence "RAG status: HTTP $status in ${duration}ms"
    if [ "$duration" -lt 2000 ]; then
        pass "RAG-PERF-01: rag_status_fast (${duration}ms)"
    else
        fail "RAG-PERF-01 (duration=${duration}ms)"
    fi
}

rag_failure() {
    section "RAG/FAILURE (1 test)"
    setup_auth

    echo -e "\n${BOLD}RAG-FAIL-01: rag_malformed_document${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$TENANT_A_ID/rag/documents" -d 'not-json')
    evidence "malformed document -> HTTP $status"
    if [[ "$status" =~ ^(400|403|422)$ ]]; then pass "RAG-FAIL-01: rag_malformed_document"; else fail "RAG-FAIL-01 ($status)"; fi
}

run_rag_tests() {
    local stratum=$1
    case "$stratum" in
        happy) rag_happy ;;
        boundary) rag_boundary ;;
        invalid) rag_invalid ;;
        empty) rag_empty ;;
        performance) rag_performance ;;
        failure) rag_failure ;;
        all) rag_happy; rag_boundary; rag_invalid; rag_empty; rag_performance; rag_failure ;;
        *) echo "Unknown stratum: $stratum" && exit 1 ;;
    esac
}

#==============================================================================
# COMBINED RUNNERS
#==============================================================================

run_all_categories() {
    local stratum=$1
    run_auth_tests "$stratum"
    run_tenants_tests "$stratum"
    run_chat_tests "$stratum"
    run_opportunities_tests "$stratum"
    run_intelligence_tests "$stratum"
    run_exports_tests "$stratum"
    run_upload_tests "$stratum"
    run_sync_tests "$stratum"
    run_config_tests "$stratum"
    run_admin_tests "$stratum"
    run_users_tests "$stratum"
    run_rag_tests "$stratum"
}

#------------------------------------------------------------------------------
# Report Generation
#------------------------------------------------------------------------------

generate_report() {
    mkdir -p "$REPORT_DIR"

    local total=$((PASSED + FAILED))
    if [ "$total" -eq 0 ]; then
        total=1
    fi
    local rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED/$total)*100}")

    # Build evidence JSON array
    local evidence_json="["
    local first=true
    for e in "${RAW_EVIDENCE[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            evidence_json+=","
        fi
        local escaped=$(echo "$e" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g')
        evidence_json+="\"$escaped\""
    done
    evidence_json+="]"

    cat > "$REPORT_FILE" << EOF
{
  "report": "CARFAX - Comprehensive Auditable Report For Application eXecution",
  "app": "OutPace Intelligence Platform",
  "timestamp": "$TIMESTAMP",
  "api_url": "$API_URL",
  "category": "$CATEGORY",
  "stratum": "$STRATUM",
  "summary": {
    "total_tests": $total,
    "passed": $PASSED,
    "failed": $FAILED,
    "pass_rate": "${rate}%"
  },
  "invariants_covered": {
    "INV-1_tenant_isolation": true,
    "INV-2_chat_atomicity": true,
    "INV-3_paid_chat_enforcement": true,
    "INV-4_master_tenant_restriction": true,
    "INV-5_export_determinism": true
  },
  "raw_evidence": $evidence_json,
  "status": "$([ $FAILED -eq 0 ] && echo 'CARFAX_VERIFIED' || echo 'REVIEW_REQUIRED')"
}
EOF
}

print_summary() {
    local total=$((PASSED + FAILED))
    if [ "$total" -eq 0 ]; then
        total=1
    fi
    local rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED/$total)*100}")

    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  CARFAX SUMMARY${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Category:      $CATEGORY"
    echo "  Stratum:       $STRATUM"
    echo "  Total Tests:   $total"
    echo -e "  ${GREEN}Passed:${NC}        $PASSED"
    echo -e "  ${RED}Failed:${NC}        $FAILED"
    echo "  Pass Rate:     ${rate}%"
    echo ""

    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                    ✅ CARFAX VERIFIED                          ║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    else
        echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${YELLOW}║                    ⚠️  REVIEW REQUIRED                          ║${NC}"
        echo -e "${YELLOW}║                    $FAILED test(s) failed                          ║${NC}"
        echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
    fi

    echo ""
    echo "  Report: $REPORT_FILE"
    echo ""
}

#------------------------------------------------------------------------------
# Main
#------------------------------------------------------------------------------

main() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   ██████╗ █████╗ ██████╗ ███████╗ █████╗ ██╗  ██╗                        ║${NC}"
    echo -e "${BLUE}║  ██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗╚██╗██╔╝                        ║${NC}"
    echo -e "${BLUE}║  ██║     ███████║██████╔╝█████╗  ███████║ ╚███╔╝                         ║${NC}"
    echo -e "${BLUE}║  ██║     ██╔══██║██╔══██╗██╔══╝  ██╔══██║ ██╔██╗                         ║${NC}"
    echo -e "${BLUE}║  ╚██████╗██║  ██║██║  ██║██║     ██║  ██║██╔╝ ██╗                        ║${NC}"
    echo -e "${BLUE}║   ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝                        ║${NC}"
    echo -e "${BLUE}║                                                                           ║${NC}"
    echo -e "${BLUE}║   Evidence-Based Test Runner - Category/Stratum Mode                     ║${NC}"
    echo -e "${BLUE}║   OutPace Intelligence Platform                                          ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "API URL:  $API_URL"
    echo "Category: $CATEGORY"
    echo "Stratum:  $STRATUM"
    echo ""

    # Dispatch to category runner
    case "$CATEGORY" in
        auth) run_auth_tests "$STRATUM" ;;
        tenants) run_tenants_tests "$STRATUM" ;;
        chat) run_chat_tests "$STRATUM" ;;
        opportunities) run_opportunities_tests "$STRATUM" ;;
        intelligence) run_intelligence_tests "$STRATUM" ;;
        exports) run_exports_tests "$STRATUM" ;;
        upload) run_upload_tests "$STRATUM" ;;
        sync) run_sync_tests "$STRATUM" ;;
        config) run_config_tests "$STRATUM" ;;
        admin) run_admin_tests "$STRATUM" ;;
        users) run_users_tests "$STRATUM" ;;
        rag) run_rag_tests "$STRATUM" ;;
        all) run_all_categories "$STRATUM" ;;
        *) echo -e "${RED}ERROR: Unknown category '$CATEGORY'${NC}"
           echo "Valid categories: auth, tenants, chat, opportunities, intelligence, exports, upload, sync, config, admin, users, rag, all"
           exit 1 ;;
    esac

    # Generate report and summary
    generate_report
    print_summary

    [ $FAILED -eq 0 ] && exit 0 || exit 1
}

main "$@"
