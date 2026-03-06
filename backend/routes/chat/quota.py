from datetime import datetime, timezone
import logging
from fastapi import HTTPException, status
from pymongo import ReturnDocument

logger = logging.getLogger(__name__)


async def check_quota(tenant: dict) -> None:
    """CHAT-02 pre-check for tenant chat enabled policy."""
    chat_policy = tenant.get("chat_policy", {})
    if not chat_policy.get("enabled", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat not enabled for tenant")


async def increment_quota(db, tenant_id: str, monthly_limit):
    """Reserve one monthly message quota atomically with month reset support."""
    if monthly_limit is None:
        return False, None

    month_key = datetime.now(timezone.utc).strftime("%Y-%m")
    result = await db.tenants.find_one_and_update(
        {
            "id": tenant_id,
            "$or": [
                {"chat_usage": None},
                {"chat_usage": {"$exists": False}},
                {"chat_usage.month": {"$ne": month_key}},
                {"chat_usage.month": month_key, "chat_usage.messages_used": {"$lt": monthly_limit}},
            ],
        },
        [
            {
                "$set": {
                    "chat_usage": {
                        "$cond": {
                            "if": {
                                "$or": [
                                    {"$eq": [{"$type": "$chat_usage"}, "missing"]},
                                    {"$eq": ["$chat_usage", None]},
                                    {"$ne": ["$chat_usage.month", month_key]},
                                ]
                            },
                            "then": {"month": month_key, "messages_used": 1},
                            "else": {
                                "month": "$chat_usage.month",
                                "messages_used": {"$add": ["$chat_usage.messages_used", 1]},
                            },
                        }
                    }
                }
            }
        ],
        return_document=ReturnDocument.AFTER,
    )

    if not result:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Monthly chat limit exceeded")

    new_usage = result.get("chat_usage", {}).get("messages_used", 0)
    logger.info("[quota] Atomic reservation for tenant %s: month=%s, usage=%s/%s", tenant_id, month_key, new_usage, monthly_limit)
    return True, month_key


async def release_quota(db, tenant_id: str, quota_reserved: bool, monthly_limit) -> None:
    """Release reserved quota on failure (best-effort)."""
    if quota_reserved and monthly_limit is not None:
        try:
            result = await db.tenants.update_one(
                {"id": tenant_id, "chat_usage.messages_used": {"$gt": 0}},
                {"$inc": {"chat_usage.messages_used": -1}},
            )
            if result.modified_count == 0:
                logger.warning("[quota] Release attempted but no update for tenant %s", tenant_id)
            else:
                logger.info("[quota] Released reservation for tenant %s", tenant_id)
        except Exception as release_err:
            logger.warning("[quota] Failed to release reservation: %s", release_err)
