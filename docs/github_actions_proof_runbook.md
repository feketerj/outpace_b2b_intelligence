# GitHub Actions Proof Runbook

> **Purpose**: Execute PR/merge/nightly workflows on GitHub Actions and capture evidence that the verification system cannot lie.  
> **Time Required**: ~10 minutes  
> **Prerequisites**: Push access to the repository

---

## Quick Reference

| Workflow | Trigger | SYNC-02 | Marker Gate | Artifacts |
|----------|---------|---------|-------------|-----------|
| `pr-checks.yml` | PR opened | ❌ No | ❌ No | ❌ No |
| `merge-main.yml` | Push to main | ✅ Yes (1) | ✅ Yes | ✅ Yes |
| `nightly.yml` | Cron / manual | ❌ No | ❌ No | ❌ No |

---

## Step 1: Push Code to GitHub

### Option A: Emergent Platform (Recommended)
1. In the Emergent chat UI, click **"Save to GitHub"**
2. Select the target repository
3. Provide a commit message: `P0: Verification hardening - single SYNC-02, marker gating, canonical validator`

### Option B: Manual Git Commands
```bash
# From your local clone of the repository
cd /path/to/outpace_b2b_intelligence

# Create branch
git checkout -b verification-hardening

# Stage all changes
git add .

# Commit
git commit -m "P0: Verification hardening - single SYNC-02, marker gating, canonical validator"

# Push
git push origin verification-hardening
```

---

## Step 2: Open Pull Request

1. Navigate to: https://github.com/feketerj/outpace_b2b_intelligence/pulls
2. Click **"New pull request"**
3. Configure:
   - **Base**: `main`
   - **Compare**: `verification-hardening` (or your branch name)
4. Title: `P0: Verification Hardening - Single SYNC-02 + Marker Gating`
5. Body: Copy contents from `PR_DESCRIPTION.md` in the repository root
6. Click **"Create pull request"**

**Record**: `PR_URL = https://github.com/feketerj/outpace_b2b_intelligence/pull/___`

---

## Step 3: Verify PR Workflow (No Sync)

The PR workflow should trigger automatically within ~30 seconds.

### Where to Look
1. Go to the **"Checks"** tab on the PR page
2. Or: Actions → Find the run for your PR

### What to Verify
| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| Workflow completes | ✅ Green checkmark | ☐ |
| No sync calls made | No `/api/admin/sync` in logs | ☐ |
| Final message | `"PR checks complete (no external sync calls)"` | ☐ |

### Log Strings to Search For
```
✅ EXPECTED (must appear):
   "PR checks complete (no external sync calls)"
   "pytest" (should show tests running)

❌ MUST NOT APPEAR:
   "SYNC-02"
   "/api/admin/sync"
   "/api/sync/manual"
```

**Record**: `PR_WORKFLOW_URL = https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___`

---

## Step 4: Merge Pull Request

1. On the PR page, click **"Merge pull request"**
2. Confirm the merge
3. This triggers the `merge-main.yml` workflow

---

## Step 5: Verify Merge Workflow (Single SYNC-02 + Artifacts)

### Where to Look
1. Go to: Actions → **"Merge to Main (Full Suite)"** → Most recent run
2. Or use the link from the merge commit

### What to Verify

#### A. Single SYNC-02 Execution
| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| SYNC-02 appears | Exactly ONCE in logs | ☐ |
| SYNC-02 passes | `✅ PASS: SYNC-02: admin_sync_returns_full_contract` | ☐ |

**Log string to search**:
```
"SYNC-02: admin_sync_returns_full_contract"
```
→ Must appear **exactly once**. Use Ctrl+F and count occurrences.

#### B. Marker Gate Passes
| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| Marker gate step | Completes green | ☐ |
| Gate message | `"MARKER GATE PASSED: tenant=..."` | ☐ |

**Log string to search**:
```
"MARKER GATE PASSED: tenant="
```

#### C. Artifacts Uploaded
1. Scroll to bottom of the workflow run page
2. Find the **"Artifacts"** section

| Artifact Name | Expected | Present |
|---------------|----------|---------|
| `sync-contract-marker` | Marker JSON file | ☐ |
| `carfax-reports` | CARFAX JSON reports | ☐ |

**Record**: `MERGE_WORKFLOW_URL = https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___`

---

## Step 6: Trigger Nightly Workflow (Optional)

1. Go to: Actions → **"Nightly Monte Carlo"**
2. Click **"Run workflow"** dropdown (right side)
3. Select branch: `main`
4. Click **"Run workflow"**

### What to Verify
| Check | Expected | Pass/Fail |
|-------|----------|-----------|
| Workflow starts | Run appears in list | ☐ |
| Workflow completes | ✅ Green checkmark | ☐ |
| No sync calls | No SYNC-02 in logs | ☐ |

**Record**: `NIGHTLY_WORKFLOW_URL = https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___`

---

## Evidence Collection Template

Copy this template and fill in the values:

```
═══════════════════════════════════════════════════════════════
GITHUB ACTIONS VERIFICATION EVIDENCE
═══════════════════════════════════════════════════════════════

PR URL:
  https://github.com/feketerj/outpace_b2b_intelligence/pull/___

PR WORKFLOW RUN:
  URL: https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___
  Status: [PASS/FAIL]
  Sync Calls: [NONE DETECTED / ERROR - SEE LOG]

MERGE WORKFLOW RUN:
  URL: https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___
  Status: [PASS/FAIL]
  SYNC-02 Count: [1 / ERROR]
  Marker Gate: [PASSED / FAILED]
  
  Log Snippet (SYNC-02):
    [paste line containing "SYNC-02: admin_sync_returns_full_contract"]
  
  Log Snippet (Marker Gate):
    [paste line containing "MARKER GATE PASSED"]

ARTIFACTS:
  sync-contract-marker: [PRESENT / MISSING]
  carfax-reports: [PRESENT / MISSING]

NIGHTLY WORKFLOW RUN (if executed):
  URL: https://github.com/feketerj/outpace_b2b_intelligence/actions/runs/___
  Status: [PASS/FAIL]
  Sync Calls: [NONE DETECTED / ERROR]

═══════════════════════════════════════════════════════════════
```

---

## Troubleshooting

### PR Workflow Fails
- Check if `pytest` dependencies are installed
- Verify `--pr-mode` flag is being used
- Ensure no `|| true` bypass was accidentally removed from a required test

### Merge Workflow Fails on SYNC-02
- Check if `API_URL` secret is configured in repository settings
- Verify the sync endpoint is accessible
- Check for network/timeout issues

### Merge Workflow Fails on Marker Gate
- SYNC-02 may have failed silently (check curl output)
- Marker file may not have been written (check for contract validation errors)
- Freshness window may have expired if run took >10 minutes

### Artifacts Missing
- Check `if: always()` is present on upload steps
- Verify paths: `/tmp/carfax_sync02_ok.marker` and `carfax_reports/`

---

## Verification Complete Criteria

All of the following must be true:

- [ ] PR workflow passed with zero sync calls
- [ ] Merge workflow passed with exactly one SYNC-02
- [ ] Merge workflow shows "MARKER GATE PASSED"
- [ ] Both artifacts are present in merge workflow
- [ ] (Optional) Nightly workflow ran successfully

Once complete, the verification system is proven in the real GitHub Actions environment.
