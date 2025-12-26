# TH-MC-003 Evidence Packet

## Certification Summary

| Field | Value |
|-------|-------|
| **Test ID** | TH-MC-003 |
| **Date** | 2025-12-25 |
| **Ruling** | BASELINE CERTIFIED |
| **Confidence** | 95% (Rule 59 satisfied) |

## Test Parameters

| Parameter | Value |
|-----------|-------|
| **Unit of Trial** | `carfax.sh all` via Git Bash with `API_URL=http://127.0.0.1:8000` |
| **Iterations Attempted** | 59 |
| **Iterations Passed** | 59 |
| **Iterations Failed** | 0 |
| **Pass Rate** | 100% |

## Environment

| Component | Version/Value |
|-----------|---------------|
| **Shell** | Git Bash 5.2.37 (MINGW64) |
| **Platform** | Windows host |
| **Namespace** | Unified (test runner + API on Windows) |
| **API URL** | `http://127.0.0.1:8000` |

## Statistical Basis

The Monte Carlo certification follows the **Rule of 59**:

> To achieve 95% confidence that a process has a true pass rate of at least 95%,
> you must observe 59 consecutive passes with zero failures.

This test achieved **59/59 passes (100%)**, satisfying the 95% confidence threshold.

## Artifacts

### Primary Log

| Attribute | Value |
|-----------|-------|
| **Path** | `mc_reports/mc_gitbash_20251225_184447.log` |
| **Type** | Consolidated Monte Carlo log |
| **Description** | Full output from 59-iteration run |
| **SHA256** | `1dfe921fa468893394704c2a7913192779a08d0dde90f293dc11899e97e220c5` |

### Final Report

| Attribute | Value |
|-----------|-------|
| **Path** | `carfax_reports/carfax_20251225_190120.json` |
| **Type** | Final baseline report |
| **Description** | 35/35 pass report from final iteration |
| **SHA256** | `2336ba0f3975840d8e408495c1f5d30bf28a3474ad3131745651ddc51883e192` |

## Hash Verification

To verify artifact integrity:

### PowerShell (Windows)
```powershell
Get-FileHash mc_reports/mc_gitbash_20251225_184447.log -Algorithm SHA256
# Expected: 1DFE921FA468893394704C2A7913192779A08D0DDE90F293DC11899E97E220C5

Get-FileHash carfax_reports/carfax_20251225_190120.json -Algorithm SHA256
# Expected: 2336BA0F3975840D8E408495C1F5D30BF28A3474AD3131745651DDC51883E192
```

### Git Bash / Linux
```bash
sha256sum mc_reports/mc_gitbash_20251225_184447.log
# Expected: 1dfe921fa468893394704c2a7913192779a08d0dde90f293dc11899e97e220c5

sha256sum carfax_reports/carfax_20251225_190120.json
# Expected: 2336ba0f3975840d8e408495c1f5d30bf28a3474ad3131745651ddc51883e192
```

## Reproduction Instructions

To reproduce this certification run:

### Prerequisites
1. Windows machine with Git Bash installed
2. API server running on port 8000
3. MongoDB container (`mongo-b2b`) running
4. Test fixtures seeded (`seed_carfax_tenants.py`, `seed_carfax_users.py`)

### Execution Command

**PowerShell:**
```powershell
& "C:\Program Files\Git\bin\bash.exe" -lc "API_URL=\"http://127.0.0.1:8000\" bash carfax.sh all"
```

**Git Bash:**
```bash
API_URL="http://127.0.0.1:8000" bash carfax.sh all
```

### Expected Output
- 35 tests executed per iteration
- All 35 tests pass (100% pass rate)
- Report generated in `carfax_reports/`

### Monte Carlo Validation
For full Monte Carlo certification, run 59 consecutive iterations:
```bash
for i in $(seq 1 59); do
  API_URL="http://127.0.0.1:8000" bash carfax.sh all
  if [ $? -ne 0 ]; then
    echo "FAILED at iteration $i"
    exit 1
  fi
done
echo "59/59 PASSED - Certification achieved"
```

## Certification Chain

| Step | Actor | Action | Timestamp |
|------|-------|--------|-----------|
| 1 | Test Advisor | Initiated Monte Carlo run | 2025-12-25 18:44:47 |
| 2 | Test Harness | Executed 59 iterations | 2025-12-25 18:44:47 - 19:01:20 |
| 3 | Test Advisor | Verified 59/59 passes | 2025-12-25 19:01:20 |
| 4 | Test Advisor | Certified baseline | 2025-12-25 19:01:20 |

## Related Documents

- [Verification Contract](../verification_contract.md)
- [Test Plan v3](../test-plan-v3.md)
- [GitHub Actions Proof Runbook](../github_actions_proof_runbook.md)

---

**Document Status:** IMMUTABLE
**Created:** 2025-12-25
**Author:** Test Advisor (Automated)
This document becomes immutable upon commit to the main branch and must not be modified after that point except through a controlled, auditable process for correcting clerical errors.
