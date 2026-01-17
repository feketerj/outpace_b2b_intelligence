"""
OpenTelemetry instrumentation for APM/observability.

This module provides optional telemetry integration that can be enabled
via environment variables. When disabled (default), it's a no-op.

Supported backends via OTLP:
- Google Cloud Trace (GCP)
- Datadog
- New Relic
- Jaeger
- Any OTLP-compatible collector

Configuration:
    OTEL_ENABLED=true                          # Enable telemetry
    OTEL_SERVICE_NAME=outpace-api              # Service name in traces
    OTEL_EXPORTER_OTLP_ENDPOINT=http://...     # OTLP collector endpoint
    OTEL_TRACES_SAMPLER_ARG=1.0                # Sampling ratio (0.0-1.0)

Usage (in server.py):
    from backend.utils.telemetry import setup_telemetry
    
    app = FastAPI(...)
    setup_telemetry(app)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def is_telemetry_enabled() -> bool:
    """Check if OpenTelemetry is enabled via environment."""
    return os.environ.get("OTEL_ENABLED", "false").lower() in ("true", "1", "yes")


def setup_telemetry(app) -> bool:
    """
    Initialize OpenTelemetry instrumentation if enabled.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        True if telemetry was initialized, False otherwise
    """
    if not is_telemetry_enabled():
        logger.info("[telemetry] OpenTelemetry disabled (set OTEL_ENABLED=true to enable)")
        return False
    
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except ImportError as e:
        logger.warning(f"[telemetry] OpenTelemetry packages not installed: {e}")
        logger.warning("[telemetry] Run: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-httpx opentelemetry-instrumentation-logging")
        return False
    
    # Get configuration from environment
    service_name = os.environ.get("OTEL_SERVICE_NAME", "outpace-api")
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    sampling_ratio = float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0"))
    
    if not otlp_endpoint:
        logger.warning("[telemetry] OTEL_EXPORTER_OTLP_ENDPOINT not set, telemetry disabled")
        return False
    
    try:
        # Create resource with service name
        resource = Resource.create({
            SERVICE_NAME: service_name,
            "deployment.environment": os.environ.get("ENV", "development"),
        })
        
        # Create sampler
        sampler = TraceIdRatioBased(sampling_ratio)
        
        # Create tracer provider
        provider = TracerProvider(resource=resource, sampler=sampler)
        
        # Create OTLP exporter
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        
        # Add batch processor
        provider.add_span_processor(BatchSpanProcessor(exporter))
        
        # Set as global tracer provider
        trace.set_tracer_provider(provider)
        
        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(app)
        
        # Instrument httpx (for external API calls)
        HTTPXClientInstrumentor().instrument()
        
        # Instrument logging (adds trace context to logs)
        LoggingInstrumentor().instrument(set_logging_format=True)
        
        logger.info(
            f"[telemetry] OpenTelemetry initialized: "
            f"service={service_name}, endpoint={otlp_endpoint}, sampling={sampling_ratio}"
        )
        return True
        
    except Exception as e:
        logger.error(f"[telemetry] Failed to initialize OpenTelemetry: {e}")
        return False


def get_current_span():
    """
    Get the current active span for adding custom attributes.
    
    Returns None if telemetry is disabled.
    
    Usage:
        span = get_current_span()
        if span:
            span.set_attribute("user.id", user_id)
            span.set_attribute("tenant.id", tenant_id)
    """
    if not is_telemetry_enabled():
        return None
    
    try:
        from opentelemetry import trace
        return trace.get_current_span()
    except ImportError:
        return None


def add_span_attributes(**attributes) -> None:
    """
    Add custom attributes to the current span.
    
    No-op if telemetry is disabled.
    
    Usage:
        add_span_attributes(user_id="123", tenant_id="456")
    """
    span = get_current_span()
    if span:
        for key, value in attributes.items():
            span.set_attribute(key, str(value) if value is not None else "")


def record_exception(exception: Exception, **attributes) -> None:
    """
    Record an exception in the current span.
    
    No-op if telemetry is disabled.
    
    Usage:
        try:
            risky_operation()
        except Exception as e:
            record_exception(e, operation="risky_operation")
            raise
    """
    span = get_current_span()
    if span:
        span.record_exception(exception, attributes=attributes)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))
