import httpx
import logging
import os
from datetime import datetime, timezone
import uuid
from typing import Dict, Any

from utils.scoring import calculate_opportunity_score

logger = logging.getLogger(__name__)

HIGHERGOV_API_KEY = os.getenv("HIGHERGOV_API_KEY")
HIGHERGOV_BASE_URL = "https://www.highergov.com/api-external"

async def sync_highergov_opportunities(db, tenant: dict) -> int:
    """
    Fetch opportunities from HigherGov API for a tenant.
    Returns number of new opportunities added.
    """
    tenant_id = tenant["id"]
    search_profile = tenant.get("search_profile", {})
    naics_codes = search_profile.get("naics_codes", [])
    keywords = search_profile.get("keywords", [])
    
    if not naics_codes and not keywords:
        logger.warning(f"No search criteria for tenant {tenant_id}")
        return 0
    
    # Check if placeholder key
    if not HIGHERGOV_API_KEY or "placeholder" in HIGHERGOV_API_KEY.lower():
        logger.warning("HigherGov API key not configured, skipping sync")
        return 0
    
    new_count = 0
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Build query parameters
            params = {
                "api_key": HIGHERGOV_API_KEY,
                "page_size": 50,
                "page_number": 1
            }
            
            if naics_codes:
                params["naics_codes"] = ",".join(naics_codes)
            if keywords:
                params["keywords"] = " ".join(keywords)
            
            response = await client.get(
                f"{HIGHERGOV_BASE_URL}/opportunity/",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            opportunities = data.get("results", [])
            
            # Get scoring weights
            weights = tenant.get("scoring_weights", {})
            
            # Process each opportunity
            for opp_data in opportunities:
                external_id = opp_data.get("id") or str(uuid.uuid4())
                
                # Check if already exists
                existing = await db.opportunities.find_one({
                    "tenant_id": tenant_id,
                    "external_id": external_id
                })
                
                if existing:
                    continue
                
                # Parse and normalize data
                now = datetime.now(timezone.utc).isoformat()
                opportunity = {
                    "id": str(uuid.uuid4()),
                    "tenant_id": tenant_id,
                    "external_id": external_id,
                    "title": opp_data.get("title", "Untitled"),
                    "description": opp_data.get("description", ""),
                    "agency": opp_data.get("agency", ""),
                    "due_date": opp_data.get("due_date"),
                    "estimated_value": opp_data.get("estimated_value"),
                    "naics_code": opp_data.get("naics_code"),
                    "keywords": keywords,
                    "source_type": "highergov",
                    "source_url": opp_data.get("url", ""),
                    "raw_data": opp_data,
                    "score": 0,
                    "ai_relevance_summary": None,
                    "captured_date": now,
                    "created_at": now,
                    "updated_at": now
                }
                
                # Calculate score
                opportunity["score"] = calculate_opportunity_score(opportunity, weights)
                
                # Insert into database
                await db.opportunities.insert_one(opportunity)
                new_count += 1
            
            # Update tenant rate limit
            await db.tenants.update_one(
                {"id": tenant_id},
                {"$inc": {"rate_limit_used": len(opportunities)}}
            )
            
    except Exception as e:
        logger.error(f"HigherGov API error for tenant {tenant_id}: {e}")
        raise
    
    return new_count