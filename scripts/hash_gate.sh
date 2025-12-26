#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

printf '%s\n' "=== HASH GATE ==="
printf '%s\n' "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "Repo root: $REPO_ROOT"
printf '%s\n' "Verifying artifacts via scripts/verify_hashes.py"
printf '\n'

cd "$REPO_ROOT"

if python scripts/verify_hashes.py; then
    printf '\n'
    printf '%s\n' "=== HASH GATE: PASS ==="
    exit 0
else
    printf '\n'
    printf '%s\n' "=== HASH GATE: FAIL ==="
    printf '%s\n' "One or more artifacts failed integrity verification."
    exit 1
fi
