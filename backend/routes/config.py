from fastapi import APIRouter, HTTPException, status, Depends, Body, Request
from typing import Dict, Any, Set
import logging
from datetime import datetime, timezone

from backend.utils.auth import get_current_super_admin, get_current_tenant_admin, TokenData
from backend.database import get_database

router = APIRouter()
logger = logging.getLogger(__name__)

def get_db():
    return get_database()


# ALLOWED fields for intelligence_config - SINGLE SOURCE OF TRUTH
ALLOWED_INTELLIGENCE_CONFIG_FIELDS: Set[str] = {
    "enabled",
    "perplexity_prompt_template",
    "schedule_cron",
    "lookback_days",
    "deadline_window_days",
    "target_sources",
    "report_sections",
    "scoring_weights",
}

ALLOWED_INTELLIGENCE_SCORING_WEIGHTS: Set[str] = {
    "relevance", "amount", "timeline", "win_probability", "strategic_fit", "partner_potential"
}


@router.put("/tenants/{tenant_id}/intelligence-config")
async def update_intelligence_config(
    tenant_id: str,
    request: Request,
    current_user: TokenData = Depends(get_current_tenant_admin)
):
    """
    Update intelligence configuration for a tenant.
    
    CRITICAL: Unknown fields are REJECTED with HTTP 400.
    The system will NEVER return success while dropping data.
    """
    db = get_db()
    
    # STEP 1: Get raw request body
    try:
        config_data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body"
        )
    
    if not config_data or not isinstance(config_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body must be a non-empty JSON object"
        )
    
    # STEP 2: REJECT unknown fields BEFORE any processing
    unknown_fields = []
    for key in config_data.keys():
        if key not in ALLOWED_INTELLIGENCE_CONFIG_FIELDS:
            unknown_fields.append(key)
        elif key == "scoring_weights" and isinstance(config_data[key], dict):
            for subkey in config_data[key].keys():
                if subkey not in ALLOWED_INTELLIGENCE_SCORING_WEIGHTS:
                    unknown_fields.append(f"scoring_weights.{subkey}")
    
    if unknown_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown fields rejected: {', '.join(unknown_fields)}"
        )
    
    # STEP 3: Access control
    if current_user.role != "super_admin" and current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # STEP 4: Validate tenant exists
    tenant = await db.tenants.find_one({"id": tenant_id})
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # STEP 5: Validate cron expression if provided
    if "schedule_cron" in config_data:
        cron = config_data["schedule_cron"]
        if cron and len(cron.split()) != 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cron expression. Must be in format: 'minute hour day month day_of_week'"
            )
    
    # STEP 6: Update intelligence_config (merge, don't overwrite)
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
