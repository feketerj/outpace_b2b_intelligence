# OutPace B2B Intelligence — Production Remediation Plan

> **Purpose**: Turn open-ended work into a sequence of checkpoints the agent can finish and verify.
> Each milestone is small enough to complete in one loop. Stop-and-fix rule: if validation fails, repair before moving on.
> This plan references `PROMPT.md` as the specification. Read it first.

---

## Architecture Overview

```
outpace_b2b_intelligence/
├── backend/
│   ├── routes/
│   │   ├── chat/                    # NEW — decomposed from chat.py (30KB)
│   │   │   ├── __init__.py          # Router aggregation + exports
│   │   │   ├── streaming.py         # SSE streaming logic
│   │   │   ├── quota.py             # Monthly quota enforcement
│   │   │   ├── history.py           # Chat history CRUD
│   │   │   ├── rag_injection.py     # RAG document retrieval + injection
│   │   │   └── domain_context.py    # Tenant domain context for system prompts
│   │   └── ... (other routes unchanged)
│   ├── utils/
│   │   └── secret_manager.py        # NEW — GCP Secret Manager with env fallback
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── tenants/             # NEW — decomposed from TenantsPage.jsx (88KB)
│   │   │   │   ├── index.jsx        # Page shell + state coordination
│   │   │   │   ├── TenantList.jsx   # Tenant cards grid
│   │   │   │   ├── TenantForm.jsx   # Create/Edit dialog shell with tabs
│   │   │   │   ├── BrandingTab.jsx  # Logo, colors, themes, backgrounds
│   │   │   │   ├── SearchProfileTab.jsx
│   │   │   │   ├── IntelligenceConfigTab.jsx
│   │   │   │   ├── ChatPolicyTab.jsx
│   │   │   │   ├── KnowledgeTab.jsx
│   │   │   │   ├── AgentConfigTab.jsx
│   │   │   │   └── ScoringWeightsTab.jsx
│   │   │   ├── NotFoundPage.jsx     # NEW — 404 catch-all
│   │   │   └── ... (other pages unchanged)
│   │   └── ...
│   └── ...
├── .gitleaks.toml                   # NEW
├── .pre-commit-config.yaml          # NEW
└── agent_docs/                      # NEW — this planning directory
    ├── PROMPT.md
    ├── PLAN.md                      # This file
    └── IMPLEMENT.md
```

---

## Milestone 0: Reconnaissance & Setup (Read-Only)

**Objective**: Understand the current state before changing anything. Read all files that will be modified.

### Tasks
- [ ] Read `CLAUDE.md` (repo root) — understand existing agent constraints and TTPs
- [ ] Read `backend/routes/chat.py` — map all functions, imports, and inter-dependencies
- [ ] Read `frontend/src/pages/TenantsPage.jsx` — map all state variables, handlers, and tab boundaries
- [ ] Read `frontend/src/context/TenantContext.jsx` — understand raw fetch pattern
- [ ] Read `frontend/src/App.jsx` — understand current route structure
- [ ] Read `backend/database.py` — understand current connection logic
- [ ] Read `backend/server.py` — understand middleware and CORS config
- [ ] Read `.gitignore` — understand current exclusions
- [ ] Read `backend/utils/secrets.py` — understand existing secrets pattern (13.3KB, large)
- [ ] Run `pytest --tb=short -q` — capture baseline test results
- [ ] Run `grep -rn "Admin123!" --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx" .` — capture credential spread
- [ ] Run `wc -l backend/routes/chat.py frontend/src/pages/TenantsPage.jsx` — capture baseline sizes

### Acceptance Criteria
- You have read every file listed above
- You have a written inventory of functions in `chat.py` and state/handlers in `TenantsPage.jsx`
- Baseline test results are captured (expected: 300+ pass, 0 fail)

### Validation
```bash
echo "Milestone 0: Recon complete — all files read, baseline captured"
```

---

## Milestone 1: Repository Cleanup & .gitignore

**Objective**: Remove dead files, temp files, test artifacts, and CRA holdovers. Update `.gitignore`.

### Tasks
- [ ] Delete `tmpclaude-a604-cwd` from repo root
- [ ] Delete `frontend/tmpclaude-54a6-cwd`
- [ ] Delete `test_export.pdf` from repo root
- [ ] Delete `test_export.xlsx` from repo root
- [ ] Delete `frontend/craco.config.js`
- [ ] Delete `frontend/plugins/` directory (all 4 files: `health-check/health-endpoints.js`, `health-check/webpack-health-plugin.js`, `visual-edits/babel-metadata-plugin.js`, `visual-edits/dev-server-setup.js`)
- [ ] Delete `frontend/src/App.css` (unused CRA boilerplate — verify no imports reference it first)
- [ ] Update `.gitignore` to add:
  ```
  # Agent temp files
  tmpclaude-*
  
  # Test artifacts
  test_export.*
  carfax_reports/
  
  # Environment files
  .env
  .env.*
  !.env.example
  
  # Playwright artifacts
  frontend/playwright-report/
  frontend/test-results/
  ```
- [ ] Verify `frontend/src/App.css` is not imported anywhere: `grep -r "App.css" frontend/src/`

### Acceptance Criteria
- All 7 files/directories listed above are deleted
- `.gitignore` contains the new entries
- No import references to deleted files

### Validation
```bash
# Verify deletions
ls tmpclaude-* test_export.* frontend/craco.config.js frontend/plugins/ frontend/src/App.css 2>/dev/null && echo "FAIL: files still exist" || echo "PASS: all deleted"

# Verify .gitignore
grep -q "tmpclaude-" .gitignore && grep -q "test_export" .gitignore && grep -q "carfax_reports" .gitignore && echo "PASS: .gitignore updated" || echo "FAIL: .gitignore incomplete"

# Verify no broken imports
grep -r "App.css" frontend/src/ && echo "FAIL: App.css still imported" || echo "PASS: no broken imports"

# Run tests to ensure nothing broke
pytest --tb=short -q
```

**Stop-and-fix**: If any test fails after deletions, the deleted file was actually used. Restore it and investigate.

---

## Milestone 2: Credential Purge (Source Code)

**Objective**: Remove all hardcoded test credentials from source files. Replace with environment variable references.

### Tasks
- [ ] Audit all files containing `Admin123!`: `grep -rn "Admin123!" --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx" .`
- [ ] Audit all files containing `Test123!`: `grep -rn "Test123!" --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx" .`
- [ ] Audit all files containing `admin@outpace.ai` in source code: `grep -rn "admin@outpace.ai" --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx" .`
- [ ] In `carfax.sh`: Replace hardcoded credentials with environment variable reads:
  ```bash
  # BEFORE:
  ADMIN_EMAIL="admin@outpace.ai"
  ADMIN_PASSWORD="Admin123!"
  # AFTER:
  ADMIN_EMAIL="${CARFAX_ADMIN_EMAIL:?CARFAX_ADMIN_EMAIL not set}"
  ADMIN_PASSWORD="${CARFAX_ADMIN_PASSWORD:?CARFAX_ADMIN_PASSWORD not set}"
  ```
- [ ] In `carfax_sync_contract.sh`: Same pattern as above
- [ ] In `ci_verify.sh`: Same pattern
- [ ] In `scripts/seed_carfax_tenants.py`: Replace hardcoded passwords with `os.environ.get()` calls
- [ ] In `scripts/seed_carfax_users.py`: Same
- [ ] In Playwright E2E tests (`frontend/e2e/auth.spec.ts`): Replace `Admin123!` with `process.env.E2E_ADMIN_PASSWORD`
- [ ] In `docker-compose.test.yml`: Add environment variables for test credentials (read from `.env.test.local` or CI secrets)
- [ ] In GitHub Actions workflows (`ci.yml`, etc.): Add credential env vars that map to GitHub Secrets
- [ ] Update `.env.example` to include the new credential env vars with placeholder values:
  ```
  CARFAX_ADMIN_EMAIL=admin@your-domain.com
  CARFAX_ADMIN_PASSWORD=changeme
  CARFAX_TENANT_A_EMAIL=tenant-a@test.com
  CARFAX_TENANT_A_PASSWORD=changeme
  CARFAX_TENANT_B_EMAIL=tenant-b@test.com
  CARFAX_TENANT_B_PASSWORD=changeme
  E2E_ADMIN_PASSWORD=changeme
  ```
- [ ] In every file: ensure `admin@outpace.ai` only appears in `.env.example` and documentation, never in executable code

### Acceptance Criteria
- `grep -r "Admin123!" . --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx"` returns 0 results
- `grep -r "Test123!" . --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx"` returns 0 results
- All test scripts read credentials from environment variables
- `.env.example` documents all required credential variables

### Validation
```bash
# Zero hardcoded credentials in source
CRED_HITS=$(grep -rn "Admin123!\|Test123!" --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx" --include="*.ts" . | grep -v "node_modules" | grep -v "PROMPT.md" | grep -v "PLAN.md" | wc -l)
echo "Credential hits: $CRED_HITS"
[ "$CRED_HITS" -eq 0 ] && echo "PASS" || echo "FAIL"

# Ensure env vars are documented
grep -q "CARFAX_ADMIN_EMAIL" .env.example && echo "PASS: env documented" || echo "FAIL: env not documented"

# Tests still pass with env vars set
export CARFAX_ADMIN_EMAIL="admin@outpace.ai"
export CARFAX_ADMIN_PASSWORD="Admin123!"
export CARFAX_TENANT_A_EMAIL="tenant-b-test@test.com"
export CARFAX_TENANT_A_PASSWORD="Test123!"
pytest --tb=short -q
```

**Stop-and-fix**: If tests fail, you missed an environment variable mapping. Check test output for the specific missing var.

---

## Milestone 3: Backend — `chat.py` Decomposition

**Objective**: Split `backend/routes/chat.py` (30KB, ~900 lines) into a `chat/` package with focused modules under 500 lines each.

### Tasks
- [ ] Create `backend/routes/chat/` directory
- [ ] Create `backend/routes/chat/__init__.py` — aggregates the router, re-exports all endpoints
- [ ] Extract SSE streaming logic → `backend/routes/chat/streaming.py`
  - `stream_chat_response()`, SSE event formatting, streaming error handling
- [ ] Extract quota logic → `backend/routes/chat/quota.py`
  - `check_quota()`, `increment_quota()`, monthly reset, `CHAT-02` enforcement
- [ ] Extract history logic → `backend/routes/chat/history.py`
  - `get_chat_history()`, `save_chat_turn()`, conversation listing
- [ ] Extract RAG injection → `backend/routes/chat/rag_injection.py`
  - Document retrieval, chunk ranking, context window construction
- [ ] Extract domain context → `backend/routes/chat/domain_context.py`
  - Tenant domain context loading, system prompt construction
- [ ] Update `backend/server.py` to import from `backend.routes.chat` instead of `backend.routes.chat`
  - The import path should remain the same if `__init__.py` re-exports the router
- [ ] Delete the original `backend/routes/chat.py` file
- [ ] Verify all imports resolve correctly

### Acceptance Criteria
- `backend/routes/chat.py` no longer exists
- `backend/routes/chat/__init__.py` exports the FastAPI router
- No file in `backend/routes/chat/` exceeds 500 lines
- All chat-related endpoints work identically (same URLs, same request/response contracts)

### Validation
```bash
# Verify file structure
ls backend/routes/chat/__init__.py backend/routes/chat/streaming.py backend/routes/chat/quota.py backend/routes/chat/history.py backend/routes/chat/rag_injection.py backend/routes/chat/domain_context.py
echo "PASS: all chat modules exist"

# Verify no file exceeds 500 lines
for f in backend/routes/chat/*.py; do
  LINES=$(wc -l < "$f")
  if [ "$LINES" -gt 500 ]; then
    echo "FAIL: $f has $LINES lines (max 500)"
  else
    echo "PASS: $f has $LINES lines"
  fi
done

# Verify original file deleted
[ ! -f backend/routes/chat.py ] && echo "PASS: chat.py removed" || echo "FAIL: chat.py still exists"

# Run full test suite
pytest --tb=short -q
bash carfax.sh 2>&1 | tail -5
```

**Stop-and-fix**: If any chat test fails, the decomposition broke an import or lost a function. Check `__init__.py` re-exports.

---

## Milestone 4: Frontend — `TenantsPage.jsx` Decomposition

**Objective**: Split `frontend/src/pages/TenantsPage.jsx` (88KB, ~2400 lines) into a `tenants/` directory with focused modules.

### Tasks
- [ ] Create `frontend/src/pages/tenants/` directory
- [ ] Create `frontend/src/pages/tenants/index.jsx` — Page shell: top-level state, API calls, coordinates child components
- [ ] Extract tenant list → `frontend/src/pages/tenants/TenantList.jsx`
  - Tenant card grid, search, create button, delete confirmation
- [ ] Extract form dialog → `frontend/src/pages/tenants/TenantForm.jsx`
  - Dialog shell with tab navigation, form state management, save/cancel handlers
- [ ] Extract branding tab → `frontend/src/pages/tenants/BrandingTab.jsx`
  - Logo upload, ColorPicker usage, visual theme dropdown, glow/sheen toggles, background image
- [ ] Extract search profile tab → `frontend/src/pages/tenants/SearchProfileTab.jsx`
  - NAICS codes, keywords, interest areas, HigherGov config, fetch flags
- [ ] Extract intelligence config tab → `frontend/src/pages/tenants/IntelligenceConfigTab.jsx`
  - Enabled toggle, Perplexity prompt template, schedule cron, lookback/deadline windows
- [ ] Extract chat policy tab → `frontend/src/pages/tenants/ChatPolicyTab.jsx`
  - Enabled toggle, message limits, token limits, history turns
- [ ] Extract knowledge tab → `frontend/src/pages/tenants/KnowledgeTab.jsx`
  - Company profile, key facts, offerings, differentiators, prohibited claims, tone
- [ ] Extract agent config tab → `frontend/src/pages/tenants/AgentConfigTab.jsx`
  - Agent IDs, system prompt templates
- [ ] Extract scoring weights tab → `frontend/src/pages/tenants/ScoringWeightsTab.jsx`
  - Value/deadline/relevance sliders with sum-to-1.0 validation
- [ ] Update `frontend/src/App.jsx` route: change import from `./pages/TenantsPage` to `./pages/tenants`
- [ ] Delete the original `frontend/src/pages/TenantsPage.jsx`

### Acceptance Criteria
- `frontend/src/pages/TenantsPage.jsx` no longer exists
- `frontend/src/pages/tenants/index.jsx` is the new entry point
- No file in `frontend/src/pages/tenants/` exceeds 500 lines
- All tenant management functionality works identically in the browser
- `data-testid` attributes are preserved on all interactive elements

### Validation
```bash
# Verify file structure
ls frontend/src/pages/tenants/index.jsx frontend/src/pages/tenants/TenantList.jsx frontend/src/pages/tenants/TenantForm.jsx frontend/src/pages/tenants/BrandingTab.jsx frontend/src/pages/tenants/SearchProfileTab.jsx frontend/src/pages/tenants/IntelligenceConfigTab.jsx frontend/src/pages/tenants/ChatPolicyTab.jsx frontend/src/pages/tenants/KnowledgeTab.jsx frontend/src/pages/tenants/AgentConfigTab.jsx frontend/src/pages/tenants/ScoringWeightsTab.jsx
echo "PASS: all tenant modules exist"

# Verify no file exceeds 500 lines
for f in frontend/src/pages/tenants/*.jsx; do
  LINES=$(wc -l < "$f")
  if [ "$LINES" -gt 500 ]; then
    echo "FAIL: $f has $LINES lines (max 500)"
  else
    echo "PASS: $f has $LINES lines"
  fi
done

# Verify original file deleted
[ ! -f frontend/src/pages/TenantsPage.jsx ] && echo "PASS: TenantsPage.jsx removed" || echo "FAIL: TenantsPage.jsx still exists"

# Build frontend
cd frontend && npm run build && cd ..
echo "PASS: frontend builds successfully"

# Run Playwright
npx playwright test
```

**Stop-and-fix**: If the build fails, check for missing imports or circular dependencies between tab components.

---

## Milestone 5: Frontend Fixes

**Objective**: Fix known frontend bugs and gaps.

### Tasks
- [ ] **TenantContext raw fetch fix** (`frontend/src/context/TenantContext.jsx`):
  - Replace `fetch(url, { headers: { Authorization: ... } })` with `apiClient.get(url)`
  - This ensures token refresh interceptor handles expired tokens during branding fetch
- [ ] **404 catch-all route** (`frontend/src/pages/NotFoundPage.jsx`):
  - Create a styled 404 page using existing shadcn/ui Card component
  - Include "Go to Dashboard" and "Go to Login" buttons
  - Add route in `App.jsx`: `<Route path="*" element={<NotFoundPage />} />`
- [ ] **SuperAdminDashboard live health** (`frontend/src/pages/SuperAdminDashboard.jsx`):
  - Replace hardcoded "● Healthy" / "● Running" / "● Active" with live fetch from `/api/health`
  - Show actual MongoDB status, API version, scheduler state
  - Handle fetch failure gracefully (show "● Unknown" with yellow indicator)
- [ ] **DatabaseManager chat tab** (`frontend/src/pages/DatabaseManager.jsx`):
  - Replace hardcoded `['test-conv-1', 'smoke-test-123', 'final-test']` with API call to list conversations
  - If no conversation listing endpoint exists, add `GET /api/chat/conversations` to backend
- [ ] **Remove unused dependencies**:
  - Verify `zustand` is unused: `grep -r "zustand\|create(" frontend/src/ --include="*.jsx" --include="*.js"`
  - Verify `recharts` is unused: `grep -r "recharts\|ResponsiveContainer\|LineChart\|BarChart" frontend/src/`
  - If confirmed unused, run: `cd frontend && npm uninstall zustand recharts`
- [ ] **Fix Playwright test discoverability**:
  - Move `frontend/tests/export-download.spec.js` to `frontend/e2e/export-download.spec.ts`
  - Update port from hardcoded `3000` to use config: `baseURL` from Playwright config (or `3333`)

### Acceptance Criteria
- TenantContext uses `apiClient` for all API calls
- Navigation to `/nonexistent-path` shows a styled 404 page
- SuperAdminDashboard shows live health data from the backend
- DatabaseManager chat tab fetches real conversation IDs
- `npm ls zustand recharts` shows they are not in `package.json` (if confirmed unused)
- All Playwright tests run via `npx playwright test` (including export tests)

### Validation
```bash
# TenantContext check
grep -c "apiClient" frontend/src/context/TenantContext.jsx | grep -q "0" && echo "FAIL: TenantContext still uses raw fetch" || echo "PASS: TenantContext uses apiClient"

# 404 page exists
[ -f frontend/src/pages/NotFoundPage.jsx ] && echo "PASS: 404 page exists" || echo "FAIL: no 404 page"

# Build
cd frontend && npm run build && cd ..

# Playwright
npx playwright test
```

---

## Milestone 6: Security Hardening

**Objective**: Add gitleaks, pre-commit hooks, CORS hardening, and GCP Secret Manager integration.

### Tasks
- [ ] **Gitleaks configuration** (`.gitleaks.toml`):
  ```toml
  title = "OutPace B2B Intelligence Gitleaks Config"
  
  [allowlist]
  description = "Allowlisted patterns"
  paths = [
    '''\.env\.example''',
    '''docs/.*\.md''',
    '''agent_docs/.*\.md''',
    '''mocks/.*'''
  ]
  ```
- [ ] **Pre-commit config** (`.pre-commit-config.yaml`):
  ```yaml
  repos:
    - repo: https://github.com/gitleaks/gitleaks
      rev: v8.21.2
      hooks:
        - id: gitleaks
  ```
- [ ] **GCP Secret Manager integration** (`backend/utils/secret_manager.py`):
  - Create a `get_secret(name: str, default: str = None) -> str` function
  - Try GCP Secret Manager first (if `GOOGLE_CLOUD_PROJECT` env var is set)
  - Fall back to environment variables if GCP is not configured
  - Cache secrets in memory for the process lifetime
  - Used by: `backend/utils/secrets.py` (modify existing to delegate to this module)
- [ ] **CORS hardening** (`backend/server.py`):
  - Read allowed origins from `CORS_ALLOWED_ORIGINS` env var (comma-separated)
  - Default to `["http://localhost:3000"]` in development
  - Never use `["*"]` in production
  - Add to `.env.example`: `CORS_ALLOWED_ORIGINS=https://your-domain.com`
- [ ] **Populate `docs/AUDIT_FINDINGS.md`**:
  - Write a summary of all findings from this remediation
  - Include date, severity, status (resolved/pending), and file paths

### Acceptance Criteria
- `gitleaks detect --source .` reports 0 findings
- `.pre-commit-config.yaml` exists and references gitleaks
- `backend/utils/secret_manager.py` exists with `get_secret()` function
- CORS in `server.py` reads from env var, not hardcoded
- `docs/AUDIT_FINDINGS.md` has content > 0 bytes

### Validation
```bash
# Gitleaks
gitleaks detect --source . --config .gitleaks.toml -v 2>&1 | tail -3

# Secret manager module
python -c "from backend.utils.secret_manager import get_secret; print('PASS: import works')"

# CORS check
grep -q "CORS_ALLOWED_ORIGINS" backend/server.py && echo "PASS: CORS from env" || echo "FAIL: CORS not from env"

# Audit findings populated
[ -s docs/AUDIT_FINDINGS.md ] && echo "PASS: audit findings populated" || echo "FAIL: still empty"

# Tests
pytest --tb=short -q
```

---

## Milestone 7: Database & Backend Hardening

**Objective**: Improve MongoDB connection resilience, add proper read/write concerns, and harden the sync scheduler.

### Tasks
- [ ] **MongoDB connection resilience** (`backend/database.py`):
  - Add `serverSelectionTimeoutMS=5000` to connection options
  - Add `retryWrites=true` and `retryReads=true`
  - Set `w='majority'` write concern for production (configurable via env var)
  - Set `readPreference='primaryPreferred'` for reads
  - Add connection retry logic with exponential backoff (3 attempts)
  - Log connection events (connected, disconnected, retry)
- [ ] **Sync scheduler hardening** (`backend/scheduler/sync_scheduler.py`):
  - Add retry logic (3 attempts with backoff) for HigherGov API failures
  - Add dead-letter pattern: failed syncs log to `sync_failures` collection with full error context
  - Add sync duration tracking (start_time, end_time, duration_ms)
  - Add observability: emit structured log with `tenant_id`, `sync_type`, `result`, `duration_ms`
- [ ] **Test coverage gate restoration** (`.github/workflows/ci.yml`):
  - Add `pytest --cov=backend --cov-report=term --cov-fail-under=70` (start at 70%, increase over time)
  - If current coverage is below 70%, set the gate to current coverage minus 2% (prevent regression without blocking)

### Acceptance Criteria
- `backend/database.py` includes retry logic and write concern configuration
- `backend/scheduler/sync_scheduler.py` includes retry and dead-letter patterns
- CI workflow includes a coverage gate

### Validation
```bash
# Database module has new config
grep -q "retryWrites" backend/database.py && echo "PASS: retry config" || echo "FAIL: no retry config"
grep -q "w=" backend/database.py && echo "PASS: write concern" || echo "FAIL: no write concern"

# Scheduler has retry pattern
grep -q "retry\|backoff\|dead.letter\|sync_failures" backend/scheduler/sync_scheduler.py && echo "PASS: retry/DLQ" || echo "FAIL: no retry/DLQ"

# CI has coverage gate
grep -q "cov-fail-under" .github/workflows/ci.yml && echo "PASS: coverage gate" || echo "FAIL: no coverage gate"

# Tests
pytest --tb=short -q
```

---

## Milestone 8: Branch Cleanup & PR #23

**Objective**: Merge or close PR #23, delete stale branches.

### Tasks
- [ ] **Evaluate PR #23** (`fix/production-audit-remediation` → `main`):
  - Check if changes conflict with milestones 1-7 above
  - If PR #23 changes overlap with this remediation, cherry-pick the non-overlapping commits and close the PR
  - If PR #23 is fully compatible, merge it first (before the milestones above, if possible)
  - Document the decision in `docs/AUDIT_FINDINGS.md`
- [ ] **Delete stale branches** (after confirming no valuable unmerged work):
  - `claude/add-ci-workflows-s7vHh`
  - `claude/add-test-dockerfile-kya9r`
  - `feature/docker-compose-test`
  - `feature/test-infrastructure`
  - `fix/production-audit-remediation` (after merge or close)
- [ ] **Branch protection** (document recommendation — cannot be set via code):
  - Recommend enabling branch protection on `main`: require PR reviews, require status checks, no force push
  - Add this recommendation to `docs/AUDIT_FINDINGS.md`

### Acceptance Criteria
- PR #23 is either merged or closed with documented rationale
- All stale branches are deleted
- `git branch -r` shows only `origin/main`

### Validation
```bash
# Verify branches
git fetch --prune
BRANCHES=$(git branch -r | grep -v "origin/main" | grep -v "HEAD" | wc -l)
echo "Non-main remote branches: $BRANCHES"
[ "$BRANCHES" -eq 0 ] && echo "PASS: only main remains" || echo "FAIL: stale branches exist"
```

**Note**: This milestone requires GitHub API access or manual action for branch deletion and PR operations. If running as a Codex agent without GitHub API access, output the exact `git push origin --delete <branch>` commands as a script.

---

## Milestone 9: Git History Cleanup

**Objective**: Purge credentials from git history using BFG Repo Cleaner or `git filter-repo`.

### Tasks
- [ ] **Create credential replacement file** (`/tmp/cred_replacements.txt`):
  ```
  Admin123!  →  ***REDACTED***
  Test123!   →  ***REDACTED***
  ```
- [ ] **Run BFG or git filter-repo**:
  ```bash
  # Option A: BFG
  java -jar bfg.jar --replace-text /tmp/cred_replacements.txt .
  git reflog expire --expire=now --all
  git gc --prune=now --aggressive
  
  # Option B: git filter-repo
  git filter-repo --replace-text /tmp/cred_replacements.txt --force
  ```
- [ ] **Force push** (requires `--force` — this is the ONE acceptable force push):
  ```bash
  git push origin main --force
  ```
- [ ] **Verify**: `git log --all -p | grep "Admin123!"` returns 0 results

### Acceptance Criteria
- `git log --all -p | grep -c "Admin123!"` returns 0
- `git log --all -p | grep -c "Test123!"` returns 0
- Force push completed successfully

### Validation
```bash
HISTORY_HITS=$(git log --all -p 2>/dev/null | grep -c "Admin123!\|Test123!" || echo 0)
echo "Credential hits in history: $HISTORY_HITS"
[ "$HISTORY_HITS" -eq 0 ] && echo "PASS: history clean" || echo "FAIL: credentials still in history"
```

**⚠️ WARNING**: This rewrites git history. All collaborators must re-clone after this step. Coordinate with the repo owner before executing.

---

## Milestone 10: Final Validation & Documentation

**Objective**: Run the complete "Done When" checklist from `PROMPT.md` and update documentation.

### Tasks
- [ ] Run every validation command from the "Done When" checklist in `PROMPT.md`
- [ ] Update `docs/AUDIT_FINDINGS.md` with final status of all findings
- [ ] Update `docs/PROJECT_STATUS.md` with completion summary
- [ ] Update `README.md` with any new setup instructions (env vars for test credentials)
- [ ] Commit all documentation changes

### Acceptance Criteria
- Every item in the "Done When" checklist passes
- All documentation is current

### Validation
```bash
# Run the full "Done When" checklist
echo "=== DONE WHEN CHECKLIST ==="

echo "1. Admin123! check:"
grep -r "Admin123!" . --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx" | grep -v "PROMPT.md\|PLAN.md" | wc -l

echo "2. Test123! check:"
grep -r "Test123!" . --include="*.py" --include="*.sh" --include="*.js" --include="*.jsx" | grep -v "PROMPT.md\|PLAN.md" | wc -l

echo "3. chat.py removed:"
[ ! -f backend/routes/chat.py ] && echo "YES" || echo "NO"

echo "4. TenantsPage.jsx removed:"
[ ! -f frontend/src/pages/TenantsPage.jsx ] && echo "YES" || echo "NO"

echo "5. Max lines in chat modules:"
for f in backend/routes/chat/*.py; do wc -l "$f"; done

echo "6. Max lines in tenant modules:"
for f in frontend/src/pages/tenants/*.jsx; do wc -l "$f"; done

echo "7. Stale branches:"
git branch -r | grep -v "origin/main" | grep -v "HEAD"

echo "8. pytest:"
pytest --tb=short -q 2>&1 | tail -3

echo "9. Gitleaks:"
gitleaks detect --source . --config .gitleaks.toml 2>&1 | tail -3

echo "10. Deleted files check:"
ls tmpclaude-* test_export.* frontend/craco.config.js frontend/plugins/ frontend/src/App.css 2>/dev/null && echo "FILES STILL EXIST" || echo "ALL CLEAN"

echo "11. .gitignore entries:"
grep "tmpclaude\|test_export\|carfax_reports" .gitignore

echo "12. Audit findings populated:"
[ -s docs/AUDIT_FINDINGS.md ] && echo "YES" || echo "NO"

echo "=== END CHECKLIST ==="
```

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-05 | Milestone order: cleanup → creds → decompose → frontend → security → DB → branches → history → docs | Dependencies flow downward; history cleanup must be last (force push) |
| 2026-03-05 | 500-line limit per file after decomposition | Industry standard for maintainability; enforced by validation commands |
| 2026-03-05 | Coverage gate at 70% (not 80%+) | Starting conservative — gate was previously removed. 70% prevents regression without blocking current work |
| 2026-03-05 | GCP Secret Manager with env fallback | Allows local development with env vars while supporting production secret rotation |
| 2026-03-05 | Git history rewrite is Milestone 9 (near-last) | All file changes must be complete before rewriting history, otherwise the rewrite misses new commits |
