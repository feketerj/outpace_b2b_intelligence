#!/bin/bash
#==============================================================================
# CARFAX - Comprehensive Auditable Report For Application eXecution
# OutPace Intelligence Platform - Evidence-Based Test Runner
# Single source of truth for API_URL from TEST_PLAN.json
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

# Single source of truth for API_URL (matches TEST_PLAN.json)
API_URL="${API_URL:-https://carfax-verified.preview.emergentagent.com}"
REPORT_DIR="/app/carfax_reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_FILE="$REPORT_DIR/carfax_$TIMESTAMP.json"
LOG_FILE="/var/log/supervisor/backend.err.log"

# Fixtures from TEST_PLAN.json
ADMIN_EMAIL="admin@outpace.ai"
ADMIN_PASSWORD="Admin123!"
TENANT_A_EMAIL="tenant-test@test.com"
TENANT_A_PASSWORD="Test123!"
TENANT_B_EMAIL="tenant-b-test@test.com"
TENANT_B_PASSWORD="Test123!"
TENANT_A_ID="bec8a414-b00d-4a58-9539-5f732db23b35"
TENANT_B_ID="8aa521eb-56ad-4727-8f09-c01fc7921c21"

# Counters
PASSED=0
FAILED=0
declare -a EVIDENCE

#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------

log_evidence() {
    EVIDENCE+=("$1")
    echo -e "${CYAN}   📋 $1${NC}"
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
    curl -s -X POST "$API_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$email\",\"password\":\"$password\"}" | \
        python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null
}

http_status() {
    curl -s -o /dev/null -w "%{http_code}" "$@"
}

#------------------------------------------------------------------------------
# S0: Smoke Tests (6 tests)
#------------------------------------------------------------------------------

test_S0_smoke() {
    section "S0_smoke (6 tests)"
    
    # S0-01: login_super_admin
    echo -e "\n${BOLD}S0-01: login_super_admin${NC}"
    ADMIN_TOKEN=$(get_token "$ADMIN_EMAIL" "$ADMIN_PASSWORD")
    log_evidence "access_token=${ADMIN_TOKEN:+present}"
    if [ -n "$ADMIN_TOKEN" ]; then
        pass "S0-01: login_super_admin"
    else
        fail "S0-01: login_super_admin"
    fi
    
    # S0-02: login_tenant_user
    echo -e "\n${BOLD}S0-02: login_tenant_user${NC}"
    TENANT_A_TOKEN=$(get_token "$TENANT_A_EMAIL" "$TENANT_A_PASSWORD")
    log_evidence "access_token=${TENANT_A_TOKEN:+present}"
    if [ -n "$TENANT_A_TOKEN" ]; then
        pass "S0-02: login_tenant_user"
    else
        fail "S0-02: login_tenant_user"
    fi
    
    # Get Tenant B token for later tests
    TENANT_B_TOKEN=$(get_token "$TENANT_B_EMAIL" "$TENANT_B_PASSWORD")
    
    # S0-03: auth_me
    echo -e "\n${BOLD}S0-03: auth_me${NC}"
    local status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/auth/me")
    log_evidence "HTTP $status"
    [ "$status" = "200" ] && pass "S0-03: auth_me" || fail "S0-03: auth_me ($status)"
    
    # S0-04: list_opportunities
    echo -e "\n${BOLD}S0-04: list_opportunities${NC}"
    status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/opportunities")
    log_evidence "HTTP $status"
    [ "$status" = "200" ] && pass "S0-04: list_opportunities" || fail "S0-04: list_opportunities ($status)"
    
    # S0-05: list_intelligence
    echo -e "\n${BOLD}S0-05: list_intelligence${NC}"
    status=$(http_status -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/intelligence")
    log_evidence "HTTP $status"
    [ "$status" = "200" ] && pass "S0-05: list_intelligence" || fail "S0-05: list_intelligence ($status)"
    
    # S0-06: health
    echo -e "\n${BOLD}S0-06: health${NC}"
    status=$(http_status "$API_URL/health")
    log_evidence "HTTP $status"
    [ "$status" = "200" ] && pass "S0-06: health" || fail "S0-06: health ($status)"
}

#------------------------------------------------------------------------------
# S1: Tenant Isolation Invariants (INV-1)
#------------------------------------------------------------------------------

test_S1_tenant_isolation() {
    section "S1_invariants_tenant_isolation (3 tests)"
    
    # ISO-01: cross_tenant_get_opportunity_403
    echo -e "\n${BOLD}ISO-01: cross_tenant_get_opportunity_403${NC}"
    local opps=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/opportunities")
    local opp_id=$(echo "$opps" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)
    
    if [ -n "$opp_id" ]; then
        log_evidence "Setup: Tenant A opp_id=$opp_id"
        local status=$(http_status -H "Authorization: Bearer $TENANT_B_TOKEN" "$API_URL/api/opportunities/$opp_id")
        log_evidence "Tenant B GET -> HTTP $status"
        [ "$status" = "403" ] && pass "ISO-01: cross_tenant_get_opportunity_403 [INV-1]" || fail "ISO-01 ($status)"
    else
        log_evidence "No opportunities for Tenant A"
        fail "ISO-01: cross_tenant_get_opportunity_403 (no data)"
    fi
    
    # ISO-02: cross_tenant_get_intelligence_403
    echo -e "\n${BOLD}ISO-02: cross_tenant_get_intelligence_403${NC}"
    local intel=$(curl -s -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/intelligence")
    local intel_id=$(echo "$intel" | python3 -c "import sys,json; d=json.load(sys.stdin); data=d.get('data',d) if isinstance(d,dict) else d; print(data[0]['id'] if data else '')" 2>/dev/null)
    
    if [ -n "$intel_id" ]; then
        log_evidence "Setup: Tenant A intel_id=$intel_id"
        local status=$(http_status -H "Authorization: Bearer $TENANT_B_TOKEN" "$API_URL/api/intelligence/$intel_id")
        log_evidence "Tenant B GET -> HTTP $status"
        [ "$status" = "403" ] && pass "ISO-02: cross_tenant_get_intelligence_403 [INV-1]" || fail "ISO-02 ($status)"
    else
        log_evidence "No intelligence for Tenant A"
        fail "ISO-02: cross_tenant_get_intelligence_403 (no data)"
    fi
    
    # ISO-03: cross_tenant_export_pdf_403
    echo -e "\n${BOLD}ISO-03: cross_tenant_export_pdf_403${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $TENANT_B_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[]}")
    log_evidence "Tenant B export with Tenant A id -> HTTP $status"
    [ "$status" = "403" ] && pass "ISO-03: cross_tenant_export_pdf_403 [INV-1, INV-5]" || fail "ISO-03 ($status)"
}

#------------------------------------------------------------------------------
# S5: Master Tenant Restrictions (INV-4)
#------------------------------------------------------------------------------

test_S5_master_restrictions() {
    section "S5_master_tenant_restrictions (3 tests)"
    
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
        log_evidence "No master tenant found"
        fail "S5: No master tenant"
        return
    fi
    log_evidence "Master tenant ID: $master_id"
    
    # MASTER-01: chat_policy
    echo -e "\n${BOLD}MASTER-01: master_blocks_chat_policy${NC}"
    local status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$master_id" -d '{"chat_policy":{"enabled":true}}')
    log_evidence "PUT chat_policy -> HTTP $status"
    [ "$status" = "403" ] && pass "MASTER-01: master_blocks_chat_policy [INV-4]" || fail "MASTER-01 ($status)"
    
    # MASTER-02: rag_policy
    echo -e "\n${BOLD}MASTER-02: master_blocks_rag_policy${NC}"
    status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$master_id" -d '{"rag_policy":{"enabled":true}}')
    log_evidence "PUT rag_policy -> HTTP $status"
    [ "$status" = "403" ] && pass "MASTER-02: master_blocks_rag_policy [INV-4]" || fail "MASTER-02 ($status)"
    
    # MASTER-03: tenant_knowledge
    echo -e "\n${BOLD}MASTER-03: master_blocks_tenant_knowledge${NC}"
    status=$(http_status -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/tenants/$master_id" -d '{"tenant_knowledge":{"snippets":[]}}')
    log_evidence "PUT tenant_knowledge -> HTTP $status"
    [ "$status" = "403" ] && pass "MASTER-03: master_blocks_tenant_knowledge [INV-4]" || fail "MASTER-03 ($status)"
}

#------------------------------------------------------------------------------
# S6: Exports Determinism (INV-5)
#------------------------------------------------------------------------------

test_S6_exports() {
    section "S6_exports_determinism (3 tests)"
    
    # EXP-01: empty_selection_404
    echo -e "\n${BOLD}EXP-01: empty_selection_404_pdf${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[],\"intelligence_ids\":[]}")
    log_evidence "Empty selection -> HTTP $status"
    [ "$status" = "404" ] && pass "EXP-01: empty_selection_404_pdf [INV-5]" || fail "EXP-01 ($status)"
    
    # EXP-02: nonexistent_ids_404
    echo -e "\n${BOLD}EXP-02: nonexistent_ids_404_pdf${NC}"
    status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d "{\"tenant_id\":\"$TENANT_A_ID\",\"opportunity_ids\":[\"bogus-id\"]}")
    log_evidence "Bogus ID -> HTTP $status"
    [ "$status" = "404" ] && pass "EXP-02: nonexistent_ids_404_pdf [INV-5]" || fail "EXP-02 ($status)"
    
    # EXP-03: missing_tenant_id_400
    echo -e "\n${BOLD}EXP-03: missing_tenant_id_super_admin_400${NC}"
    status=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/exports/pdf" -d '{"opportunity_ids":[]}')
    log_evidence "Missing tenant_id -> HTTP $status"
    [ "$status" = "400" ] && pass "EXP-03: missing_tenant_id_super_admin_400 [INV-5]" || fail "EXP-03 ($status)"
}

#------------------------------------------------------------------------------
# S7: Sync Authorization
#------------------------------------------------------------------------------

test_S7_sync() {
    section "S7_integrations_sync (2 tests)"
    
    # SYNC-01: manual_sync super_admin only
    echo -e "\n${BOLD}SYNC-01: manual_sync_endpoint_super_admin_only${NC}"
    local s1=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/sync/manual/$TENANT_A_ID")
    local s2=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/sync/manual/$TENANT_A_ID")
    log_evidence "tenant_user -> HTTP $s1, super_admin -> HTTP $s2"
    if [ "$s1" = "403" ] && [[ "$s2" =~ ^(200|202)$ ]]; then
        pass "SYNC-01: manual_sync_endpoint_super_admin_only"
    else
        fail "SYNC-01 (tenant=$s1, admin=$s2)"
    fi
    
    # SYNC-02: admin/sync super_admin only
    echo -e "\n${BOLD}SYNC-02: admin_trigger_sync_super_admin_only${NC}"
    s1=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/admin/sync/$TENANT_A_ID")
    s2=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/admin/sync/$TENANT_A_ID")
    log_evidence "tenant_user -> HTTP $s1, super_admin -> HTTP $s2"
    if [ "$s1" = "403" ] && [[ "$s2" =~ ^(200|202|404|500)$ ]]; then
        pass "SYNC-02: admin_trigger_sync_super_admin_only"
    else
        fail "SYNC-02 (tenant=$s1, admin=$s2)"
    fi
}

#------------------------------------------------------------------------------
# S8: Upload Authorization (with real multipart CSV)
#------------------------------------------------------------------------------

test_S8_upload() {
    section "S8_upload_branding (2 tests)"
    
    # UPLOAD-01: logo super_admin only
    echo -e "\n${BOLD}UPLOAD-01: tenant_logo_upload_super_admin_only${NC}"
    local s1=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" "$API_URL/api/upload/logo/$TENANT_A_ID")
    local s2=$(http_status -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "$API_URL/api/upload/logo/$TENANT_A_ID")
    log_evidence "tenant_user -> HTTP $s1, super_admin -> HTTP $s2"
    if [ "$s1" = "403" ] && [[ "$s2" =~ ^(200|400|422)$ ]]; then
        pass "UPLOAD-01: tenant_logo_upload_super_admin_only"
    else
        fail "UPLOAD-01 (tenant=$s1, admin=$s2)"
    fi
    
    # UPLOAD-02: CSV upload with real multipart (auth test)
    echo -e "\n${BOLD}UPLOAD-02: opportunities_csv_upload_super_admin_only${NC}"
    
    # Build a tiny CSV fixture
    local TMP_CSV="/tmp/carfax_upload.csv"
    printf "title,agency,due_date,estimated_value\nTest Opportunity,Test Agency,2026-01-01,1000\n" > "$TMP_CSV"
    
    # tenant_user should get 403 (auth before file parsing)
    s1=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $TENANT_A_TOKEN" \
        -F "file=@$TMP_CSV;type=text/csv" \
        "$API_URL/api/upload/opportunities/csv/$TENANT_A_ID")
    
    # super_admin should get 200 or other non-403
    s2=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -F "file=@$TMP_CSV;type=text/csv" \
        "$API_URL/api/upload/opportunities/csv/$TENANT_A_ID")
    
    log_evidence "tenant_user -> HTTP $s1, super_admin -> HTTP $s2"
    
    # Clean up
    rm -f "$TMP_CSV"
    
    # tenant_user must be 403, super_admin must NOT be 403
    if [ "$s1" = "403" ] && [ "$s2" != "403" ]; then
        pass "UPLOAD-02: opportunities_csv_upload_super_admin_only"
    else
        fail "UPLOAD-02 (tenant=$s1, admin=$s2)"
    fi
}

#------------------------------------------------------------------------------
# S2: Chat Gating (input guardrails)
#------------------------------------------------------------------------------

test_S2_chat() {
    section "S2_chat_gating (2 tests)"
    
    # CHAT-05a: conversation_id with spaces
    echo -e "\n${BOLD}CHAT-05a: conversation_id_spaces_rejected${NC}"
    local status=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d '{"conversation_id":"test with spaces","message":"hi","agent_type":"opportunities"}')
    log_evidence "conversation_id with spaces -> HTTP $status"
    [ "$status" = "400" ] && pass "CHAT-05a: conversation_id_spaces_rejected" || fail "CHAT-05a ($status)"
    
    # CHAT-05b: conversation_id too long
    echo -e "\n${BOLD}CHAT-05b: conversation_id_too_long_rejected${NC}"
    local long_id=$(python3 -c "print('x'*200)")
    status=$(http_status -X POST -H "Authorization: Bearer $TENANT_A_TOKEN" -H "Content-Type: application/json" \
        "$API_URL/api/chat/message" -d "{\"conversation_id\":\"$long_id\",\"message\":\"hi\",\"agent_type\":\"opportunities\"}")
    log_evidence "conversation_id > 128 chars -> HTTP $status"
    [ "$status" = "400" ] && pass "CHAT-05b: conversation_id_too_long_rejected" || fail "CHAT-05b ($status)"
}

#------------------------------------------------------------------------------
# Report Generation
#------------------------------------------------------------------------------

generate_report() {
    mkdir -p "$REPORT_DIR"
    
    local total=$((PASSED + FAILED))
    local rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED/$total)*100}")
    
    cat > "$REPORT_FILE" << EOF
{
  "report": "CARFAX - Comprehensive Auditable Report For Application eXecution",
  "app": "OutPace Intelligence Platform",
  "timestamp": "$TIMESTAMP",
  "api_url": "$API_URL",
  "test_plan": "TEST_PLAN.json",
  "summary": {
    "total_tests": $total,
    "passed": $PASSED,
    "failed": $FAILED,
    "pass_rate": "${rate}%"
  },
  "suites_run": [
    "S0_smoke (6)",
    "S1_tenant_isolation (3)",
    "S2_chat_gating (2)",
    "S5_master_restrictions (3)",
    "S6_exports_determinism (3)",
    "S7_sync (2)",
    "S8_upload (2)"
  ],
  "invariants_tested": {
    "INV-1_tenant_isolation": true,
    "INV-4_master_tenant_restriction": true,
    "INV-5_export_determinism": true
  },
  "status": "$([ $FAILED -eq 0 ] && echo 'CARFAX_VERIFIED' || echo 'REVIEW_REQUIRED')"
}
EOF
}

print_summary() {
    local total=$((PASSED + FAILED))
    local rate=$(awk "BEGIN {printf \"%.1f\", ($PASSED/$total)*100}")
    
    echo ""
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}${BOLD}  CARFAX SUMMARY${NC}"
    echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "  Total Tests:   $total"
    echo -e "  ${GREEN}Passed:${NC}        $PASSED"
    echo -e "  ${RED}Failed:${NC}        $FAILED"
    echo "  Pass Rate:     ${rate}%"
    echo ""
    echo "  Invariants Tested:"
    echo "    ✓ INV-1 (Tenant Isolation)"
    echo "    ✓ INV-4 (Master Tenant Restriction)"
    echo "    ✓ INV-5 (Export Determinism)"
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                    ✅ CARFAX VERIFIED                          ║${NC}"
        echo -e "${GREEN}║              All tests passed - System verified                ║${NC}"
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
    echo -e "${BLUE}║   Evidence-Based Test Runner                                             ║${NC}"
    echo -e "${BLUE}║   OutPace Intelligence Platform                                          ║${NC}"
    echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "API URL: $API_URL"
    echo ""
    
    # Run all test suites
    test_S0_smoke
    test_S1_tenant_isolation
    test_S5_master_restrictions
    test_S6_exports
    test_S7_sync
    test_S8_upload
    test_S2_chat
    
    # Generate report and summary
    generate_report
    print_summary
    
    [ $FAILED -eq 0 ] && exit 0 || exit 1
}

main "$@"
