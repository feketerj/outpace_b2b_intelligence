# TASK: Test Suite Hardening

**Created:** 2026-01-07
**Priority:** HIGH
**Audited by:** Previous agent session
**Status:** COMPLETE (2026-01-07)

---

## CONTEXT

An audit of the test suite found that tests verify guards EXIST but don't verify guards WORK. This is "compliance theater" - the appearance of testing without actual validation.

**Pattern found:** Tests check `"$inc" in source_code` but don't verify quota actually limits concurrent access.

---

## CRITICAL GAPS TO CLOSE

### GAP 1: Data Flow (HIGH)
**Problem:** No test does INSERT→SELECT→verify. Could write corrupted data and never know.

**Tests to create in `backend/tests/test_data_flow.py`:**
```python
# 1. Write-read consistency
async def test_create_opportunity_persists_all_fields():
    """Create opportunity, query it back, verify all fields match."""

# 2. Update persistence
async def test_update_opportunity_persists_changes():
    """Update opportunity, query it back, verify changes persisted."""

# 3. Delete removes data
async def test_delete_opportunity_removes_record():
    """Delete opportunity, query it back, verify 404 or empty."""

# 4. Bulk insert consistency
async def test_csv_upload_creates_all_records():
    """Upload CSV with 10 records, verify all 10 queryable."""
```

---

### GAP 2: Idempotency (HIGH)
**Problem:** No protection against double-submit. Retry = duplicate records.

**Tests to create in `backend/tests/test_idempotency.py`:**
```python
# 1. Create with external_id deduplication
async def test_create_with_same_external_id_returns_existing():
    """POST twice with same external_id, verify same record returned."""

# 2. PATCH is idempotent
async def test_patch_same_status_twice_succeeds():
    """PATCH status=pursuing twice, both should succeed."""

# 3. DELETE is idempotent
async def test_delete_twice_handles_gracefully():
    """DELETE same record twice, second should be 404 or 204."""
```

**Implementation needed if tests fail:**
- Add `external_id` field to opportunities
- Add unique index on (tenant_id, external_id)
- Upsert logic in create endpoint

---

### GAP 3: Race Conditions (HIGH)
**Problem:** Code has `$inc` for atomic updates but no test proves it works under load.

**Tests to create in `backend/tests/test_concurrency.py`:**
```python
# 1. Concurrent quota updates
async def test_concurrent_chat_messages_respect_quota():
    """Spawn 20 concurrent requests, verify quota not exceeded."""

# 2. Concurrent opportunity updates
async def test_concurrent_status_updates_are_atomic():
    """Spawn 5 concurrent PATCH requests, verify consistent final state."""
```

---

### GAP 4: Integration Tests (HIGH)
**Problem:** Tests check source patterns, not actual HTTP responses.

**Tests to create in `backend/tests/test_integration.py`:**
```python
# 1. Full endpoint response validation
async def test_opportunities_endpoint_response_matches_schema():
    """Call GET /opportunities, validate response structure."""

# 2. Error response validation
async def test_401_error_response_format():
    """Call endpoint without auth, verify error response format."""

# 3. Cross-tenant request blocked
async def test_cross_tenant_request_returns_403():
    """Tenant A token, request Tenant B data, verify 403."""
```

---

### GAP 5: Pagination Edge Cases (MEDIUM)
**Tests to create in `backend/tests/test_pagination.py`:**
```python
async def test_pagination_boundary_values():
    """Create 25 records, test page=1,2,3 with per_page=10."""

async def test_invalid_page_returns_400():
    """page=-1 or page=0 should return 400."""

async def test_per_page_capped_at_maximum():
    """per_page=1000 should cap at 100."""
```

---

### GAP 6: Error Message Safety (MEDIUM)
**Tests to add to `backend/tests/test_adversarial.py`:**
```python
async def test_login_error_doesnt_leak_password():
    """POST /auth/login with wrong password, verify password not in response."""

async def test_db_error_not_exposed_to_client():
    """Trigger constraint violation, verify client gets generic error."""
```

---

## SUCCESS CRITERIA

1. All new tests pass ✓
2. Tests actually FAIL when protection is removed (verify by temporarily breaking code) ✓
3. `python scripts/doctor.py` still passes (regression check) ✓
4. Total test count increases by ~15-20 tests ✓ (Actually added 57 tests: 235 → 292)

## COMPLETION SUMMARY (2026-01-07)

| Gap | File | Tests Added |
|-----|------|-------------|
| GAP 1: Data Flow | test_data_flow.py | 9 |
| GAP 2: Idempotency | test_idempotency.py | 8 |
| GAP 3: Race Conditions | test_concurrency.py | 8 |
| GAP 4: Integration | test_integration.py | 12 |
| GAP 5: Pagination | test_pagination.py | 15 |
| GAP 6: Error Safety | test_adversarial.py | 5 |
| **TOTAL** | | **57** |

Implemented by fresh agent via hook-based context injection. Validated segregation of duties pattern (auditor creates specs, implementer executes).

---

## IMPLEMENTATION ORDER

1. **test_data_flow.py** - Most critical, foundation for everything else
2. **test_idempotency.py** - Prevents duplicate data issues
3. **test_concurrency.py** - Prevents race conditions
4. **test_integration.py** - Validates actual HTTP behavior
5. **test_pagination.py** - Edge case coverage
6. **test_adversarial.py additions** - Security hardening

---

## CONSTRAINTS

- Use existing test infrastructure (conftest.py fixtures)
- Use test database (DB_NAME=test), not production
- Tests must be independent (no shared state between tests)
- Tests must clean up after themselves
- Follow existing test patterns in codebase

---

## VERIFICATION

After implementation, run:
```bash
python scripts/doctor.py
```

All 7 checks must pass. If new tests fail, fix the underlying code - don't skip the tests.
