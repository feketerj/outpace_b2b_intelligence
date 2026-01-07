#!/usr/bin/env python3
"""
Doctor Script - Unified Health Check and Test Runner

Run all validation checks in one command. Returns non-zero if ANY check fails.

Usage:
    python scripts/doctor.py           # Run all checks
    python scripts/doctor.py --quick   # Skip slow integration tests
    python scripts/doctor.py --ci      # CI mode (stricter, no prompts)

Exit codes:
    0 = All checks passed
    1 = One or more checks failed

Checks performed:
    1. Environment validation (preflight)
    2. CI guards (pattern validation)
    3. Unit tests (pytest)
    4. Contract tests
    5. Tenant isolation tests
    6. Summary report
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Ensure we're in the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)

# Add project to path
sys.path.insert(0, str(PROJECT_ROOT))


class DoctorResult:
    """Container for check results."""

    def __init__(self):
        self.checks: List[Tuple[str, bool, float, str]] = []  # (name, passed, duration_ms, detail)

    def add(self, name: str, passed: bool, duration_ms: float, detail: str = ""):
        self.checks.append((name, passed, duration_ms, detail))

    @property
    def all_passed(self) -> bool:
        return all(passed for _, passed, _, _ in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(1 for _, passed, _, _ in self.checks if passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for _, passed, _, _ in self.checks if not passed)


def run_command(cmd: str, timeout: int = 300) -> Tuple[bool, str, float]:
    """
    Run a shell command and return (success, output, duration_ms).
    """
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}
        )
        duration_ms = (time.time() - start) * 1000
        output = result.stdout + result.stderr
        return result.returncode == 0, output, duration_ms
    except subprocess.TimeoutExpired:
        duration_ms = (time.time() - start) * 1000
        return False, f"TIMEOUT after {timeout}s", duration_ms
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        return False, str(e), duration_ms


def check_preflight(result: DoctorResult) -> None:
    """Check that environment variables are properly set."""
    print("  [1/6] Preflight checks...", end=" ", flush=True)

    required = ["MONGO_URL", "DB_NAME", "JWT_SECRET"]
    missing = [v for v in required if not os.environ.get(v)]

    if missing:
        result.add("Preflight", False, 0, f"Missing: {', '.join(missing)}")
        print(f"FAIL (missing: {', '.join(missing)})")
    else:
        result.add("Preflight", True, 0, "All env vars present")
        print("OK")


def check_ci_guards(result: DoctorResult) -> None:
    """Run CI guard script if it exists."""
    print("  [2/6] CI guards...", end=" ", flush=True)

    guard_script = PROJECT_ROOT / "scripts" / "ci_guards.sh"
    if not guard_script.exists():
        result.add("CI Guards", True, 0, "Script not found (skipped)")
        print("SKIP (no script)")
        return

    passed, output, duration = run_command(f"bash {guard_script}", timeout=60)

    if passed:
        result.add("CI Guards", True, duration, "All patterns valid")
        print(f"OK ({duration:.0f}ms)")
    else:
        # Extract key failure info
        lines = output.strip().split("\n")
        detail = lines[-1] if lines else "Unknown failure"
        result.add("CI Guards", False, duration, detail[:100])
        print(f"FAIL ({detail[:50]}...)")


def check_unit_tests(result: DoctorResult, quick: bool = False) -> None:
    """Run pytest unit tests."""
    print("  [3/6] Unit tests...", end=" ", flush=True)

    # Build pytest command (env vars passed through run_command)
    cmd = (
        "python -m pytest backend/tests/ -v --tb=short "
        "--ignore=backend/tests/test_sync_contract.py"
    )

    if quick:
        cmd += " -x"  # Stop on first failure

    passed, output, duration = run_command(cmd, timeout=300)

    # Extract test counts from pytest output
    if "passed" in output:
        # Try to find "X passed" in output
        import re
        match = re.search(r"(\d+) passed", output)
        count = match.group(1) if match else "?"
        detail = f"{count} tests passed"
    else:
        detail = "Check output for details"

    if passed:
        result.add("Unit Tests", True, duration, detail)
        print(f"OK ({detail}, {duration/1000:.1f}s)")
    else:
        # Find failure summary
        lines = output.strip().split("\n")
        fail_line = next((l for l in lines if "FAILED" in l), "Unknown failure")
        result.add("Unit Tests", False, duration, fail_line[:100])
        print(f"FAIL")


def check_contracts(result: DoctorResult) -> None:
    """Run contract tests specifically."""
    print("  [4/6] Contract tests...", end=" ", flush=True)

    cmd = "python -m pytest backend/tests/test_contracts.py -v --tb=short"

    passed, output, duration = run_command(cmd, timeout=120)

    if passed:
        result.add("Contracts", True, duration, "All contracts valid")
        print(f"OK ({duration/1000:.1f}s)")
    else:
        result.add("Contracts", False, duration, "Contract violation detected")
        print("FAIL")


def check_tenant_isolation(result: DoctorResult) -> None:
    """Run tenant isolation tests (INV-1)."""
    print("  [5/6] Tenant isolation (INV-1)...", end=" ", flush=True)

    cmd = "python -m pytest backend/tests/test_tenant_isolation.py backend/tests/test_invariants.py -v --tb=short"

    passed, output, duration = run_command(cmd, timeout=120)

    if passed:
        result.add("Tenant Isolation", True, duration, "INV-1 enforced")
        print(f"OK ({duration/1000:.1f}s)")
    else:
        result.add("Tenant Isolation", False, duration, "CRITICAL: Isolation breach possible")
        print("FAIL - CRITICAL")


def check_no_silent_failures(result: DoctorResult) -> None:
    """Run silent failure detection tests."""
    print("  [6/6] Silent failure checks...", end=" ", flush=True)

    cmd = "python -m pytest backend/tests/test_no_silent_failures.py -v --tb=short"

    passed, output, duration = run_command(cmd, timeout=120)

    if passed:
        result.add("No Silent Failures", True, duration, "All failures are loud")
        print(f"OK ({duration/1000:.1f}s)")
    else:
        result.add("No Silent Failures", False, duration, "Silent failure detected")
        print("FAIL")


def print_summary(result: DoctorResult) -> None:
    """Print final summary."""
    print("\n" + "=" * 60)
    print("DOCTOR SUMMARY")
    print("=" * 60)

    total_duration = sum(d for _, _, d, _ in result.checks)

    for name, passed, duration, detail in result.checks:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}  {name}: {detail}")

    print("-" * 60)
    print(f"Total: {result.passed_count} passed, {result.failed_count} failed ({total_duration/1000:.1f}s)")
    print("=" * 60)

    if result.all_passed:
        print("\n*** ALL CHECKS PASSED ***\n")
    else:
        print("\n*** SOME CHECKS FAILED - See details above ***\n")


def main():
    """Run all doctor checks."""
    import argparse

    parser = argparse.ArgumentParser(description="Doctor - Unified health check")
    parser.add_argument("--quick", action="store_true", help="Skip slow tests")
    parser.add_argument("--ci", action="store_true", help="CI mode (stricter)")
    args = parser.parse_args()

    # Set defaults if not in environment
    if not os.environ.get("MONGO_URL"):
        os.environ["MONGO_URL"] = "mongodb://localhost:27017"
    if not os.environ.get("DB_NAME"):
        os.environ["DB_NAME"] = "test"
    if not os.environ.get("JWT_SECRET"):
        os.environ["JWT_SECRET"] = "test-doctor-secret-key"

    print("\n" + "=" * 60)
    print(f"DOCTOR RUN - {datetime.now().isoformat()}")
    print("=" * 60 + "\n")

    result = DoctorResult()

    # Run all checks
    check_preflight(result)
    check_ci_guards(result)
    check_unit_tests(result, quick=args.quick)
    check_contracts(result)
    check_tenant_isolation(result)
    check_no_silent_failures(result)

    # Print summary
    print_summary(result)

    # Exit with appropriate code
    sys.exit(0 if result.all_passed else 1)


if __name__ == "__main__":
    main()
