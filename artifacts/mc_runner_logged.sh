#!/bin/bash
# Monte Carlo Runner for carfax.sh - WITH FULL LOGGING
# Requires 59 consecutive passes for 95% confidence

export API_URL=http://127.0.0.1:8000
TARGET=59
PASS_COUNT=0
REPORT_INTERVAL=10
LOGFILE="mc_reports/mc_consolidated_$(date +%Y%m%d_%H%M%S).log"

mkdir -p mc_reports

# Start logging
exec > >(tee -a "$LOGFILE") 2>&1

echo "=== MONTE CARLO VALIDATION CAMPAIGN ==="
echo "Target: $TARGET consecutive passes"
echo "Log File: $LOGFILE"
echo "Started: $(date -Iseconds)"
echo ""

for run in $(seq 1 $TARGET); do
    TIMESTAMP=$(date -Iseconds)
    
    # Run carfax.sh and capture output
    OUTPUT=$(bash carfax.sh all 2>&1)
    EXIT_CODE=$?
    
    # Extract test count from output (looking for "PASSED: X/35")
    TEST_COUNT=$(echo "$OUTPUT" | grep -oP 'PASSED:\s*\K\d+/\d+' | tail -1)
    if [ -z "$TEST_COUNT" ]; then
        # Try alternate pattern
        TEST_COUNT=$(echo "$OUTPUT" | grep -oP '\d+/35\s*tests?\s*passed' | grep -oP '\d+/35' | tail -1)
    fi
    if [ -z "$TEST_COUNT" ]; then
        # Count individual PASS lines
        PASS_LINES=$(echo "$OUTPUT" | grep -c "PASS")
        TEST_COUNT="${PASS_LINES}/35"
    fi
    
    # Log every run
    echo "RUN $run | TIME: $TIMESTAMP | EXIT: $EXIT_CODE | TESTS: $TEST_COUNT"
    
    # Check for success: exit 0 AND 35/35
    if [ $EXIT_CODE -eq 0 ] && [[ "$TEST_COUNT" == "35/35" ]]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        echo "  -> PASS (consecutive: $PASS_COUNT)"
    else
        # FAILURE - halt and report
        echo "  -> FAIL"
        echo ""
        echo "=== FAILURE DETECTED ==="
        echo "Run: $run"
        echo "Timestamp: $TIMESTAMP"
        echo "Exit Code: $EXIT_CODE"
        echo "Test Count: $TEST_COUNT"
        echo ""
        echo "=== FULL OUTPUT ==="
        echo "$OUTPUT"
        echo ""
        echo "=== MONTE CARLO HALTED ==="
        echo "Consecutive passes before failure: $((PASS_COUNT))"
        exit 1
    fi
done

echo ""
echo "=== MONTE CARLO VALIDATION COMPLETE ==="
echo "Result: SUCCESS"
echo "Consecutive Passes: $PASS_COUNT/$TARGET"
echo "Completed: $(date -Iseconds)"
echo ""
echo "95% confidence baseline established."
echo "Log File: $LOGFILE"
exit 0
