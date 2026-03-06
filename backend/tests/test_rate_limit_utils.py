"""
Unit tests for backend/utils/rate_limit.py

Covers: module-level constants, rate_limit_exceeded_handler,
and the decorator factory functions.
"""

import os
import pytest
from unittest.mock import MagicMock, patch


class TestRateLimitConstants:
    """Environment-variable-driven constants are read correctly."""

    def test_default_rate_limit_env(self):
        """DEFAULT_RATE_LIMIT is set from env or falls back to '100/minute'."""
        with patch.dict(os.environ, {"RATE_LIMIT_DEFAULT": "200/minute"}, clear=False):
            import importlib
            import backend.utils.rate_limit as rl
            importlib.reload(rl)
            assert rl.DEFAULT_RATE_LIMIT == "200/minute"

    def test_auth_rate_limit_env(self):
        with patch.dict(os.environ, {"RATE_LIMIT_AUTH": "5/minute"}, clear=False):
            import importlib
            import backend.utils.rate_limit as rl
            importlib.reload(rl)
            assert rl.AUTH_RATE_LIMIT == "5/minute"

    def test_upload_rate_limit_env(self):
        with patch.dict(os.environ, {"RATE_LIMIT_UPLOAD": "30/minute"}, clear=False):
            import importlib
            import backend.utils.rate_limit as rl
            importlib.reload(rl)
            assert rl.UPLOAD_RATE_LIMIT == "30/minute"


class TestRateLimitExceededHandler:
    """Custom handler returns 429 JSON with retry-after."""

    def _make_request(self, path="/api/test", ip="1.2.3.4"):
        request = MagicMock()
        request.url.path = path
        request.client.host = ip
        return request

    def _make_exc(self, retry_after=60):
        """Build a mock RateLimitExceeded without touching the real constructor."""
        exc = MagicMock()
        exc.detail = "100 per 1 minute"
        exc.retry_after = retry_after
        return exc

    def test_returns_429_status(self):
        from backend.utils.rate_limit import rate_limit_exceeded_handler

        response = rate_limit_exceeded_handler(self._make_request(), self._make_exc(60))
        assert response.status_code == 429

    def test_response_body_contains_detail(self):
        import json
        from backend.utils.rate_limit import rate_limit_exceeded_handler

        response = rate_limit_exceeded_handler(self._make_request(), self._make_exc(30))
        body = json.loads(response.body)
        assert "detail" in body
        assert "Rate limit exceeded" in body["detail"]

    def test_response_contains_retry_after(self):
        import json
        from backend.utils.rate_limit import rate_limit_exceeded_handler

        response = rate_limit_exceeded_handler(self._make_request(), self._make_exc(45))
        assert response.headers.get("Retry-After") == "45"
        body = json.loads(response.body)
        assert body["retry_after_seconds"] == 45

    def test_handler_without_retry_after_attribute_uses_default(self):
        """When exc.retry_after is not set, falls back to 60."""
        import json
        from backend.utils.rate_limit import rate_limit_exceeded_handler

        exc = MagicMock(spec=[])  # No attributes by default
        exc.detail = "10 per 1 minute"
        # spec=[] means getattr(exc, 'retry_after', 60) will use the default

        response = rate_limit_exceeded_handler(self._make_request(), exc)
        body = json.loads(response.body)
        assert body["retry_after_seconds"] == 60


class TestRateLimitDecorators:
    """Decorator factories return limiter decorators."""

    def test_auth_rate_limit_returns_callable(self):
        from backend.utils.rate_limit import auth_rate_limit
        decorator = auth_rate_limit()
        assert callable(decorator)

    def test_upload_rate_limit_returns_callable(self):
        from backend.utils.rate_limit import upload_rate_limit
        decorator = upload_rate_limit()
        assert callable(decorator)

    def test_default_rate_limit_returns_callable(self):
        from backend.utils.rate_limit import default_rate_limit
        decorator = default_rate_limit()
        assert callable(decorator)

    def test_no_rate_limit_returns_callable(self):
        from backend.utils.rate_limit import no_rate_limit
        decorator = no_rate_limit()
        assert callable(decorator)
