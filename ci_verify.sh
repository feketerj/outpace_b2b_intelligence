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

# Suite 2: Full CARFAX Invariant Suite (includes live sync tests)
# This runs all 26 invariant tests including sync permission checks
run_suite "CARFAX Full Suite" "cd /app && bash carfax.sh"

# Suite 3: Sync Contract Shape Tests (quick - ONE sync call)
# Run AFTER carfax.sh to verify contract shape without redundant sync calls
# Uses responses from a single sync call to verify schema
run_suite "Sync Contract Shape" "cd /app && bash carfax_sync_contract.sh"

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
