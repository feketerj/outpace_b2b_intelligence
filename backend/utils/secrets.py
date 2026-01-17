"""
Secrets management abstraction layer.

Supports multiple backends:
- Environment variables (development, default)
- AWS Secrets Manager (production)
- GCP Secret Manager (production)
- HashiCorp Vault (enterprise)

Usage:
    from utils.secrets import get_secret

    jwt_secret = get_secret("JWT_SECRET")
    mongo_url = get_secret("MONGO_URL", default="mongodb://localhost:27017")

Configuration:
    Set SECRETS_BACKEND environment variable:
    - "env" (default): Read from environment variables
    - "aws": Read from AWS Secrets Manager
    - "gcp": Read from GCP Secret Manager
    - "vault": Read from HashiCorp Vault
"""

import os
import json
import logging
from functools import lru_cache
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Backend selection via environment
SECRETS_BACKEND = os.environ.get("SECRETS_BACKEND", "env")


class SecretsProvider:
    """Abstract base class for secrets providers."""

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret by key."""
        raise NotImplementedError

    def clear_cache(self) -> None:
        """Clear any cached secrets (for rotation)."""
        pass


class EnvSecretsProvider(SecretsProvider):
    """
    Development provider: reads secrets from environment variables.

    This is the default and simplest provider. Suitable for local development
    and CI/CD environments where secrets are injected via environment.
    """

    def get_secret(self, key: str) -> Optional[str]:
        """Read secret from environment variable."""
        # Also check for _FILE suffix (Docker secrets pattern)
        file_key = f"{key}_FILE"
        file_path = os.environ.get(file_key)

        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    value = f.read().strip()
                    logger.debug(f"[secrets] Loaded {key} from file")
                    return value
            except IOError as e:
                logger.error(f"[secrets] Failed to read {file_key}: {e}")

        return os.environ.get(key)


class AWSSecretsProvider(SecretsProvider):
    """
    Production provider: reads secrets from AWS Secrets Manager.

    Requires:
    - boto3 package installed
    - AWS credentials configured (IAM role, env vars, or config file)
    - AWS_REGION environment variable set

    Secret naming convention:
    - outpace/{environment}/jwt-secret
    - outpace/{environment}/mongo-url
    - outpace/{environment}/api-keys (JSON with highergov, perplexity, mistral keys)
    """

    def __init__(self):
        try:
            import boto3
            self.client = boto3.client(
                'secretsmanager',
                region_name=os.environ.get('AWS_REGION', 'us-east-1')
            )
            self._cache: Dict[str, str] = {}
            self._env = os.environ.get('ENVIRONMENT', 'production')
        except ImportError:
            raise RuntimeError(
                "boto3 required for AWS secrets backend. "
                "Install with: pip install boto3"
            )

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from AWS Secrets Manager."""
        # Map environment variable names to AWS secret paths
        secret_map = {
            "JWT_SECRET": f"outpace/{self._env}/jwt-secret",
            "MONGO_URL": f"outpace/{self._env}/mongo-url",
            "DB_NAME": f"outpace/{self._env}/db-name",
            "HIGHERGOV_API_KEY": (f"outpace/{self._env}/api-keys", "highergov"),
            "PERPLEXITY_API_KEY": (f"outpace/{self._env}/api-keys", "perplexity"),
            "MISTRAL_API_KEY": (f"outpace/{self._env}/api-keys", "mistral"),
        }

        if key not in secret_map:
            # Fall back to environment for unmapped keys
            logger.debug(f"[secrets] {key} not in AWS map, using env fallback")
            return os.environ.get(key)

        mapping = secret_map[key]

        # Simple secret (direct string value)
        if isinstance(mapping, str):
            return self._fetch_secret(mapping)

        # JSON secret (extract specific key from JSON object)
        secret_path, json_key = mapping
        secret_json = self._fetch_secret(secret_path)
        if secret_json:
            try:
                data = json.loads(secret_json)
                return data.get(json_key)
            except json.JSONDecodeError as e:
                logger.error(f"[secrets] Failed to parse JSON from {secret_path}: {e}")

        return None

    def _fetch_secret(self, secret_name: str) -> Optional[str]:
        """Fetch raw secret value from AWS."""
        if secret_name in self._cache:
            return self._cache[secret_name]

        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            value = response.get('SecretString')
            self._cache[secret_name] = value
            logger.info(f"[secrets] Loaded secret: {secret_name}")
            return value
        except self.client.exceptions.ResourceNotFoundException:
            logger.error(f"[secrets] Secret not found: {secret_name}")
            return None
        except self.client.exceptions.AccessDeniedException:
            logger.error(f"[secrets] Access denied for secret: {secret_name}")
            return None
        except Exception as e:
            logger.error(f"[secrets] Failed to fetch {secret_name}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the secrets cache (useful after rotation)."""
        self._cache.clear()
        logger.info("[secrets] AWS secrets cache cleared")


class GCPSecretsProvider(SecretsProvider):
    """
    Production provider: reads secrets from GCP Secret Manager.

    Requires:
    - google-cloud-secret-manager package installed
    - GOOGLE_CLOUD_PROJECT or GCP_PROJECT_ID set

    Secret naming convention:
    - outpace-{environment}-jwt-secret
    - outpace-{environment}-mongo-url
    - outpace-{environment}-db-name
    - outpace-{environment}-api-keys (JSON with highergov, perplexity, mistral keys)
    """

    def __init__(self):
        try:
            from google.cloud import secretmanager
            self.client = secretmanager.SecretManagerServiceClient()
            self._cache: Dict[str, str] = {}
            self._env = os.environ.get("ENVIRONMENT", "production")
            self._project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
            self._prefix = os.environ.get("GCP_SECRET_PREFIX", "outpace")
            if not self._project_id:
                raise RuntimeError("GCP project ID not configured (set GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT)")
        except ImportError:
            raise RuntimeError(
                "google-cloud-secret-manager required for GCP secrets backend. "
                "Install with: pip install google-cloud-secret-manager"
            )

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from GCP Secret Manager."""
        secret_map = {
            "JWT_SECRET": f"{self._prefix}-{self._env}-jwt-secret",
            "MONGO_URL": f"{self._prefix}-{self._env}-mongo-url",
            "DB_NAME": f"{self._prefix}-{self._env}-db-name",
            "HIGHERGOV_API_KEY": (f"{self._prefix}-{self._env}-api-keys", "highergov"),
            "PERPLEXITY_API_KEY": (f"{self._prefix}-{self._env}-api-keys", "perplexity"),
            "MISTRAL_API_KEY": (f"{self._prefix}-{self._env}-api-keys", "mistral"),
        }

        if key not in secret_map:
            logger.debug(f"[secrets] {key} not in GCP map, using env fallback")
            return os.environ.get(key)

        mapping = secret_map[key]
        if isinstance(mapping, str):
            return self._fetch_secret(mapping)

        secret_name, json_key = mapping
        secret_json = self._fetch_secret(secret_name)
        if secret_json:
            try:
                data = json.loads(secret_json)
                return data.get(json_key)
            except json.JSONDecodeError as e:
                logger.error(f"[secrets] Failed to parse JSON from {secret_name}: {e}")
        return None

    def _fetch_secret(self, secret_name: str) -> Optional[str]:
        if secret_name in self._cache:
            return self._cache[secret_name]

        try:
            resource = f"projects/{self._project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(name=resource)
            value = response.payload.data.decode("utf-8")
            self._cache[secret_name] = value
            logger.info(f"[secrets] Loaded secret: {secret_name}")
            return value
        except Exception as e:
            logger.error(f"[secrets] Failed to fetch {secret_name}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the secrets cache (useful after rotation)."""
        self._cache.clear()
        logger.info("[secrets] GCP secrets cache cleared")


class VaultSecretsProvider(SecretsProvider):
    """
    Enterprise provider: reads secrets from HashiCorp Vault.

    Requires:
    - hvac package installed
    - VAULT_ADDR environment variable
    - VAULT_TOKEN or AppRole credentials

    Secret path convention:
    - secret/data/outpace/{key_name}
    """

    def __init__(self):
        try:
            import hvac
            vault_addr = os.environ.get("VAULT_ADDR", "http://localhost:8200")
            vault_token = os.environ.get("VAULT_TOKEN")

            self.client = hvac.Client(url=vault_addr, token=vault_token)

            if not self.client.is_authenticated():
                raise RuntimeError("Vault authentication failed")

            self._cache: Dict[str, str] = {}
            logger.info(f"[secrets] Connected to Vault at {vault_addr}")

        except ImportError:
            raise RuntimeError(
                "hvac required for Vault secrets backend. "
                "Install with: pip install hvac"
            )

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve secret from HashiCorp Vault."""
        cache_key = key.lower()

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=f"outpace/{cache_key}"
            )
            value = response['data']['data'].get('value')
            self._cache[cache_key] = value
            logger.info(f"[secrets] Loaded secret from Vault: {key}")
            return value
        except Exception as e:
            logger.error(f"[secrets] Failed to fetch {key} from Vault: {e}")
            # Fall back to environment
            return os.environ.get(key)

    def clear_cache(self) -> None:
        """Clear the secrets cache."""
        self._cache.clear()
        logger.info("[secrets] Vault secrets cache cleared")


# Provider registry
_PROVIDERS = {
    "env": EnvSecretsProvider,
    "aws": AWSSecretsProvider,
    "gcp": GCPSecretsProvider,
    "vault": VaultSecretsProvider,
}

# Singleton instance
_provider_instance: Optional[SecretsProvider] = None


def get_secrets_provider() -> SecretsProvider:
    """
    Get the configured secrets provider (singleton).

    The provider is determined by SECRETS_BACKEND environment variable.
    """
    global _provider_instance

    if _provider_instance is None:
        provider_class = _PROVIDERS.get(SECRETS_BACKEND, EnvSecretsProvider)
        logger.info(f"[secrets] Initializing secrets backend: {SECRETS_BACKEND}")
        _provider_instance = provider_class()

    return _provider_instance


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get a secret value.

    This is the main entry point for retrieving secrets. It automatically
    uses the configured backend (env, aws, or vault).

    Args:
        key: Secret name (e.g., "JWT_SECRET", "MONGO_URL")
        default: Default value if secret is not found (use sparingly)

    Returns:
        Secret value, default, or None if not found

    Example:
        jwt_secret = get_secret("JWT_SECRET")
        if not jwt_secret:
            raise RuntimeError("JWT_SECRET not configured")
    """
    provider = get_secrets_provider()
    value = provider.get_secret(key)

    if value is None:
        if default is not None:
            logger.warning(f"[secrets] Using default value for {key}")
            return default
        logger.warning(f"[secrets] Secret not found: {key}")

    return value


def clear_secrets_cache() -> None:
    """
    Clear any cached secrets.

    Call this after secret rotation to force re-fetch from the backend.
    """
    provider = get_secrets_provider()
    provider.clear_cache()


def require_secret(key: str) -> str:
    """
    Get a required secret, raising an error if not found.

    Use this for secrets that are absolutely required for the application
    to function. The application will fail fast if the secret is missing.

    Args:
        key: Secret name

    Returns:
        Secret value

    Raises:
        RuntimeError: If secret is not found
    """
    value = get_secret(key)
    if value is None:
        raise RuntimeError(f"Required secret not found: {key}")
    return value
