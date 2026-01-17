# Production Readiness Gap Status (Follow-up)

Date: 2026-01-15
Role: QC (read-only assessment)
Source baseline: `PRODUCTION_READINESS_AUDIT.md` (2025-01-23)

## Summary
- Many baseline gaps have been partially or fully addressed (rate limiting, env documentation, deployment guides, E2E coverage, sync contract hardening).
- Remaining risks center on external-dependency resilience (retries/circuit breakers), quota race/atomicity, caching/perf, and some CARFAX regressions (rate-limit induced failures, export status codes).

## Gap-by-Gap Assessment

### Error Handling & Silent Failures
- Global exception handler, notify_error, tracing: **present** (server.py).
- Silent external API handling: **likely unresolved** (no evidence of explicit retries or circuit breakers; services unchanged).
- Quota race condition (chat): **no atomic update fix observed**; CARFAX still shows rate-limit edge failures.

### Security
- Tenant isolation: **tests passing** (INV-1 suite, CARFAX isolation tests). No evidence of DB-level enforcement; still code-level only.
- File upload security: **partial**—basic MIME/size checks in upload.py; no content sniff/AV scan.
- Rate limiting storage: **memory backend** still default; no Redis config observed.
- Secrets management: **still env-based**; no vault integration noted.

### Data Integrity & Atomicity
- Sync atomicity: **partial**—sync endpoint exposed and contract enforced; no bulk/transactional rollback added.
- MongoDB transactions: **still standalone**; no replica set/migration tooling observed.
- Quota atomicity: **unfixed** (see above).

### Testing
- Unit/integration: **green** (289 tests). Tenant isolation and contract tests pass.
- Playwright E2E: **present and passing** (14 tests).
- CARFAX: **5/70 failing** (auth rate-limit edge, export 400 vs expected 404, perf auth 429). Evidence in latest run with API_URL=http://host.docker.internal:8000.
- Coverage: **still unknown** (no pytest-cov reports found).
- Load/security fuzz: **not observed**.

### Deployment/Docs/Operations
- `.env.example` and deployment docs: **present** (DEPLOYMENT.md, PROJECT_STATUS, PROJECT_MEMORY).
- Docker compose/Nginx/TLS: **present** per docs.
- Runbook/DR/backup: **not observed** (still gaps).
- Monitoring/alerting: **notify_error** exists; no documented monitoring stack.

### External Dependencies
- Retries/circuit breakers/rate-limit handling for upstreams: **not implemented** (per code inspection; no tenacity/circuitbreaker usage).
- API key rotation: **still static env-based**.

### Performance & Scalability
- Caching: **absent**.
- Connection pool tuning: **not evident** (defaults in database init).
- N+1 audit: **not evidenced**.

### Documentation & Operational Readiness
- Deployment guides improved; UI test plan exists.
- Comprehensive runbook/DR/backups/monitoring docs: **absent**.

## Outstanding Risks (high/critical)
- No retry/circuit breaker/fallback for external services (risk of cascade/availability).
- Chat quota atomicity/race not fixed; CARFAX auth rate-limit flakiness suggests limiter interplay.
- Exports return 400 where contract expects 404 (contract drift in CARFAX S6).
- CARFAX auth boundary tests failing due to 429 (rate limiter tuning/fixtures).
- No caching or connection pool tuning; potential perf under load.
- Secrets remain env-based; no centralized secret manager.
- Coverage metrics absent; load/security tests missing.

## Evidence Pointers
- Tests: backend pytest (289 pass), Playwright (14 pass), CARFAX (65/70 pass, 5 fail) – see latest QC run.
- Files reviewed: `backend/server.py`, `backend/routes/upload.py`, `docs/DEPLOYMENT.md`, `PROJECT_STATUS.md`, `PROJECT_MEMORY.md`, `carfax.sh`, `.env.example` (presence), `frontend/src/pages/TenantsPage.jsx` (sync toast contract), `docs/QC_REPORT.md` (latest QC summary).

## Next Actions (QC recommendations)
1) Add retry/backoff and circuit-breakers around HigherGov/Perplexity/Mistral; handle 429s gracefully.
2) Fix chat quota atomicity and rate-limit tuning to avoid 429 in auth boundary/perf strata.
3) Align exports contract to return 404 for empty/nonexistent selections per CARFAX expectations.
4) Introduce coverage reporting and load/security test suites.
5) Add caching/connection-pool tuning for Mongo; consider replica set for transactions.
6) Document runbook, DR, backups, and monitoring/alerting; integrate secrets manager.
7) Re-run CARFAX after fixes; ensure marker proof remains intact.
