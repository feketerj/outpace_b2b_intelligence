#!/usr/bin/env bash
set -euo pipefail

RUNS=59
PASS=0
FAIL=0
START=$(date +%s)

for i in $(seq 1 $RUNS); do
    if ./carfax.sh all; then
        PASS=$((PASS + 1))
        echo "RUN $i/$RUNS: PASS"
    else
        FAIL=$((FAIL + 1))
        echo "RUN $i/$RUNS: FAIL"
    fi
done

END=$(date +%s)
RUNTIME=$((END - START))

echo "MONTE CARLO COMPLETE"
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "RUNTIME: ${RUNTIME}s"
echo "CONFIDENCE: $([ $FAIL -eq 0 ] && echo '95% (p<0.05)' || echo 'FAILED')"
