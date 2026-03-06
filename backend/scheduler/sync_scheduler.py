import asyncio
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone
import uuid

from backend.services.highergov_service import sync_highergov_opportunities
from backend.services.perplexity_service import sync_perplexity_intelligence
from backend.utils.retention import apply_retention_policies

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

_SYNC_MAX_ATTEMPTS = 3
_SYNC_RETRY_BASE_DELAY = 2  # seconds


async def _sync_with_retry(label: str, coro_factory, tenant_id: str, db):
    """
    Run an async coroutine with up to _SYNC_MAX_ATTEMPTS retries and exponential
    backoff.  Returns (result, None) on success or (None, last_exc) on exhaustion.
    Dead-letter records are written to the ``sync_failures`` collection on every
    failed attempt so that operators can diagnose and replay.
    """
    last_exc = None
    for attempt in range(1, _SYNC_MAX_ATTEMPTS + 1):
        attempt_start = datetime.now(timezone.utc)
        try:
            result = await coro_factory()
            logger.info(
                "[sync_scheduler] %s succeeded on attempt %d/%d tenant_id=%s",
                label, attempt, _SYNC_MAX_ATTEMPTS, tenant_id,
            )
            return result, None
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "[sync_scheduler] %s attempt %d/%d failed tenant_id=%s error=%s",
                label, attempt, _SYNC_MAX_ATTEMPTS, tenant_id, exc,
            )
            attempt_end = datetime.now(timezone.utc)
            duration_ms = int((attempt_end - attempt_start).total_seconds() * 1000)

            # Dead-letter: record every failed attempt for later inspection/replay
            failure_record = {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "sync_type": label,
                "attempt": attempt,
                "max_attempts": _SYNC_MAX_ATTEMPTS,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "failed_at": attempt_end.isoformat(),
                "duration_ms": duration_ms,
            }
            try:
                await db.sync_failures.insert_one(failure_record)
            except Exception as db_exc:
                logger.error(
                    "[sync_scheduler] Failed to write dead-letter record tenant_id=%s error=%s",
                    tenant_id, db_exc,
                )

            if attempt < _SYNC_MAX_ATTEMPTS:
                delay = _SYNC_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info(
                    "[sync_scheduler] Retrying %s in %ss tenant_id=%s",
                    label, delay, tenant_id,
                )
                await asyncio.sleep(delay)

    logger.error(
        "[sync_scheduler] %s exhausted all %d attempts tenant_id=%s last_error=%s",
        label, _SYNC_MAX_ATTEMPTS, tenant_id, last_exc,
    )
    return None, last_exc

def start_scheduler(db):
    """Start the background scheduler for automated syncs"""
    logger.info("Starting automated sync scheduler...")
    
    # Default daily sync at 2 AM UTC for tenants without custom schedule
    scheduler.add_job(
        lambda: asyncio.run(daily_sync_all_tenants(db)),
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_sync_default",
        name="Daily Data Sync (Default)",
        replace_existing=True
    )

    if os.environ.get("RETENTION_ENABLED", "false").lower() == "true":
        retention_cron = os.environ.get("RETENTION_CRON", "0 3 * * *")
        parts = retention_cron.split()
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
            scheduler.add_job(
                lambda: asyncio.run(apply_retention_policies(db)),
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week
                ),
                id="data_retention_job",
                name="Data Retention Cleanup",
                replace_existing=True
            )
            logger.info(f"Retention job scheduled: {retention_cron}")
        else:
            logger.warning(f"Invalid RETENTION_CRON format: {retention_cron}")
    
    # Note: Per-tenant custom schedules will be loaded on first sync
    # Cannot use asyncio.run() here as we're in an event loop
    
    scheduler.start()
    logger.info("Scheduler started successfully")

async def setup_tenant_schedules(db):
    """Set up individual schedules for tenants with custom intelligence config"""
    tenants_cursor = db.tenants.find({"status": "active"}, {"_id": 0})
    tenants = await tenants_cursor.to_list(length=None)
    
    for tenant in tenants:
        intel_config = tenant.get("intelligence_config", {})
        schedule_cron = intel_config.get("schedule_cron")
        
        # Only add custom schedule if different from default
        if schedule_cron and schedule_cron != "0 2 * * *":
            tenant_id = tenant["id"]
            tenant_name = tenant["name"]
            
            try:
                # Parse cron expression
                parts = schedule_cron.split()
                if len(parts) == 5:
                    minute, hour, day, month, day_of_week = parts
                    
                    scheduler.add_job(
                        lambda tid=tenant_id: asyncio.run(sync_single_tenant_by_id(db, tid)),
                        trigger=CronTrigger(
                            minute=minute,
                            hour=hour,
                            day=day,
                            month=month,
                            day_of_week=day_of_week
                        ),
                        id=f"sync_tenant_{tenant_id}",
                        name=f"Custom Sync: {tenant_name}",
                        replace_existing=True
                    )
                    logger.info(f"Added custom schedule for {tenant_name}: {schedule_cron}")
            except Exception as e:
                logger.error(f"Failed to parse cron schedule '{schedule_cron}' for tenant {tenant_name}: {e}")

async def sync_single_tenant_by_id(db, tenant_id: str):
    """Sync a single tenant by ID (for custom schedules)"""
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if tenant:
        await sync_tenant_data(db, tenant)

def stop_scheduler():
    """Stop the background scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")

async def daily_sync_all_tenants(db):
    """Execute daily sync for all active tenants"""
    logger.info("Starting daily sync for all tenants...")
    
    try:
        # Get all active tenants
        tenants_cursor = db.tenants.find({"status": "active"}, {"_id": 0})
        tenants = await tenants_cursor.to_list(length=None)
        
        logger.info(f"Found {len(tenants)} active tenants to sync")
        
        # Sync each tenant (with rate limiting)
        for tenant in tenants:
            try:
                await sync_tenant_data(db, tenant)
                # Brief delay between tenants to avoid API rate limits
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error syncing tenant {tenant['id']}: {e}")
        
        logger.info("Daily sync completed successfully")
    except Exception as e:
        logger.error(f"Error in daily sync: {e}")

async def sync_tenant_data(db, tenant: dict):
    """Sync data for a single tenant with retry logic and dead-letter logging."""
    tenant_id = tenant["id"]
    logger.info(
        "[sync_scheduler] Starting sync tenant_id=%s name=%s",
        tenant_id, tenant["name"],
    )

    sync_start = datetime.now(timezone.utc)
    errors = []
    opp_count = 0
    intel_count = 0

    # Sync HigherGov opportunities — with retry + dead-letter
    result, exc = await _sync_with_retry(
        label="highergov",
        coro_factory=lambda: sync_highergov_opportunities(db, tenant),
        tenant_id=tenant_id,
        db=db,
    )
    if exc is None:
        opp_count = result or 0
    else:
        errors.append(f"HigherGov sync failed: {exc}")

    # Sync Perplexity intelligence — with retry + dead-letter
    result, exc = await _sync_with_retry(
        label="perplexity",
        coro_factory=lambda: sync_perplexity_intelligence(db, tenant),
        tenant_id=tenant_id,
        db=db,
    )
    if exc is None:
        intel_count = result or 0
    else:
        errors.append(f"Perplexity sync failed: {exc}")

    # Calculate sync duration
    sync_end = datetime.now(timezone.utc)
    duration_ms = int((sync_end - sync_start).total_seconds() * 1000)
    duration_seconds = duration_ms / 1000.0
    sync_result = "failed" if errors else "success"

    # Structured observability log
    logger.info(
        "[sync_scheduler] sync_complete tenant_id=%s sync_type=automated "
        "result=%s duration_ms=%d opp_count=%d intel_count=%d errors=%s",
        tenant_id, sync_result, duration_ms, opp_count, intel_count, errors,
    )

    # Persist sync log
    sync_log = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "sync_type": "automated",
        "sync_timestamp": sync_start.isoformat(),
        "end_time": sync_end.isoformat(),
        "duration_ms": duration_ms,
        "records_fetched": opp_count + intel_count,
        "records_created": opp_count + intel_count,
        "records_updated": 0,
        "errors": errors,
        "sync_duration_seconds": duration_seconds,
        "status": sync_result,
    }
    await db.sync_logs.insert_one(sync_log)

    # Update tenant's last sync timestamp
    await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": {"last_synced_at": sync_end.isoformat()}},
    )

    return {
        "opportunities_synced": opp_count,
        "intelligence_synced": intel_count,
        "errors": errors,
        "duration_seconds": duration_seconds,
    }