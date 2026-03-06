import json
import logging

logger = logging.getLogger(__name__)


def format_sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event payload."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def stream_chat_response(chunks):
    """Yield SSE chunks from an iterable/async iterable source."""
    try:
        for chunk in chunks:
            yield format_sse_event("token", {"content": chunk})
        yield format_sse_event("done", {"ok": True})
    except Exception as exc:
        logger.exception("SSE streaming error")
        yield format_sse_event("error", {"detail": str(exc)})
