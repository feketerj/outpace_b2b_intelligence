from fastapi import APIRouter, HTTPException, status, Depends, Body
from typing import Dict, Any
import logging
from datetime import datetime, timezone

from utils.auth import get_current_super_admin, get_current_tenant_admin, TokenData
from database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()

@router.put("/tenants/{tenant_id}/intelligence-config")
async def update_intelligence_config(
    tenant_id: str,
    config_data: Dict[str, Any] = Body(...),
    current_user: TokenData = Depends(get_current_tenant_admin)
):
    """
    Update intelligence configuration for a tenant.
    
    Supports:
    - Custom Perplexity prompt templates
    - Custom sync schedules (cron expressions)
    - Lookback window and deadline configurations
    - Enable/disable intelligence generation
    
    Example config_data:
    {
        "enabled": true,
        "perplexity_prompt_template": "Your custom prompt with {{COMPANY_NAME}} variables...",
        "schedule_cron": "0 6 * * *",  # Daily at 6 AM UTC
        "lookback_days": 14,
        "deadline_window_days": 120,
        "target_sources": ["site:maritime.dot.gov", "site:grants.gov"],
        "scoring_weights": {
            "relevance": 25,
            "amount": 20,
            "timeline": 15,
            "win_probability": 15,
            "strategic_fit": 15,
            "partner_potential": 10
        }
    }
    """
    db = get_db()
    
    # Access control
    if current_user.role != "super_admin" and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Validate tenant exists
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Validate cron expression if provided
    if "schedule_cron" in config_data:
        cron = config_data["schedule_cron"]
        if cron and len(cron.split()) != 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression. Must be in format: 'minute hour day month day_of_week'"
            )
    
    # Update intelligence_config
    existing_config = tenant.get("intelligence_config", {})
    updated_config = {**existing_config, **config_data}
    updated_config["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.tenants.update_one(
        {"id": tenant_id},
        {
            "$set": {
                "intelligence_config": updated_config,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    # If schedule changed, reload scheduler
    if "schedule_cron" in config_data:
        try:
            from scheduler.sync_scheduler import scheduler, setup_tenant_schedules
            import asyncio
            
            # Reload tenant schedules
            asyncio.create_task(setup_tenant_schedules(db))
            logger.info(f"Reloaded schedules after updating tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to reload schedules: {e}")
    
    return {
        "status": "success",
        "message": "Intelligence configuration updated",
        "config": updated_config
    }

@router.get("/tenants/{tenant_id}/intelligence-config")
async def get_intelligence_config(
    tenant_id: str,
    current_user: TokenData = Depends(get_current_tenant_admin)
):
    """Get current intelligence configuration for a tenant"""
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
    
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant["name"],
        "intelligence_config": tenant.get("intelligence_config", {})
    }
