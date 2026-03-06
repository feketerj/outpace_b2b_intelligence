"""
GCP Secret Manager integration with environment variable fallback.

Resolution order:
1. In-memory cache (process lifetime)
2. GCP Secret Manager (if GOOGLE_CLOUD_PROJECT env var is set)
3. Environment variables

Usage:
    from backend.utils.secret_manager import get_secret

    jwt_secret = get_secret("JWT_SECRET")
    mongo_url = get_secret("MONGO_URL", default="mongodb://localhost:27017")
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory cache: maps secret name → resolved value
_cache: dict[str, Optional[str]] = {}


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieve a secret by name.

    Resolution order:
    1. In-memory cache (fastest — avoids repeated GCP round-trips)
    2. GCP Secret Manager (if GOOGLE_CLOUD_PROJECT is set)
    3. Environment variable with the same name
    4. Provided default value

    Args:
        name: The secret name / environment variable key.
        default: Value to return when the secret cannot be resolved.

    Returns:
        The resolved secret value, or *default* if not found.
    """
    if name in _cache:
        return _cache[name]

    value: Optional[str] = None

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project_id:
        value = _fetch_from_gcp(name, project_id)

    if value is None:
        value = os.environ.get(name)

    if value is None:
        value = default

    # Cache even None/default so we don't repeatedly hit GCP for missing secrets
    _cache[name] = value
    return value


def _fetch_from_gcp(name: str, project_id: str) -> Optional[str]:
    """
    Fetch a secret from GCP Secret Manager.

    Returns None (without raising) if the secret does not exist, the
    ``google-cloud-secret-manager`` package is not installed, or the
    caller does not have the necessary IAM permissions.
    """
    try:
        from google.cloud import secretmanager  # type: ignore[import]
    except ImportError:
        logger.debug("[secret_manager] google-cloud-secret-manager not installed; skipping GCP lookup")
        return None

    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_path = f"projects/{project_id}/secrets/{name}/versions/latest"
        response = client.access_secret_version(request={"name": secret_path})
        value = response.payload.data.decode("utf-8")
        logger.debug(f"[secret_manager] Loaded {name!r} from GCP Secret Manager")
        return value
    except Exception as exc:  # noqa: BLE001 — GCP SDK raises varied exception types
        # Log at debug level: missing secrets and permission errors are expected
        # when running locally without GCP credentials.
        logger.debug(f"[secret_manager] GCP Secret Manager lookup failed for {name!r}: {type(exc).__name__}: {exc}")
        return None


def clear_cache() -> None:
    """
    Evict all cached secrets.

    Call this during secret rotation or in tests that need fresh resolution.
    """
    _cache.clear()
    logger.info("[secret_manager] Secret cache cleared")
