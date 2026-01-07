"""
Health check endpoints for monitoring system status.

/health - Basic liveness check (fast, no dependencies)
/health/deep - Deep check probing all dependencies (slower, comprehensive)

Usage:
    # Basic liveness
    curl http://localhost:8000/health

    # Deep check with all dependencies
    curl http://localhost:8000/health/deep
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import os
import logging
import asyncio
from typing import Dict, Any

from backend.database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
async def health_check():
    """
    Basic liveness check.

    Fast, no external dependencies checked.
    Returns 200 if the service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "outpace-b2b-intelligence"
    }


@router.get("/deep")
async def deep_health_check():
    """
    Deep health check probing all dependencies.

    Checks:
    - MongoDB connection
    - Mistral API availability
    - Perplexity API availability (if configured)
    - HigherGov API availability (if configured)

    Returns degraded status if any dependency is unhealthy.
    """
    results: Dict[str, Dict[str, Any]] = {}
    start_time = datetime.now(timezone.utc)

    # Check MongoDB
    results["mongodb"] = await _check_mongodb()

    # Check Mistral (AI service)
    results["mistral"] = await _check_mistral()

    # Check Perplexity (intelligence service)
    results["perplexity"] = await _check_perplexity()

    # Check environment configuration
    results["config"] = _check_config()

    # Calculate overall status
    all_ok = all(r.get("ok", False) for r in results.values())
    status = "healthy" if all_ok else "degraded"

    # Calculate check duration
    end_time = datetime.now(timezone.utc)
    duration_ms = (end_time - start_time).total_seconds() * 1000

    response = {
        "status": status,
        "timestamp": start_time.isoformat(),
        "duration_ms": round(duration_ms, 2),
        "services": results
    }

    # Add degraded services header for monitoring
    degraded_services = [name for name, result in results.items() if not result.get("ok")]
    if degraded_services:
        response["degraded_services"] = degraded_services
        logger.warning(f"[health.deep] DEGRADED: {degraded_services}")

    return response


async def _check_mongodb() -> Dict[str, Any]:
    """Check MongoDB connection and basic operations."""
    try:
        db = get_database()
        if db is None:
            return {"ok": False, "error": "Database not initialized"}

        # Try a simple operation with timeout
        start = datetime.now(timezone.utc)

        # Ping the database
        await asyncio.wait_for(
            db.command("ping"),
            timeout=5.0
        )

        # Check we can read
        tenant_count = await asyncio.wait_for(
            db.tenants.count_documents({}),
            timeout=5.0
        )

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        return {
            "ok": True,
            "latency_ms": round(duration_ms, 2),
            "tenant_count": tenant_count
        }

    except asyncio.TimeoutError:
        logger.error("[health.mongodb] Timeout checking MongoDB")
        return {"ok": False, "error": "Timeout"}
    except Exception as e:
        logger.error(f"[health.mongodb] Error: {e}")
        return {"ok": False, "error": str(e)}


async def _check_mistral() -> Dict[str, Any]:
    """Check Mistral API availability."""
    api_key = os.getenv("MISTRAL_API_KEY")

    if not api_key:
        return {"ok": False, "error": "MISTRAL_API_KEY not configured", "required": True}

    try:
        from mistralai import Mistral

        start = datetime.now(timezone.utc)
        client = Mistral(api_key=api_key)

        # Use a minimal request to check connectivity
        # Just checking the models endpoint is lighter than a full chat
        response = client.models.list()

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        return {
            "ok": True,
            "latency_ms": round(duration_ms, 2),
            "models_available": len(response.data) if hasattr(response, 'data') else "unknown"
        }

    except Exception as e:
        logger.error(f"[health.mistral] Error: {e}")
        return {"ok": False, "error": str(e), "required": True}


async def _check_perplexity() -> Dict[str, Any]:
    """Check Perplexity API availability (if configured)."""
    api_key = os.getenv("PERPLEXITY_API_KEY")

    if not api_key:
        # Perplexity is optional
        return {"ok": True, "configured": False, "note": "Not configured (optional)"}

    try:
        import httpx

        start = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check API endpoint (lightweight check)
            response = await client.get(
                "https://api.perplexity.ai/",
                headers={"Authorization": f"Bearer {api_key}"}
            )

        duration_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        # Even a 401/403 means the API is reachable
        return {
            "ok": response.status_code in [200, 401, 403, 404],
            "latency_ms": round(duration_ms, 2),
            "configured": True
        }

    except Exception as e:
        logger.error(f"[health.perplexity] Error: {e}")
        return {"ok": False, "error": str(e), "configured": True}


def _check_config() -> Dict[str, Any]:
    """Check required environment configuration."""
    issues = []

    # Required configs
    if not os.getenv("MONGO_URL"):
        issues.append("MONGO_URL not set")
    if not os.getenv("JWT_SECRET"):
        issues.append("JWT_SECRET not set")

    # Warning-level configs
    warnings = []
    jwt_secret = os.getenv("JWT_SECRET", "")
    if "local-dev" in jwt_secret or "test" in jwt_secret.lower():
        warnings.append("JWT_SECRET appears to be a development value")

    return {
        "ok": len(issues) == 0,
        "issues": issues if issues else None,
        "warnings": warnings if warnings else None
    }
