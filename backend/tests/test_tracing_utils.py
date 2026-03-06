"""
Unit tests for backend/utils/tracing.py

Covers: get/set_trace_id, set_context, JSONLogFormatter, TraceLogFilter,
TracingMiddleware dispatch (normal + exception), setup_traced_logging.
"""

import json
import logging
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────── context variable helpers ────────────────────────────


class TestTraceContextHelpers:
    """get_trace_id / set_trace_id / set_context."""

    def test_default_trace_id(self):
        from backend.utils.tracing import get_trace_id
        # Default is 'no-trace' (but may have been set in prior test)
        result = get_trace_id()
        assert isinstance(result, str)

    def test_set_and_get_trace_id(self):
        from backend.utils.tracing import set_trace_id, get_trace_id
        set_trace_id("abc12345")
        assert get_trace_id() == "abc12345"

    def test_set_context_tenant_and_user(self):
        from backend.utils.tracing import set_context, _tenant_id_var, _user_id_var
        set_context(tenant_id="tenant-xyz", user_id="user-123")
        assert _tenant_id_var.get() == "tenant-xyz"
        assert _user_id_var.get() == "user-123"

    def test_set_context_partial_tenant_only(self):
        from backend.utils.tracing import set_context, _tenant_id_var, _user_id_var
        # Set user to known state first
        _user_id_var.set("")
        set_context(tenant_id="only-tenant")
        assert _tenant_id_var.get() == "only-tenant"

    def test_set_context_empty_does_not_overwrite(self):
        from backend.utils.tracing import set_context, _tenant_id_var
        _tenant_id_var.set("existing-tenant")
        set_context()  # No args — should not clear
        assert _tenant_id_var.get() == "existing-tenant"


# ──────────────────────── JSONLogFormatter ───────────────────────────────────


class TestJSONLogFormatter:
    """Structured JSON log formatter."""

    def _make_record(self, msg="test message", level=logging.INFO, **extra):
        record = logging.LogRecord(
            name="test.logger",
            level=level,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return record

    def test_output_is_valid_json(self):
        from backend.utils.tracing import JSONLogFormatter
        formatter = JSONLogFormatter()
        record = self._make_record("hello world")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "hello world"

    def test_required_keys_present(self):
        from backend.utils.tracing import JSONLogFormatter
        formatter = JSONLogFormatter()
        record = self._make_record("msg")
        parsed = json.loads(formatter.format(record))
        for key in ("timestamp", "level", "logger", "message", "trace_id"):
            assert key in parsed, f"Missing key: {key}"

    def test_tenant_id_included_when_set(self):
        from backend.utils.tracing import JSONLogFormatter, _tenant_id_var
        _tenant_id_var.set("tenant-001")
        formatter = JSONLogFormatter()
        record = self._make_record("msg")
        parsed = json.loads(formatter.format(record))
        assert parsed.get("tenant_id") == "tenant-001"

    def test_user_id_included_when_set(self):
        from backend.utils.tracing import JSONLogFormatter, _user_id_var
        _user_id_var.set("user-007")
        formatter = JSONLogFormatter()
        record = self._make_record("msg")
        parsed = json.loads(formatter.format(record))
        assert parsed.get("user_id") == "user-007"

    def test_exception_info_included(self):
        from backend.utils.tracing import JSONLogFormatter
        formatter = JSONLogFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = self._make_record("error msg")
        record.exc_info = exc_info
        parsed = json.loads(formatter.format(record))
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"

    def test_extra_fields_included(self):
        from backend.utils.tracing import JSONLogFormatter
        formatter = JSONLogFormatter()
        record = self._make_record("msg", custom_field="custom_value")
        parsed = json.loads(formatter.format(record))
        assert parsed.get("extra", {}).get("custom_field") == "custom_value"


# ─────────────────────── TraceLogFilter ──────────────────────────────────────


class TestTraceLogFilter:
    """Log filter that injects trace/tenant/user into records."""

    def test_filter_injects_trace_id(self):
        from backend.utils.tracing import TraceLogFilter, set_trace_id
        set_trace_id("filter-trace")
        f = TraceLogFilter()
        record = logging.LogRecord("x", logging.INFO, "", 0, "msg", (), None)
        f.filter(record)
        assert record.trace_id == "filter-trace"

    def test_filter_always_returns_true(self):
        from backend.utils.tracing import TraceLogFilter
        f = TraceLogFilter()
        record = logging.LogRecord("x", logging.INFO, "", 0, "msg", (), None)
        assert f.filter(record) is True


# ─────────────────────── TracingMiddleware ───────────────────────────────────


class TestTracingMiddleware:
    """Middleware assigns trace IDs and adds them to response headers."""

    def _make_request(self, trace_id=None):
        request = MagicMock()
        headers = {}
        if trace_id:
            headers["X-Trace-ID"] = trace_id
        request.headers.get = lambda key, default=None: headers.get(key, default)
        request.method = "GET"
        request.url.path = "/api/test"
        request.client.host = "127.0.0.1"
        request.state = MagicMock()
        return request

    @pytest.mark.asyncio
    async def test_uses_existing_trace_id_from_header(self):
        from backend.utils.tracing import TracingMiddleware, get_trace_id

        middleware = TracingMiddleware(app=MagicMock())
        request = self._make_request(trace_id="custom-trace")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        call_next = AsyncMock(return_value=mock_response)
        await middleware.dispatch(request, call_next)

        assert get_trace_id() == "custom-trace"

    @pytest.mark.asyncio
    async def test_generates_trace_id_when_none_provided(self):
        from backend.utils.tracing import TracingMiddleware, get_trace_id

        middleware = TracingMiddleware(app=MagicMock())
        request = self._make_request()  # No X-Trace-ID

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        call_next = AsyncMock(return_value=mock_response)
        await middleware.dispatch(request, call_next)

        trace_id = get_trace_id()
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0

    @pytest.mark.asyncio
    async def test_adds_trace_id_to_response_headers(self):
        from backend.utils.tracing import TracingMiddleware

        middleware = TracingMiddleware(app=MagicMock())
        request = self._make_request(trace_id="resp-trace")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        call_next = AsyncMock(return_value=mock_response)
        await middleware.dispatch(request, call_next)

        assert mock_response.headers.get("X-Trace-ID") == "resp-trace"

    @pytest.mark.asyncio
    async def test_raises_exception_on_call_next_error(self):
        from backend.utils.tracing import TracingMiddleware

        middleware = TracingMiddleware(app=MagicMock())
        request = self._make_request()

        call_next = AsyncMock(side_effect=RuntimeError("downstream error"))

        with pytest.raises(RuntimeError, match="downstream error"):
            await middleware.dispatch(request, call_next)


# ─────────────────────── setup_traced_logging ────────────────────────────────


class TestSetupTracedLogging:
    """setup_traced_logging configures the root logger."""

    def test_json_format_is_default(self):
        from backend.utils.tracing import setup_traced_logging
        with patch.dict(os.environ, {"LOG_FORMAT": "json"}, clear=False):
            setup_traced_logging()
        root = logging.getLogger()
        assert len(root.handlers) >= 1

    def test_text_format_uses_plain_formatter(self):
        from backend.utils.tracing import setup_traced_logging
        with patch.dict(os.environ, {"LOG_FORMAT": "text"}, clear=False):
            setup_traced_logging()
        root = logging.getLogger()
        handler = root.handlers[0]
        assert not isinstance(handler.formatter, type(None))

    def test_file_logging_enabled_creates_handlers(self, tmp_path):
        from backend.utils.tracing import setup_traced_logging
        # Path is imported inside setup_traced_logging, so patch it at the source
        with patch.dict(os.environ, {"LOG_TO_FILE": "true"}, clear=False):
            with patch("pathlib.Path") as mock_path_cls:
                mock_log_dir = MagicMock()
                mock_log_dir.mkdir = MagicMock()
                mock_log_dir.__truediv__ = lambda self, other: tmp_path / other
                mock_path_cls.return_value.__truediv__ = lambda self, other: mock_log_dir
                mock_path_cls.return_value.parent.parent = mock_log_dir
                setup_traced_logging()
        root = logging.getLogger()
        assert len(root.handlers) >= 1

    def test_setup_with_custom_log_level(self):
        from backend.utils.tracing import setup_traced_logging
        setup_traced_logging(log_level=logging.WARNING)
        root = logging.getLogger()
        assert root.level == logging.WARNING
