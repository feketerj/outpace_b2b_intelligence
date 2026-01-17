# P0 Verification Hardening - Single SYNC-02 Proof + Marker Gating

## Summary

This PR completes the P0 remediation of the sync verification system, ensuring:
- **Exactly ONE real sync call** (SYNC-02) per CI run on merge-to-main
- **Zero sync calls** on PR checks
- **Marker-gated CI** with strict validation (7 fields, freshness ≤10min, strict UUID)
- **Canonical validator reuse** eliminating drift between workflow logic and validators

## What Changed

### Core Fix: Deterministic Sync Verification
The sync endpoints now block until completion and return a structured contract with exact counts.
CI proof is based on a marker file artifact, not log parsing or timeout behavior.

### Proof Chain
```
ci_verify.sh → carfax.sh → SYNC-02 → contract validation → atomic marker write → marker gate
```

### Files Changed

#### GitHub Actions Workflows
| File | Change |
|------|--------|
| `.github/workflows/merge-main.yml` | Single SYNC-02 runner, canonical marker validator import, artifact uploads |
| `.github/workflows/pr-checks.yml` | Removed `\|\| true` bypass, no sync calls allowed |
| `.github/workflows/nightly.yml` | Fixed matrix syntax, validator-only (no sync) |

#### Verification Scripts
| File | Change |
|------|--------|
| `carfax.sh` | Canonical proof owner banner, repo-relative paths, SYNC-02 writes marker atomically |
| `ci_verify.sh` | Canonical CI runner banner, repo-relative paths |
| `carfax_sync_contract.sh` | DEPRECATED with CI guard (blocks when `CI=true`) |
| `test_negative_cases.sh` | NEW: Proves CI fails on missing/stale/malformed markers |

#### Backend Tests
| File | Change |
|------|--------|
| `backend/tests/test_sync_contract.py` | Added `@pytest.mark.external_sync` (excluded from CI) |
| `backend/tests/test_sync_frontend_contract.py` | Repo-relative path resolution for GHA |

#### Documentation
| File | Change |
|------|--------|
| `docs/verification_contract.md` | NEW: Complete verification architecture documentation |

## Guarantees

| Guarantee | Enforcement |
|-----------|-------------|
| Single SYNC-02 per merge | Only `ci_verify.sh` → `carfax.sh` path triggers sync |
| No sync on PR | PR workflow uses `--pr-mode` marker exclusion |
| Marker gating | Canonical `marker_validator.py` validates 7 fields + freshness + UUID |
| Strict UUID | Default `strict_uuid=True` in all validators |
| No `/app` hardcoding | All paths use `$GITHUB_WORKSPACE` or repo-relative resolution |
| Artifact uploads | Marker + CARFAX reports uploaded on merge-to-main |

## How to Verify

### Local Verification
```bash
# Full CI verification (merge mode)
rm -f /tmp/carfax_sync02_ok.marker && bash ci_verify.sh

# Negative case proof
bash test_negative_cases.sh

# PR mode verification (no sync)
cd backend && python -m pytest -m "not external_sync" -v
```

### Expected Workflow Behavior

| Workflow | Trigger | SYNC-02 | Marker Gate | Artifacts |
|----------|---------|---------|-------------|-----------|
| `pr-checks.yml` | PR | ❌ No | ❌ No | ❌ No |
| `merge-main.yml` | Push to main | ✅ Yes (1) | ✅ Yes | ✅ Yes |
| `nightly.yml` | Cron 2AM UTC | ❌ No | ❌ No | ❌ No |

## Marker Schema (v1.0)

```json
{
  "tenant_id": "UUID (RFC 4122 strict)",
  "status": "success | partial",
  "sync_timestamp": "ISO 8601 UTC",
  "opportunities_synced": "integer",
  "intelligence_synced": "integer",
  "contract_validated": "true (boolean)",
  "marker_created_utc": "ISO 8601 UTC (fresh ≤10 min)"
}
```

## Artifacts Location

After merge-to-main workflow completes:
- **Marker artifact**: `sync-contract-marker` → `/tmp/carfax_sync02_ok.marker`
- **CARFAX reports**: `carfax-reports` → `carfax_reports/*.json`

## CI Runtime

- Current: ~36-54 seconds
- Limit: 180 seconds
- Margin: 70%+ headroom

## Breaking Changes

None. This PR only affects CI/verification infrastructure, not product behavior.

## Testing Checklist

- [x] `ci_verify.sh` passes locally (26/26 tests, marker gate valid)
- [x] `test_negative_cases.sh` passes (7/7 negative cases correctly fail)
- [x] YAML syntax validated for all workflows
- [x] Canonical validator import works in GHA-like context
- [x] Deprecated script blocked in CI environment
- [ ] PR workflow passes on GitHub Actions (no sync)
- [ ] Merge workflow passes on GitHub Actions (single SYNC-02)
- [ ] Artifacts visible in GitHub Actions after merge
