#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Monte Carlo Rule 59 Runner
# Executes carfax.sh N times consecutively, stops on first failure
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$SCRIPT_DIR"  # Assumes script is in repo root

# Configuration
ITERATIONS="${MC_ITERATIONS:-59}"
API_URL="${API_URL:-http://127.0.0.1:8000}"
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
LOG_DIR="$REPO_ROOT/mc_reports"
LOG_FILE="$LOG_DIR/mc_gitbash_${TIMESTAMP}.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# ============================================================
# Preflight Check
# ============================================================
preflight() {
    echo "=== PREFLIGHT CHECK ===" | tee -a "$LOG_FILE"
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
    echo "Shell: $BASH_VERSION" | tee -a "$LOG_FILE"
    echo "Platform: $(uname -a)" | tee -a "$LOG_FILE"
    echo "API_URL: $API_URL" | tee -a "$LOG_FILE"
    echo "Iterations: $ITERATIONS" | tee -a "$LOG_FILE"
    echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    # Check API health
    echo "Checking API health..." | tee -a "$LOG_FILE"
    HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" "$API_URL/health" 2>&1) || true

    if [[ "$HTTP_CODE" != "200" ]]; then
        echo "PREFLIGHT FAIL: API health check returned $HTTP_CODE" | tee -a "$LOG_FILE"
        echo "Ensure API is running at $API_URL" | tee -a "$LOG_FILE"
        exit 1
    fi

    echo "PREFLIGHT PASS: API healthy (HTTP $HTTP_CODE)" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
}

# ============================================================
# Monte Carlo Loop
# ============================================================
run_monte_carlo() {
    local passed=0
    local start_time
    start_time=$(date +%s)

    echo "=== MONTE CARLO START ===" | tee -a "$LOG_FILE"
    echo "Start: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"

    for i in $(seq 1 "$ITERATIONS"); do
        echo "--- RUN $i/$ITERATIONS ---" | tee -a "$LOG_FILE"

        # Execute carfax.sh and capture result
        if API_URL="$API_URL" bash "$REPO_ROOT/carfax.sh" all >> "$LOG_FILE" 2>&1; then
            passed=$((passed + 1))
            echo "RUN $i: PASS (consecutive: $passed)" | tee -a "$LOG_FILE"
        else
            local end_time
            end_time=$(date +%s)
            local duration=$((end_time - start_time))

            echo "" | tee -a "$LOG_FILE"
            echo "=== MONTE CARLO FAIL ===" | tee -a "$LOG_FILE"
            echo "Failed at iteration: $i" | tee -a "$LOG_FILE"
            echo "Consecutive passes before failure: $passed" | tee -a "$LOG_FILE"
            echo "Duration: ${duration}s" | tee -a "$LOG_FILE"
            echo "End: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"

            exit 1
        fi

        echo "" | tee -a "$LOG_FILE"
    done

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo "=== MONTE CARLO PASS ===" | tee -a "$LOG_FILE"
    echo "Iterations: $ITERATIONS" | tee -a "$LOG_FILE"
    echo "Consecutive passes: $passed" | tee -a "$LOG_FILE"
    echo "Duration: ${duration}s" | tee -a "$LOG_FILE"
    echo "Confidence: 95% (Rule 59 satisfied)" | tee -a "$LOG_FILE"
    echo "End: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG_FILE"
    echo "Log: $LOG_FILE" | tee -a "$LOG_FILE"
}

# ============================================================
# Main
# ============================================================
main() {
    preflight
    run_monte_carlo
}

main "$@"
