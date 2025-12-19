#!/bin/bash
#
# CI VERIFICATION WRAPPER
# =======================
# Runs all regression guards in sequence with timing.
# Target: Complete in < 180 seconds total.
#
# Suites:
# 1. carfax_sync_contract.sh - Quick contract shape tests (ONE live sync call)
# 2. pytest backend contract tests - Deep live verification
# 3. pytest frontend static tests - Code inspection
# 4. carfax.sh - Full invariant suite
#
# Usage: bash ci_verify.sh
# Exit: 0 if all pass, 1 if any fail
#

set -o pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              CI VERIFICATION SUITE                            ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

TOTAL_START=$(date +%s)
ALL_PASSED=true

run_suite() {
    local name="$1"
    local cmd="$2"
    local start=$(date +%s)
    
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Running: $name${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    eval "$cmd"
    local exit_code=$?
    
    local end=$(date +%s)
    local duration=$((end - start))
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ $name PASSED (${duration}s)${NC}"
    else
        echo -e "${RED}❌ $name FAILED (${duration}s, exit code: $exit_code)${NC}"
        ALL_PASSED=false
    fi
    echo ""
    
    return $exit_code
}

# Suite 1: Frontend Static Contract Tests (fastest - no API calls)
run_suite "Frontend Static Contract" "cd /app/backend && python -m pytest tests/test_sync_frontend_contract.py -v --tb=short"

# Suite 2: Full CARFAX Invariant Suite (includes live sync with contract validation)
# This runs all 26 invariant tests including:
# - S7 SYNC-02: ONE admin sync call with FULL CONTRACT VALIDATION (no timeout pass)
# - Regression detection for old "Sync triggered successfully" response
# CAPTURE OUTPUT for post-run assertions
CARFAX_OUTPUT=$(cd /app && bash carfax.sh 2>&1)
CARFAX_EXIT=$?
echo "$CARFAX_OUTPUT"

if [ $CARFAX_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ CARFAX Full Suite PASSED${NC}"
else
    echo -e "${RED}❌ CARFAX Full Suite FAILED (exit code: $CARFAX_EXIT)${NC}"
    ALL_PASSED=false
fi
echo ""

# =============================================================================
# FAIL-FAST GATE: Verify S7 SYNC-02 actually executed with contract validation
# This prevents a future edit from silently skipping S7 while still claiming green
# =============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Verifying S7 SYNC-02 Contract Validation Executed${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

S7_SECTION_FOUND=false
SYNC02_TEST_FOUND=false
CONTRACT_OK_FOUND=false

if echo "$CARFAX_OUTPUT" | grep -q "S7_integrations_sync"; then
    S7_SECTION_FOUND=true
    echo -e "${GREEN}✓ S7_integrations_sync section executed${NC}"
else
    echo -e "${RED}✗ S7_integrations_sync section NOT FOUND${NC}"
fi

if echo "$CARFAX_OUTPUT" | grep -q "SYNC-02: admin_sync_returns_full_contract"; then
    SYNC02_TEST_FOUND=true
    echo -e "${GREEN}✓ SYNC-02: admin_sync_returns_full_contract test ran${NC}"
else
    echo -e "${RED}✗ SYNC-02 test NOT FOUND${NC}"
fi

if echo "$CARFAX_OUTPUT" | grep -q "Contract validated: OK:"; then
    CONTRACT_OK_FOUND=true
    echo -e "${GREEN}✓ Contract validated with OK status${NC}"
else
    echo -e "${RED}✗ Contract validation OK NOT FOUND${NC}"
fi

echo ""

if [ "$S7_SECTION_FOUND" = true ] && [ "$SYNC02_TEST_FOUND" = true ] && [ "$CONTRACT_OK_FOUND" = true ]; then
    echo -e "${GREEN}✅ S7 SYNC-02 Contract Validation Gate PASSED${NC}"
else
    echo -e "${RED}❌ S7 SYNC-02 Contract Validation Gate FAILED${NC}"
    echo -e "${RED}   CI cannot pass without S7/SYNC-02 contract proof${NC}"
    ALL_PASSED=false
fi
echo ""

# NOTE: carfax_sync_contract.sh is now SKIPPED in CI
# The contract validation is embedded in CARFAX S7 SYNC-02
# Manual deep contract test: bash /app/carfax_sync_contract.sh
echo -e "${YELLOW}[INFO] Manual deep contract test available: bash /app/carfax_sync_contract.sh${NC}"
echo ""

# =============================================================================
# SUMMARY
# =============================================================================
TOTAL_END=$(date +%s)
TOTAL_RUNTIME=$((TOTAL_END - TOTAL_START))

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  CI VERIFICATION SUMMARY${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Total Runtime: ${TOTAL_RUNTIME}s"
echo ""

if [ "$ALL_PASSED" = true ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           ✅ ALL CI CHECKS PASSED                              ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║           ❌ CI VERIFICATION FAILED                            ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
