"""
External API usage tracking for cost monitoring and auditing.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from backend.database import get_database

logger = logging.getLogger(__name__)


def _month_key(timestamp: datetime) -> str:
    return timestamp.strftime("%Y-%m")


async def record_external_usage(
    db,
    tenant_id: str,
    service: str,
    operation: str,
    status: str,
    duration_ms: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    cost_usd: Optional[float] = None
) -> None:
    """
    Record external API usage for cost tracking and auditability.
    """
    try:
        if db is None:
            db = get_database()

        now = datetime.now(timezone.utc)
        month = _month_key(now)

        if cost_usd is None:
            env_key = f"COST_PER_CALL_{service.upper()}"
            try:
                cost_usd = float(os.environ.get(env_key, "0")) or None
            except ValueError:
                cost_usd = None

        usage_doc = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "service": service,
            "operation": operation,
            "status": status,
            "duration_ms": duration_ms,
            "cost_usd": cost_usd,
            "metadata": metadata or {},
            "timestamp": now.isoformat(),
        }

        await db.external_api_usage.insert_one(usage_doc)

        if cost_usd is not None:
            await db.tenant_costs.update_one(
                {"tenant_id": tenant_id, "month": month, "service": service},
                {
                    "$inc": {"cost_usd": cost_usd, "calls": 1},
                    "$setOnInsert": {"created_at": now.isoformat()}
                },
                upsert=True
            )
    except Exception as e:
        logger.warning(f"[usage] Failed to record external usage: {e}")
