"""
Data retention utilities for GDPR and operational hygiene.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


def _parse_days(env_key: str) -> Optional[int]:
    value = os.environ.get(env_key)
    if not value:
        return None
    try:
        days = int(value)
        return days if days > 0 else None
    except ValueError:
        logger.warning(f"[retention] Invalid value for {env_key}: {value}")
        return None


async def apply_retention_policies(db) -> Dict[str, int]:
    """
    Apply retention policies to configured collections.
    """
    now = datetime.now(timezone.utc)
    policies: List[tuple] = [
        ("chat_messages", _parse_days("RETENTION_DAYS_CHAT_MESSAGES"), "created_at"),
        ("chat_turns", _parse_days("RETENTION_DAYS_CHAT_TURNS"), "created_at"),
        ("sync_logs", _parse_days("RETENTION_DAYS_SYNC_LOGS"), "sync_timestamp"),
        ("intelligence", _parse_days("RETENTION_DAYS_INTELLIGENCE"), "created_at"),
        ("opportunities", _parse_days("RETENTION_DAYS_OPPORTUNITIES"), "created_at"),
    ]

    results: Dict[str, int] = {}
    for collection, days, field in policies:
        if not days:
            continue
        cutoff = (now - timedelta(days=days)).isoformat()
        result = await db[collection].delete_many({field: {"$lt": cutoff}})
        results[collection] = result.deleted_count
        logger.info(f"[retention] Deleted {result.deleted_count} from {collection} (>{days} days)")

    return results
