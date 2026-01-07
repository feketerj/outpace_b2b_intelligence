"""
Startup preflight checks - validates environment before accepting requests.

This module runs BEFORE the server starts accepting traffic.
Any critical failure here results in exit(1) and clear error logging.

Usage (in server.py lifespan):
    from backend.utils.preflight import run_preflight_checks

    async def lifespan(app: FastAPI):
        await run_preflight_checks()  # Exits if critical failure
        # ... rest of startup
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)

# Required environment variables - server won't start without these
REQUIRED_ENV_VARS = ["MONGO_URL", "DB_NAME", "JWT_SECRET"]

# Patterns that indicate development/test secrets
DEV_SECRET_PATTERNS = ["local-dev", "test-secret", "changeme", "development"]


class PreflightResult:
    """Container for preflight check results."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.checks_passed: int = 0

    @property
    def critical_failure(self) -> bool:
        return len(self.errors) > 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        logger.critical(f"[PREFLIGHT_ERROR] {msg}")

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning(f"[PREFLIGHT_WARN] {msg}")

    def add_pass(self, check_name: str) -> None:
        self.checks_passed += 1
        logger.info(f"[PREFLIGHT_OK] {check_name}")


def _check_required_env_vars(result: PreflightResult) -> None:
    """Check that all required environment variables are set."""
    for var in REQUIRED_ENV_VARS:
        value = os.environ.get(var)
        if not value:
            result.add_error(f"Missing required env var: {var}")
        elif not value.strip():
            result.add_error(f"Empty env var: {var}")
        else:
            result.add_pass(f"ENV_{var}_SET")


def _check_jwt_secret_quality(result: PreflightResult) -> None:
    """Warn if JWT_SECRET looks like a development value."""
    jwt_secret = os.environ.get("JWT_SECRET", "")

    if not jwt_secret:
        return  # Already caught by required env var check

    for pattern in DEV_SECRET_PATTERNS:
        if pattern.lower() in jwt_secret.lower():
            result.add_warning(
                f"JWT_SECRET contains '{pattern}' - ensure this is intentional"
            )
            return

    if len(jwt_secret) < 32:
        result.add_warning(
            f"JWT_SECRET is only {len(jwt_secret)} chars - recommend >= 32 chars for production"
        )
    else:
        result.add_pass("JWT_SECRET_QUALITY")


async def _check_mongodb_connectivity(result: PreflightResult, timeout_seconds: float = 10.0) -> None:
    """Test MongoDB connectivity with timeout."""
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        return  # Already caught by required env var check

    try:
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=int(timeout_seconds * 1000))

        # Try to ping the server
        await asyncio.wait_for(
            client.admin.command("ping"),
            timeout=timeout_seconds
        )

        result.add_pass("MONGODB_CONNECTIVITY")
        client.close()

    except asyncio.TimeoutError:
        result.add_error(f"MongoDB connection timed out after {timeout_seconds}s")
    except Exception as e:
        result.add_error(f"MongoDB connection failed: {type(e).__name__}: {e}")


def _check_canaries(result: PreflightResult) -> None:
    """Run canary detection on environment (optional)."""
    try:
        from backend.utils.canaries import check_env_for_dev_secrets

        warnings = check_env_for_dev_secrets()
        for w in warnings:
            result.add_warning(w)

        if not warnings:
            result.add_pass("NO_DEV_CANARIES")
    except ImportError:
        # Canaries module not available - skip this check
        logger.debug("[PREFLIGHT_SKIP] Canaries module not available, skipping env canary check")


async def run_preflight_checks(
    exit_on_failure: bool = True,
    mongodb_timeout: float = 10.0
) -> PreflightResult:
    """
    Run all preflight checks.

    Args:
        exit_on_failure: If True, calls sys.exit(1) on critical failure
        mongodb_timeout: Seconds to wait for MongoDB connection

    Returns:
        PreflightResult with all check outcomes
    """
    logger.info("[PREFLIGHT_START] Running startup validation...")
    start_time = datetime.now(timezone.utc)

    result = PreflightResult()

    # Sync checks
    _check_required_env_vars(result)
    _check_jwt_secret_quality(result)
    _check_canaries(result)

    # Async checks
    await _check_mongodb_connectivity(result, mongodb_timeout)

    # Calculate duration
    duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

    # Final verdict
    if result.critical_failure:
        logger.critical(
            f"[PREFLIGHT_FAILED] {len(result.errors)} critical errors, "
            f"{len(result.warnings)} warnings in {duration_ms:.0f}ms"
        )
        for error in result.errors:
            logger.critical(f"  - {error}")

        if exit_on_failure:
            sys.exit(1)
    else:
        logger.info(
            f"[PREFLIGHT_PASSED] {result.checks_passed} checks passed, "
            f"{len(result.warnings)} warnings in {duration_ms:.0f}ms"
        )

    return result
