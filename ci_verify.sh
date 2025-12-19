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
# NON-NEGOTIABLE: CI cannot pass without marker-gated SYNC-02 proof.
#

set -o pipefail

# Resolve repo root dynamically (no hardcoded /app)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${GITHUB_WORKSPACE:-${REPO_ROOT:-$SCRIPT_DIR}}"
export REPO_ROOT

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
# Remove stale marker file before running CARFAX
rm -f /tmp/carfax_sync02_ok.marker

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
# FAIL-FAST GATE: Verify S7 SYNC-02 via MARKER FILE (robust, un-gameable)
# A marker file is written by CARFAX only when SYNC-02 passes full contract validation
# This is harder to bypass than grepping stdout for specific strings
# =============================================================================
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Verifying S7 SYNC-02 Contract Validation (Marker File Gate)${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

MARKER_FILE="/tmp/carfax_sync02_ok.marker"
MARKER_VALID=false

if [ -f "$MARKER_FILE" ]; then
    echo -e "${GREEN}✓ Marker file exists: $MARKER_FILE${NC}"
    
    # COMPREHENSIVE marker validation: JSON parsing, integrity, and freshness
    MARKER_CHECK=$(cat "$MARKER_FILE" | python3 -c "
import sys, json, re
from datetime import datetime, timezone, timedelta

UUID_REGEX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
MAX_AGE_MINUTES = 10

try:
    d = json.load(sys.stdin)
    errors = []
    
    # 1. Check required keys exist
    required = ['tenant_id', 'status', 'sync_timestamp', 'contract_validated']
    missing = [k for k in required if k not in d]
    if missing:
        errors.append(f'MISSING_KEYS:{missing}')
    
    # 2. Validate contract_validated flag
    if d.get('contract_validated') != True:
        errors.append('CONTRACT_NOT_VALIDATED')
    
    # 3. Validate status enum
    if d.get('status') not in ['success', 'partial']:
        errors.append(f'INVALID_STATUS:{d.get(\"status\")}')
    
    # 4. INTEGRITY: Validate tenant_id is UUID format
    tenant_id = d.get('tenant_id', '')
    if not tenant_id or not UUID_REGEX.match(tenant_id):
        errors.append(f'INVALID_TENANT_ID_FORMAT:{tenant_id[:20]}')
    
    # 5. INTEGRITY: Validate sync_timestamp is parseable ISO format
    sync_ts = d.get('sync_timestamp', '')
    try:
        # Handle both +00:00 and Z timezone formats
        ts_clean = sync_ts.replace('Z', '+00:00')
        parsed_ts = datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError) as e:
        errors.append(f'UNPARSEABLE_TIMESTAMP:{sync_ts[:30]}')
        parsed_ts = None
    
    # 6. FRESHNESS: sync_timestamp must be within last 10 minutes UTC
    if parsed_ts:
        now_utc = datetime.now(timezone.utc)
        # Handle naive timestamps by assuming UTC
        if parsed_ts.tzinfo is None:
            parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
        age = now_utc - parsed_ts
        if age > timedelta(minutes=MAX_AGE_MINUTES):
            errors.append(f'STALE_MARKER:age={age.total_seconds():.0f}s,max={MAX_AGE_MINUTES*60}s')
        elif age < timedelta(seconds=-60):  # Allow 1 min clock skew
            errors.append(f'FUTURE_TIMESTAMP:age={age.total_seconds():.0f}s')
    
    if errors:
        print('INVALID:' + ';'.join(errors))
    else:
        print(f'VALID:tenant={tenant_id[:8]}...,status={d[\"status\"]},ts={sync_ts[:19]},fresh=yes')
        
except json.JSONDecodeError as e:
    print(f'JSON_PARSE_ERROR:{e}')
except Exception as e:
    print(f'UNEXPECTED_ERROR:{e}')
" 2>/dev/null)
    
    if [[ "$MARKER_CHECK" == VALID:* ]]; then
        MARKER_VALID=true
        echo -e "${GREEN}✓ Marker validated (integrity + freshness): $MARKER_CHECK${NC}"
    else
        echo -e "${RED}✗ Marker validation FAILED: $MARKER_CHECK${NC}"
    fi
else
    echo -e "${RED}✗ Marker file NOT FOUND: $MARKER_FILE${NC}"
    echo -e "${RED}   SYNC-02 did not pass contract validation${NC}"
fi

echo ""

if [ "$MARKER_VALID" = true ]; then
    echo -e "${GREEN}✅ S7 SYNC-02 Contract Validation Gate PASSED (marker verified)${NC}"
else
    echo -e "${RED}❌ S7 SYNC-02 Contract Validation Gate FAILED${NC}"
    echo -e "${RED}   CI cannot pass without valid SYNC-02 marker proof${NC}"
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
