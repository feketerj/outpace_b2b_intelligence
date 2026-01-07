"""
Canary detection for identifying test/dev data in production.

Canary values are known-bad patterns that should never appear in
production environments. Finding them indicates either:
1. Test data leaked into production
2. Configuration error (dev secrets in prod)
3. Attempted exploitation

Usage:
    from backend.utils.canaries import check_for_canaries, CanaryDetected

    check_for_canaries(user_email, "user.email")
    check_for_canaries(api_key, "external_api_key")
"""

import os
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class CanaryDetected(Exception):
    """Raised when a canary value is detected in production."""
    pass


# ==================== CANARY VALUE DEFINITIONS ====================

# Test emails that should never appear in production
TEST_EMAIL_PATTERNS = [
    r"test@test\.com",
    r"test@example\.com",
    r"admin@outpace\.ai",  # Fixture admin (unless in test mode)
    r".*@localhost$",
    r".*@127\.0\.0\.1$",
    r"carfax@.*",  # Test harness email
]

# Null/placeholder UUIDs
NULL_UUIDS = [
    "00000000-0000-0000-0000-000000000000",
    "11111111-1111-1111-1111-111111111111",
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
]

# Development secrets that should never be in production
DEV_SECRET_FRAGMENTS = [
    "local-dev-secret",
    "test-secret",
    "changeme",
    "password123",
    "admin123",
    "development_key",
    "your-secret-here",
    "sk_test_",  # Stripe test key prefix
    "pk_test_",  # Stripe test key prefix
]

# Sensitive environment variable names
SENSITIVE_ENV_PATTERNS = [
    r".*_SECRET.*",
    r".*_KEY.*",
    r".*_TOKEN.*",
    r".*_PASSWORD.*",
    r".*API_KEY.*",
    r".*PRIVATE_KEY.*",
]


def _matches_any_pattern(value: str, patterns: List[str]) -> Optional[str]:
    """Check if value matches any regex pattern, return the matching pattern."""
    for pattern in patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return pattern
    return None


def check_for_canaries(
    value: str,
    context: str,
    raise_in_prod: bool = True
) -> Optional[str]:
    """
    Check if a value contains any canary patterns.

    Args:
        value: The value to check
        context: Description of where this value came from (for logging)
        raise_in_prod: If True, raise CanaryDetected in production

    Returns:
        The matching canary pattern if found, None otherwise

    Raises:
        CanaryDetected: If canary found and raise_in_prod=True and not in test mode
    """
    if not value:
        return None

    value_str = str(value)

    # Check test emails
    match = _matches_any_pattern(value_str, TEST_EMAIL_PATTERNS)
    if match:
        return _handle_canary_match(value_str, match, context, "test_email", raise_in_prod)

    # Check null UUIDs
    if value_str.lower() in [u.lower() for u in NULL_UUIDS]:
        return _handle_canary_match(value_str, "NULL_UUID", context, "null_uuid", raise_in_prod)

    # Check dev secrets
    for fragment in DEV_SECRET_FRAGMENTS:
        if fragment.lower() in value_str.lower():
            return _handle_canary_match(value_str, fragment, context, "dev_secret", raise_in_prod)

    return None


def _handle_canary_match(
    value: str,
    pattern: str,
    context: str,
    canary_type: str,
    raise_in_prod: bool
) -> str:
    """Handle a canary match - log and optionally raise."""

    # Check if we're in test mode
    allow_canaries = os.getenv("ALLOW_CANARIES", "").lower() in ("true", "1", "yes")
    is_testing = os.getenv("TESTING", "").lower() in ("true", "1", "yes")
    is_dev = os.getenv("ENVIRONMENT", "production").lower() in ("development", "dev", "local")

    # Redact the actual value in logs
    redacted = value[:4] + "..." if len(value) > 4 else "***"

    if allow_canaries or is_testing or is_dev:
        logger.debug(
            f"[canary.allowed] type={canary_type} context={context} "
            f"pattern={pattern} value={redacted}"
        )
        return pattern

    # Production - this is a problem
    logger.warning(
        f"[CANARY_DETECTED] type={canary_type} context={context} "
        f"pattern={pattern} value={redacted}"
    )

    if raise_in_prod:
        raise CanaryDetected(
            f"Production canary detected in {context}: "
            f"value matches '{pattern}' ({canary_type})"
        )

    return pattern


def check_env_for_dev_secrets() -> List[str]:
    """
    Scan environment variables for development secrets.

    Call at application startup to catch misconfigurations.

    Returns:
        List of warnings about suspicious environment values
    """
    warnings = []

    for key, value in os.environ.items():
        # Check if this looks like a sensitive variable
        if _matches_any_pattern(key, SENSITIVE_ENV_PATTERNS):
            # Check if value contains dev secret fragments
            for fragment in DEV_SECRET_FRAGMENTS:
                if fragment.lower() in value.lower():
                    warnings.append(
                        f"ENV_WARNING: {key} contains dev secret pattern '{fragment}'"
                    )

    if warnings:
        logger.warning(f"[canary.env_check] Found {len(warnings)} suspicious env vars")
        for w in warnings:
            logger.warning(f"[canary.env_check] {w}")

    return warnings


def sanitize_for_logging(value: str, sensitive: bool = False) -> str:
    """
    Sanitize a value for safe logging.

    Args:
        value: The value to sanitize
        sensitive: If True, redact more aggressively

    Returns:
        Sanitized value safe for logging
    """
    if not value:
        return "<empty>"

    if sensitive or len(value) > 100:
        # Show first/last few chars
        if len(value) > 8:
            return f"{value[:4]}...{value[-4:]}"
        return "***"

    # Check if it looks like a secret and redact
    for fragment in DEV_SECRET_FRAGMENTS:
        if fragment.lower() in value.lower():
            return "<redacted:possible_secret>"

    return value
