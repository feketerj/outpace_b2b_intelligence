# OutPace B2B Intelligence — Production Remediation Specification

> **Purpose**: Freeze the target so the agent doesn't "build something impressive but wrong."
> This document is the full project specification for the production remediation of `outpace_b2b_intelligence`.
> After reading this file, generate or update `PLAN.md` with a milestone-based plan, then execute via `IMPLEMENT.md`.

---

## Goals

1. **Credential Purge** — Remove all hardcoded test credentials from the codebase and git history. Replace with environment-variable-only patterns.
2. **Monolith Decomposition** — Break `frontend/src/pages/TenantsPage.jsx` (88KB) and `backend/routes/chat.py` (30KB) into maintainable, testable modules under 500 lines each.
3. **Branch Hygiene** — Clean up 5 stale branches, merge or close PR #23, establish branch protection rules.
4. **Repository Cleanup** — Remove dead code (CRA/craco holdovers, temp files, test artifacts from repo root), update `.gitignore`.
5. **Security Hardening** — Implement GCP Secret Manager integration, add `gitleaks` pre-commit hook, enforce CORS allowlist, add rate limiting to all public endpoints.
6. **Database Hardening** — Configure MongoDB Atlas with replica set, read/write concerns, TTL indexes, and connection retry logic.
7. **CI/CD Improvements** — Restore test coverage gate, fix broken Playwright test paths, add secret scanning to CI pipeline.
8. **Frontend Quality** — Fix TenantContext raw `fetch` bypass, add 404 catch-all route, remove unused dependencies (`zustand`, `recharts`), add loading skeletons.
9. **Intelligence Report Styling** — Improve the AI-generated intelligence report display with proper markdown rendering, citation formatting, and professional layout.
10. **Automated Data Pipelines** — Harden the HigherGov sync scheduler with retry logic, dead-letter queue, and observability.
11. **RAG Differentiation** — Enhance the RAG pipeline to provide genuinely differentiated tenant-specific AI responses vs generic chat.

---

## Non-Goals

- **No new features** — This is remediation only. Do not add new API endpoints, new pages, or new UI functionality beyond what's specified above.
- **No framework migrations** — Do not migrate from FastAPI to another framework, from MongoDB to PostgreSQL, or from Vite to another bundler.
- **No TypeScript conversion** — The frontend is `.jsx` by design. Do not convert to TypeScript.
- **No infrastructure provisioning** — Do not create GCP projects, MongoDB Atlas clusters, or CI runners. Only write the code that integrates with them.
- **No UI redesign** — The dark theme and branding system are complete. Only fix bugs and add missing polish (loading states, 404 page).
- **No dependency major version bumps** — Do not upgrade React 19, Vite 7, or FastAPI to new major versions unless required to fix a specific bug documented here.

---

## Hard Constraints

### Stack (Do Not Change)
- **Backend**: Python 3.11, FastAPI, Motor (async MongoDB), uvicorn
- **Frontend**: React 19, Vite 7, shadcn/ui (new-york style, JSX not TSX), Tailwind CSS
- **Database**: MongoDB 7.0 (Motor async driver)
- **Testing**: pytest + carfax.sh (bash integration tests) + Playwright E2E
- **CI**: GitHub Actions
- **Deployment**: Docker Compose (api + mongodb + nginx)

### Architecture Rules
- All database queries MUST include `tenant_id` filter (enforced by `backend/utils/invariants.py`)
- All API keys MUST come from environment variables, never hardcoded
- All error responses MUST include `trace_id` (from `backend/utils/tracing.py`)
- JWT auth uses access + refresh tokens; refresh tokens stored in MongoDB with `token_hash` and `jti` UUID
- The `carfax.sh` test harness is the SINGLE SOURCE OF TRUTH for sync contract validation — exactly ONE sync call per CI run
- `CLAUDE.md` in repo root is the existing agent operating protocol — READ IT FIRST, DO NOT OVERWRITE IT
- Per-tenant branding uses CSS custom properties (`--tenant-primary`, etc.) injected at runtime

### Quality Gates
- All existing tests (300+ pytest, 70+ carfax.sh, 14 Playwright E2E) MUST continue to pass
- No `except: pass` or bare `except Exception` without logging
- No files larger than 500 lines after decomposition (with exception of generated/vendored code like shadcn components)
- Every new function must have a docstring
- Every API endpoint change must update `docs/API_CONTRACT.json`

---

## Deliverables

When this remediation is complete, the following must exist:

### Files Created
- `backend/routes/chat/` — Directory replacing `chat.py` monolith (with `__init__.py`, `streaming.py`, `quota.py`, `history.py`, `rag_injection.py`, `domain_context.py`)
- `frontend/src/pages/tenants/` — Directory replacing `TenantsPage.jsx` (with `index.jsx`, `TenantList.jsx`, `TenantForm.jsx`, `BrandingTab.jsx`, `SearchProfileTab.jsx`, `IntelligenceConfigTab.jsx`, `ChatPolicyTab.jsx`, `KnowledgeTab.jsx`, `AgentConfigTab.jsx`, `ScoringWeightsTab.jsx`)
- `frontend/src/pages/NotFoundPage.jsx` — 404 catch-all route
- `.gitleaks.toml` — Gitleaks configuration at repo root
- `.pre-commit-config.yaml` — Pre-commit hooks including gitleaks
- `backend/utils/secret_manager.py` — GCP Secret Manager integration (with env var fallback)
- `docs/AUDIT_FINDINGS.md` — Populated (currently empty 0-byte placeholder)

### Files Modified
- `.gitignore` — Updated to exclude `*.sh` test scripts with credentials, `test_export.*`, `tmpclaude-*`, `carfax_reports/`
- `backend/database.py` — Connection retry logic, read/write concern configuration
- `backend/server.py` — CORS allowlist from env var (not wildcard)
- `frontend/src/App.jsx` — Add 404 route, remove unused imports
- `frontend/src/context/TenantContext.jsx` — Replace raw `fetch` with `apiClient`
- `frontend/src/pages/SuperAdminDashboard.jsx` — Live health status from `/health` endpoint
- `frontend/src/pages/DatabaseManager.jsx` — Replace hardcoded conversation IDs with API call
- `frontend/package.json` — Remove `zustand` and `recharts` if confirmed unused
- `backend/routes/intelligence.py` — Enhanced report formatting with markdown support
- `backend/scheduler/sync_scheduler.py` — Retry logic, dead-letter pattern, observability hooks

### Files Deleted
- `tmpclaude-a604-cwd` (repo root)
- `frontend/tmpclaude-54a6-cwd`
- `test_export.pdf` (repo root)
- `test_export.xlsx` (repo root)
- `frontend/craco.config.js`
- `frontend/plugins/` (entire directory — 4 dead webpack plugin files, ~58KB)
- `frontend/src/App.css` (unused CRA boilerplate)

### Git History Cleanup
- `carfax.sh` credentials purged from git history using `git filter-repo` or BFG Repo Cleaner
- All references to `Admin123!` and `Test123!` removed from committed files (24+ files)

### Branch Cleanup
- `claude/add-ci-workflows-s7vHh` — deleted
- `claude/add-test-dockerfile-kya9r` — deleted
- `feature/docker-compose-test` — deleted
- `feature/test-infrastructure` — deleted
- `fix/production-audit-remediation` — merged via PR #23 then branch deleted

---

## "Done When" Checklist

Every item must be true before this remediation is considered complete:

- [ ] `grep -r "Admin123!" .` returns zero results (excluding this spec file)
- [ ] `grep -r "Test123!" .` returns zero results (excluding this spec file)
- [ ] `grep -r "admin@outpace.ai" . --include="*.py" --include="*.js" --include="*.jsx" --include="*.sh"` returns zero results in source code (only in `.env.example` and docs)
- [ ] `wc -l backend/routes/chat.py` — file no longer exists (replaced by `chat/` package)
- [ ] `wc -l frontend/src/pages/TenantsPage.jsx` — file no longer exists (replaced by `tenants/` directory)
- [ ] No file in `backend/routes/chat/` exceeds 500 lines
- [ ] No file in `frontend/src/pages/tenants/` exceeds 500 lines
- [ ] `git branch -r` shows only `origin/main` (all stale branches deleted)
- [ ] `pytest` passes with 0 failures
- [ ] `bash carfax.sh` passes 70/70 tests
- [ ] `npx playwright test` passes all 14+ tests
- [ ] `gitleaks detect --source .` reports 0 findings
- [ ] `ls tmpclaude-* test_export.* frontend/craco.config.js frontend/plugins/ frontend/src/App.css 2>/dev/null` returns nothing
- [ ] `.gitignore` contains entries for: `tmpclaude-*`, `test_export.*`, `carfax_reports/`, `.env*` (except `.env.example`)
- [ ] `curl localhost:8000/health` returns JSON with live MongoDB status (not hardcoded)
- [ ] Frontend navigation to `/nonexistent-path` shows a styled 404 page
- [ ] `docs/AUDIT_FINDINGS.md` has content (not 0 bytes)
- [ ] All commits pass `gitleaks` pre-commit hook
