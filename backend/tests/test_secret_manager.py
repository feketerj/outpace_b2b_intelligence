"""
Unit tests for backend/utils/secret_manager.py

Covers: cache hits, env-var fallback, default fallback, GCP path (mocked),
ImportError branch, GCP exception branch, and clear_cache.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────── helpers ────────────────────────────────────────

def _reload_module():
    """Return a freshly-imported secret_manager with an empty cache."""
    import importlib
    import backend.utils.secret_manager as sm
    sm.clear_cache()
    return sm


# ────────────────────────── cache tests ─────────────────────────────────────


class TestSecretManagerCache:
    """In-memory cache behaviour."""

    def setup_method(self):
        from backend.utils import secret_manager
        secret_manager.clear_cache()

    def test_cache_hit_returns_same_value(self):
        """Second call returns cached value without hitting env."""
        from backend.utils.secret_manager import get_secret

        with patch.dict(os.environ, {"MY_SECRET": "first-value"}, clear=True):
            first = get_secret("MY_SECRET")

        # Env no longer has the key, but cache should still hold it
        second = get_secret("MY_SECRET")
        assert first == "first-value"
        assert second == "first-value"

    def test_cache_stores_none_for_missing_key(self):
        """Missing key is cached as None so env is not re-checked."""
        from backend.utils.secret_manager import get_secret, _cache

        with patch.dict(os.environ, {}, clear=True):
            result = get_secret("DEFINITELY_NOT_SET_XYZ")

        assert result is None
        assert "DEFINITELY_NOT_SET_XYZ" in _cache

    def test_clear_cache_evicts_all_entries(self):
        """clear_cache empties the cache dict."""
        from backend.utils.secret_manager import get_secret, clear_cache, _cache

        with patch.dict(os.environ, {"CACHED_KEY": "val"}, clear=True):
            get_secret("CACHED_KEY")

        assert "CACHED_KEY" in _cache
        clear_cache()
        assert "CACHED_KEY" not in _cache


# ────────────────────────── env-var fallback ─────────────────────────────────


class TestSecretManagerEnvVarFallback:
    """Resolution from environment variables."""

    def setup_method(self):
        from backend.utils import secret_manager
        secret_manager.clear_cache()

    def test_returns_env_var_when_set(self):
        from backend.utils.secret_manager import get_secret

        with patch.dict(os.environ, {"SOME_API_KEY": "env-value"}, clear=True):
            assert get_secret("SOME_API_KEY") == "env-value"

    def test_returns_default_when_env_not_set(self):
        from backend.utils.secret_manager import get_secret

        with patch.dict(os.environ, {}, clear=True):
            assert get_secret("MISSING_KEY", default="my-default") == "my-default"

    def test_returns_none_when_no_default_and_env_not_set(self):
        from backend.utils.secret_manager import get_secret

        with patch.dict(os.environ, {}, clear=True):
            assert get_secret("MISSING_KEY_NO_DEFAULT") is None


# ────────────────────── GCP Secret Manager path ──────────────────────────────


class TestSecretManagerGCP:
    """GCP Secret Manager integration (mocked)."""

    def setup_method(self):
        from backend.utils import secret_manager
        secret_manager.clear_cache()

    def test_gcp_import_error_falls_back_to_env(self):
        """When google-cloud-secret-manager is not installed, fall back to env."""
        from backend.utils.secret_manager import get_secret

        # Simulate GOOGLE_CLOUD_PROJECT being set
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-project", "MY_KEY": "env-val"}, clear=True):
            # Patch the import inside _fetch_from_gcp to raise ImportError
            with patch.dict("sys.modules", {"google.cloud": None, "google.cloud.secretmanager": None}):
                result = get_secret("MY_KEY")

        assert result == "env-val"

    def test_gcp_client_exception_falls_back_to_env(self):
        """GCP client exception → fall back to env var."""
        from backend.utils.secret_manager import get_secret

        mock_secretmanager = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.access_secret_version.side_effect = Exception("Permission denied")
        mock_secretmanager.SecretManagerServiceClient.return_value = mock_client_instance

        mock_google_cloud = MagicMock()
        mock_google_cloud.secretmanager = mock_secretmanager

        with patch.dict(
            os.environ,
            {"GOOGLE_CLOUD_PROJECT": "my-project", "GCP_FALLBACK_KEY": "from-env"},
            clear=True,
        ):
            with patch.dict("sys.modules", {"google.cloud": mock_google_cloud, "google.cloud.secretmanager": mock_secretmanager}):
                result = get_secret("GCP_FALLBACK_KEY")

        assert result == "from-env"

    def test_gcp_success_returns_secret_value(self):
        """Successful GCP lookup returns the secret payload."""
        from backend.utils.secret_manager import get_secret

        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = "gcp-secret-value"

        mock_client_instance = MagicMock()
        mock_client_instance.access_secret_version.return_value = mock_response

        mock_secretmanager = MagicMock()
        mock_secretmanager.SecretManagerServiceClient.return_value = mock_client_instance

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-project"}, clear=True):
            with patch.dict("sys.modules", {"google.cloud": MagicMock(secretmanager=mock_secretmanager), "google.cloud.secretmanager": mock_secretmanager}):
                with patch("backend.utils.secret_manager._fetch_from_gcp", return_value="gcp-secret-value"):
                    result = get_secret("GCP_KEY")

        assert result == "gcp-secret-value"


# ─────────────── _fetch_from_gcp directly ───────────────────────────────────


class TestFetchFromGCP:
    """Direct tests of the private _fetch_from_gcp helper."""

    def setup_method(self):
        from backend.utils import secret_manager
        secret_manager.clear_cache()

    def test_returns_none_on_import_error(self):
        """ImportError from google.cloud → returns None."""
        from backend.utils.secret_manager import _fetch_from_gcp

        with patch.dict("sys.modules", {"google.cloud": None, "google.cloud.secretmanager": None}):
            result = _fetch_from_gcp("MY_KEY", "my-project")

        assert result is None

    def test_returns_none_on_gcp_exception(self):
        """Any exception from GCP client → returns None."""
        from backend.utils.secret_manager import _fetch_from_gcp

        mock_secretmanager = MagicMock()
        mock_client = MagicMock()
        mock_client.access_secret_version.side_effect = RuntimeError("Access denied")
        mock_secretmanager.SecretManagerServiceClient.return_value = mock_client

        with patch.dict("sys.modules", {
            "google.cloud": MagicMock(secretmanager=mock_secretmanager),
            "google.cloud.secretmanager": mock_secretmanager,
        }):
            result = _fetch_from_gcp("MY_KEY", "my-project")

        assert result is None

    def test_returns_decoded_value_on_success(self):
        """Successful GCP lookup decodes and returns the payload."""
        from backend.utils.secret_manager import _fetch_from_gcp

        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = "decoded-value"
        mock_client = MagicMock()
        mock_client.access_secret_version.return_value = mock_response
        mock_secretmanager = MagicMock()
        mock_secretmanager.SecretManagerServiceClient.return_value = mock_client

        with patch.dict("sys.modules", {
            "google.cloud": MagicMock(secretmanager=mock_secretmanager),
            "google.cloud.secretmanager": mock_secretmanager,
        }):
            result = _fetch_from_gcp("MY_KEY", "my-project")

        assert result == "decoded-value"
