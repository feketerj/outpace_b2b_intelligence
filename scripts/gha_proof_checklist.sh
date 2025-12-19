#!/bin/bash
#
# GitHub Actions Proof Checklist
# ===============================
# Prints the exact log strings and artifacts to verify in GitHub Actions.
# This script makes NO network calls - it is purely instructional.
#
# Usage: bash scripts/gha_proof_checklist.sh
#

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}╔═══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║           GITHUB ACTIONS PROOF CHECKLIST                                      ║${NC}"
echo -e "${BOLD}║           (No network calls - instructional only)                             ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  1. PR WORKFLOW VERIFICATION${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✓ LOG STRINGS THAT MUST APPEAR:${NC}"
echo "    \"PR checks complete (no external sync calls)\""
echo "    \"passed\" (pytest summary)"
echo ""
echo -e "${RED}✗ LOG STRINGS THAT MUST NOT APPEAR:${NC}"
echo "    \"SYNC-02\""
echo "    \"/api/admin/sync\""
echo "    \"/api/sync/manual\""
echo "    \"admin_sync_returns_full_contract\""
echo ""
echo -e "${YELLOW}  Search tip: Use Ctrl+F in the workflow log viewer${NC}"
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  2. MERGE WORKFLOW VERIFICATION${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✓ SYNC-02 PROOF (must appear EXACTLY ONCE):${NC}"
echo "    \"SYNC-02: admin_sync_returns_full_contract\""
echo ""
echo "    How to verify:"
echo "    1. Open merge workflow run"
echo "    2. Expand 'Run CI verification' step"
echo "    3. Ctrl+F search for 'SYNC-02'"
echo "    4. Count occurrences (must be exactly 1)"
echo ""
echo -e "${GREEN}✓ MARKER GATE PROOF (must appear):${NC}"
echo "    \"MARKER GATE PASSED: tenant=\""
echo ""
echo "    Full expected format:"
echo "    \"MARKER GATE PASSED: tenant=8aa521eb..., status=success, age=Xs, opp=N, intel=N\""
echo ""
echo -e "${GREEN}✓ CI SUMMARY (must appear):${NC}"
echo "    \"✅ ALL CI CHECKS PASSED\""
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  3. ARTIFACTS TO VERIFY${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Location: Bottom of merge workflow run page → 'Artifacts' section"
echo ""
echo -e "${GREEN}  Required Artifacts:${NC}"
echo "    ┌─────────────────────────┬─────────────────────────────────────────┐"
echo "    │ Artifact Name           │ Contents                                │"
echo "    ├─────────────────────────┼─────────────────────────────────────────┤"
echo "    │ sync-contract-marker    │ /tmp/carfax_sync02_ok.marker (JSON)     │"
echo "    │ carfax-reports          │ carfax_reports/*.json                   │"
echo "    └─────────────────────────┴─────────────────────────────────────────┘"
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  4. NIGHTLY WORKFLOW VERIFICATION (if triggered)${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✓ LOG STRINGS THAT MUST APPEAR:${NC}"
echo "    \"Monte Carlo Summary\""
echo "    \"SYNC-02: NOT RUN (nightly uses validators only)\""
echo ""
echo -e "${RED}✗ LOG STRINGS THAT MUST NOT APPEAR:${NC}"
echo "    \"admin_sync_returns_full_contract\""
echo "    \"/api/admin/sync\""
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  5. EVIDENCE TEMPLATE (copy and fill)${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
cat << 'TEMPLATE'
═══════════════════════════════════════════════════════════════
GITHUB ACTIONS VERIFICATION EVIDENCE
═══════════════════════════════════════════════════════════════

PR URL:
  https://github.com/feketerj/outpace_b2b_intelligence/pull/___

PR WORKFLOW:
  URL: https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___
  Status: [PASS/FAIL]
  Sync calls detected: [YES/NO]

MERGE WORKFLOW:
  URL: https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___
  Status: [PASS/FAIL]
  
  SYNC-02 Log Line:
    [paste: "✅ PASS: SYNC-02: admin_sync_returns_full_contract"]
  
  Marker Gate Log Line:
    [paste: "MARKER GATE PASSED: tenant=..."]
  
  SYNC-02 Count: [1]

ARTIFACTS:
  sync-contract-marker: [YES/NO]
  carfax-reports: [YES/NO]

NIGHTLY WORKFLOW (optional):
  URL: https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___
  Status: [PASS/FAIL]

═══════════════════════════════════════════════════════════════
TEMPLATE
echo ""

echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  6. PASS/FAIL CRITERIA${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  All of the following must be TRUE for verification to pass:"
echo ""
echo "    [ ] PR workflow completed successfully"
echo "    [ ] PR workflow made ZERO sync calls"
echo "    [ ] Merge workflow completed successfully"
echo "    [ ] Merge workflow executed EXACTLY ONE SYNC-02"
echo "    [ ] Merge workflow shows 'MARKER GATE PASSED'"
echo "    [ ] Artifact 'sync-contract-marker' is present"
echo "    [ ] Artifact 'carfax-reports' is present"
echo ""
echo -e "${GREEN}  If all checks pass: Verification system is proven in real GitHub Actions.${NC}"
echo -e "${RED}  If any check fails: Investigate and fix before declaring success.${NC}"
echo ""

echo -e "${BOLD}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  END OF CHECKLIST${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Full runbook: docs/github_actions_proof_runbook.md"
echo "  PR description: PR_DESCRIPTION.md"
echo ""
