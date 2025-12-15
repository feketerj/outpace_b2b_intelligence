import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timezone
import uuid

from services.highergov_service import sync_highergov_opportunities
from services.perplexity_service import sync_perplexity_intelligence

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def start_scheduler(db):
    """Start the background scheduler for automated syncs"""
    logger.info("Starting automated sync scheduler...")
    
    # Daily sync at 2 AM UTC
    scheduler.add_job(
        lambda: asyncio.run(daily_sync_all_tenants(db)),
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_sync",
        name="Daily Data Sync",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started successfully")

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
    """Sync data for a single tenant"""
    tenant_id = tenant["id"]
    logger.info(f"Syncing data for tenant: {tenant['name']} ({tenant_id})")
    
    sync_start = datetime.now(timezone.utc)
    errors = []
    opp_count = 0
    intel_count = 0
    
    try:
        # Sync HigherGov opportunities
        try:
            opp_count = await sync_highergov_opportunities(db, tenant)
            logger.info(f"Synced {opp_count} opportunities from HigherGov for tenant {tenant_id}")
        except Exception as e:
            error_msg = f"HigherGov sync failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        
        # Sync Perplexity intelligence
        try:
            intel_count = await sync_perplexity_intelligence(db, tenant)
            logger.info(f"Synced {intel_count} intelligence items from Perplexity for tenant {tenant_id}")
        except Exception as e:
            error_msg = f"Perplexity sync failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
        
    except Exception as e:
        error_msg = f"General sync error: {str(e)}"
        errors.append(error_msg)
        logger.error(error_msg)
    
    # Calculate sync duration
    sync_end = datetime.now(timezone.utc)
    duration = (sync_end - sync_start).total_seconds()
    
    # Log sync results
    sync_log = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "sync_type": "automated",
        "sync_timestamp": sync_start.isoformat(),
        "records_fetched": opp_count + intel_count,
        "records_created": opp_count + intel_count,
        "records_updated": 0,
        "errors": errors,
        "sync_duration_seconds": duration,
        "status": "failed" if errors else "success"
    }
    
    await db.sync_logs.insert_one(sync_log)
    
    # Update tenant's last sync timestamp
    await db.tenants.update_one(
        {"id": tenant_id},
        {"$set": {"last_synced_at": sync_end.isoformat()}}
    )