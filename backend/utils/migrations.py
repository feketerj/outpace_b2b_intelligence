"""
Simple migration framework for MongoDB.
"""

import logging
from datetime import datetime, timezone
from typing import Callable, List, Dict

logger = logging.getLogger(__name__)


async def _migration_20260123_01(db):
    """Ensure tenant status and GDPR fields exist."""
    await db.tenants.update_many(
        {"status": {"$exists": False}},
        {"$set": {"status": "active"}}
    )
    await db.tenants.update_many(
        {"gdpr_exported_at": {"$exists": False}},
        {"$set": {"gdpr_exported_at": None}}
    )
    await db.tenants.update_many(
        {"gdpr_deleted_at": {"$exists": False}},
        {"$set": {"gdpr_deleted_at": None}}
    )


MIGRATIONS: List[Dict[str, Callable]] = [
    {
        "id": "20260123_01_tenant_status_gdpr_fields",
        "apply": _migration_20260123_01,
        "description": "Ensure tenant status and GDPR fields exist",
    }
]


async def run_migrations(db) -> None:
    """Run any pending migrations."""
    applied = await db.migrations.find({}, {"_id": 0, "id": 1}).to_list(length=None)
    applied_ids = {m["id"] for m in applied}

    for migration in MIGRATIONS:
        migration_id = migration["id"]
        if migration_id in applied_ids:
            continue
        logger.info(f"[migrations] Applying {migration_id}: {migration['description']}")
        await migration["apply"](db)
        await db.migrations.insert_one(
            {
                "id": migration_id,
                "description": migration["description"],
                "applied_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.info(f"[migrations] Applied {migration_id}")
