# QC Checklist Extensions

Updated: 2026-01-12

This checklist extends QC coverage for the areas requested. Use it as an audit guide; collect evidence (artifacts, logs, marker files) for each item.

## Compliance & Evidence
- Verify marker proof chain: run `ci_verify.sh`/`carfax.sh` and validate `/tmp/carfax_sync02_ok.marker` (freshness, types, required fields).
- Reject log-grep “proof”; require structured artifacts for CI pass.
- Confirm GitHub Actions workflows enforce the marker gate and do not skip tests.

## Environment & Platform Blindness
- Run doctor/guards on POSIX shell to avoid Windows path breakage; ensure scripts handle CRLF and mangled paths.
- Validate WSL/host networking guidance (`host.docker.internal`) in tests and Docker flows.
- Check for OS-dependent assumptions in scripts (bash paths, shebangs).

## Technical Debt & Dead Code
- Scan for TODO/FIXME/XXX, stubs, skeletons; ensure none are in critical paths.
- Re-scan routes for unexposed handlers (e.g., missing `@router` decorators).
- Identify tight couplings (e.g., slowapi Request requirement) that block unit invocations.

## Narrative vs. Reality
- Cross-check documented PASS claims against fresh runs (doctor, pytest, carfax, Playwright). Require current artifacts.
- Ensure docs (PROJECT_STATUS, PROJECT_MEMORY, TEST_PLAN) match code behavior and endpoints.

## Preconditions & Guards
- Confirm env var preflight must pass before serving; validate required secrets present.
- Verify auth/rate-limit/role checks on every endpoint, including bulk upload and sync status.
- Ensure tests provide required dependencies (e.g., Request when limiter enabled) or limiter is disabled in unit context.

## Split Brain / Cross-Contamination
- Re-run tenant isolation and cross-tenant access tests; check tenant scoping in bulk imports and deletes.
- Validate concurrency/idempotency suites for race/run conditions.

## Data Flow & State
- Re-run data_flow tests once limiter/test harness mismatch is addressed; verify INSERT→SELECT consistency and bulk CSV ingest integrity.
- Confirm delete paths truly delete and return 404 for missing resources (no silent data loss).

## Contracts & Drift
- Compare live OpenAPI/spec to docs/API_CONTRACT.json and TEST_PLAN invariants; ensure sync/status endpoint is covered.
- Validate response schemas vs. invariants; watch for lying code or mismatched docstrings.

## Testing Integrity
- Ensure tests are not altered during runs; no skips/xfails hiding failures. Non-zero exit on doctor/pytest failures.
- Guard against agents faking results: require stored artifacts/logs for claims.

## Frontend Coverage
- Remember frontend is in scope: run Playwright E2E and UI test plan; verify .env alignment with backend.

## Corruption & Paths
- Check for mangled paths, CRLF issues, and corrupted files in scripts/docker-compose mounts.
- Verify stop-weight delimiters/empty shapes are not used to mask missing data.

## Scope & Context
- Watch scope creep: keep SSOT for env/seed data; update docs when behavior changes.
- Confirm doc/context freshness checks remain active (doctor step 7).
