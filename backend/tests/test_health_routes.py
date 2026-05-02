"""
Unit tests for backend/routes/health.py

Tests the health check helper functions with mocked dependencies.
No real DB or API connections are made.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestCheckConfig:
    """_check_config validates environment configuration."""

    def test_returns_ok_when_all_required_env_vars_set(self):
        from backend.routes.health import _check_config

        with patch.dict(os.environ, {
            "MONGO_URL": "mongodb://localhost:27017",
            "JWT_SECRET": "a-good-long-secret-key-here-abcdefgh",
        }, clear=False):
            result = _check_config()

        assert result["ok"] is True
        assert not result.get("issues")

    def test_returns_not_ok_when_mongo_url_missing(self):
        from backend.routes.health import _check_config

        with patch.dict(os.environ, {"JWT_SECRET": "a-secret-key"}, clear=True):
            result = _check_config()

        assert result["ok"] is False
        assert result["issues"] is not None
        assert any("MONGO_URL" in i for i in result["issues"])

    def test_returns_not_ok_when_jwt_secret_missing(self):
        from backend.routes.health import _check_config

        with patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost"}, clear=True):
            result = _check_config()

        assert result["ok"] is False

    def test_warns_when_jwt_secret_is_dev_value(self):
        from backend.routes.health import _check_config

        with patch.dict(os.environ, {
            "MONGO_URL": "mongodb://localhost",
            "JWT_SECRET": "local-dev-secret-key",
        }, clear=False):
            result = _check_config()

        assert result.get("warnings") is not None
        assert any("development" in w.lower() for w in result["warnings"])

    def test_warns_when_jwt_secret_contains_test(self):
        from backend.routes.health import _check_config

        with patch.dict(os.environ, {
            "MONGO_URL": "mongodb://localhost",
            "JWT_SECRET": "test-secret-key-abc",
        }, clear=False):
            result = _check_config()

        assert result.get("warnings") is not None


class TestCheckMongoDB:
    """_check_mongodb checks database connectivity."""

    @pytest.mark.asyncio
    async def test_returns_ok_on_successful_ping(self):
        from backend.routes.health import _check_mongodb

        mock_db = MagicMock()
        mock_db.command = AsyncMock(return_value={"ok": 1})
        with patch("backend.routes.health.get_database", return_value=mock_db):
            result = await _check_mongodb()

        assert result["ok"] is True
        assert "latency_ms" in result
        assert "tenant_count" not in result

    @pytest.mark.asyncio
    async def test_returns_not_ok_when_db_is_none(self):
        from backend.routes.health import _check_mongodb

        with patch("backend.routes.health.get_database", return_value=None):
            result = await _check_mongodb()

        assert result["ok"] is False
        assert "not initialized" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_returns_not_ok_on_exception(self):
        from backend.routes.health import _check_mongodb

        mock_db = MagicMock()
        mock_db.command = AsyncMock(side_effect=Exception("connection refused"))

        with patch("backend.routes.health.get_database", return_value=mock_db):
            result = await _check_mongodb()

        assert result["ok"] is False
        assert result.get("error") == "Exception"

    @pytest.mark.asyncio
    async def test_returns_not_ok_on_timeout(self):
        import asyncio
        from backend.routes.health import _check_mongodb

        mock_db = MagicMock()
        mock_db.command = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("backend.routes.health.get_database", return_value=mock_db):
            result = await _check_mongodb()

        assert result["ok"] is False
        assert result.get("error") == "Timeout"


class TestCheckMistral:
    """_check_mistral checks AI service availability."""

    @pytest.mark.asyncio
    async def test_returns_not_ok_when_key_not_configured(self):
        from backend.routes.health import _check_mistral

        with patch.dict(os.environ, {}, clear=True):
            result = await _check_mistral()

        assert result["ok"] is False
        assert "not configured" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_returns_ok_when_api_responds(self):
        from backend.routes.health import _check_mistral

        mock_response = MagicMock()
        mock_response.data = [MagicMock(), MagicMock()]
        mock_client = MagicMock()
        mock_client.models.list.return_value = mock_response

        with patch.dict(os.environ, {"MISTRAL_API_KEY": "real-key"}, clear=False):
            with patch("mistralai.Mistral", return_value=mock_client):
                result = await _check_mistral()

        assert result["ok"] is True
        assert result["models_available"] == 2

    @pytest.mark.asyncio
    async def test_returns_not_ok_when_api_raises(self):
        from backend.routes.health import _check_mistral

        mock_client = MagicMock()
        mock_client.models.list.side_effect = Exception("API error")

        with patch.dict(os.environ, {"MISTRAL_API_KEY": "real-key"}, clear=False):
            with patch("mistralai.Mistral", return_value=mock_client):
                result = await _check_mistral()

        assert result["ok"] is False
        assert "API error" in result.get("error", "")


class TestCheckPerplexity:
    """_check_perplexity checks intelligence service availability."""

    @pytest.mark.asyncio
    async def test_returns_ok_not_configured_when_key_missing(self):
        from backend.routes.health import _check_perplexity

        with patch.dict(os.environ, {}, clear=True):
            result = await _check_perplexity()

        assert result["ok"] is True
        assert result["configured"] is False

    @pytest.mark.asyncio
    async def test_returns_ok_when_api_responds_with_200(self):
        from backend.routes.health import _check_perplexity

        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "real-key"}, clear=False):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await _check_perplexity()

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_returns_ok_even_with_401(self):
        """401 means API is reachable, just unauthorized."""
        from backend.routes.health import _check_perplexity

        mock_response = MagicMock()
        mock_response.status_code = 401

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "real-key"}, clear=False):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await _check_perplexity()

        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_returns_not_ok_on_exception(self):
        from backend.routes.health import _check_perplexity

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("timeout"))

        with patch.dict(os.environ, {"PERPLEXITY_API_KEY": "real-key"}, clear=False):
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await _check_perplexity()

        assert result["ok"] is False


class TestDeepHealthCheck:
    """deep_health_check combines all component checks."""

    @pytest.mark.asyncio
    async def test_returns_healthy_when_all_ok(self):
        from backend.routes.health import deep_health_check

        ok_result = {"ok": True}

        with patch("backend.routes.health._check_mongodb", AsyncMock(return_value=ok_result)):
            with patch("backend.routes.health._check_mistral", AsyncMock(return_value=ok_result)):
                with patch("backend.routes.health._check_perplexity", AsyncMock(return_value=ok_result)):
                    with patch("backend.routes.health._check_config", return_value=ok_result):
                        result = await deep_health_check()

        assert result["status"] == "healthy"
        assert "degraded_services" not in result

    @pytest.mark.asyncio
    async def test_returns_degraded_when_any_not_ok(self):
        from backend.routes.health import deep_health_check

        ok_result = {"ok": True}
        fail_result = {"ok": False, "error": "DB is down"}

        with patch("backend.routes.health._check_mongodb", AsyncMock(return_value=fail_result)):
            with patch("backend.routes.health._check_mistral", AsyncMock(return_value=ok_result)):
                with patch("backend.routes.health._check_perplexity", AsyncMock(return_value=ok_result)):
                    with patch("backend.routes.health._check_config", return_value=ok_result):
                        result = await deep_health_check()

        assert result["status"] == "degraded"
        assert "mongodb" in result.get("degraded_services", [])

    @pytest.mark.asyncio
    async def test_response_contains_required_fields(self):
        from backend.routes.health import deep_health_check

        ok_result = {"ok": True}

        with patch("backend.routes.health._check_mongodb", AsyncMock(return_value=ok_result)):
            with patch("backend.routes.health._check_mistral", AsyncMock(return_value=ok_result)):
                with patch("backend.routes.health._check_perplexity", AsyncMock(return_value=ok_result)):
                    with patch("backend.routes.health._check_config", return_value=ok_result):
                        result = await deep_health_check()

        for field in ("status", "timestamp", "duration_ms", "services"):
            assert field in result, f"Missing field: {field}"


class TestHealthCheck:
    """Basic liveness health check."""

    @pytest.mark.asyncio
    async def test_returns_healthy_status(self):
        from backend.routes.health import health_check

        result = await health_check()

        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert result["service"] == "outpace-b2b-intelligence"
