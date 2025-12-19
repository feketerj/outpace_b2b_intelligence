#!/bin/bash
#
# NEGATIVE CASE VERIFICATION
# ==========================
# Proves that CI correctly fails on invalid marker states.
# This script does NOT make any sync calls.
#
# Usage: bash test_negative_cases.sh
#
# Tests:
#   1. Missing marker → FAIL
#   2. Stale marker (>10 min old) → FAIL
#   3. Malformed JSON → FAIL
#   4. Missing required field → FAIL
#   5. Invalid UUID → FAIL
#   6. contract_validated=false → FAIL
#

# Note: NOT using set -e because we expect failures

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

MARKER_FILE="/tmp/carfax_sync02_ok.marker"
PASSED=0
FAILED=0

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           NEGATIVE CASE VERIFICATION                          ║"
echo "║       Proving CI fails correctly on invalid states            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Marker validation function (extracted from ci_verify.sh)
validate_marker() {
    python3 << 'PYEOF'
import sys, json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

UUID_REGEX = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
MAX_AGE_MINUTES = 10
MARKER_PATH = Path('/tmp/carfax_sync02_ok.marker')

try:
    if not MARKER_PATH.exists():
        print('FAIL:MARKER_NOT_FOUND')
        sys.exit(1)
    
    try:
        data = json.loads(MARKER_PATH.read_text())
    except json.JSONDecodeError as e:
        print(f'FAIL:MALFORMED_JSON:{e}')
        sys.exit(1)
    
    errors = []
    
    # Check required fields
    required = ['tenant_id', 'status', 'sync_timestamp', 'contract_validated', 'marker_created_utc']
    missing = [k for k in required if k not in data]
    if missing:
        errors.append(f'MISSING_FIELDS:{missing}')
    
    # Check contract_validated
    if data.get('contract_validated') is not True:
        errors.append(f'CONTRACT_NOT_VALIDATED:{data.get("contract_validated")}')
    
    # Check UUID format
    tenant_id = data.get('tenant_id', '')
    if not UUID_REGEX.match(str(tenant_id)):
        errors.append(f'INVALID_UUID:{tenant_id[:20]}')
    
    # Check freshness
    marker_ts = data.get('marker_created_utc', '')
    try:
        ts_clean = marker_ts.replace('Z', '+00:00')
        parsed_ts = datetime.fromisoformat(ts_clean)
        if parsed_ts.tzinfo is None:
            parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - parsed_ts
        if age > timedelta(minutes=MAX_AGE_MINUTES):
            errors.append(f'STALE_MARKER:age={age.total_seconds():.0f}s')
    except:
        errors.append(f'UNPARSEABLE_TIMESTAMP:{marker_ts[:30]}')
    
    if errors:
        print('FAIL:' + ';'.join(errors))
        sys.exit(1)
    
    print(f'PASS:tenant={tenant_id[:8]}...')
    sys.exit(0)

except Exception as e:
    print(f'FAIL:UNEXPECTED:{e}')
    sys.exit(1)
PYEOF
}

run_test() {
    local name="$1"
    local setup="$2"
    local expected_fail="$3"
    
    echo -e "${YELLOW}TEST: $name${NC}"
    
    # Setup the test condition
    eval "$setup"
    
    # Run validation
    result=$(validate_marker 2>&1) || true
    
    if [[ "$result" == FAIL:* ]]; then
        if [ "$expected_fail" = "true" ]; then
            echo -e "${GREEN}  ✓ Correctly failed: $result${NC}"
            ((PASSED++))
        else
            echo -e "${RED}  ✗ Unexpected failure: $result${NC}"
            ((FAILED++))
        fi
    else
        if [ "$expected_fail" = "true" ]; then
            echo -e "${RED}  ✗ Should have failed but passed: $result${NC}"
            ((FAILED++))
        else
            echo -e "${GREEN}  ✓ Correctly passed: $result${NC}"
            ((PASSED++))
        fi
    fi
    echo ""
}

# Clean up before tests
rm -f "$MARKER_FILE"

# Test 1: Missing marker
run_test "Missing marker" \
    "rm -f $MARKER_FILE" \
    "true"

# Test 2: Stale marker (20 minutes old)
run_test "Stale marker (20 min old)" \
    "python3 -c \"
import json
from datetime import datetime, timezone, timedelta
old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
marker = {
    'tenant_id': '8aa521eb-56ad-4727-8f09-c01fc7921c21',
    'status': 'success',
    'sync_timestamp': old_time.isoformat(),
    'contract_validated': True,
    'marker_created_utc': old_time.isoformat()
}
with open('$MARKER_FILE', 'w') as f:
    json.dump(marker, f)
\"" \
    "true"

# Test 3: Malformed JSON
run_test "Malformed JSON" \
    "echo '{not valid json' > $MARKER_FILE" \
    "true"

# Test 4: Missing required field (no tenant_id)
run_test "Missing required field (tenant_id)" \
    "python3 -c \"
import json
from datetime import datetime, timezone
marker = {
    'status': 'success',
    'sync_timestamp': datetime.now(timezone.utc).isoformat(),
    'contract_validated': True,
    'marker_created_utc': datetime.now(timezone.utc).isoformat()
}
with open('$MARKER_FILE', 'w') as f:
    json.dump(marker, f)
\"" \
    "true"

# Test 5: Invalid UUID
run_test "Invalid UUID format" \
    "python3 -c \"
import json
from datetime import datetime, timezone
marker = {
    'tenant_id': 'not-a-valid-uuid',
    'status': 'success',
    'sync_timestamp': datetime.now(timezone.utc).isoformat(),
    'contract_validated': True,
    'marker_created_utc': datetime.now(timezone.utc).isoformat()
}
with open('$MARKER_FILE', 'w') as f:
    json.dump(marker, f)
\"" \
    "true"

# Test 6: contract_validated=false
run_test "contract_validated=false" \
    "python3 -c \"
import json
from datetime import datetime, timezone
marker = {
    'tenant_id': '8aa521eb-56ad-4727-8f09-c01fc7921c21',
    'status': 'success',
    'sync_timestamp': datetime.now(timezone.utc).isoformat(),
    'contract_validated': False,
    'marker_created_utc': datetime.now(timezone.utc).isoformat()
}
with open('$MARKER_FILE', 'w') as f:
    json.dump(marker, f)
\"" \
    "true"

# Test 7: Valid marker (should pass)
run_test "Valid marker (control test)" \
    "python3 -c \"
import json
from datetime import datetime, timezone
marker = {
    'tenant_id': '8aa521eb-56ad-4727-8f09-c01fc7921c21',
    'status': 'success',
    'sync_timestamp': datetime.now(timezone.utc).isoformat(),
    'opportunities_synced': 10,
    'intelligence_synced': 0,
    'contract_validated': True,
    'marker_created_utc': datetime.now(timezone.utc).isoformat()
}
with open('$MARKER_FILE', 'w') as f:
    json.dump(marker, f)
\"" \
    "false"

# Summary
echo "═══════════════════════════════════════════════════════════════"
echo "  NEGATIVE CASE SUMMARY"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Passed: $PASSED"
echo "  Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     ✅ ALL NEGATIVE CASES CORRECTLY HANDLED                   ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    rm -f "$MARKER_FILE"
    exit 0
else
    echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║     ❌ NEGATIVE CASE VERIFICATION FAILED                       ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
    rm -f "$MARKER_FILE"
    exit 1
fi
