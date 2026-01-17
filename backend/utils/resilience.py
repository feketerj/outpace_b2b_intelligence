"""
Resilience utilities for external API calls.
Provides retry logic with exponential backoff and circuit breaker pattern.
"""

import logging
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    before_sleep_log
)
import asyncio
from functools import wraps

logger = logging.getLogger(__name__)

# Retry configuration for HTTP calls
def _is_retryable_http_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code if exc.response else None
        return status_code == 429 or (status_code is not None and status_code >= 500)
    return False


async def _respect_retry_after(response: httpx.Response) -> None:
    retry_after = response.headers.get("Retry-After")
    if not retry_after:
        return
    try:
        delay = float(retry_after)
        # Safety cap to avoid long stalls
        delay = min(delay, 30.0)
        if delay > 0:
            await asyncio.sleep(delay)
    except ValueError:
        return


retry_on_http = retry_if_exception(_is_retryable_http_error)

RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type((
        httpx.TimeoutException,
        httpx.NetworkError,
        httpx.ConnectError,
    )) | retry_on_http,
    "before_sleep": before_sleep_log(logger, logging.WARNING),
    "reraise": True
}


def with_retry(func):
    """
    Decorator to add retry logic to async functions.
    Retries on network errors with exponential backoff.
    """
    @wraps(func)
    @retry(**RETRY_CONFIG)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper


class RetryableClient:
    """
    HTTP client wrapper with built-in retry logic.
    Use for external API calls that should retry on transient failures.
    """

    def __init__(self, timeout: float = 30.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    @retry(**RETRY_CONFIG)
    async def get(self, url: str, **kwargs) -> httpx.Response:
        """GET request with retry logic."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, **kwargs)
            if response.status_code == 429:
                logger.warning(f"Rate limited (429) for {url}, will retry")
                await _respect_retry_after(response)
                raise httpx.HTTPStatusError(
                    "Rate limited (429)",
                    request=response.request,
                    response=response
                )
            # Retry on 5xx errors too
            if response.status_code >= 500:
                logger.warning(f"Server error {response.status_code} for {url}, will retry")
                raise httpx.HTTPStatusError(
                    f"Server error {response.status_code}",
                    request=response.request,
                    response=response
                )
            return response

    @retry(**RETRY_CONFIG)
    async def post(self, url: str, **kwargs) -> httpx.Response:
        """POST request with retry logic."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, **kwargs)
            if response.status_code == 429:
                logger.warning(f"Rate limited (429) for {url}, will retry")
                await _respect_retry_after(response)
                raise httpx.HTTPStatusError(
                    "Rate limited (429)",
                    request=response.request,
                    response=response
                )
            # Retry on 5xx errors too
            if response.status_code >= 500:
                logger.warning(f"Server error {response.status_code} for {url}, will retry")
                raise httpx.HTTPStatusError(
                    f"Server error {response.status_code}",
                    request=response.request,
                    response=response
                )
            return response


# Simple circuit breaker state (in-memory, per-service)
_circuit_state = {}

class CircuitBreaker:
    """
    Simple circuit breaker implementation.
    Opens after failure_threshold consecutive failures.
    Allows retry after recovery_timeout seconds.
    """

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        if name not in _circuit_state:
            _circuit_state[name] = {
                "failures": 0,
                "last_failure": None,
                "state": "closed"  # closed = healthy, open = failing
            }

    @property
    def state(self):
        return _circuit_state[self.name]

    def is_open(self) -> bool:
        """Check if circuit is open (should reject calls)."""
        import time

        if self.state["state"] == "closed":
            return False

        # Check if recovery timeout has passed
        if self.state["last_failure"]:
            elapsed = time.time() - self.state["last_failure"]
            if elapsed > self.recovery_timeout:
                logger.info(f"[circuit:{self.name}] Recovery timeout passed, allowing retry")
                self.state["state"] = "half-open"
                return False

        return True

    def record_success(self):
        """Record a successful call."""
        self.state["failures"] = 0
        self.state["state"] = "closed"
        logger.debug(f"[circuit:{self.name}] Success recorded, circuit closed")

    def record_failure(self):
        """Record a failed call."""
        import time

        self.state["failures"] += 1
        self.state["last_failure"] = time.time()

        if self.state["failures"] >= self.failure_threshold:
            self.state["state"] = "open"
            logger.warning(
                f"[circuit:{self.name}] Circuit OPEN after {self.state['failures']} failures. "
                f"Will retry after {self.recovery_timeout}s"
            )


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


def circuit_protected(circuit: CircuitBreaker):
    """
    Decorator to protect a function with circuit breaker.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if circuit.is_open():
                raise CircuitOpenError(
                    f"Circuit '{circuit.name}' is open. Service unavailable."
                )

            try:
                result = await func(*args, **kwargs)
                circuit.record_success()
                return result
            except Exception as e:
                circuit.record_failure()
                raise

        return wrapper
    return decorator


# Pre-configured circuit breakers for each external service
highergov_circuit = CircuitBreaker("highergov", failure_threshold=5, recovery_timeout=60)
perplexity_circuit = CircuitBreaker("perplexity", failure_threshold=5, recovery_timeout=60)
mistral_circuit = CircuitBreaker("mistral", failure_threshold=5, recovery_timeout=60)
