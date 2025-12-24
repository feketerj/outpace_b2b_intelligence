# AGENT OPERATIONAL PROTOCOL - OutPace B2B Intelligence Dashboard

## I. PROJECT CONTEXT (BINDING)
- **Environment:** Local-only (Emergent is DEAD)
- **Stack:** Docker Desktop, MongoDB (mongo-b2b:27017), FastAPI (8000), WSL Ubuntu
- **DB:** `outpace_intelligence` (no other DB names accepted)
- **Repo:** C:\Projects\outpace_b2b_intelligence
- **WSL Networking:** API_URL=http://host.docker.internal:8000 (localhost is INVALID from WSL)

## II. EXECUTION PHASES (REQUIRED ORDER - NO SKIPPING)
1. **RECON** (read-only) - Gather ground truth, verify environment, read specs
2. **PLAN** (no code) - Task graph, parallel tracks, write-lock table
3. **EXECUTE** (scoped) - Branch per track, enforce locks
4. **VALIDATE** (proof-based) - Run validations, capture outputs
5. **MERGE** (controlled) - PR per branch, proof required

## III. HARD GUARDRAILS (MUST ENFORCE)
- **No guessing.** If source-of-truth missing: STOP and report.
- **No placeholders, TODOs, "should work", or mocks.**
- **No test manipulation.** Never modify tests to match broken behavior.
- **No fabricated data.** Fail loudly with real error.
- **No repo pollution.** `git status` must be clean before proof.
- **No user-run commands.** Route to agents. User approves decisions only.
- **No repeated attempts.** One attempt per technique, then pivot with new evidence.

## IV. PROOF REQUIREMENTS
- **Fail-loud is MERGE-BLOCKING:** All test harness setup calls must verify status/body and abort on non-2xx.
- **No summaries as proof.** Return raw command output, file paths, line numbers, SHAs.
- **Hash critical artifacts:** Reports, baseline state, runner scripts get SHA256 locked.
- **QC must verify independently.** Coding claims require QC proof before acceptance.

## V. PARALLELISM RULES

### Write-Lock Table (MANDATORY)
| File/Path | Owner | Branch | Status |
|-----------|-------|--------|--------|

- One file = one writer at a time
- If overlap detected: SERIALIZE or STOP

### Track Classification
- **GREEN:** No file overlap, independent branches, safe to parallel
- **YELLOW:** Related files, gate needed before merge
- **RED:** Same file or dependency chain, must serialize

### Safety Rules
- No track modifies `carfax.sh` while tests running
- No track touches seed scripts while docker-compose executing
- If uncertain: DO NOT PARALLELIZE

## VI. VALIDATION GATES
- **Docker build:** Must pass before merge
- **Test suite:** 35/35 required for baseline
- **Monte Carlo:** 59 runs of full suite for 95% confidence
- **Seed compatibility:** Scripts must use MONGO_URL/DB_NAME env vars

## VII. AGENT RETURN CONTRACT (MANDATORY)
```json
{
  "status": "DONE | PARTIAL | BLOCKED",
  "branch": "<name>",
  "commit_hash": "<sha>",
  "files_changed": ["<paths>"],
  "commands_executed": ["<cmd>"],
  "output_last_N_lines": "<verbatim>",
  "validation_proof": "<evidence>",
  "risks_introduced": ["<list>"],
  "next_gate": "<what's needed>"
}
```

## VIII. KNOWN FAILURE MODES (WATCHLIST)
- **Premature termination:** Require multiple approaches before declaring failure
- **Environment assumption:** Always verify Docker running, containers up, ports available
- **Fixture mismatch:** Tenant UUIDs must match carfax.sh hardcoded values
- **DB_NAME drift:** Never seed to wrong database
- **Silent setup failures:** Tenant PUT must return 200 or abort

## IX. PROJECT-SPECIFIC GOTCHAS
- `carfax.sh` expects: admin@outpace.ai / Admin123!
- Seed scripts: `seed_carfax_tenants.py`, `seed_carfax_users.py`
- MongoDB container name: `mongo-b2b`
- JWT_SECRET must be set for auth to work
- Python packages: Use `--break-system-packages` in WSL if needed
- Containerized tests require two-step: seed profile first, then test run
