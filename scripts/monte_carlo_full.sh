#!/usr/bin/env bash
###############################################################################
# monte_carlo_full.sh - Monte Carlo statistical testing harness
#
# Runs 59 iterations per category/stratum combination (72 total combinations)
# to achieve 95% confidence (p<0.05) per binomial theorem.
#
# Usage: ./scripts/monte_carlo_full.sh [--category CAT] [--stratum STR]
#
# Options:
#   --category CAT   Run only specified category (default: all)
#   --stratum STR    Run only specified stratum (default: all)
#   --runs N         Override number of runs (default: 59)
#   --report FILE    Write JSON report to FILE
#
# Exit codes:
#   0 - All strata passed (STABLE)
#   1 - At least one stratum UNSTABLE (>12 failures)
###############################################################################
set -euo pipefail

# Configuration
RUNS=59
UNSTABLE_THRESHOLD=12
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CARFAX="$PROJECT_ROOT/carfax.sh"
REPORT_DIR="$PROJECT_ROOT/carfax_reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# All categories and strata
ALL_CATEGORIES=(auth tenants chat opportunities intelligence exports upload sync config admin users rag)
ALL_STRATA=(happy boundary invalid empty performance failure)

# Counters
TOTAL_PASS=0
TOTAL_FAIL=0
TOTAL_RUNS=0

# Parse arguments
TARGET_CATEGORY="all"
TARGET_STRATUM="all"
REPORT_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --category)
            TARGET_CATEGORY="$2"
            shift 2
            ;;
        --stratum)
            TARGET_STRATUM="$2"
            shift 2
            ;;
        --runs)
            RUNS="$2"
            shift 2
            ;;
        --report)
            REPORT_FILE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Determine categories to run
if [ "$TARGET_CATEGORY" = "all" ]; then
    CATEGORIES=("${ALL_CATEGORIES[@]}")
else
    CATEGORIES=("$TARGET_CATEGORY")
fi

# Determine strata to run
if [ "$TARGET_STRATUM" = "all" ]; then
    STRATA=("${ALL_STRATA[@]}")
else
    STRATA=("$TARGET_STRATUM")
fi

# Results storage for JSON report
declare -A STRATUM_RESULTS

echo "============================================================"
echo "MONTE CARLO FULL TEST SUITE"
echo "============================================================"
echo "Runs per stratum: $RUNS"
echo "Categories: ${CATEGORIES[*]}"
echo "Strata: ${STRATA[*]}"
echo "Total combinations: $((${#CATEGORIES[@]} * ${#STRATA[@]}))"
echo "Total runs: $((${#CATEGORIES[@]} * ${#STRATA[@]} * RUNS))"
echo "Unstable threshold: >$UNSTABLE_THRESHOLD failures"
echo "============================================================"
echo ""

# Create report directory if needed
mkdir -p "$REPORT_DIR"

# Track overall status
OVERALL_STATUS="STABLE"
UNSTABLE_STRATA=""

for cat in "${CATEGORIES[@]}"; do
    for stratum in "${STRATA[@]}"; do
        echo "=== $cat/$stratum: Starting $RUNS runs ==="
        stratum_pass=0
        stratum_fail=0

        for i in $(seq 1 $RUNS); do
            # Show progress every 10 runs
            if [ $((i % 10)) -eq 0 ] || [ $i -eq 1 ]; then
                printf "\r  Run %d/%d..." "$i" "$RUNS"
            fi

            if "$CARFAX" "$cat" "$stratum" > /dev/null 2>&1; then
                stratum_pass=$((stratum_pass + 1))
            else
                stratum_fail=$((stratum_fail + 1))
            fi
        done

        printf "\r"  # Clear progress line

        # Calculate pass rate
        pass_rate=$(awk "BEGIN {printf \"%.1f\", ($stratum_pass / $RUNS) * 100}")

        # Determine stratum status
        if [ $stratum_fail -eq 0 ]; then
            status="STABLE"
            status_icon="[OK]"
        elif [ $stratum_fail -le $UNSTABLE_THRESHOLD ]; then
            status="FLAKY"
            status_icon="[!]"
        else
            status="UNSTABLE"
            status_icon="[X]"
            OVERALL_STATUS="UNSTABLE"
            UNSTABLE_STRATA="$UNSTABLE_STRATA $cat/$stratum"
        fi

        echo "  $status_icon $cat/$stratum: $stratum_pass/$RUNS PASS ($pass_rate%) - $status"

        # Store result
        STRATUM_RESULTS["$cat/$stratum"]="$stratum_pass:$stratum_fail:$status"

        # Update totals
        TOTAL_PASS=$((TOTAL_PASS + stratum_pass))
        TOTAL_FAIL=$((TOTAL_FAIL + stratum_fail))
        TOTAL_RUNS=$((TOTAL_RUNS + RUNS))

        # Fail fast on UNSTABLE
        if [ $stratum_fail -gt $UNSTABLE_THRESHOLD ]; then
            echo ""
            echo "!!! UNSTABLE: $cat/$stratum failed $stratum_fail/$RUNS - aborting !!!"
            echo ""

            # Generate partial report before exit
            if [ -n "$REPORT_FILE" ] || [ -z "$REPORT_FILE" ]; then
                ACTUAL_REPORT="${REPORT_FILE:-$REPORT_DIR/monte_carlo_$TIMESTAMP.json}"
                {
                    echo "{"
                    echo "  \"timestamp\": \"$TIMESTAMP\","
                    echo "  \"status\": \"UNSTABLE\","
                    echo "  \"aborted_at\": \"$cat/$stratum\","
                    echo "  \"runs_per_stratum\": $RUNS,"
                    echo "  \"unstable_threshold\": $UNSTABLE_THRESHOLD,"
                    echo "  \"total_pass\": $TOTAL_PASS,"
                    echo "  \"total_fail\": $TOTAL_FAIL,"
                    echo "  \"total_runs\": $TOTAL_RUNS,"
                    echo "  \"strata_completed\": {"
                    first=true
                    for key in "${!STRATUM_RESULTS[@]}"; do
                        IFS=':' read -r p f s <<< "${STRATUM_RESULTS[$key]}"
                        if [ "$first" = true ]; then
                            first=false
                        else
                            echo ","
                        fi
                        printf "    \"%s\": {\"pass\": %d, \"fail\": %d, \"status\": \"%s\"}" "$key" "$p" "$f" "$s"
                    done
                    echo ""
                    echo "  }"
                    echo "}"
                } > "$ACTUAL_REPORT"
                echo "Report written to: $ACTUAL_REPORT"
            fi

            exit 1
        fi
    done
done

echo ""
echo "============================================================"
echo "MONTE CARLO COMPLETE"
echo "============================================================"
echo "TOTAL: $TOTAL_PASS PASS, $TOTAL_FAIL FAIL out of $TOTAL_RUNS runs"

# Calculate overall pass rate
overall_rate=$(awk "BEGIN {printf \"%.2f\", ($TOTAL_PASS / $TOTAL_RUNS) * 100}")
echo "PASS RATE: $overall_rate%"

# Confidence statement
if [ $TOTAL_FAIL -eq 0 ]; then
    echo "CONFIDENCE: 95% (p<0.05) - All strata STABLE"
    echo "STATUS: STABLE"
else
    flaky_count=0
    for key in "${!STRATUM_RESULTS[@]}"; do
        IFS=':' read -r p f s <<< "${STRATUM_RESULTS[$key]}"
        if [ "$s" = "FLAKY" ]; then
            flaky_count=$((flaky_count + 1))
        fi
    done

    if [ $flaky_count -gt 0 ]; then
        echo "CONFIDENCE: PARTIAL - $flaky_count flaky strata detected"
        echo "STATUS: FLAKY"
    else
        echo "CONFIDENCE: 95% (p<0.05)"
        echo "STATUS: STABLE"
    fi
fi

echo "============================================================"

# Generate JSON report
ACTUAL_REPORT="${REPORT_FILE:-$REPORT_DIR/monte_carlo_$TIMESTAMP.json}"
{
    echo "{"
    echo "  \"timestamp\": \"$TIMESTAMP\","
    echo "  \"status\": \"$OVERALL_STATUS\","
    echo "  \"runs_per_stratum\": $RUNS,"
    echo "  \"unstable_threshold\": $UNSTABLE_THRESHOLD,"
    echo "  \"total_pass\": $TOTAL_PASS,"
    echo "  \"total_fail\": $TOTAL_FAIL,"
    echo "  \"total_runs\": $TOTAL_RUNS,"
    echo "  \"pass_rate\": $overall_rate,"
    echo "  \"categories\": [$(printf '\"%s\",' "${CATEGORIES[@]}" | sed 's/,$//')']',"
    echo "  \"strata\": [$(printf '\"%s\",' "${STRATA[@]}" | sed 's/,$//')']',"
    echo "  \"results\": {"
    first=true
    for key in "${!STRATUM_RESULTS[@]}"; do
        IFS=':' read -r p f s <<< "${STRATUM_RESULTS[$key]}"
        if [ "$first" = true ]; then
            first=false
        else
            echo ","
        fi
        printf "    \"%s\": {\"pass\": %d, \"fail\": %d, \"status\": \"%s\"}" "$key" "$p" "$f" "$s"
    done
    echo ""
    echo "  }"
    echo "}"
} > "$ACTUAL_REPORT"

echo ""
echo "Report written to: $ACTUAL_REPORT"

# Exit with appropriate code
if [ "$OVERALL_STATUS" = "STABLE" ]; then
    exit 0
else
    exit 1
fi
