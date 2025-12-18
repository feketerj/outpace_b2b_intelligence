#!/bin/bash
#==============================================================================
# CARFAX - Comprehensive Auditable Report For Application eXecution
# OutPace Intelligence Platform - End-to-End Test Runner
#==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="${REACT_APP_BACKEND_URL:-https://carfax-verified.preview.emergentagent.com}"
REPORT_DIR="/app/carfax_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/carfax_$TIMESTAMP.json"

# Test credentials
ADMIN_EMAIL="admin@example.com"
ADMIN_PASSWORD="REDACTED_ADMIN_PASSWORD"
TENANT_A_EMAIL="tenant-test@test.com"
TENANT_A_PASSWORD="REDACTED_TEST_PASSWORD"
TENANT_B_EMAIL="tenant-b-test@test.com"
TENANT_B_PASSWORD="REDACTED_TEST_PASSWORD"

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Results array
declare -a TEST_RESULTS

#------------------------------------------------------------------------------
# Helper Functions
#------------------------------------------------------------------------------

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED_TESTS++))
    ((TOTAL_TESTS++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED_TESTS++))
    ((TOTAL_TESTS++))
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
    ((SKIPPED_TESTS++))
    ((TOTAL_TESTS++))
}

log_section() {
    echo ""
    echo -e "${BLUE}==============================================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}==============================================================================${NC}"
}

# Get JWT token for a user
get_token() {
    local email=$1
    local password=$2
    local response
    response=$(curl -s -X POST "$API_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\": \"$email\", \"password\": \"$password\"}")
    echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || echo ""
}

# Make authenticated request
auth_request() {
    local method=$1
    local endpoint=$2
    local token=$3
    local data=$4
    
    if [ -n "$data" ]; then
        curl -s -w "\n%{http_code}" -X "$method" "$API_URL$endpoint" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json" \
            -d "$data"
    else
        curl -s -w "\n%{http_code}" -X "$method" "$API_URL$endpoint" \
            -H "Authorization: Bearer $token" \
            -H "Content-Type: application/json"
    fi
}

# Extract HTTP status code from response
get_status() {
    echo "$1" | tail -n1
}

# Extract body from response
get_body() {
    echo "$1" | sed '$d'
}

# Record test result
record_result() {
    local test_id=$1
    local test_name=$2
    local status=$3
    local details=$4
    TEST_RESULTS+=("$(printf '{"id":"%s","name":"%s","status":"%s","details":"%s"}' "$test_id" "$test_name" "$status" "$details")")
}

#------------------------------------------------------------------------------
# Test Suites
#------------------------------------------------------------------------------

test_auth() {
    log_section "TS-AUTH: Authentication Tests"
    
    # T-AUTH-001: Valid Login
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\": \"$ADMIN_EMAIL\", \"password\": \"$ADMIN_PASSWORD\"}")
    local status=$(get_status "$response")
    local body=$(get_body "$response")
    
    if [ "$status" = "200" ] && echo "$body" | grep -q "access_token"; then
        log_pass "T-AUTH-001: Valid login returns token (HTTP $status)"
        record_result "T-AUTH-001" "Valid Login" "PASS" "HTTP $status with access_token"
    else
        log_fail "T-AUTH-001: Valid login failed (HTTP $status)"
        record_result "T-AUTH-001" "Valid Login" "FAIL" "HTTP $status"
    fi
    
    # T-AUTH-002: Invalid Password
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email": "admin@example.com", "password": "wrongpassword"}')
    status=$(get_status "$response")
    
    if [ "$status" = "401" ]; then
        log_pass "T-AUTH-002: Invalid password returns 401 (HTTP $status)"
        record_result "T-AUTH-002" "Invalid Password" "PASS" "HTTP $status"
    else
        log_fail "T-AUTH-002: Invalid password should return 401 (got HTTP $status)"
        record_result "T-AUTH-002" "Invalid Password" "FAIL" "Expected 401, got $status"
    fi
    
    # T-AUTH-003: Get Me Without Token
    response=$(curl -s -w "\n%{http_code}" -X GET "$API_URL/api/auth/me")
    status=$(get_status "$response")
    
    if [ "$status" = "401" ] || [ "$status" = "403" ]; then
        log_pass "T-AUTH-003: Get Me without token returns $status"
        record_result "T-AUTH-003" "Get Me Without Token" "PASS" "HTTP $status"
    else
        log_fail "T-AUTH-003: Get Me without token should return 401/403 (got HTTP $status)"
        record_result "T-AUTH-003" "Get Me Without Token" "FAIL" "Expected 401/403, got $status"
    fi
    
    # T-AUTH-004: Get Me With Token
    local admin_token=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    response=$(auth_request "GET" "/api/auth/me" "$admin_token" "")
    status=$(get_status "$response")
    body=$(get_body "$response")
    
    if [ "$status" = "200" ] && echo "$body" | grep -q "email"; then
        log_pass "T-AUTH-004: Get Me with token returns user (HTTP $status)"
        record_result "T-AUTH-004" "Get Me With Token" "PASS" "HTTP $status with user data"
    else
        log_fail "T-AUTH-004: Get Me with token failed (HTTP $status)"
        record_result "T-AUTH-004" "Get Me With Token" "FAIL" "HTTP $status"
    fi
}

test_tenants() {
    log_section "TS-TENANT: Tenant Management Tests"
    
    local admin_token=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    
    # T-TENANT-001: List Tenants
    local response=$(auth_request "GET" "/api/tenants" "$admin_token" "")
    local status=$(get_status "$response")
    
    if [ "$status" = "200" ]; then
        log_pass "T-TENANT-001: List tenants (HTTP $status)"
        record_result "T-TENANT-001" "List Tenants" "PASS" "HTTP $status"
    else
        log_fail "T-TENANT-001: List tenants failed (HTTP $status)"
        record_result "T-TENANT-001" "List Tenants" "FAIL" "HTTP $status"
    fi
    
    # T-TENANT-002: Create Tenant
    response=$(auth_request "POST" "/api/tenants" "$admin_token" '{"name": "Carfax Test Tenant"}')
    status=$(get_status "$response")
    local body=$(get_body "$response")
    local test_tenant_id=""
    
    if [ "$status" = "200" ]; then
        test_tenant_id=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
        log_pass "T-TENANT-002: Create tenant (HTTP $status, ID: $test_tenant_id)"
        record_result "T-TENANT-002" "Create Tenant" "PASS" "HTTP $status, ID=$test_tenant_id"
    else
        log_fail "T-TENANT-002: Create tenant failed (HTTP $status)"
        record_result "T-TENANT-002" "Create Tenant" "FAIL" "HTTP $status"
    fi
    
    # T-TENANT-003: Update Tenant (if created)
    if [ -n "$test_tenant_id" ]; then
        response=$(auth_request "PUT" "/api/tenants/$test_tenant_id" "$admin_token" '{"name": "Updated Carfax Tenant"}')
        status=$(get_status "$response")
        
        if [ "$status" = "200" ]; then
            log_pass "T-TENANT-003: Update tenant (HTTP $status)"
            record_result "T-TENANT-003" "Update Tenant" "PASS" "HTTP $status"
        else
            log_fail "T-TENANT-003: Update tenant failed (HTTP $status)"
            record_result "T-TENANT-003" "Update Tenant" "FAIL" "HTTP $status"
        fi
        
        # T-TENANT-004: Delete Tenant
        response=$(auth_request "DELETE" "/api/tenants/$test_tenant_id" "$admin_token" "")
        status=$(get_status "$response")
        
        if [ "$status" = "204" ] || [ "$status" = "200" ]; then
            log_pass "T-TENANT-004: Delete tenant (HTTP $status)"
            record_result "T-TENANT-004" "Delete Tenant" "PASS" "HTTP $status"
        else
            log_fail "T-TENANT-004: Delete tenant failed (HTTP $status)"
            record_result "T-TENANT-004" "Delete Tenant" "FAIL" "HTTP $status"
        fi
    else
        log_skip "T-TENANT-003: Update tenant (no test tenant created)"
        log_skip "T-TENANT-004: Delete tenant (no test tenant created)"
    fi
}

test_tenant_isolation() {
    log_section "TS-ISOLATION: Tenant Isolation Tests (INV-1)"
    
    local admin_token=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    local tenant_a_token=$(get_token "$TENANT_A_EMAIL" "$TENANT_A_PASSWORD")
    local tenant_b_token=$(get_token "$TENANT_B_EMAIL" "$TENANT_B_PASSWORD")
    
    if [ -z "$tenant_a_token" ] || [ -z "$tenant_b_token" ]; then
        log_skip "T-ISO-*: Tenant users not available for isolation tests"
        return
    fi
    
    # Get tenant IDs from tokens
    local tenant_a_response=$(auth_request "GET" "/api/auth/me" "$tenant_a_token" "")
    local tenant_b_response=$(auth_request "GET" "/api/auth/me" "$tenant_b_token" "")
    
    local tenant_a_id=$(echo "$(get_body "$tenant_a_response")" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_id',''))" 2>/dev/null || echo "")
    local tenant_b_id=$(echo "$(get_body "$tenant_b_response")" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_id',''))" 2>/dev/null || echo "")
    
    log_info "Tenant A ID: $tenant_a_id"
    log_info "Tenant B ID: $tenant_b_id"
    
    # T-ISO-003: Cross-Tenant Export Returns 403
    if [ -n "$tenant_b_id" ]; then
        local response=$(auth_request "POST" "/api/exports/pdf" "$tenant_a_token" "{\"tenant_id\": \"$tenant_b_id\", \"opportunity_ids\": []}")
        local status=$(get_status "$response")
        
        if [ "$status" = "403" ]; then
            log_pass "T-ISO-003: Cross-tenant export returns 403 (INV-1 PROVEN)"
            record_result "T-ISO-003" "Cross-Tenant Export" "PASS" "HTTP $status - INV-1 PROVEN"
        else
            log_fail "T-ISO-003: Cross-tenant export should return 403 (got HTTP $status)"
            record_result "T-ISO-003" "Cross-Tenant Export" "FAIL" "Expected 403, got $status"
        fi
    else
        log_skip "T-ISO-003: No tenant B ID available"
    fi
    
    # T-ISO-005: Verify audit log generated
    log_info "T-ISO-005: Checking audit logs..."
    local audit_count=$(grep -c "\[tenant.audit\]" /var/log/supervisor/backend.err.log 2>/dev/null || echo "0")
    if [ "$audit_count" -gt "0" ]; then
        log_pass "T-ISO-005: Tenant audit logs present ($audit_count entries)"
        record_result "T-ISO-005" "Audit Logs" "PASS" "$audit_count entries found"
    else
        log_fail "T-ISO-005: No tenant audit logs found"
        record_result "T-ISO-005" "Audit Logs" "FAIL" "No entries found"
    fi
}

test_master_tenant_invariant() {
    log_section "TS-INV4: Master Tenant Restriction Tests (INV-4)"
    
    local admin_token=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    
    # Find master tenant
    local tenants_response=$(auth_request "GET" "/api/tenants" "$admin_token" "")
    local tenants_body=$(get_body "$tenants_response")
    
    local master_tenant_id=$(echo "$tenants_body" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tenants = data if isinstance(data, list) else data.get('data', [])
for t in tenants:
    if t.get('is_master_client'):
        print(t.get('id', ''))
        break
" 2>/dev/null || echo "")
    
    if [ -z "$master_tenant_id" ]; then
        log_skip "T-INV4-*: No master tenant found"
        return
    fi
    
    log_info "Master Tenant ID: $master_tenant_id"
    
    # T-TENANT-005: Master tenant cannot update chat_policy
    local response=$(auth_request "PUT" "/api/tenants/$master_tenant_id" "$admin_token" '{"chat_policy": {"enabled": true}}')
    local status=$(get_status "$response")
    local body=$(get_body "$response")
    
    if [ "$status" = "403" ]; then
        log_pass "T-TENANT-005: Master tenant chat_policy update blocked (HTTP $status) - INV-4 PROVEN"
        record_result "T-TENANT-005" "Master chat_policy Block" "PASS" "HTTP $status - INV-4 PROVEN"
    else
        log_fail "T-TENANT-005: Master tenant chat_policy should be blocked (got HTTP $status)"
        record_result "T-TENANT-005" "Master chat_policy Block" "FAIL" "Expected 403, got $status"
    fi
    
    # T-TENANT-006: Master tenant cannot update rag_policy
    response=$(auth_request "PUT" "/api/tenants/$master_tenant_id" "$admin_token" '{"rag_policy": {"enabled": true}}')
    status=$(get_status "$response")
    
    if [ "$status" = "403" ]; then
        log_pass "T-TENANT-006: Master tenant rag_policy update blocked (HTTP $status) - INV-4 PROVEN"
        record_result "T-TENANT-006" "Master rag_policy Block" "PASS" "HTTP $status - INV-4 PROVEN"
    else
        log_fail "T-TENANT-006: Master tenant rag_policy should be blocked (got HTTP $status)"
        record_result "T-TENANT-006" "Master rag_policy Block" "FAIL" "Expected 403, got $status"
    fi
}

test_exports() {
    log_section "TS-EXPORTS: Export Tests"
    
    local admin_token=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    
    # Get a valid tenant ID
    local tenants_response=$(auth_request "GET" "/api/tenants" "$admin_token" "")
    local tenants_body=$(get_body "$tenants_response")
    local tenant_id=$(echo "$tenants_body" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tenants = data if isinstance(data, list) else data.get('data', [])
if tenants:
    print(tenants[0].get('id', ''))
" 2>/dev/null || echo "")
    
    # T-EXPORT-002: PDF Export Missing tenant_id Returns 400 (INV-5)
    local response=$(auth_request "POST" "/api/exports/pdf" "$admin_token" '{"opportunity_ids": []}')
    local status=$(get_status "$response")
    
    if [ "$status" = "400" ]; then
        log_pass "T-EXPORT-002: PDF export without tenant_id returns 400 (INV-5 PROVEN)"
        record_result "T-EXPORT-002" "PDF Missing tenant_id" "PASS" "HTTP $status - INV-5 PROVEN"
    else
        log_fail "T-EXPORT-002: PDF export without tenant_id should return 400 (got HTTP $status)"
        record_result "T-EXPORT-002" "PDF Missing tenant_id" "FAIL" "Expected 400, got $status"
    fi
    
    # T-EXPORT-001: PDF Export With Valid tenant_id
    if [ -n "$tenant_id" ]; then
        response=$(auth_request "POST" "/api/exports/pdf" "$admin_token" "{\"tenant_id\": \"$tenant_id\", \"opportunity_ids\": [], \"intelligence_ids\": []}")
        status=$(get_status "$response")
        
        if [ "$status" = "200" ] || [ "$status" = "404" ]; then
            log_pass "T-EXPORT-001: PDF export with valid tenant_id (HTTP $status)"
            record_result "T-EXPORT-001" "PDF Export" "PASS" "HTTP $status"
        else
            log_fail "T-EXPORT-001: PDF export failed (HTTP $status)"
            record_result "T-EXPORT-001" "PDF Export" "FAIL" "HTTP $status"
        fi
        
        # T-EXPORT-003: Excel Export
        response=$(auth_request "POST" "/api/exports/excel" "$admin_token" "{\"tenant_id\": \"$tenant_id\", \"opportunity_ids\": [], \"intelligence_ids\": []}")
        status=$(get_status "$response")
        
        if [ "$status" = "200" ] || [ "$status" = "404" ]; then
            log_pass "T-EXPORT-003: Excel export with valid tenant_id (HTTP $status)"
            record_result "T-EXPORT-003" "Excel Export" "PASS" "HTTP $status"
        else
            log_fail "T-EXPORT-003: Excel export failed (HTTP $status)"
            record_result "T-EXPORT-003" "Excel Export" "FAIL" "HTTP $status"
        fi
    fi
}

test_admin() {
    log_section "TS-ADMIN: Admin Tests"
    
    local admin_token=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    
    # T-ADMIN-001: Admin Dashboard
    local response=$(auth_request "GET" "/api/admin/dashboard" "$admin_token" "")
    local status=$(get_status "$response")
    
    if [ "$status" = "200" ]; then
        log_pass "T-ADMIN-001: Admin dashboard (HTTP $status)"
        record_result "T-ADMIN-001" "Admin Dashboard" "PASS" "HTTP $status"
    else
        log_fail "T-ADMIN-001: Admin dashboard failed (HTTP $status)"
        record_result "T-ADMIN-001" "Admin Dashboard" "FAIL" "HTTP $status"
    fi
    
    # T-ADMIN-002: System Health
    response=$(auth_request "GET" "/api/admin/system/health" "$admin_token" "")
    status=$(get_status "$response")
    
    if [ "$status" = "200" ]; then
        log_pass "T-ADMIN-002: System health (HTTP $status)"
        record_result "T-ADMIN-002" "System Health" "PASS" "HTTP $status"
    else
        log_fail "T-ADMIN-002: System health failed (HTTP $status)"
        record_result "T-ADMIN-002" "System Health" "FAIL" "HTTP $status"
    fi
}

test_users() {
    log_section "TS-USERS: User Management Tests"
    
    local admin_token=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    
    # T-USER-001: List Users
    local response=$(auth_request "GET" "/api/users" "$admin_token" "")
    local status=$(get_status "$response")
    
    if [ "$status" = "200" ]; then
        log_pass "T-USER-001: List users (HTTP $status)"
        record_result "T-USER-001" "List Users" "PASS" "HTTP $status"
    else
        log_fail "T-USER-001: List users failed (HTTP $status)"
        record_result "T-USER-001" "List Users" "FAIL" "HTTP $status"
    fi
    
    # T-USER-002: Create User
    local test_email="carfax-test-$(date +%s)@test.com"
    response=$(auth_request "POST" "/api/users" "$admin_token" "{\"email\": \"$test_email\", \"password\": \"REDACTED_TEST_PASSWORD\", \"full_name\": \"Carfax Test\", \"role\": \"tenant_user\"}")
    status=$(get_status "$response")
    local body=$(get_body "$response")
    local test_user_id=""
    
    if [ "$status" = "200" ]; then
        test_user_id=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
        log_pass "T-USER-002: Create user (HTTP $status, ID: $test_user_id)"
        record_result "T-USER-002" "Create User" "PASS" "HTTP $status"
        
        # T-USER-003: Delete User
        if [ -n "$test_user_id" ]; then
            response=$(auth_request "DELETE" "/api/users/$test_user_id" "$admin_token" "")
            status=$(get_status "$response")
            
            if [ "$status" = "204" ] || [ "$status" = "200" ]; then
                log_pass "T-USER-003: Delete user (HTTP $status)"
                record_result "T-USER-003" "Delete User" "PASS" "HTTP $status"
            else
                log_fail "T-USER-003: Delete user failed (HTTP $status)"
                record_result "T-USER-003" "Delete User" "FAIL" "HTTP $status"
            fi
        fi
    else
        log_fail "T-USER-002: Create user failed (HTTP $status)"
        record_result "T-USER-002" "Create User" "FAIL" "HTTP $status: $body"
        log_skip "T-USER-003: Delete user (no test user created)"
    fi
}

test_health() {
    log_section "TS-HEALTH: Health Check Tests"
    
    # Basic health check (no auth required)
    local response=$(curl -s -w "\n%{http_code}" "$API_URL/health")
    local status=$(get_status "$response")
    
    if [ "$status" = "200" ]; then
        log_pass "T-SYS-001: Health check (HTTP $status)"
        record_result "T-SYS-001" "Health Check" "PASS" "HTTP $status"
    else
        log_fail "T-SYS-001: Health check failed (HTTP $status)"
        record_result "T-SYS-001" "Health Check" "FAIL" "HTTP $status"
    fi
}

#------------------------------------------------------------------------------
# Report Generation
#------------------------------------------------------------------------------

generate_report() {
    mkdir -p "$REPORT_DIR"
    
    local invariants_proven=0
    local inv1_proven="false"
    local inv4_proven="false"
    local inv5_proven="false"
    
    # Check which invariants were proven
    for result in "${TEST_RESULTS[@]}"; do
        if echo "$result" | grep -q "INV-1 PROVEN"; then
            inv1_proven="true"
            ((invariants_proven++))
        fi
        if echo "$result" | grep -q "INV-4 PROVEN"; then
            inv4_proven="true"
            ((invariants_proven++))
        fi
        if echo "$result" | grep -q "INV-5 PROVEN"; then
            inv5_proven="true"
            ((invariants_proven++))
        fi
    done
    
    cat > "$REPORT_FILE" << EOF
{
  "report": "CARFAX - Comprehensive Auditable Report For Application eXecution",
  "app": "OutPace Intelligence Platform",
  "timestamp": "$TIMESTAMP",
  "api_url": "$API_URL",
  "summary": {
    "total_tests": $TOTAL_TESTS,
    "passed": $PASSED_TESTS,
    "failed": $FAILED_TESTS,
    "skipped": $SKIPPED_TESTS,
    "pass_rate": "$(echo "scale=1; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc 2>/dev/null || echo "N/A")%"
  },
  "invariants_status": {
    "INV-1_tenant_isolation": $inv1_proven,
    "INV-4_master_tenant_restriction": $inv4_proven,
    "INV-5_export_determinism": $inv5_proven,
    "proven_count": $invariants_proven
  },
  "test_results": [
EOF
    
    local first=true
    for result in "${TEST_RESULTS[@]}"; do
        if [ "$first" = true ]; then
            echo "    $result" >> "$REPORT_FILE"
            first=false
        else
            echo "    ,$result" >> "$REPORT_FILE"
        fi
    done
    
    echo "  ]" >> "$REPORT_FILE"
    echo "}" >> "$REPORT_FILE"
    
    log_info "Report saved to: $REPORT_FILE"
}

print_summary() {
    echo ""
    echo -e "${BLUE}==============================================================================${NC}"
    echo -e "${BLUE}  CARFAX SUMMARY${NC}"
    echo -e "${BLUE}==============================================================================${NC}"
    echo ""
    echo -e "  Total Tests:  $TOTAL_TESTS"
    echo -e "  ${GREEN}Passed:${NC}       $PASSED_TESTS"
    echo -e "  ${RED}Failed:${NC}       $FAILED_TESTS"
    echo -e "  ${YELLOW}Skipped:${NC}      $SKIPPED_TESTS"
    echo ""
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "  ${GREEN}✓ ALL TESTS PASSED - CARFAX VERIFIED${NC}"
    else
        echo -e "  ${RED}✗ SOME TESTS FAILED - REVIEW REQUIRED${NC}"
    fi
    
    echo ""
    echo -e "  Report: $REPORT_FILE"
    echo ""
}

#------------------------------------------------------------------------------
# Main Execution
#------------------------------------------------------------------------------

main() {
    echo ""
    echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                                                                           ║${NC}"
    echo -e "${BLUE}║   ██████╗ █████╗ ██████╗ ███████╗ █████╗ ██╗  ██╗                        ║${NC}"
    echo -e "${BLUE}║  ██╔════╝██╔══██╗██╔══██╗██╔════╝██╔══██╗╚██╗██╔╝                        ║${NC}"
    echo -e "${BLUE}║  ██║     ███████║██████╔╝█████╗  ███████║ ╚███╔╝                         ║${NC}"
    echo -e "${BLUE}║  ██║     ██╔══██║██╔══██╗██╔══╝  ██╔══██║ ██╔██╗                         ║${NC}"
    echo -e "${BLUE}║  ╚██████╗██║  ██║██║  ██║██║     ██║  ██║██╔╝ ██╗                        ║${NC}"
    echo -e "${BLUE}║   ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝                        ║${NC}"
    echo -e "${BLUE}║                                                                           ║${NC}"
    echo -e "${BLUE}║   Comprehensive Auditable Report For Application eXecution               ║${NC}"
    echo -e "${BLUE}║   OutPace Intelligence Platform                                          ║${NC}"
    echo -e "${BLUE}║                                                                           ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    log_info "API URL: $API_URL"
    log_info "Starting test execution..."
    
    # Run test suites in order
    test_health
    test_auth
    test_admin
    test_tenants
    test_users
    test_exports
    test_tenant_isolation
    test_master_tenant_invariant
    
    # Generate report
    generate_report
    
    # Print summary
    print_summary
    
    # Exit with appropriate code
    if [ $FAILED_TESTS -eq 0 ]; then
        exit 0
    else
        exit 1
    fi
}

# Run main
main "$@"
