# Verification Contract

> Last updated: 2025-12-19  
> Status: P0 Hardened  

This document defines what constitutes proof in the OutPace Intelligence Platform CI/CD system.

---

## Core Principle

**Green without proof is red.**

CI may only pass if there is cryptographic evidence that the sync contract was validated.

---

## What Constitutes Proof

Proof requires ALL of the following:

### 1. A Real Sync Call (SYNC-02)
- Exactly ONE real HTTP call to `/api/admin/sync/{tenant_id}`
- The call must block until completion (up to 120 seconds)
- Timeouts are NOT proof (they result in CI failure)
- Network errors are NOT proof (they result in CI failure)

### 2. Full Contract Validation
The sync response MUST contain these 7 fields with correct types:

| Field | Type | Description |
|-------|------|-------------|
| `tenant_id` | string (UUID) | RFC 4122 compliant UUID |
| `tenant_name` | string | Human-readable tenant name |
| `opportunities_synced` | integer | Count of synced opportunities |
| `intelligence_synced` | integer | Count of synced intelligence reports |
| `status` | enum | `success` or `partial` |
| `sync_timestamp` | string | ISO 8601 timestamp |
| `errors` | array | List of errors (empty on full success) |

### 3. Atomic Marker Write
After contract validation succeeds:
- A marker file is written atomically to `/tmp/carfax_sync02_ok.marker`
- Atomic write uses: `write to temp file` → `mv to final path`
- Marker contains proof metadata (tenant_id, status, timestamp, etc.)

### 4. Marker Gate Validation
CI validates the marker file:
- **Exists**: File must be present
- **Valid JSON**: Must parse without errors
- **Fresh**: `marker_created_utc` must be within 10 minutes of current UTC
- **UUID Valid**: `tenant_id` must match RFC 4122 format
- **Contract Validated**: `contract_validated` must be `true` (boolean, not string)

---

## What CI Trusts

| Trusted | Not Trusted |
|---------|-------------|
| Marker file existence + content | Log output patterns |
| JSON structure validation | String matching in stdout |
| Timestamp freshness checks | Timeout completion |
| UUID format validation | HTTP status codes alone |
| Atomic file operations | Retry success |

---

## Why SYNC-02 is Unique

SYNC-02 is the **only** real sync call allowed in CI because:

1. **Determinism**: One call produces one proof artifact
2. **Cost Control**: External API calls have rate limits and costs
3. **Reproducibility**: Single call = single state snapshot
4. **Auditability**: Marker file provides forensic evidence

### What About SYNC-01?

SYNC-01 is a **permission check only**:
- Uses 5-second timeout
- Only checks HTTP status code (expects 403 for tenant users)
- Does NOT execute a real sync
- Does NOT write any marker

---

## Why Marker Gating Exists

The marker file gate prevents these failure modes:

| Failure Mode | How Marker Prevents It |
|--------------|----------------------|
| CI passes on network timeout | Marker not written without valid response |
| CI passes on partial response | Contract validation catches missing fields |
| CI passes on stale proof | Freshness check rejects old markers |
| CI passes on test skip | No marker = gate fails |
| Log-based validation bypass | Marker is structured data, not grep target |

---

## Proof Chain

```
┌─────────────────┐
│  ci_verify.sh   │  ← Canonical CI entry point
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   carfax.sh     │  ← Executes test suites including SYNC-02
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    SYNC-02      │  ← Single real sync call
│  (test_S7_sync) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Contract Check  │  ← Validates 7 required fields
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Atomic Marker   │  ← Writes proof artifact
│     Write       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Marker Gate    │  ← Validates proof (exists + fresh + valid)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   CI Pass/Fail  │  ← Final determination
└─────────────────┘
```

---

## File Ownership

| File | Role | Sync Calls |
|------|------|------------|
| `ci_verify.sh` | Canonical CI runner | 0 (calls carfax.sh) |
| `carfax.sh` | Proof owner (SYNC-02) | 1 (SYNC-02 only) |
| `carfax_sync_contract.sh` | DEPRECATED (manual only) | 3 (not CI-safe) |
| `test_sync_contract.py` | Deep testing (excluded from CI) | Multiple |

---

## Negative Case Guarantees

CI MUST fail on:
- ❌ Missing marker file
- ❌ Malformed JSON in marker
- ❌ Stale marker (>10 minutes old)
- ❌ Invalid UUID in tenant_id
- ❌ `contract_validated` not `true`
- ❌ Missing required fields
- ❌ Curl timeout or network error during SYNC-02

Run `bash test_negative_cases.sh` to verify these guarantees.

---

## For Future Contributors

**DO NOT:**
- Add retries or sleeps to mask failures
- Accept timeouts as success
- Add additional sync calls to CI
- Bypass marker validation
- Use log grepping as proof
- Trust HTTP status codes without response body validation

**DO:**
- Fail fast and loud on any anomaly
- Maintain single proof ownership in `carfax.sh`
- Keep marker validation strict
- Document any changes to this contract
- Run negative case tests after changes

---

## Verification Commands

```bash
# Full CI verification (single sync, marker gate)
rm -f /tmp/carfax_sync02_ok.marker && bash ci_verify.sh

# Negative case proof
bash test_negative_cases.sh

# PR-mode verification (no sync)
cd backend && python -m pytest -m "not external_sync" -v

# View current marker
cat /tmp/carfax_sync02_ok.marker | python3 -m json.tool
```
