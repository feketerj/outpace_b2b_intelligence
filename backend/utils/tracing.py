"""
Request tracing middleware with structured JSON logging for cloud environments.

Features:
- JSON-formatted logs to STDOUT (cloud-native, queryable)
- trace_id correlation across all log messages
- Optional file logging for local development
- Automatic trace_id injection in all log records

Usage:
    # In server.py:
    from backend.utils.tracing import TracingMiddleware, setup_traced_logging
    setup_traced_logging()
    app.add_middleware(TracingMiddleware)

    # In any route/service:
    from backend.utils.tracing import get_trace_id
    trace_id = get_trace_id()
    logger.info("Processing request", extra={"user_id": "123"})
"""

import uuid
import json
import sys
import os
import logging
from datetime import datetime, timezone
from contextvars import ContextVar
from typing import Any, Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variable to hold trace_id for the current request
_trace_id_var: ContextVar[str] = ContextVar('trace_id', default='no-trace')
_tenant_id_var: ContextVar[str] = ContextVar('tenant_id', default='')
_user_id_var: ContextVar[str] = ContextVar('user_id', default='')


def get_trace_id() -> str:
    """Get the current request's trace ID."""
    return _trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """Set the trace ID for the current context."""
    _trace_id_var.set(trace_id)


def set_context(tenant_id: str = '', user_id: str = '') -> None:
    """Set additional context for logging."""
    if tenant_id:
        _tenant_id_var.set(tenant_id)
    if user_id:
        _user_id_var.set(user_id)


class JSONLogFormatter(logging.Formatter):
    """
    Structured JSON log formatter for cloud log aggregation.

    Output format:
    {
        "timestamp": "2026-01-15T12:00:00.000Z",
        "level": "INFO",
        "logger": "backend.routes.auth",
        "message": "User login successful",
        "trace_id": "abc12345",
        "tenant_id": "tenant-uuid",
        "user_id": "user-uuid",
        "extra": {...}
    }
    """

    def format(self, record: logging.LogRecord) -> str:
        # Build the log entry
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, 'trace_id', get_trace_id()),
        }

        # Add tenant/user context if available
        tenant_id = getattr(record, 'tenant_id', None) or _tenant_id_var.get()
        user_id = getattr(record, 'user_id', None) or _user_id_var.get()

        if tenant_id:
            log_entry["tenant_id"] = tenant_id
        if user_id:
            log_entry["user_id"] = user_id

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info[2] else None
            }

        # Add any extra fields passed via extra={...}
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'trace_id', 'tenant_id', 'user_id', 'message', 'taskName'
        }
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in standard_attrs and not k.startswith('_')
        }
        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, default=str)


class TraceLogFilter(logging.Filter):
    """
    Log filter that adds trace_id and context to all log records.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        record.tenant_id = _tenant_id_var.get()
        record.user_id = _user_id_var.get()
        return True


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a trace_id to every request.

    - Checks for incoming X-Trace-ID header (for distributed tracing)
    - Generates a new ID if none provided
    - Adds trace_id to response headers
    - Stores trace_id in context for use in logging
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        logger = logging.getLogger(__name__)

        # Get trace_id from header or generate new one
        trace_id = request.headers.get("X-Trace-ID")
        if not trace_id:
            trace_id = str(uuid.uuid4())[:8]  # Short ID for readability

        # Store in context variable
        set_trace_id(trace_id)

        # Store in request state for route handlers
        request.state.trace_id = trace_id

        # Log request start with structured data
        logger.debug(
            "request_start",
            extra={
                "event": "request_start",
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else "unknown"
            }
        )

        try:
            response = await call_next(request)

            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id

            # Log request end with structured data
            logger.debug(
                "request_end",
                extra={
                    "event": "request_end",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                }
            )

            return response

        except Exception as e:
            logger.error(
                "request_error",
                extra={
                    "event": "request_error",
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise


def setup_traced_logging(log_level: int = logging.INFO) -> None:
    """
    Configure logging with trace_id injection.

    Cloud-native by default:
        - JSON-formatted logs to STDOUT (captured by Docker/K8s/CloudWatch)
        - File logging disabled by default (containers are ephemeral)

    Environment variables:
        - LOG_FORMAT: 'json' (default) or 'text' (human-readable for local dev)
        - LOG_TO_FILE: 'true' to enable file logging (for local dev only)

    Args:
        log_level: Minimum log level (default: INFO)
    """
    from logging.handlers import RotatingFileHandler
    from pathlib import Path

    # Check environment for format preference
    log_format_env = os.environ.get('LOG_FORMAT', 'json').lower()
    use_json = log_format_env == 'json'
    enable_file_logging = os.environ.get('LOG_TO_FILE', 'false').lower() == 'true'

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers = []

    # === PRIMARY: STDOUT handler (cloud-native) ===
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(TraceLogFilter())

    if use_json:
        stdout_handler.setFormatter(JSONLogFormatter())
    else:
        # Human-readable format for local development
        stdout_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - [trace=%(trace_id)s] - %(name)s - %(message)s'
        ))

    root_logger.addHandler(stdout_handler)

    # === OPTIONAL: File handlers (for local development only) ===
    if enable_file_logging:
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        # Main log file (always JSON for parseability)
        file_handler = RotatingFileHandler(
            log_dir / "server.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.addFilter(TraceLogFilter())
        file_handler.setFormatter(JSONLogFormatter())
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)

        # Error-only log file
        error_handler = RotatingFileHandler(
            log_dir / "errors.log",
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.addFilter(TraceLogFilter())
        error_handler.setFormatter(JSONLogFormatter())
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)

        logging.getLogger(__name__).info(
            "file_logging_enabled",
            extra={"log_dir": str(log_dir)}
        )
