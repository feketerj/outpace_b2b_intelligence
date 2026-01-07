"""
Request tracing middleware for correlating logs across operations.

Every request gets a trace_id that flows through all log messages,
making it easy to grep for all activity related to a single request.

Usage:
    # In main.py:
    from backend.utils.tracing import TracingMiddleware
    app.add_middleware(TracingMiddleware)

    # In any route/service:
    from backend.utils.tracing import get_trace_id
    trace_id = get_trace_id()
    logger.info(f"[trace={trace_id}] Processing request...")
"""

import uuid
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variable to hold trace_id for the current request
_trace_id_var: ContextVar[str] = ContextVar('trace_id', default='no-trace')


def get_trace_id() -> str:
    """Get the current request's trace ID."""
    return _trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    """Set the trace ID for the current context."""
    _trace_id_var.set(trace_id)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a trace_id to every request.

    - Checks for incoming X-Trace-ID header (for distributed tracing)
    - Generates a new ID if none provided
    - Adds trace_id to response headers
    - Stores trace_id in context for use in logging
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get trace_id from header or generate new one
        trace_id = request.headers.get("X-Trace-ID")
        if not trace_id:
            trace_id = str(uuid.uuid4())[:8]  # Short ID for readability

        # Store in context variable
        set_trace_id(trace_id)

        # Store in request state for route handlers
        request.state.trace_id = trace_id

        # Log request start
        logger.debug(
            f"[trace={trace_id}] REQUEST_START method={request.method} "
            f"path={request.url.path}"
        )

        try:
            response = await call_next(request)

            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id

            # Log request end
            logger.debug(
                f"[trace={trace_id}] REQUEST_END status={response.status_code}"
            )

            return response

        except Exception as e:
            logger.error(
                f"[trace={trace_id}] REQUEST_ERROR: {type(e).__name__}: {e}"
            )
            raise


class TraceLogFilter(logging.Filter):
    """
    Log filter that adds trace_id to all log records.

    Usage:
        handler = logging.StreamHandler()
        handler.addFilter(TraceLogFilter())
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [trace=%(trace_id)s] - %(message)s'
        ))
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


def setup_traced_logging(log_level: int = logging.INFO) -> None:
    """
    Configure logging to include trace_id in all messages.

    Call this at application startup.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Create handler with trace filter
    handler = logging.StreamHandler()
    handler.addFilter(TraceLogFilter())
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [trace=%(trace_id)s] - %(message)s'
    ))

    # Remove existing handlers and add traced one
    root_logger.handlers = []
    root_logger.addHandler(handler)
