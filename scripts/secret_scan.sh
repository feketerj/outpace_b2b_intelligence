#!/usr/bin/env bash
#
# High-signal public-repo hygiene scan.
# This complements provider secret scanning by catching repo-specific leaks and
# tracked generated artifacts before they land in CI.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) is required for scripts/secret_scan.sh" >&2
  exit 1
fi

RG_ARGS=(
  --hidden
  -g '!.git/**'
  -g '!frontend/node_modules/**'
  -g '!**/__pycache__/**'
  -g '!frontend/package-lock.json'
  -g '!scripts/secret_scan.sh'
)

PATTERNS=(
  'Admin[0-9]{3}!'
  'Test[0-9]{3}!'
  'outpace[0-9]{4}'
  'demo[0-9]{3}'
  'TOKEN="eyJ'
  'Authorization: Bearer eyJ'
  'sk-[A-Za-z0-9_-]{20,}'
  'AIza[0-9A-Za-z_-]{20,}'
)

failed=0

for pattern in "${PATTERNS[@]}"; do
  if rg -n "${RG_ARGS[@]}" -e "$pattern"; then
    echo "Potential secret-like value matched pattern: $pattern" >&2
    failed=1
  fi
done

if rg -n "${RG_ARGS[@]}" -e '^[[:space:]#]*(HIGHERGOV|MISTRAL|PERPLEXITY)_API_KEY=' \
  | grep -Ev '(<set-|<key>|REPLACE|your-)' ; then
  echo "Potential committed API key assignment found" >&2
  failed=1
fi

tracked_artifacts="$(git ls-files '.claude' 'agent_docs' 'frontend/playwright-report' 'frontend/test-results' 'carfax_reports/*.json')"
if [ -n "$tracked_artifacts" ]; then
  echo "Generated/internal artifacts are tracked:" >&2
  echo "$tracked_artifacts" >&2
  failed=1
fi

if [ "$failed" -ne 0 ]; then
  echo "Secret scan failed" >&2
  exit 1
fi

echo "Secret scan passed"
