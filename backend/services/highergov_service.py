import httpx
import logging
import os
from datetime import datetime, timezone
import uuid
from typing import Dict, Any

from utils.scoring import calculate_opportunity_score
from services.mistral_service import score_opportunity_with_ai

logger = logging.getLogger(__name__)

HIGHERGOV_BASE_URL = "https://www.highergov.com/api-external"
DEFAULT_HIGHERGOV_KEY = os.getenv("HIGHERGOV_API_KEY")  # Default/fallback key

async def sync_highergov_opportunities(db, tenant: dict) -> int:
    """
    Fetch opportunities from HigherGov API for a tenant.
    Uses tenant-specific API key or falls back to default.
    Runs AI scoring BEFORE displaying opportunities.
    Returns number of new opportunities added.
    """
    tenant_id = tenant["id"]
    tenant_name = tenant["name"]
    search_profile = tenant.get("search_profile", {})
    
    # Get API key (tenant-specific or default)
    highergov_api_key = search_profile.get("highergov_api_key") or DEFAULT_HIGHERGOV_KEY
    
    if not highergov_api_key or "placeholder" in highergov_api_key.lower():
        logger.warning(f"HigherGov API key not configured for tenant {tenant_id}, skipping sync")
        return 0
    
    logger.info(f"Using {'tenant-specific' if search_profile.get('highergov_api_key') else 'default'} HigherGov key for {tenant_name}")
    
    naics_codes = search_profile.get("naics_codes", [])
    keywords = search_profile.get("keywords", [])
    fetch_full_docs = search_profile.get("fetch_full_documents", False)
    fetch_nsn = search_profile.get("fetch_nsn", False)
    fetch_grants = search_profile.get("fetch_grants", True)
    fetch_contracts = search_profile.get("fetch_contracts", True)
    
    if not naics_codes and not keywords:
        logger.warning(f"No search criteria for tenant {tenant_id}")
        return 0
    
    new_count = 0
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Build query parameters
            params = {
                "api_key": highergov_api_key,
                "page_size": 50,
                "page_number": 1
            }
            
            if naics_codes:
                params["naics_codes"] = ",".join(naics_codes)
            if keywords:
                params["keywords"] = " ".join(keywords)
            if fetch_full_docs:
                params["include_documents"] = "true"
            if fetch_nsn:
                params["include_nsn"] = "true"
            
            # Fetch contracts if enabled
            opportunities_list = []
            if fetch_contracts:
                try:
                    response = await client.get(
                        f"{HIGHERGOV_BASE_URL}/opportunity/",
                        params=params
                    )
                    response.raise_for_status()
                    data = response.json()
                    opportunities_list.extend(data.get("results", []))
                    logger.info(f"Fetched {len(data.get('results', []))} contracts for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"Failed to fetch contracts: {e}")
            
            # Fetch grants if enabled
            if fetch_grants:
                try:
                    grants_params = params.copy()
                    grants_params["source_type"] = "grants"
                    response = await client.get(
                        f"{HIGHERGOV_BASE_URL}/opportunity/",
                        params=grants_params
                    )
                    response.raise_for_status()
                    data = response.json()
                    opportunities_list.extend(data.get("results", []))
                    logger.info(f"Fetched {len(data.get('results', []))} grants for tenant {tenant_id}")
                except Exception as e:
                    logger.error(f"Failed to fetch grants: {e}")
            
            # Get scoring weights
            weights = tenant.get("scoring_weights", {})
            
            # Process each opportunity with AI scoring BEFORE inserting
            for opp_data in opportunities_list:
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
                
                # Calculate base score
                opportunity["score"] = calculate_opportunity_score(opportunity, weights)
                
                # AI SCORING BEFORE DISPLAY
                try:
                    ai_result = await score_opportunity_with_ai(opportunity, tenant)
                    opportunity["ai_relevance_summary"] = ai_result.get("relevance_summary")
                    
                    # Apply AI score adjustment
                    adjustment = ai_result.get("suggested_score_adjustment", 0)
                    opportunity["score"] = max(0, min(100, opportunity["score"] + adjustment))
                    
                    # Store full AI analysis if schema provided
                    if "key_highlights" in ai_result:
                        opportunity["ai_analysis"] = ai_result
                    
                    logger.info(f"AI scored opportunity: {opportunity['title'][:50]} - Score: {opportunity['score']}")
                except Exception as e:
                    logger.error(f"AI scoring failed: {e}")
                
                # Insert into database
                await db.opportunities.insert_one(opportunity)
                new_count += 1
            
            # Update tenant rate limit
            await db.tenants.update_one(
                {"id": tenant_id},
                {"$inc": {"rate_limit_used": len(opportunities_list)}}
            )
            
    except Exception as e:
        logger.error(f"HigherGov API error for tenant {tenant_id}: {e}")
        raise
    
    return new_count