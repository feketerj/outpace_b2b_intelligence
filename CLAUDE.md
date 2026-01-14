# CLAUDE.MD

Date: 2026-01-03
Updated: 2026-01-07

---

## USER BLOCK

OBJECTIVE
* Build and maintain the OutPace B2B Intelligence Dashboard - a multi-tenant SaaS platform for government contracting opportunity tracking
* Backend: FastAPI + MongoDB
* Frontend: React (planned)

CONSTRAINTS
* Never optimize for the appearance of completion or claim narrative success until testing is complete
* Never produce your own "official" tests or "score your own homework"
* Never lie, evade, or otherwise hide the truth
* Never edit the USER BLOCK of the CLAUDE.md file

MANDATORY
* Failures are loud
* Bugs are easily identifiable
* Error logs that are easy to parse and unambiguous

PERMITTED
* Emitting: "I don't know", "I cannot solve 'x'", "I cannot perform 'X' in this environment"
* Multiple passes - includes: your first interpretation might be wrong, verify against working implementations, understanding is iterative
* Questioning assumptions - "the spec is complete" is an assumption, not a fact
* Investigating before committing - sitting with ambiguity while gathering evidence is permitted
* Use of subagents
* Edits to the PRODUCER BLOCK of the CLAUDE.md file

---

## PROOF REQUIRED

Before saying "done", "fixed", "verified", or "works", output:

```proof
ACTION: [what user task was tested]
EXECUTED: [exact command/click/request]
OUTPUT: [actual response or result]
RESULT: [pass/fail + evidence]
```

No proof block = not done.

---

## PRODUCER BLOCK

### Project Context
- **Environment:** Local development (Docker Desktop, WSL Ubuntu)
- **Stack:** FastAPI (port 8000), MongoDB (mongo-b2b:27017), React (planned)
- **DB:** `outpace_intelligence`
- **Repo:** C:\Projects\outpace_b2b_intelligence
- **WSL Networking:** API_URL=http://host.docker.internal:8000 (localhost invalid from WSL)

### Environment Variables
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=outpace_intelligence
JWT_SECRET=local-dev-secret-key-12345
```

### Key Files
- `carfax.sh` - Test harness runner (expects admin@outpace.ai / Admin123!)
- `seed_carfax_tenants.py`, `seed_carfax_users.py` - Database seeding
- MongoDB container: `mongo-b2b`

### Known Gotchas
- JWT_SECRET must be set for auth to work
- Python packages in WSL: use `--break-system-packages` if needed
- Tenant UUIDs in tests must match seeded values

### Battle Rhythm

**Cold start (new agent/compacted context):**
1. Read CLAUDE.md (this file)
2. Read `docs/INDEX.yaml` - routing table to find what you need
3. Read `docs/PROJECT_STATUS.md` - current state
4. Read `docs/FAILURE_PATTERNS.md` if debugging

**Before starting work:**
1. Read `docs/PROJECT_STATUS.md` - what's the current state?
2. Read `docs/PROJECT_MEMORY.md` - what was done last session?

**When hitting errors:**
1. Check `docs/FAILURE_PATTERNS.md` - is this a known pattern?
2. Follow Signal -> Check -> Fix

**After completing work:**
1. Update `docs/PROJECT_STATUS.md` with test results
2. Update `docs/PROJECT_MEMORY.md` with session notes
3. Update `docs/FAILURE_PATTERNS.md` if new pattern discovered

**Quick Commands:**
- Health check: `python scripts/doctor.py`
- Unit tests: `pytest backend/tests/ -v`
- Start server: See docs/INDEX.yaml for full command

---

## FAILURE PATTERNS

### The "Fail Loud" Contract
- Every critical failure must emit a clear, parseable error message
- Never mask errors - if a dependency is missing, fail immediately with clear output
- Exit codes matter: 0 = success, non-zero = failure (be consistent)

### Input Validation Order
**Strict Sequence:**
1. **Trim** (whitespace)
2. **Check Empty** (length > 0)
3. **Validate Pattern** (regex/schema)

Checking "Empty" before "Trim" allows whitespace-only inputs to pass, causing cryptic failures later.

### Same Error, Different Root Cause
Identical error messages can have completely different root causes:

| Error | Obvious Cause | Actual Cause |
|-------|--------------|--------------|
| "Connection refused" | Server down | Wrong port/host |
| "401 Unauthorized" | Bad credentials | JWT_SECRET mismatch |
| "Tenant not found" | Missing data | UUID format mismatch |

**Pattern:**
1. Note where the error *appears*
2. Trace back to where the value *originated*
3. The origin is often different from the appearance point

### Expected-Failure Semantics
If a test expects failure and the observed failure matches the expected pattern, the test **PASSES**.
Anti-pattern: Treating "failure observed" as "test failed."

---

## TACTICS, TECHNIQUES, AND PROCEDURES (TTPs)

### TTP-001: Progressive Testing
Start with minimal scope and increase progressively. Catches bugs at lower cost.

| Phase | Scope | Purpose |
|-------|-------|---------|
| Smoke | 1-2 endpoints | Basic connectivity |
| Happy Path | Core flows | Expected success |
| Boundary | Edge cases | Limits |
| Invalid | Bad inputs | Validation |
| Full Suite | Everything | Confidence |

**Stop and fix at each gate.** Don't proceed with failures.

### TTP-002: Verify Environment Before Blaming Code
When output doesn't match expectations:
1. Check if the service is actually running
2. Check if you're hitting the right endpoint/port
3. Check if the database has the expected data
4. **Then** look at code

### TTP-003: Windows Environment Gotchas
- **PATH visibility:** Fresh installs may not be visible in current shell session
- **File locking:** Windows holds file handles; cleanup can fail
- **Line endings:** CRLF vs LF can break scripts
- **Shell differences:** PowerShell, CMD, Git Bash, WSL all behave differently

### TTP-004: Specs Are Incomplete By Default
Treat every specification as incomplete until proven otherwise by checking actual behavior.

**Pattern:**
- Spec defines contract → Implementation interprets contract → Reality is what passes tests
- When in doubt, check what *working* implementations actually do
- "The spec is complete" is an assumption, not a fact

### TTP-005: Context Preservation
Before stopping or when context is getting long:
- Document current state (what works, what doesn't)
- Document blocking items
- Document next steps

This file serves that purpose.

### TTP-006: Commander's Intent
Understand the *underlying goal*, not just the literal instruction.

**Pattern:**
- User says "add React" → The goal might be "make it visually impressive," not specifically React
- User says "fix the bug" → Understand *why* it's a bug, not just what the symptom is
- Ask: "What does success look like?" if unclear

### TTP-007: Segregation of Duties in Testing
The producer cannot certify their own work. Bugs found by the same agent that wrote the code are invisible bugs.

**Pattern:**
- carfax.sh (external test harness) validates backend changes
- CI guards (grep-based) catch pattern violations
- Monte Carlo mode: 59 consecutive passes for 95% statistical confidence

---

## CONTRACT INTEGRITY MEASURES

| Measure | Location | Purpose |
|---------|----------|---------|
| Preflight Validation | `backend/utils/preflight.py` | Exit(1) if MONGO_URL/DB_NAME/JWT_SECRET missing |
| Tenant Isolation | `backend/utils/invariants.py` | `assert_tenant_match()`, `assert_single_tenant()` |
| Unknown Field Rejection | All routes | HTTP 400 on unrecognized fields in mutations |
| Structured Audit Logging | `[audit.*]` tags | Machine-parseable logs for agents |
| Request Tracing | X-Trace-ID header | Correlation across log entries |
| CI Guards | `scripts/ci_guards.sh` | Grep-based pattern validation |
| Guard Tests | `backend/tests/test_invariants.py` | Programmatic invariant checks |

---

## SESSION NOTES

### 2026-01-07: Context Routing Index Created
- Created `docs/INDEX.yaml` - routing table for documentation
- Purpose: Eliminate search waste, direct agents to authoritative sources
- Identified consolidation candidates (see INDEX.yaml for archive_candidates)
- Updated Battle Rhythm to reference INDEX.yaml on cold start

