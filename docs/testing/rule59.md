# Rule 59: Monte Carlo Confidence Protocol

## Purpose

Rule 59 establishes statistical confidence in test suite reliability.

**Principle:** 59 consecutive passes = 95% confidence that the true failure rate is ≤5%.

## Mathematical Basis

- If a test has a 5% failure rate, the probability of 59 consecutive passes is 0.95^59 ≈ 0.05 (5%)
- Therefore, observing 59 consecutive passes gives 95% confidence the failure rate is ≤5%
- This is a one-sided confidence bound

## Rules

1. **Unit of Trial**: The complete test suite (not individual tests)
2. **Consecutive**: Counter resets to 0 on any failure
3. **No Partitioning**: Cannot split runs across environments or time windows
4. **Same Configuration**: All runs must use identical environment/config

## Usage

### Standard Execution (59 runs)

```bash
# From repo root, using Git Bash on Windows
API_URL="http://127.0.0.1:8000" ./mc_runner_gitbash.sh
```

### Custom Iteration Count

```bash
MC_ITERATIONS=100 API_URL="http://127.0.0.1:8000" ./mc_runner_gitbash.sh
```

## Output

Logs written to: `mc_reports/mc_gitbash_<timestamp>.log`

Each log contains:
- Preflight check results (shell, platform, API health)
- Per-iteration pass/fail
- Final summary with confidence level

## Failure Handling

On any failure:
1. Runner exits immediately (fail-fast)
2. Log shows which iteration failed
3. Consecutive pass counter resets to 0
4. Full re-run required from iteration 1

## Evidence Requirements

For certification, provide:
- Iterations attempted
- Consecutive passes
- First failure iteration (if any)
- Log file path + SHA256 hash
- Final report path + SHA256 hash

## Historical Certifications

| Date | Certification ID | Iterations | Result | Log |
|------|-----------------|------------|--------|-----|
| 2025-12-25 | TH-MC-003 | 59/59 | PASS | mc_gitbash_20251225_184447.log |
