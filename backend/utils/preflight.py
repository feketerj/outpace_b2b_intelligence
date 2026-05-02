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


def _check_cors_security(result: PreflightResult) -> None:
    """
    Check CORS configuration security.

    In production (ENV=production): Wildcard CORS is a CRITICAL ERROR - server won't start.
    In development: Wildcard CORS is a WARNING - server starts but logs the risk.
    """
    cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS") or os.environ.get("CORS_ORIGINS", "")
    environment = os.environ.get("ENV", "development").lower()
    is_production = environment in ("production", "prod")

    is_wildcard = not cors_origins or cors_origins.strip() == "*"

    if is_wildcard and is_production:
        # PRODUCTION: This is a critical security error - fail hard
        result.add_error(
            "CORS_ALLOWED_ORIGINS is wildcard ('*') in production environment. "
            "This allows ANY website to make authenticated API calls. "
            "Set CORS_ALLOWED_ORIGINS to your allowed domains (e.g., https://yourdomain.com). "
            "Server will NOT start until this is fixed."
        )
    elif is_wildcard:
        # DEVELOPMENT: Warn but allow startup
        result.add_warning(
            "CORS_ALLOWED_ORIGINS not set or is '*' - allowing ANY origin. "
            "This is acceptable for local development but WILL FAIL in production (ENV=production). "
            "Set CORS_ALLOWED_ORIGINS=http://localhost:3000 for dev."
        )
    else:
        result.add_pass("CORS_ALLOWED_ORIGINS_CONFIGURED")


def _check_secrets_backend(result: PreflightResult) -> None:
    """Validate secrets backend configuration for production."""
    backend = os.environ.get("SECRETS_BACKEND", "env").lower()
    if backend == "gcp":
        project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            result.add_error("GCP Secret Manager selected but GCP_PROJECT_ID/GOOGLE_CLOUD_PROJECT not set")
        else:
            result.add_pass("GCP_PROJECT_ID_SET")


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


def _check_rate_limit_storage(result: PreflightResult) -> None:
    """
    Check rate limit storage configuration for production readiness.

    In production (ENV=production): In-memory storage is a WARNING because:
    - Rate limits reset on server restart
    - Each instance has independent limits (defeats purpose in multi-instance)

    In development: In-memory storage is acceptable.
    """
    rate_limit_storage = os.environ.get("RATE_LIMIT_STORAGE", "memory://")
    environment = os.environ.get("ENV", "development").lower()
    is_production = environment in ("production", "prod")

    is_memory = rate_limit_storage.startswith("memory://") or not rate_limit_storage

    if is_memory and is_production:
        result.add_warning(
            "RATE_LIMIT_STORAGE is using in-memory storage in production. "
            "Rate limits will reset on restart and won't be shared across instances. "
            "Set RATE_LIMIT_STORAGE=redis://redis:6379/0 for production deployments."
        )
    elif is_memory:
        # Development - just note it
        logger.debug("[PREFLIGHT_INFO] Using in-memory rate limiting (OK for development)")
        result.add_pass("RATE_LIMIT_STORAGE_DEV")
    else:
        result.add_pass("RATE_LIMIT_STORAGE_CONFIGURED")


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
    _check_cors_security(result)
    _check_secrets_backend(result)
    _check_rate_limit_storage(result)
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
