from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any
import logging
from datetime import datetime, timezone

from utils.auth import get_current_super_admin, TokenData
from server import db as get_db

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/dashboard")
async def get_admin_dashboard(
    current_user: TokenData = Depends(get_current_super_admin)
) -> Dict[str, Any]:
    """Get system-wide dashboard statistics"""
    db = get_db()
    
    # Get counts
    total_tenants = await db.tenants.count_documents({})
    active_tenants = await db.tenants.count_documents({"status": "active"})
    total_users = await db.users.count_documents({})
    total_opportunities = await db.opportunities.count_documents({})
    total_intelligence = await db.intelligence.count_documents({})
    
    # Get recent sync logs
    recent_syncs_cursor = db.sync_logs.find({}, {"_id": 0}).sort("sync_timestamp", -1).limit(10)
    recent_syncs = await recent_syncs_cursor.to_list(length=10)
    
    # Get tenants with high API usage
    high_usage_pipeline = [
        {"$match": {"rate_limit_used": {"$gt": 400}}},
        {"$project": {
            "_id": 0,
            "id": 1,
            "name": 1,
            "rate_limit_used": 1,
            "rate_limit_monthly": 1
        }},
        {"$limit": 5}
    ]
    high_usage = await db.tenants.aggregate(high_usage_pipeline).to_list(length=5)
    
    return {
        "summary": {
            "total_tenants": total_tenants,
            "active_tenants": active_tenants,
            "total_users": total_users,
            "total_opportunities": total_opportunities,
            "total_intelligence": total_intelligence
        },
        "recent_syncs": recent_syncs,
        "high_usage_tenants": high_usage,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/sync/{tenant_id}")
async def trigger_manual_sync(
    tenant_id: str,
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Manually trigger data sync for a tenant"""
    db = get_db()
    
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Import here to avoid circular dependency
    from scheduler.sync_scheduler import sync_tenant_data
    
    try:
        await sync_tenant_data(db, tenant)
        return {"status": "success", "message": "Sync triggered successfully"}
    except Exception as e:
        logger.error(f"Manual sync failed for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )

@router.get("/system/health")
async def check_system_health(
    current_user: TokenData = Depends(get_current_super_admin)
):
    """Check system health status"""
    db = get_db()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "healthy",
            "scheduler": "healthy"
        }
    }
    
    # Check database connection
    try:
        await db.command("ping")
    except Exception as e:
        health_status["services"]["database"] = "unhealthy"
        health_status["status"] = "degraded"
    
    return health_status