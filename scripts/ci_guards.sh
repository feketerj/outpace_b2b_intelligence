#!/bin/bash
#
# CI Guards - Grep-based checks for critical code patterns
#
# These guards verify that critical patterns exist and anti-patterns don't.
# Run in CI before merge to catch regressions.
#
# Usage:
#   ./scripts/ci_guards.sh
#
# Exit codes:
#   0 - All guards pass
#   1 - Guard failure detected
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

echo "========================================"
echo "CI Guards - Pattern Validation"
echo "========================================"
echo ""

# ------------------------------------------
# ANTI-PATTERN GUARDS (must NOT exist)
# ------------------------------------------

echo "Checking anti-patterns..."

# Guard: No silent except: pass
if grep -rn "except\s*:" "$BACKEND_DIR" --include="*.py" | grep -v "except.*as" | grep "pass" | grep -v "test_" | grep -v "__pycache__"; then
    echo -e "${RED}FAIL${NC}: Found 'except: pass' pattern (silent failure)"
    FAILED=1
else
    echo -e "${GREEN}PASS${NC}: No 'except: pass' patterns found"
fi

# Guard: No hardcoded dev secrets in code
if grep -rn "local-dev-secret\|test-secret-key\|changeme\|outpace[0-9][0-9][0-9][0-9]" "$BACKEND_DIR" --include="*.py" | grep -v "test_" | grep -v "__pycache__" | grep -v "canaries.py" | grep -v "preflight.py"; then
    echo -e "${YELLOW}WARN${NC}: Found potential hardcoded dev secrets"
fi

# Guard: No hardcoded password hashes in seed/bootstrap scripts
if grep -rn "get_password_hash([\"']" "$BACKEND_DIR" "$PROJECT_ROOT/scripts" --include="*.py" | grep -v "test_" | grep -v "__pycache__"; then
    echo -e "${RED}FAIL${NC}: Found hardcoded password passed to get_password_hash"
    FAILED=1
else
    echo -e "${GREEN}PASS${NC}: No hardcoded password hashing in seed/bootstrap scripts"
fi

# Guard: No TODO/FIXME in critical security files
SECURITY_FILES="$BACKEND_DIR/utils/auth.py $BACKEND_DIR/routes/auth.py"
for f in $SECURITY_FILES; do
    if [ -f "$f" ] && grep -n "TODO\|FIXME\|XXX\|HACK" "$f"; then
        echo -e "${YELLOW}WARN${NC}: Found TODO/FIXME in security file: $f"
    fi
done

echo ""

# ------------------------------------------
# REQUIRED PATTERN GUARDS (must exist)
# ------------------------------------------

echo "Checking required patterns..."

# Guard: Tenant isolation in opportunities
if grep -q "tenant_id" "$BACKEND_DIR/routes/opportunities.py"; then
    echo -e "${GREEN}PASS${NC}: opportunities.py contains tenant_id checks"
else
    echo -e "${RED}FAIL${NC}: opportunities.py missing tenant_id checks"
    FAILED=1
fi

# Guard: Tenant isolation in chat
if grep -rq "tenant_id" "$BACKEND_DIR/routes/chat/"; then
    echo -e "${GREEN}PASS${NC}: chat/ contains tenant_id checks"
else
    echo -e "${RED}FAIL${NC}: chat/ missing tenant_id checks"
    FAILED=1
fi

# Guard: JWT validation exists
if grep -q "get_current_user\|verify_token\|TokenData" "$BACKEND_DIR/utils/auth.py"; then
    echo -e "${GREEN}PASS${NC}: auth.py has JWT validation"
else
    echo -e "${RED}FAIL${NC}: auth.py missing JWT validation"
    FAILED=1
fi

# Guard: Audit logging exists
AUDIT_COUNT=$(grep -rn "\[audit\." "$BACKEND_DIR/routes" --include="*.py" | wc -l)
if [ "$AUDIT_COUNT" -ge 5 ]; then
    echo -e "${GREEN}PASS${NC}: Found $AUDIT_COUNT audit log entries"
else
    echo -e "${RED}FAIL${NC}: Insufficient audit logging (found $AUDIT_COUNT, need >= 5)"
    FAILED=1
fi

# Guard: Unknown field rejection in tenants
if grep -q "Unknown fields rejected" "$BACKEND_DIR/routes/tenants.py"; then
    echo -e "${GREEN}PASS${NC}: tenants.py rejects unknown fields"
else
    echo -e "${RED}FAIL${NC}: tenants.py not rejecting unknown fields"
    FAILED=1
fi

# Guard: Unknown field rejection in opportunities
if grep -q "Unknown fields rejected" "$BACKEND_DIR/routes/opportunities.py"; then
    echo -e "${GREEN}PASS${NC}: opportunities.py rejects unknown fields"
else
    echo -e "${RED}FAIL${NC}: opportunities.py not rejecting unknown fields"
    FAILED=1
fi

# Guard: Error logging in external service calls
if grep -q "logger.error\|logger.exception" "$BACKEND_DIR/services/mistral_service.py" 2>/dev/null; then
    echo -e "${GREEN}PASS${NC}: mistral_service.py has error logging"
else
    echo -e "${YELLOW}WARN${NC}: mistral_service.py may lack error logging"
fi

# Guard: Preflight checks exist and are integrated
if grep -q "PREFLIGHT_FAILED\|PREFLIGHT_PASSED" "$BACKEND_DIR/utils/preflight.py" 2>/dev/null; then
    echo -e "${GREEN}PASS${NC}: preflight.py has structured logging"
else
    echo -e "${RED}FAIL${NC}: preflight.py missing structured logging"
    FAILED=1
fi

# Guard: Preflight is called at startup
if grep -q "run_preflight_checks" "$BACKEND_DIR/server.py" 2>/dev/null; then
    echo -e "${GREEN}PASS${NC}: server.py calls preflight checks"
else
    echo -e "${RED}FAIL${NC}: server.py not calling preflight checks"
    FAILED=1
fi

echo ""

# ------------------------------------------
# FILE EXISTENCE GUARDS
# ------------------------------------------

echo "Checking required files..."

REQUIRED_FILES=(
    "$BACKEND_DIR/utils/invariants.py"
    "$BACKEND_DIR/utils/state_machines.py"
    "$BACKEND_DIR/utils/tracing.py"
    "$BACKEND_DIR/utils/canaries.py"
    "$BACKEND_DIR/utils/preflight.py"
    "$BACKEND_DIR/tests/test_tenant_isolation.py"
    "$BACKEND_DIR/tests/test_contracts.py"
    "$BACKEND_DIR/tests/test_audit_completeness.py"
    "$BACKEND_DIR/tests/test_no_silent_failures.py"
    "$BACKEND_DIR/tests/test_preflight.py"
)

for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "$f" ]; then
        echo -e "${GREEN}PASS${NC}: $(basename $f) exists"
    else
        echo -e "${RED}FAIL${NC}: Missing required file: $f"
        FAILED=1
    fi
done

echo ""

# ------------------------------------------
# SUMMARY
# ------------------------------------------

echo "========================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All CI guards passed!${NC}"
    exit 0
else
    echo -e "${RED}CI guards failed - review issues above${NC}"
    exit 1
fi
