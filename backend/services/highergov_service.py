import httpx
import logging
import os
from datetime import datetime, timezone
import uuid
import time
from typing import Dict, Any

from backend.utils.scoring import calculate_opportunity_score
from backend.services.mistral_service import score_opportunity_with_ai
from backend.utils.resilience import (
    RetryableClient,
    circuit_protected,
    highergov_circuit,
    CircuitOpenError
)
from backend.utils.usage import record_external_usage
from backend.utils.secrets import get_secret

logger = logging.getLogger(__name__)

# Retry-enabled HTTP client for HigherGov
_http_client = RetryableClient(timeout=30.0, max_retries=3)

HIGHERGOV_BASE_URL = "https://www.highergov.com/api-external"
DEFAULT_HIGHERGOV_KEY = get_secret("HIGHERGOV_API_KEY")  # Default/fallback key

@circuit_protected(highergov_circuit)
async def sync_highergov_opportunities(db, tenant: dict) -> int:
    """
    Fetch opportunities from HigherGov API for a tenant using Search ID.
    Uses saved search from HigherGov platform (not keywords - too many results).
    Runs AI scoring BEFORE displaying opportunities.
    Returns number of new opportunities added.

    Protected by circuit breaker - fails fast if HigherGov is down.
    """
    tenant_id = tenant["id"]
    tenant_name = tenant["name"]
    search_profile = tenant.get("search_profile", {})
    
    # Get API key (tenant-specific or default)
    highergov_api_key = search_profile.get("highergov_api_key") or DEFAULT_HIGHERGOV_KEY
    
    if not highergov_api_key or "placeholder" in highergov_api_key.lower():
        logger.warning(f"HigherGov API key not configured for tenant {tenant_id}, skipping sync")
        return 0
    
    # Get search ID (required)
    search_id = search_profile.get("highergov_search_id")
    if not search_id:
        logger.warning(f"HigherGov search_id not configured for tenant {tenant_id}. Create a saved search in HigherGov platform first.")
        return 0
    
    logger.info(f"Polling HigherGov search_id: {search_id} for {tenant_name}")
    
    fetch_full_docs = search_profile.get("fetch_full_documents", False)
    fetch_nsn = search_profile.get("fetch_nsn", False)
    
    new_count = 0
    
    try:
        # Poll saved search endpoint with retry logic
        # HigherGov search endpoints can vary - try multiple formats
        params = {
            "api_key": highergov_api_key,
            "searchID": search_id,  # Note: capital ID
            "page_size": 100,
            "page": 1
        }

        if fetch_full_docs:
            params["include_documents"] = "true"
        if fetch_nsn:
            params["include_nsn"] = "true"

        # Try the contract-opportunity endpoint with searchID parameter
        # _http_client has built-in retry with exponential backoff
        try:
            start_time = time.monotonic()
            response = await _http_client.get(
                f"{HIGHERGOV_BASE_URL}/contract-opportunity/",
                params=params
            )
            response.raise_for_status()
            duration_ms = (time.monotonic() - start_time) * 1000
            await record_external_usage(
                db,
                tenant_id,
                "highergov",
                "search_contract_opportunity",
                "success",
                duration_ms=duration_ms,
                metadata={"status_code": response.status_code, "search_id": search_id}
            )
        except httpx.HTTPStatusError as e:
            # Log error and try alternate endpoint
            duration_ms = (time.monotonic() - start_time) * 1000 if "start_time" in locals() else None
            status_code = e.response.status_code if e.response else None
            await record_external_usage(
                db,
                tenant_id,
                "highergov",
                "search_contract_opportunity",
                "error",
                duration_ms=duration_ms,
                metadata={"status_code": status_code, "search_id": search_id}
            )
            # If that fails, try without the search endpoint
            logger.warning(f"Primary endpoint failed ({status_code}), trying alternative: {e}")
            params_alt = {
                "api_key": highergov_api_key,
                "search_id": search_id,
                "limit": 100
            }
            start_time = time.monotonic()
            response = await _http_client.get(
                f"{HIGHERGOV_BASE_URL}/opportunity/",
                params=params_alt
            )
            response.raise_for_status()
            duration_ms = (time.monotonic() - start_time) * 1000
            await record_external_usage(
                db,
                tenant_id,
                "highergov",
                "search_opportunity",
                "success",
                duration_ms=duration_ms,
                metadata={"status_code": response.status_code, "search_id": search_id}
            )
        
        # Process the response data (moved OUTSIDE the except block)
        data = response.json()
        
        opportunities_list = data.get("results", []) or data.get("data", [])
        logger.info(f"Fetched {len(opportunities_list)} opportunities from search_id {search_id}")
        
        # Get scoring weights
        weights = tenant.get("scoring_weights", {})
        keywords = search_profile.get("keywords", [])
        
        # Process each opportunity with AI scoring BEFORE inserting
        for opp_data in opportunities_list:
            external_id = str(opp_data.get("id") or opp_data.get("opportunity_id") or uuid.uuid4())
            
            # Check if already exists
            existing = await db.opportunities.find_one({
                "tenant_id": tenant_id,
                "external_id": external_id
            })
            
            if existing:
                continue
            
            # Parse and normalize data
            now = datetime.now(timezone.utc).isoformat()
            
            # Handle nested agency object
            agency_value = opp_data.get("agency")
            if isinstance(agency_value, dict):
                agency_str = agency_value.get("name") or agency_value.get("agency_name") or str(agency_value.get("agency_key", ""))
            else:
                agency_str = str(agency_value) if agency_value else ""
            
            # Handle nested naics_code object
            naics_value = opp_data.get("naics_code")
            if isinstance(naics_value, dict):
                naics_str = str(naics_value.get("naics_code", ""))
            else:
                naics_str = str(naics_value) if naics_value else None
            
            opportunity = {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "external_id": external_id,
                "title": opp_data.get("title", "Untitled"),
                "description": opp_data.get("description", ""),
                "agency": agency_str or opp_data.get("organization", ""),
                "due_date": opp_data.get("due_date") or opp_data.get("deadline"),
                "estimated_value": opp_data.get("estimated_value") or opp_data.get("amount"),
                "naics_code": naics_str,
                "keywords": keywords,
                "source_type": "highergov",
                "source_url": opp_data.get("url", "") or opp_data.get("link", "") or (f"https://www.highergov.com/contract-opportunity/{opp_data.get('source_id', '')}/" if opp_data.get('source_id') else ""),
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
                ai_result = await score_opportunity_with_ai(opportunity, tenant, db=db)
                opportunity["ai_relevance_summary"] = ai_result.get("relevance_summary")
                
                # Apply AI score adjustment
                adjustment = ai_result.get("suggested_score_adjustment", 0)
                opportunity["score"] = max(0, min(100, opportunity["score"] + adjustment))
                
                # Store full AI analysis if schema provided
                if "key_highlights" in ai_result:
                    opportunity["ai_analysis"] = ai_result
                
                logger.info(f"AI scored: {opportunity['title'][:40]} - Score: {opportunity['score']}")
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

async def fetch_single_opportunity(db, tenant: dict, opportunity_id: str) -> Dict[str, Any]:
    """
    Fetch a single opportunity by ID from HigherGov.
    For manual entry of specific opportunity numbers.
    """
    search_profile = tenant.get("search_profile", {})
    
    highergov_api_key = search_profile.get("highergov_api_key") or DEFAULT_HIGHERGOV_KEY
    
    if not highergov_api_key:
        raise Exception("HigherGov API key not configured")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{HIGHERGOV_BASE_URL}/opportunity/{opportunity_id}/",
                params={"api_key": highergov_api_key}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch opportunity {opportunity_id}: {e}")
        raise