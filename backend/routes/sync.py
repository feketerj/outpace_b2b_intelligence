from fastapi import APIRouter, HTTPException, status, Depends, Body
from typing import Dict, Any
import logging
from datetime import datetime, timezone

from backend.utils.auth import get_current_user, get_current_super_admin, TokenData
from backend.database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

@router.post("/manual/{tenant_id}")
async def manual_sync_tenant(
    tenant_id: str,
    sync_type: str = "all",  # "all", "opportunities", "intelligence"
    current_user: TokenData = Depends(get_current_super_admin)
):
    """
    Manually trigger data sync for a tenant.
    Super admin only.
    
    sync_type: "all" (both), "opportunities" (HigherGov only), "intelligence" (Perplexity only)
    """
    db = get_db()
    
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Import here to avoid circular dependency
    from services.highergov_service import sync_highergov_opportunities
    from services.perplexity_service import sync_perplexity_intelligence
    
    results = {
        "tenant_id": tenant_id,
        "tenant_name": tenant["name"],
        "sync_timestamp": datetime.now(timezone.utc).isoformat(),
        "opportunities_synced": 0,
        "intelligence_synced": 0,
        "errors": []
    }
    
    try:
        # Sync opportunities
        if sync_type in ["all", "opportunities"]:
            try:
                opp_count = await sync_highergov_opportunities(db, tenant)
                results["opportunities_synced"] = opp_count
                logger.info(f"Manual sync: {opp_count} opportunities for {tenant['name']}")
            except Exception as e:
                error_msg = f"HigherGov sync failed: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
        
        # Sync intelligence
        if sync_type in ["all", "intelligence"]:
            try:
                intel_count = await sync_perplexity_intelligence(db, tenant)
                results["intelligence_synced"] = intel_count
                logger.info(f"Manual sync: {intel_count} intelligence items for {tenant['name']}")
            except Exception as e:
                error_msg = f"Perplexity sync failed: {str(e)}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
        
        # Update last sync timestamp
        await db.tenants.update_one(
            {"id": tenant_id},
            {"$set": {"last_synced_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        results["status"] = "success" if not results["errors"] else "partial"
        return results
        
    except Exception as e:
        logger.error(f"Manual sync failed for tenant {tenant_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )

@router.post("/opportunity/{tenant_id}")
async def fetch_opportunity_by_id(
    tenant_id: str,
    opportunity_data: dict = Body(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Fetch a single opportunity from HigherGov by opportunity ID.
    For manual entry of specific opportunity numbers.
    Expects: {"opportunity_id": "12345"}
    """
    db = get_db()
    
    # Access control
    if current_user.role != "super_admin" and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    opportunity_id = opportunity_data.get("opportunity_id")
    if not opportunity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="opportunity_id required"
        )
    
    from services.highergov_service import fetch_single_opportunity
    
    try:
        opp_data = await fetch_single_opportunity(db, tenant, opportunity_id)
        return {
            "status": "success",
            "opportunity": opp_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch opportunity: {str(e)}"
        )
async def get_sync_status(
    tenant_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get last sync status and schedule for a tenant"""
    db = get_db()
    
    # Access control
    if current_user.role != "super_admin" and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Get latest sync log
    latest_sync = await db.sync_logs.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0}
    )
    
    search_profile = tenant.get("search_profile", {})
    intel_config = tenant.get("intelligence_config", {})
    
    return {
        "tenant_id": tenant_id,
        "last_synced_at": tenant.get("last_synced_at"),
        "auto_update_enabled": search_profile.get("auto_update_enabled", True),
        "auto_update_interval_hours": search_profile.get("auto_update_interval_hours", 24),
        "intelligence_schedule": intel_config.get("schedule_cron", "0 2 * * *"),
        "latest_sync": latest_sync
    }
