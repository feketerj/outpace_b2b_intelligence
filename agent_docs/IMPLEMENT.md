# OutPace B2B Intelligence — Implementation Runbook

> **Purpose**: This is the execution runbook. It tells the agent exactly how to operate.
> Follow the plan in `PLAN.md` milestone-by-milestone. Run validations after each. Update this file continuously.

---

## Operating Protocol

### Source of Truth
- `PROMPT.md` — What to build (specification)
- `PLAN.md` — How to build it (milestones + validation)
- `IMPLEMENT.md` — How to operate (this file — boundaries + status tracking)
- `CLAUDE.md` (repo root) — Existing agent constraints — **READ THIS FIRST, OBEY ITS RULES**

### Execution Rules

1. **Follow `PLAN.md` milestone-by-milestone.** Do not skip ahead.
2. **Run validation after each milestone.** If validation fails, fix before moving on.
3. **Keep diffs scoped.** Each commit should correspond to one milestone or one logical sub-task within a milestone.
4. **Do not expand scope.** If you discover a new issue not covered in `PROMPT.md`, document it in `docs/AUDIT_FINDINGS.md` but do not fix it unless it blocks a milestone.
5. **Update this file continuously.** After completing each milestone, update the Status Tracker below.
6. **Commit messages follow conventional format:** `fix:`, `feat:`, `chore:`, `refactor:`, `docs:`, `test:` prefixes.
7. **No placeholder code.** Every function must be complete and working. No `# TODO`, `pass`, or `raise NotImplementedError` in production paths.
8. **Test before commit.** Run `pytest --tb=short -q` before every commit. If tests fail, fix them first.

---

## Three-Tier Boundaries

### ✅ ALWAYS (Do these without asking)
- Delete files listed in `PLAN.md` Milestone 1 (temp files, dead code)
- Update `.gitignore` with new entries
- Replace hardcoded credentials with environment variable reads
- Decompose `chat.py` and `TenantsPage.jsx` following the exact module structure in `PLAN.md`
- Add docstrings to new functions
- Run tests after every change
- Fix any test you break
- Commit working code at each milestone boundary
- Update `docs/AUDIT_FINDINGS.md` with findings
- Preserve all existing `data-testid` attributes during frontend refactoring
- Keep all existing API endpoint URLs unchanged (same paths, same methods)
- Log important operations (connection retries, sync failures, credential reads)

### ⚠️ ASK FIRST (Pause and request approval before doing these)
- Merging or closing PR #23 (Milestone 8) — requires owner decision on whether the 14-file change is still valid after this remediation
- Force-pushing to `main` after git history rewrite (Milestone 9) — destructive action
- Deleting remote branches — confirm no valuable unmerged work
- Adding new Python dependencies (pip packages) not already in `requirements.txt`
- Adding new npm dependencies not already in `package.json`
- Changing any API endpoint URL or HTTP method
- Modifying the `carfax.sh` test harness beyond credential variable extraction
- Changing MongoDB collection names or index definitions
- Modifying `CLAUDE.md` (the existing agent protocol doc)

### 🚫 NEVER (Do not do these under any circumstances)
- Add new features not specified in `PROMPT.md`
- Convert `.jsx` files to `.tsx`
- Migrate from FastAPI to another framework
- Migrate from MongoDB to another database
- Change the React version, Vite version, or any major dependency version
- Use `["*"]` for CORS origins
- Use `except: pass` or bare `except Exception` without logging
- Commit real production credentials, API keys, or passwords
- Remove or weaken existing test assertions
- Delete test files or reduce test count
- Modify the single-sync invariant in `carfax.sh` (exactly ONE sync call per CI run)
- Force push to any branch except during Milestone 9 (git history cleanup)
- Create files larger than 500 lines (except generated/vendored code)
- Use `# TODO` or `# FIXME` without an accompanying implementation

---

## Commit Strategy

### Commit Sequence (one commit per sub-section)

| Commit | Milestone | Message | Files |
|--------|-----------|---------|-------|
| 1 | M1 | `chore: remove temp files and dead CRA/craco code` | delete 7 files/dirs |
| 2 | M1 | `chore: update .gitignore with temp files and test artifacts` | `.gitignore` |
| 3 | M2 | `fix(security): replace hardcoded credentials with env vars in test scripts` | `carfax.sh`, `ci_verify.sh`, `carfax_sync_contract.sh`, seed scripts |
| 4 | M2 | `fix(security): replace hardcoded credentials in Playwright tests` | `auth.spec.ts` |
| 5 | M2 | `fix(security): update CI workflows and .env.example for credential env vars` | CI YAMLs, `.env.example` |
| 6 | M3 | `refactor(backend): decompose chat.py into chat/ package` | `backend/routes/chat/*`, delete `chat.py` |
| 7 | M4 | `refactor(frontend): decompose TenantsPage.jsx into tenants/ directory` | `frontend/src/pages/tenants/*`, delete `TenantsPage.jsx`, update `App.jsx` |
| 8 | M5 | `fix(frontend): replace raw fetch in TenantContext with apiClient` | `TenantContext.jsx` |
| 9 | M5 | `feat(frontend): add 404 catch-all route` | `NotFoundPage.jsx`, `App.jsx` |
| 10 | M5 | `fix(frontend): live health status in SuperAdminDashboard` | `SuperAdminDashboard.jsx` |
| 11 | M5 | `fix(frontend): DatabaseManager chat tab uses real conversation API` | `DatabaseManager.jsx`, possibly new backend endpoint |
| 12 | M5 | `chore(frontend): remove unused zustand and recharts deps` | `package.json`, `package-lock.json` |
| 13 | M5 | `fix(test): move export-download spec to e2e dir, fix port` | move + edit spec file |
| 14 | M6 | `feat(security): add gitleaks config and pre-commit hooks` | `.gitleaks.toml`, `.pre-commit-config.yaml` |
| 15 | M6 | `feat(backend): add GCP Secret Manager integration with env fallback` | `backend/utils/secret_manager.py`, modify `secrets.py` |
| 16 | M6 | `fix(security): CORS reads allowed origins from env var` | `backend/server.py`, `.env.example` |
| 17 | M6 | `docs: populate AUDIT_FINDINGS.md with remediation results` | `docs/AUDIT_FINDINGS.md` |
| 18 | M7 | `fix(backend): add MongoDB connection retry and write concerns` | `backend/database.py` |
| 19 | M7 | `fix(backend): add retry and dead-letter pattern to sync scheduler` | `backend/scheduler/sync_scheduler.py` |
| 20 | M7 | `fix(ci): restore test coverage gate at 70%` | `.github/workflows/ci.yml` |
| 21 | M8 | `chore: delete stale branches` | branch operations |
| 22 | M9 | `chore(security): purge credentials from git history` | history rewrite |
| 23 | M10 | `docs: update project status and README for post-remediation` | `docs/PROJECT_STATUS.md`, `README.md` |

---

## Status Tracker

Update this section after completing each milestone.

| Milestone | Status | Started | Completed | Notes |
|-----------|--------|---------|-----------|-------|
| M0: Recon | ✅ Completed | 2026-03-06 | 2026-03-06 | Read all required files; captured baseline inventory and command outputs. |
| M1: Repo Cleanup | ✅ Completed | 2026-03-06 | 2026-03-06 | Deleted temp/dead files and updated .gitignore; pytest has pre-existing environment/import issues. |
| M2: Credential Purge | 🟨 In Progress | 2026-03-06 | — | Replaced hardcoded credentials across shell/python/e2e files and .env.example; broader test suite still failing for unrelated baseline reasons. |
| M3: chat.py Decomposition | ⬜ Not Started | — | — | |
| M4: TenantsPage Decomposition | ⬜ Not Started | — | — | |
| M5: Frontend Fixes | ⬜ Not Started | — | — | |
| M6: Security Hardening | ⬜ Not Started | — | — | |
| M7: DB & Backend Hardening | ⬜ Not Started | — | — | |
| M8: Branch Cleanup & PR #23 | ⬜ Not Started | — | — | |
| M9: Git History Cleanup | ⬜ Not Started | — | — | |
| M10: Final Validation | ⬜ Not Started | — | — | |

---

## Discovered Issues (Not In Original Scope)

Log any new issues found during execution here. Do not fix them unless they block a milestone.

| # | Issue | Severity | Blocks Milestone? | Resolution |
|---|-------|----------|-------------------|------------|
| — | — | — | — | — |

---

## Rollback Plan

If a milestone introduces a regression that cannot be fixed within the milestone:

1. `git stash` or `git reset --hard HEAD~N` to undo the milestone's commits
2. Document the failure in the "Discovered Issues" table above
3. Skip to the next milestone if the failure is non-blocking
4. If the failure blocks all subsequent milestones, stop and report

### Critical Rollback Points
- **Before M3 (chat.py decomposition)**: This is the riskiest refactor. Ensure all tests pass at M2 completion before starting M3.
- **Before M9 (history rewrite)**: Point of no return for git history. Ensure all code changes are complete and tested.

---

## Environment Variables Reference

These environment variables must be set for tests to pass after Milestone 2:

```bash
# Test credentials (set in CI via GitHub Secrets, locally via .env.test.local)
export CARFAX_ADMIN_EMAIL="admin@outpace.ai"
export CARFAX_ADMIN_PASSWORD="<set-from-secrets>"
export CARFAX_TENANT_A_EMAIL="tenant-b-test@test.com"
export CARFAX_TENANT_A_PASSWORD="<set-from-secrets>"
export CARFAX_TENANT_B_EMAIL="enchandia-test@test.com"
export CARFAX_TENANT_B_PASSWORD="<set-from-secrets>"
export E2E_ADMIN_PASSWORD="<set-from-secrets>"

# Existing env vars (already documented in .env.example)
export MONGO_URL="mongodb://..."
export JWT_SECRET="..."
export DB_NAME="outpace_intelligence"
export MISTRAL_API_KEY="..."
export PERPLEXITY_API_KEY="..."
export HIGHERGOV_API_KEY="..."

# New in this remediation
export CORS_ALLOWED_ORIGINS="https://your-domain.com"
export GOOGLE_CLOUD_PROJECT=""  # Optional — enables GCP Secret Manager
export WRITE_CONCERN="majority"  # MongoDB write concern (default: majority)
```

---

## Quick Reference: Key File Paths

| Purpose | Path |
|---------|------|
| FastAPI entry point | `backend/server.py` |
| MongoDB connection | `backend/database.py` |
| Auth/JWT utilities | `backend/utils/auth.py` |
| Tenant isolation guards | `backend/utils/invariants.py` |
| Existing secrets module | `backend/utils/secrets.py` |
| Request tracing | `backend/utils/tracing.py` |
| Retry/circuit breaker | `backend/utils/resilience.py` |
| Sync scheduler | `backend/scheduler/sync_scheduler.py` |
| Frontend routes | `frontend/src/App.jsx` |
| API client (axios) | `frontend/src/lib/api.js` |
| Auth context | `frontend/src/context/AuthContext.jsx` |
| Tenant context | `frontend/src/context/TenantContext.jsx` |
| Theme effects | `frontend/src/utils/themeEffects.js` |
| CI pipeline | `.github/workflows/ci.yml` |
| Test harness | `carfax.sh` |
| Agent protocol | `CLAUDE.md` |
| API contract | `docs/API_CONTRACT.json` |
| Design guidelines | `docs/DESIGN_GUIDELINES.json` |
