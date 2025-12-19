# Verification Proof Runbook

> Version: 2.0 (Truth-Boundary Edition)  
> Scope: Repo-agnostic, process-neutral

---

## Purpose

This runbook defines how to establish proof that the verification system enforces its invariants in a real CI environment. Proof is structural, not procedural.

---

## Core Concept: Truth-Establishing Execution Boundary

Proof requires executing the verification suite in an environment where:
1. The sync endpoint is reachable
2. The marker file can be written
3. Artifacts can be uploaded

This boundary is typically a CI runner (GitHub Actions, GitLab CI, etc.) but the proof semantics are identical regardless of trigger mechanism.

---

## What Constitutes Proof

Proof requires ALL of the following observable outcomes:

### 1. Single SYNC-02 Execution

The verification suite must execute exactly one real sync call. This is evidenced by the following log string appearing exactly once:

```
SYNC-02: admin_sync_returns_full_contract
```

### 2. Marker Gate Validation

The marker file must be validated by the canonical validator. This is evidenced by:

```
MARKER GATE PASSED: tenant=
```

### 3. Artifact Presence

Two artifacts must be uploaded and discoverable in the CI run:

| Artifact Name | Description |
|---------------|-------------|
| sync-contract-marker | The marker JSON file |
| carfax-reports | CARFAX test reports |

---

## Triggering a Truth-Establishing Run

The verification suite can be triggered by any mechanism that results in workflow execution. Common triggers include:

- Direct push to a branch with workflow triggers
- Pull request creation (if workflows trigger on PRs)
- Manual workflow dispatch
- Scheduled cron execution

The specific trigger mechanism is irrelevant to proof validity. What matters is that the workflow executes completely and produces the canonical proof signals.

### Identifying the Truth Boundary

Before collecting proof, identify which workflow in your repository is configured to:
1. Run ci_verify.sh (or equivalent)
2. Execute SYNC-02
3. Validate the marker gate
4. Upload artifacts

This is typically a workflow triggered on push to the main/default branch, but may vary by repository configuration.

---

## Proof Collection Procedure

### Step 1: Trigger Workflow Execution

Push code to the repository using your platform's mechanism:
- Emergent: Use "Save to GitHub" feature
- Git CLI: git push
- Platform UI: Direct commit

### Step 2: Locate the Workflow Run

In your CI platform, navigate to the workflow run that was triggered. Record:

```
RUN_URL: [URL of the workflow run]
```

### Step 3: Search for Canonical Proof Strings

In the workflow logs, search for each canonical proof string:

| Proof String | Required Count | Found |
|--------------|----------------|-------|
| SYNC-02: admin_sync_returns_full_contract | Exactly 1 | [ ] |
| MARKER GATE PASSED: tenant= | At least 1 | [ ] |

### Step 4: Verify Artifact Presence

In the workflow run's artifact section, confirm presence:

| Artifact | Present |
|----------|---------|
| sync-contract-marker | [ ] |
| carfax-reports | [ ] |

### Step 5: Record Evidence

Capture the following evidence:

```
VERIFICATION EVIDENCE
=====================

Workflow Run URL:
  [paste URL]

SYNC-02 Log Line:
  [paste the line containing "SYNC-02: admin_sync_returns_full_contract"]

Marker Gate Log Line:
  [paste the line containing "MARKER GATE PASSED: tenant="]

Artifacts Present:
  sync-contract-marker: [YES/NO]
  carfax-reports: [YES/NO]

Verification Status: [PASS/FAIL]
```

---

## Non-Truth-Boundary Runs

Some workflow configurations may exclude the sync call (e.g., PR checks, nightly validators). These runs are valid but do not establish sync-contract proof.

To verify a non-truth-boundary run is correctly configured:
1. Confirm the workflow completes successfully
2. Confirm SYNC-02 does NOT appear in logs
3. Confirm no marker artifacts are uploaded

This validates that the workflow correctly excludes sync calls when intended.

---

## Pre-Proof Audit: Repository /app References

Before declaring proof complete, audit the repository for hardcoded /app paths in CI-facing code:

```
grep -rn '"/app' *.sh docs/*.md scripts/*.sh .github/workflows/*.yml 2>/dev/null | grep -v '#'
```

Expected result: No matches, or only fallback paths in deprecated/non-CI code.

---

## Proof Validity Criteria

A verification run is valid proof if and only if:

1. The workflow completed (did not fail or cancel)
2. "SYNC-02: admin_sync_returns_full_contract" appears exactly once
3. "MARKER GATE PASSED: tenant=" appears at least once
4. Both artifacts (sync-contract-marker, carfax-reports) are present
5. No /app hardcoding exists in CI-critical paths

---

## Troubleshooting

### SYNC-02 Does Not Appear
- Verify the workflow is configured to run ci_verify.sh
- Check if PR-mode or similar exclusion is active
- Verify API_URL secret/environment variable is set

### Marker Gate Fails
- SYNC-02 may have failed (check for contract validation errors)
- Marker file may not have been written
- Freshness window (10 minutes) may have expired

### Artifacts Missing
- Verify upload steps use "if: always()" condition
- Check artifact paths match expected locations

---

## Canonical Reference

### Proof Strings (exhaustive list)
```
SYNC-02: admin_sync_returns_full_contract
MARKER GATE PASSED: tenant=
```

### Artifact Names (exhaustive list)
```
sync-contract-marker
carfax-reports
```

Any log string or artifact not in this list is NOT part of the proof contract.
